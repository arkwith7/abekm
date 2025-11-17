"""
프로바이더별 문서 필터링 유틸리티

.env 설정(DEFAULT_EMBEDDING_PROVIDER)에 따라 동적으로 필터링 조건을 생성하여
Azure와 Bedrock 환경 간 전환 시 코드 수정 없이 올바른 문서만 조회/검색하도록 지원합니다.

매핑 규칙:
- bedrock → pipeline_type: 'bedrock', 'upstage' (Upstage → Bedrock 임베딩 파이프라인)
- azure_openai → pipeline_type: 'azure_di', 'azure_openai' (Azure DI → Azure OpenAI 임베딩 파이프라인)
- openai → pipeline_type: 'openai' (OpenAI 직접 임베딩)

Storage 검증:
- bedrock → S3 경로 (aws_s3_bucket)
- azure_openai → Azure Blob 경로 (blob.core.windows.net)
"""

from typing import List, Optional
from sqlalchemy import and_, or_
from app.core.config import settings


def get_pipeline_types_for_provider(provider: str) -> List[str]:
    """
    임베딩 프로바이더에 따른 허용 pipeline_type 목록 반환
    
    Args:
        provider: 임베딩 프로바이더 (bedrock | azure_openai | openai)
    
    Returns:
        허용되는 pipeline_type 문자열 리스트
    
    Examples:
        >>> get_pipeline_types_for_provider("bedrock")
        ['bedrock', 'upstage']
        >>> get_pipeline_types_for_provider("azure_openai")
        ['azure_di', 'azure_openai']
    """
    mapping = {
        "bedrock": ["bedrock", "upstage"],  # Upstage는 Bedrock 임베딩 사용
        "azure_openai": ["azure_di", "azure_openai"],  # Azure DI는 Azure OpenAI 임베딩 사용
        "openai": ["openai"],
    }
    return mapping.get(provider, [])


def get_current_provider_pipeline_types() -> List[str]:
    """
    현재 설정된 임베딩 프로바이더의 pipeline_type 목록 반환
    
    Returns:
        현재 활성화된 프로바이더의 pipeline_type 리스트
    
    Examples:
        # .env: DEFAULT_EMBEDDING_PROVIDER=bedrock
        >>> get_current_provider_pipeline_types()
        ['bedrock', 'upstage']
    """
    current_provider = settings.get_current_embedding_provider()
    return get_pipeline_types_for_provider(current_provider)


def get_storage_path_pattern(provider: str) -> Optional[str]:
    """
    프로바이더별 저장소 경로 패턴 반환 (LIKE 연산용)
    
    Args:
        provider: 임베딩 프로바이더
    
    Returns:
        저장소 경로 패턴 문자열 또는 None
    
    Examples:
        >>> get_storage_path_pattern("bedrock")
        'raw/%'  # S3 표준 경로
        >>> get_storage_path_pattern("azure_openai")
        '%blob.core.windows.net%'
    """
    if provider == "bedrock":
        # S3 경로: raw/로 시작
        return "raw/%"
    elif provider == "azure_openai":
        # Azure Blob URL 패턴
        return "%blob.core.windows.net%"
    else:
        return None


def is_valid_storage_for_provider(storage_path: str, provider: Optional[str] = None) -> bool:
    """
    파일 경로가 프로바이더의 저장소 규칙에 부합하는지 검증
    
    Args:
        storage_path: 파일 경로 또는 URL
        provider: 검증할 프로바이더 (None이면 현재 설정 기준)
    
    Returns:
        유효하면 True, 아니면 False
    
    Examples:
        >>> is_valid_storage_for_provider("raw/USER_123/file.pdf", "bedrock")
        True
        >>> is_valid_storage_for_provider("https://account.blob.core.windows.net/...", "bedrock")
        False
    """
    if provider is None:
        provider = settings.get_current_embedding_provider()
    
    if provider == "bedrock":
        # S3: raw/로 시작하거나 HTTP(S) 미포함
        return storage_path.startswith("raw/") or not storage_path.startswith("http")
    elif provider == "azure_openai":
        # Azure Blob: blob.core.windows.net 포함
        return "blob.core.windows.net" in storage_path
    else:
        return True  # 기타 프로바이더는 제한 없음


