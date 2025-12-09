from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    # Pydantic v2 / pydantic-settings v2 configuration
    # NOTE: v1 style Field(..., env="VAR") is deprecated; we rely on case-insensitive
    # matching so ENV_VAR and env_var both map to the field name.
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )
    
    # 데이터베이스 설정 - 환경변수에서 동적 구성
    database_url: str = Field(
        default_factory=lambda: (
            f"postgresql+asyncpg://"
            f"{os.getenv('DB_USER', 'wkms')}:"
            f"{os.getenv('DB_PASSWORD', 'wkms123')}@"
            f"{os.getenv('DB_HOST', 'localhost')}:"
            f"{os.getenv('DB_PORT', '5432')}/"
            f"{os.getenv('DB_NAME', 'wkms')}"
            if not os.getenv('DATABASE_URL') else os.getenv('DATABASE_URL')
        )
    )
    
    # 데이터베이스 성능 설정
    db_pool_size: int = 40  # 20 → 40 (Connection pool 증가)
    db_max_overflow: int = 60  # 30 → 60
    db_pool_timeout: int = 60  # 30 → 60 (대기 시간 증가)
    db_pool_recycle: int = 300
    db_pool_pre_ping: bool = True
    
    # 디버그 모드 (전역)
    debug: bool = False
    
    # Redis 설정
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str = Field(
        default_factory=lambda: (
            f"redis://{os.getenv('REDIS_HOST', 'localhost')}:"
            f"{os.getenv('REDIS_PORT', '6379')}/"
            f"{os.getenv('REDIS_DB', '0')}"
            if not os.getenv('REDIS_URL') else os.getenv('REDIS_URL')
        )
    )
    
    # JWT 토큰 설정
    secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    algorithm: str = "HS256"
    # Access 토큰 만료 시간 (분) - .env에서 ACCESS_TOKEN_EXPIRE_MINUTES로 설정 가능
    access_token_expire_minutes: int = 480  # 개발: 8시간, 운영: 30분 권장
    # Refresh 토큰 만료 시간 (분) - .env에서 REFRESH_TOKEN_EXPIRE_MINUTES로 설정 가능
    refresh_token_expire_minutes: int = 60 * 24 * 7  # 7일
    
    # CORS 설정 - 환경 변수에서 읽어옴
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001"
        ],
        env="CORS_ORIGINS",
        description="CORS allowed origins list"
    )
    
    # 파일 업로드 설정
    upload_dir: str = "uploads"
    file_upload_path: str = "uploads"
    max_file_size: int = 104857600  # 100MB (대용량 파일 지원)
    allowed_file_types: List[str] = [".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".hwp", ".doc", ".xls", ".ppt"]
    allowed_file_extensions: List[str] = [".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".hwp", ".doc", ".xls", ".ppt"]
    chat_attachment_dir: str = "uploads/chat_attachments"
    
    # 한국어 처리 설정 (Simplified - 2025-10-16)
    # ❌ 제거됨: kiwipiepy 관련 설정
    # korean_nlp_provider: str = "hybrid"
    # kiwi_model_type: str = "sbg"
    # kiwi_typos_correction: str = "basic_with_continual_and_lengthening"
    # user_dictionary_path: str = "dictionaries/company_dict.txt"
    # korean_stopwords_path: str = "dictionaries/korean_stopwords.txt"
    
    # ✅ 유지: 임베딩 및 토크나이저 설정
    korean_tokenizer_model: str = "cl100k_base"  # tiktoken 모델
    
    # 문서 처리 설정
    supported_document_formats: List[str] = [
        "pdf", "docx", "pptx", "xlsx", "txt", "md", "hwp", "doc", "xls", "ppt"
    ]
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # 하이브리드 검색 설정
    hybrid_search_weights: dict = {
        "semantic": 0.7,  # 의미 검색 가중치
        "keyword": 0.3    # 키워드 검색 가중치
    }
    korean_embedding_model: str = "jhgan/ko-sroberta-multitask"
    
    # AWS 설정
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    
    # 파일 저장소 선택 (local | s3 | azure_blob)
    storage_backend: str = "local"
    # 표준 raw/ 프리픽스 사용 여부 (S3 업로드 시 경로 스킴 전환용 Feature Flag)
    use_standard_raw_prefix: bool = False
    
    # S3 설정 (storage_backend == 's3' 일 때 필수)
    aws_s3_bucket: Optional[str] = None
    s3_presign_expiry_seconds: int = 3600

    # Azure Blob Storage 설정 (storage_backend == 'azure_blob' 일 때 사용)
    azure_blob_account_name: Optional[str] = None
    azure_blob_account_key: Optional[str] = None
    azure_blob_connection_string: Optional[str] = None  # 선택: 연결 문자열 우선
    azure_blob_container_raw: str = "wkms-raw"  # 원본 업로드
    azure_blob_container_intermediate: str = "wkms-intermediate"  # 추출/페이지/임시 산출물
    azure_blob_container_derived: str = "wkms-derived"  # 청크/임베딩/요약 산출물
    azure_blob_sas_expiry_seconds: int = 3600
    azure_blob_enable_auto_container: bool = True  # 존재하지 않을 경우 자동 생성
    azure_blob_path_style: bool = False  # 사설 에뮬레이터(Azurite) 사용 시 True
    azure_blob_download_mode: str = "proxy"  # redirect: 302 리다이렉트 (CORS 필요), proxy: 서버 프록시 (CORS 불필요)
    
    # Azure OpenAI 설정
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_api_version: str = "2024-02-15-preview"
    
    # 문서 처리 제공자 선택 (azure_di | upstage | aws_textract | etc_other)
    # - azure_di: Azure Document Intelligence (한국어 완벽 지원)
    # - upstage: Upstage Document Parse (한국어 우수, Azure DI 대안)
    # - aws_textract: AWS Textract (영문 중심, 한국어 제한적)
    # - etc_other: pdfplumber 등 기타 오픈소스 라이브러리
    document_processing_provider: str = Field(
        default="azure_di",
        description="Primary document processing provider"
    )
    document_processing_fallback: Optional[str] = Field(
        default=None,
        description="Fallback document processing provider"
    )
    
    # 하위 호환성을 위한 기존 설정 유지 (Deprecated - document_processing_provider 사용 권장)
    use_azure_document_intelligence_pdf: bool = Field(
        default_factory=lambda: os.getenv("DOCUMENT_PROCESSING_PROVIDER", "azure_di").lower() == "azure_di"
    )
    
    # Azure Document Intelligence 설정
    azure_document_intelligence_endpoint: Optional[str] = None
    azure_document_intelligence_api_key: Optional[str] = None
    azure_document_intelligence_api_version: str = "2024-11-30"  # 최신 API 버전으로 업데이트 (FIGURES feature 지원)
    azure_document_intelligence_default_model: str = "prebuilt-read"

    @property
    def resolved_upload_dir(self) -> Path:
        """Ensure upload directory is always an absolute path."""
        base = Path(self.file_upload_path or self.upload_dir)
        if not base.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            base = (project_root / base).resolve()
        return base
    azure_document_intelligence_layout_model: str = "prebuilt-layout"
    azure_document_intelligence_document_model: str = "prebuilt-document"
    azure_document_intelligence_max_pages: int = 150
    azure_document_intelligence_timeout_seconds: int = 300
    azure_document_intelligence_retry_max_attempts: int = 3
    azure_document_intelligence_confidence_threshold: float = 0.8
    azure_document_intelligence_use_korean_optimization: bool = True

    # DI 성능/품질 개선 플래그 (Sprint 1)
    # 페이지 그룹 병렬 처리 활성화 여부
    di_parallel_enabled: bool = False
    # 페이지 그룹 크기 (예: 3이면 1-3, 4-6, ... 식으로 호출)
    di_page_group_size: int = 3
    # 동시 실행 그룹 수 제한 (429 대비)
    di_max_concurrency: int = 3
    # 동일 파일 해시 기반 임시 캐시 사용 여부 (/tmp/di_cache)
    di_cache_enabled: bool = False
    # 2열 레이아웃 재구성 활성화 여부 (pdfplumber 필요, 없으면 자동 생략)
    di_two_column_reorder_enabled: bool = True
    
    # Upstage Document Parse 설정
    upstage_api_key: Optional[str] = None
    upstage_api_endpoint: str = "https://api.upstage.ai/v1/document-digitization"
    upstage_max_pages: int = 150
    upstage_timeout_seconds: int = 300
    upstage_retry_max_attempts: int = 3
    upstage_model: str = "document-parse"
    upstage_ocr_mode: Optional[str] = None
    upstage_base64_categories: Optional[List[str]] = None
    upstage_merge_multipage_tables: bool = True
    upstage_use_async_api: bool = False
    upstage_async_poll_interval_seconds: int = 5
    upstage_async_timeout_seconds: int = 900
    upstage_async_api_endpoint: Optional[str] = None
    upstage_async_status_endpoint: Optional[str] = None
    
    # OpenAI 설정
    openai_api_key: Optional[str] = None
    
    # LLM 제공자 설정
    llm_providers: List[str] = Field(default_factory=lambda: ["bedrock", "azure_openai", "openai"])
    default_llm_provider: str = "bedrock"
    default_embedding_provider: Optional[str] = None  # None이면 default_llm_provider와 동일
    
    # Azure OpenAI 모델 (.env에서 설정 필수)
    azure_openai_llm_deployment: str = Field(default="")
    azure_openai_embedding_deployment: str = Field(default="text-embedding-ada-002")
    # 멀티모달(Vision) 전용 배포 (gpt-4o, gpt-4o-mini, gpt-4o-vision 등) - 선택
    azure_openai_multimodal_deployment: str = Field(default="")
    azure_openai_enable_vision_captioning: bool = True  # Vision 캡셔닝 활성화 플래그
    
    # AWS Transcribe 음성 변환 설정
    enable_audio_transcription: bool = False  # 오디오 → 텍스트 변환 플래그
    aws_transcribe_language_code: str = "ko-KR"  # 기본 언어 (ko-KR, en-US, ja-JP, zh-CN 등)
    
    # Azure CLIP 멀티모달 임베딩 모델
    azure_openai_multimodal_embedding_endpoint: Optional[str] = None
    azure_openai_multimodal_embedding_api_key: Optional[str] = None
    azure_openai_multimodal_embedding_deployment: str = "openai-clip-image-text-embed-11"
    clip_embedding_dimension: int = 512  # CLIP 임베딩 차원
    
    # AWS Bedrock 모델
    bedrock_llm_model_id: str = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_text_model_id: str = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"  # bedrock_service.py에서 사용
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_alt_embedding_model_id: str = "amazon.titan-embed-text-v1:0"  # 대체 임베딩 모델
    bedrock_embedding_dimension: int = 1024  # Titan V2 기본 차원 (1024, 512, 256 지원)
    
    # AWS Bedrock 멀티모달 모델 (Cohere Embed v4)
    bedrock_multimodal_embedding_model_id: str = "twelvelabs.marengo-embed-3-0-v1:0"
    bedrock_multimodal_embedding_dimension: int = 512
    bedrock_multimodal_llm_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # OpenAI 모델 (.env에서 설정 필수)
    openai_llm_model: str = Field(default="")
    openai_embedding_model: str = Field(default="text-embedding-ada-002")
    
    # 모델 파라미터
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    
    # 벡터 검색 설정 (멀티 벤더 지원)
    vector_dimension: int = 1536  # 기본값: Azure text-embedding-3-small (.env에서 오버라이드)
    
    # 벤더별 벡터 차원 (고정값)
    azure_vector_dimension_small: int = 1536   # Azure text-embedding-3-small
    azure_vector_dimension_large: int = 3072   # Azure text-embedding-3-large
    azure_clip_dimension: int = 512            # Azure CLIP multimodal
    aws_vector_dimension: int = 1024           # AWS Titan v2 / Cohere v4
    aws_vector_dimension_small: int = 256      # AWS Titan v2 small
    
    similarity_threshold: float = 0.7
    
    # RAG 검색 설정
    rag_similarity_threshold: float = 0.3
    rag_max_chunks: int = 30
    rag_use_reranking: bool = True
    
    # 리랭킹 제공자 설정
    rag_reranking_provider: str = Field(default="azure_openai")  # azure_openai | bedrock
    
    # 리랭킹 전용 Azure OpenAI 설정
    rag_reranking_endpoint: Optional[str] = None
    rag_reranking_api_key: Optional[str] = None
    rag_reranking_deployment: str = Field(default="")
    rag_reranking_api_version: str = Field(default="")
    rag_reranking_max_completion_tokens: int = 500
    rag_reranking_reasoning_effort: Optional[str] = None
    rag_reranking_temperature: float = 0.3
    rag_reranking_max_tokens: int = 500
    
    # 리랭킹 전용 AWS Bedrock 설정
    rag_reranking_bedrock_model_id: str = Field(default="")
    rag_reranking_bedrock_region: str = Field(default="")
    
    # OpenSearch 설정
    opensearch_endpoint: Optional[str] = None
    opensearch_username: str = "admin"
    opensearch_password: Optional[str] = None
    opensearch_index: str = "wkms-documents"
    
    # Pinecone 설정
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None
    pinecone_index_name: str = "wkms-index"
    
    # 로깅 설정
    log_level: str = "INFO"
    log_format: str = "json"
    log_dir: str = "logs"
    log_file_name: str = "backend.log"
    log_max_bytes: int = 5 * 1024 * 1024  # 5MB
    log_backup_count: int = 5
    # 별도 SQL 로그 설정
    sql_query_log_enabled: bool = True
    sql_query_log_file_name: str = "sql.log"
    sql_query_log_level: str = "INFO"
    sql_query_log_format: str = "plain"  # plain | json
    sql_query_log_all: bool = False  # True면 SLOW/SAMPLE 뿐 아니라 모든 쿼리 기록

    # SQL 로깅 제어 (세밀도 조정)
    sqlalchemy_echo: bool = False  # 개별 SQL / 파라미터 출력 (기본 비활성화)
    sql_log_slow_threshold_ms: int = 300  # 느린 쿼리 (ms) 이상만 요약 로그, 0 또는 음수면 비활성화
    sql_log_sample_rate: float = 0.0  # 0~1 사이, 느린 쿼리 외 임의 샘플 로그 (부하 분석용)
    
    # 프레젠테이션 산출물 저장 경로
    presentation_output_dir: str = "data/presentations"
    
    # Office Generator Service 설정
    office_generator_url: str = Field(
        default_factory=lambda: os.getenv('OFFICE_GENERATOR_URL', 'http://localhost:3001')
    )
    office_generator_timeout: int = 60  # seconds

    # 실행 환경
    environment: str = "development"

    # -----------------------------
    # Web Search / External Augmentation 설정
    # -----------------------------
    web_search_enabled: bool = True  # 내부 RAG 저신뢰 시 외부 검색 사용 여부 (feature flag)
    web_search_provider: str = "mock"  # mock | serpapi | tavily | bing | brave (추가 가능)
    serpapi_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    bing_search_api_key: Optional[str] = None
    brave_search_api_key: Optional[str] = None
    web_search_max_results: int = 6
    web_search_timeout_seconds: int = 8
    web_search_cache_ttl_seconds: int = 60 * 60 * 6  # 6시간 캐시
    web_search_dual_language: bool = True  # ko/en 병렬 검색
    web_search_result_language: str = "ko"  # 결과 요약 언어
    web_search_log_queries: bool = False  # 개인정보 포함 질의 외부 전송 전에 마스킹 필요
    
    # -----------------------------
    # Patent Search 설정 (Enterprise Intelligence)
    # -----------------------------
    patent_search_enabled: bool = True  # 특허 검색 기능 활성화
    kipris_api_key: Optional[str] = None  # KIPRIS API 키 (한국 특허)
    kipris_api_endpoint: str = "http://plus.kipris.or.kr/openapi/rest"  # KIPRIS REST API 엔드포인트
    # SerpAPI Google Patents (글로벌 특허 검색)
    serpapi_google_patents_enabled: bool = True  # SerpAPI Google Patents 사용 여부
    # serpapi_api_key는 위 web_search에서 이미 정의됨 (공유 사용)
    uspto_api_endpoint: str = "https://api.patentsview.org/patents"  # USPTO PatentsView API (무료)
    patent_search_max_results: int = 20  # 최대 검색 결과 수
    patent_search_timeout_seconds: int = 30  # API 타임아웃
    patent_search_cache_ttl_seconds: int = 60 * 60 * 24  # 24시간 캐시 (특허 데이터는 변동이 적음)

    # Web page fetch (검색 결과 상세 페이지 추출) 설정
    web_fetch_enabled: bool = True
    web_fetch_timeout_seconds: int = 10
    web_fetch_max_concurrent: int = 4
    web_fetch_max_chars: int = 8000  # 페이지당 최대 추출 길이
    web_fetch_user_agent: str = "WKMSBot/0.1 (+https://example.invalid)"
    web_fetch_allow_domains: List[str] = Field(default_factory=list)  # 비어있으면 전체 허용(차단 목록 우선)
    web_fetch_block_domains: List[str] = Field(default_factory=lambda: ["facebook.com", "instagram.com"])
    
    def get_embedding_dimension(self, model_id: str) -> int:
        """임베딩 모델에 따른 실제 차원 수 반환 - 성능 최적화를 위해 원본 차원 사용"""
        dimension_map = {
            # AWS Bedrock Titan 모델들
            "amazon.titan-embed-text-v1:0": 1536,
            "amazon.titan-embed-text-v2:0": 1024,  # 기본값, 512, 256도 지원
            
            # Azure OpenAI 모델들 (원본 차원 그대로 사용)
            "text-embedding-ada-002": 1536,        # 원본 1536차원
            "text-embedding-3-small": 1536,        # 원본 1536차원
            "text-embedding-3-large": 3072,        # 원본 3072차원
            
            # OpenAI 모델들 (원본 차원 사용)
            "text-embedding-ada-002": 1536,
        }
        return dimension_map.get(model_id, self.vector_dimension)
    
    def apply_smart_dimension_reduction(self, embedding: list, target_dim: int = 1024) -> list:
        """스마트 차원 축소 - 성능 저하 최소화"""
        if not embedding or len(embedding) <= target_dim:
            return embedding
            
        if len(embedding) == 1536:  # OpenAI ada-002, 3-small
            # 1536 → 1024: 앞쪽 1024개 + 중요도 기반 선택
            return embedding[:target_dim]
        elif len(embedding) == 3072:  # OpenAI 3-large  
            # 3072 → 1024: 3등분해서 각 구간에서 선택
            step = len(embedding) // target_dim
            return [embedding[i * step] for i in range(target_dim)]
        else:
            return embedding[:target_dim]
    
    def get_current_embedding_dimension(self) -> int:
        """현재 사용 중인 임베딩 모델의 차원 수 반환"""
        if self.default_llm_provider == "bedrock":
            return self.get_embedding_dimension(self.bedrock_embedding_model_id)
        elif self.default_llm_provider == "azure_openai":
            return self.get_embedding_dimension(self.azure_openai_embedding_deployment)
        elif self.default_llm_provider == "openai":
            return self.get_embedding_dimension(self.openai_embedding_model)
        else:
            return self.vector_dimension
    
    def get_current_llm_model(self) -> str:
        """현재 설정된 LLM 모델 ID 반환"""
        provider = self.get_current_llm_provider()
        
        if provider == "bedrock":
            return self.bedrock_llm_model_id
        elif provider == "azure_openai":
            return self.azure_openai_llm_deployment
        elif provider == "openai":
            return self.openai_llm_model
        else:
            return self.bedrock_llm_model_id  # 기본값

    def get_current_multimodal_model(self) -> str:
        """멀티모달(비전)용 모델 반환 (LLM for vision)"""
        provider = self.get_current_llm_provider()
        
        if provider == "bedrock":
            return self.bedrock_multimodal_llm_model_id
        elif provider == "azure_openai":
            if self.azure_openai_multimodal_deployment:
                return self.azure_openai_multimodal_deployment
            return self.azure_openai_llm_deployment
        else:
            return self.bedrock_multimodal_llm_model_id
    
    def get_current_embedding_model(self) -> str:
        """현재 설정된 임베딩 모델 ID 반환"""
        provider = self.get_current_embedding_provider()
        
        if provider == "bedrock":
            return self.bedrock_embedding_model_id
        elif provider == "azure_openai":
            return self.azure_openai_embedding_deployment
        elif provider == "openai":
            return self.openai_embedding_model
        else:
            return self.bedrock_embedding_model_id  # 기본값
    
    def get_current_multimodal_embedding_model(self) -> str:
        """현재 설정된 멀티모달 임베딩 모델 반환 (이미지+텍스트)"""
        provider = self.get_current_embedding_provider()
        
        if provider == "bedrock":
            return self.bedrock_multimodal_embedding_model_id
        elif provider == "azure_openai":
            return self.azure_openai_multimodal_embedding_deployment
        else:
            return self.bedrock_multimodal_embedding_model_id
    
    def get_current_multimodal_embedding_dimension(self) -> int:
        """현재 설정된 멀티모달 임베딩 차원 반환"""
        provider = self.get_current_embedding_provider()
        
        if provider == "bedrock":
            return self.bedrock_multimodal_embedding_dimension
        elif provider == "azure_openai":
            return self.clip_embedding_dimension
        else:
            return self.bedrock_multimodal_embedding_dimension
    
    def get_current_multimodal_endpoint(self) -> Optional[str]:
        """현재 설정된 멀티모달 임베딩 엔드포인트 반환"""
        provider = self.get_current_embedding_provider()
        
        if provider == "azure_openai":
            return self.azure_openai_multimodal_embedding_endpoint
        elif provider == "bedrock":
            return f"AWS Bedrock - {self.aws_region}"
        else:
            return None
    
    def is_multimodal_enabled(self) -> bool:
        """멀티모달 검색 활성화 여부 반환"""
        provider = self.get_current_embedding_provider()
        
        if provider == "bedrock":
            # Bedrock은 멀티모달 모델이 설정되어 있으면 활성화
            return bool(self.bedrock_multimodal_embedding_model_id)
        elif provider == "azure_openai":
            # Azure는 CLIP 엔드포인트가 설정되어 있어야 활성화
            return bool(self.azure_openai_multimodal_embedding_endpoint)
        else:
            return False
    
    def get_current_llm_provider(self) -> str:
        """현재 설정된 LLM 공급자 반환"""
        return self.default_llm_provider
    
    def get_current_embedding_provider(self) -> str:
        """현재 설정된 임베딩 공급자 반환"""
        if self.default_embedding_provider:
            return self.default_embedding_provider
        return self.default_llm_provider  # 임베딩은 LLM과 같은 공급자 사용
    
    def get_query_rewrite_config(self) -> dict:
        """질의문 재작성 LLM 설정 반환"""
        config = {
            "provider": self.query_rewrite_provider,
            "max_tokens": self.query_rewrite_max_tokens,
            "temperature": self.query_rewrite_temperature,
        }
        
        if self.query_rewrite_provider == "azure_openai":
            config.update({
                "deployment": self.query_rewrite_azure_deployment,
                "endpoint": self.query_rewrite_azure_endpoint or self.azure_openai_endpoint,
                "api_key": self.query_rewrite_azure_api_key or self.azure_openai_api_key,
                "api_version": self.query_rewrite_azure_api_version,
            })
        elif self.query_rewrite_provider == "bedrock":
            config.update({
                "model_id": self.query_rewrite_bedrock_model_id,
                "region": self.query_rewrite_bedrock_region or self.aws_region,
            })
        
        return config
    
    # Bedrock 관련 설정 추가
    bedrock_max_tokens: int = 4096
    bedrock_temperature: float = 0.7
    bedrock_top_p: float = 0.9
    bedrock_top_k: int = 50
    
    # Agent-based RAG 설정 (Phase 2)
    use_agent_architecture: bool = False  # Feature flag: 점진적 롤아웃
    agent_enable_observability: bool = True  # Agent 실행 단계 추적
    agent_enable_evaluation: bool = True  # 평가 메트릭 수집
    enable_new_summary_agent: bool = False  # 신규 요약 에이전트 사용 여부
    enable_new_presentation_agent: bool = False  # 신규 PPT 에이전트 사용 여부
    
    # Office Generator Service (Node.js PptxGenJS)
    pptxgenjs_service_url: str = "http://localhost:3001"
    pptxgenjs_api_key: str = ""
    presentation_output_dir: str = "uploads/presentations"
    
    # 질의문 재작성 및 의도 분류 LLM 설정
    query_rewrite_provider: str = "azure_openai"  # azure_openai | bedrock
    # Azure OpenAI 설정
    query_rewrite_azure_deployment: str = "gpt-4o"
    query_rewrite_azure_endpoint: str = ""
    query_rewrite_azure_api_key: str = ""
    query_rewrite_azure_api_version: str = "2024-12-01-preview"
    # Bedrock 설정
    query_rewrite_bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    query_rewrite_bedrock_region: str = "ap-northeast-2"
    # 공통 파라미터
    query_rewrite_max_tokens: int = 500
    query_rewrite_temperature: float = 0.3

    def log_file_path(self) -> str:
        return os.path.join(self.log_dir, self.log_file_name)

    def sql_log_file_path(self) -> str:
        return os.path.join(self.log_dir, self.sql_query_log_file_name)

    # ------------------------------------------------------------------
    # Post init hook (pydantic v2) to normalize CORS origins when provided
    # via environment variable as a single comma-separated string.
    # e.g. CORS_ORIGINS="http://a:3000,http://b:3000" would otherwise
    # become ["http://a:3000,http://b:3000"] (single entry) causing
    # only the first origin to effectively work in practice/logging.
    # ------------------------------------------------------------------
    def model_post_init(self, __context: any) -> None:  # type: ignore[override]
        try:
            if len(self.cors_origins) == 1:
                raw = self.cors_origins[0]
                if "," in raw and raw.count("http") > 1:
                    # Split on commas, strip whitespace
                    split_list = [o.strip() for o in raw.split(",") if o.strip()]
                    if split_list:
                        self.cors_origins = split_list  # type: ignore[assignment]
        except Exception:
            # Fail silently; CORS will just use whatever was parsed
            pass
        
        # 리랭킹 모델 검증 (RAG_USE_RERANKING=true일 때 필수)
        if self.rag_use_reranking:
            import sys
            if self.rag_reranking_provider == "azure_openai":
                if not self.rag_reranking_deployment:
                    print("❌ 에러: RAG_RERANKING_PROVIDER=azure_openai이지만 RAG_RERANKING_DEPLOYMENT가 설정되지 않았습니다.")
                    print("💡 해결: backend/.env 파일에 RAG_RERANKING_DEPLOYMENT=gpt-5-nano 등을 추가하세요.")
                    sys.exit(1)
            elif self.rag_reranking_provider == "bedrock":
                if not self.rag_reranking_bedrock_model_id:
                    print("❌ 에러: RAG_RERANKING_PROVIDER=bedrock이지만 RAG_RERANKING_BEDROCK_MODEL_ID가 설정되지 않았습니다.")
                    print("💡 해결: backend/.env 파일에 RAG_RERANKING_BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0 등을 추가하세요.")
                    sys.exit(1)


settings = Settings()