def get_provider_filter_condition(table_alias=None):
    """
    현재 프로바이더에 맞는 SQLAlchemy 필터 조건 반환
    
    Args:
        table_alias: DocExtractionSession 테이블 alias (join 사용 시)
    
    Returns:
        SQLAlchemy filter condition (pipeline_type IN (...))
    
    Usage:
        from app.models.document.multimodal_models import DocExtractionSession
        
        # 단일 테이블 쿼리
        query = select(DocExtractionSession).where(
            get_provider_filter_condition()
        )
        
        # Join 쿼리
        query = select(TbFileBssInfo).join(DocExtractionSession).where(
            get_provider_filter_condition(DocExtractionSession)
        )
    """
    from app.models.document.multimodal_models import DocExtractionSession
    
    table = table_alias if table_alias is not None else DocExtractionSession
    allowed_pipelines = get_current_provider_pipeline_types()
    
    return table.pipeline_type.in_(allowed_pipelines)


def get_provider_filter_with_status(table_alias=None, include_pending: bool = True):
    """
    프로바이더 필터 + 상태 조건을 결합한 SQLAlchemy 필터 반환
    
    Args:
        table_alias: DocExtractionSession 테이블 alias
        include_pending: pending/processing 상태 문서 포함 여부
    
    Returns:
        SQLAlchemy filter condition
    
    Usage:
        # 성공한 Bedrock 문서 + 아직 처리 안 된 문서 표시
        query = select(TbFileBssInfo).join(DocExtractionSession).where(
            get_provider_filter_with_status(DocExtractionSession, include_pending=True)
        )
    """
    from app.models.document.multimodal_models import DocExtractionSession
    from app.models.document.file_models import TbFileBssInfo
    
    table = table_alias if table_alias is not None else DocExtractionSession
    allowed_pipelines = get_current_provider_pipeline_types()
    
    # 성공적으로 처리된 문서 (현재 프로바이더)
    success_condition = and_(
        table.pipeline_type.in_(allowed_pipelines),
        table.status == 'success'
    )
    
    if include_pending:
        # pending/processing 상태 문서도 포함 (아직 처리 전)
        # 이 경우 TbFileBssInfo의 processing_status를 확인해야 함
        pending_condition = TbFileBssInfo.processing_status.in_(['pending', 'processing'])
        return or_(success_condition, pending_condition)
    else:
        return success_condition


def validate_embedding_dimension(requested_dim: int, provider: Optional[str] = None) -> tuple[bool, str]:
    """
    요청된 임베딩 차원이 현재 프로바이더 설정과 일치하는지 검증
    
    Args:
        requested_dim: 검색 요청된 벡터 차원
        provider: 검증할 프로바이더 (None이면 현재 설정)
    
    Returns:
        (유효 여부, 에러 메시지)
    
    Examples:
        >>> validate_embedding_dimension(1024, "bedrock")
        (True, "")
        >>> validate_embedding_dimension(1536, "bedrock")
        (False, "현재 Bedrock 환경은 1024차원 임베딩을 사용합니다...")
    """
    if provider is None:
        provider = settings.get_current_embedding_provider()
    
    expected_dim = settings.get_current_embedding_dimension()
    
    if requested_dim == expected_dim:
        return True, ""
    
    error_msg = (
        f"임베딩 차원 불일치: 요청={requested_dim}차원, "
        f"현재 {provider} 환경={expected_dim}차원. "
        f"현재 환경에서는 {settings.get_current_embedding_model()} 모델({expected_dim}d)을 사용 중입니다. "
        f"검색하려는 문서가 다른 프로바이더로 처리되었다면 재처리가 필요합니다."
    )
    
    return False, error_msg


def get_provider_summary() -> dict:
    """
    현재 프로바이더 설정 요약 정보 반환 (디버깅/로깅용)
    
    Returns:
        설정 정보 dict
    
    Examples:
        >>> get_provider_summary()
        {
            'embedding_provider': 'bedrock',
            'allowed_pipelines': ['bedrock', 'upstage'],
            'embedding_model': 'amazon.titan-embed-text-v2:0',
            'embedding_dimension': 1024,
            'storage_backend': 's3',
            'multimodal_enabled': True,
            'multimodal_model': 'twelvelabs.marengo-embed-3-0-v1:0',
            'multimodal_dimension': 512
        }
    """
    provider = settings.get_current_embedding_provider()
    
    return {
        "embedding_provider": provider,
        "allowed_pipelines": get_current_provider_pipeline_types(),
        "embedding_model": settings.get_current_embedding_model(),
        "embedding_dimension": settings.get_current_embedding_dimension(),
        "storage_backend": settings.storage_backend,
        "storage_bucket": getattr(settings, "aws_s3_bucket", None) or getattr(settings, "azure_blob_account_name", None),
        "multimodal_enabled": settings.is_multimodal_enabled(),
        "multimodal_model": settings.get_current_multimodal_embedding_model() if settings.is_multimodal_enabled() else None,
        "multimodal_dimension": settings.get_current_multimodal_embedding_dimension() if settings.is_multimodal_enabled() else None,
    }
