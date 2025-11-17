"""
문서 유형별 파이프라인 라우터

문서 유형에 따라 적절한 파이프라인을 선택하고 실행
"""
from typing import Dict, Any, Type
import logging

from app.schemas.document_types import DocumentType
from app.services.document.pipelines.base_pipeline import DocumentPipeline
from app.services.document.pipelines.general_pipeline import GeneralPipeline
from app.services.document.pipelines.academic_paper_pipeline import AcademicPaperPipeline

logger = logging.getLogger(__name__)


class PipelineRouter:
    """
    문서 유형에 따른 파이프라인 라우터
    
    Factory 패턴을 사용하여 문서 유형별 파이프라인 인스턴스 생성
    """
    
    # 문서 유형별 파이프라인 매핑
    PIPELINE_MAP: Dict[str, Type[DocumentPipeline]] = {
        DocumentType.GENERAL: GeneralPipeline,
        DocumentType.ACADEMIC_PAPER: AcademicPaperPipeline,
        DocumentType.PATENT: GeneralPipeline,  # 🔜 향후 PatentPipeline로 교체
    }
    
    @classmethod
    def get_pipeline(
        cls,
        document_type: str,
        document_id: int,
        file_path: str,
        file_name: str,
        container_id: str,
        processing_options: Dict[str, Any],
        user_emp_no: str
    ) -> DocumentPipeline:
        """
        문서 유형에 맞는 파이프라인 인스턴스 반환
        
        Args:
            document_type: 문서 유형 (general, academic_paper, patent, ...)
            document_id: 문서 ID (file_bss_info_sno)
            file_path: 문서 파일 경로
            file_name: 문서 파일명
            container_id: 컨테이너 ID
            processing_options: 문서 유형별 처리 옵션
            user_emp_no: 사용자 사번
        
        Returns:
            DocumentPipeline 인스턴스
        """
        # 처리 옵션 방어적 복사 (None 처리 포함)
        processing_options = dict(processing_options or {})
        
        # DocumentType enum으로 변환 (검증 포함)
        try:
            doc_type_enum = DocumentType(document_type)
        except ValueError:
            logger.warning(f"⚠️ [PipelineRouter] 알 수 없는 문서 유형: {document_type}, 기본 파이프라인 사용")
            doc_type_enum = DocumentType.GENERAL
        
        # downstream 서비스가 문서 유형을 참조할 수 있도록 옵션에 주입
        processing_options.setdefault("document_type", doc_type_enum.value)
        
        # 파이프라인 클래스 가져오기
        pipeline_class = cls.PIPELINE_MAP.get(doc_type_enum, GeneralPipeline)
        
        logger.info(f"🔀 [PipelineRouter] 문서 유형: {document_type} → 파이프라인: {pipeline_class.__name__}")
        
        # 파이프라인 인스턴스 생성
        pipeline = pipeline_class(
            document_id=document_id,
            file_path=file_path,
            file_name=file_name,
            container_id=container_id,
            processing_options=processing_options,
            user_emp_no=user_emp_no
        )
        
        return pipeline
    
    @classmethod
    async def process_document(
        cls,
        document_type: str,
        document_id: int,
        file_path: str,
        file_name: str,
        container_id: str,
        processing_options: Dict[str, Any],
        user_emp_no: str
    ) -> Dict[str, Any]:
        """
        문서 처리 전체 플로우 실행 (편의 메서드)
        
        Args:
            document_type: 문서 유형
            document_id: 문서 ID
            file_path: 문서 파일 경로
            file_name: 문서 파일명
            container_id: 컨테이너 ID
            processing_options: 문서 유형별 처리 옵션
            user_emp_no: 사용자 사번
        
        Returns:
            Dict containing:
                - success: bool
                - statistics: Dict with processing stats
                - pipeline_type: str
                - error: Optional error message
        """
        logger.info(f"🚀 [PipelineRouter] 문서 처리 시작: {file_name} (유형: {document_type})")
        
        try:
            # 파이프라인 인스턴스 생성
            pipeline = cls.get_pipeline(
                document_type=document_type,
                document_id=document_id,
                file_path=file_path,
                file_name=file_name,
                container_id=container_id,
                processing_options=processing_options,
                user_emp_no=user_emp_no
            )
            
            # 파이프라인 실행
            result = await pipeline.process()
            
            # 파이프라인 유형 정보 추가
            result["pipeline_type"] = pipeline.__class__.__name__
            result["document_type"] = document_type
            
            if result.get("success"):
                logger.info(f"✅ [PipelineRouter] 문서 처리 성공: {file_name}")
                logger.info(f"   📊 통계: {result.get('statistics', {})}")
            else:
                logger.error(f"❌ [PipelineRouter] 문서 처리 실패: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [PipelineRouter] 문서 처리 오류: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "statistics": {},
                "pipeline_type": "Unknown",
                "document_type": document_type
            }


# 편의 함수
async def process_document_with_pipeline(
    document_type: str,
    document_id: int,
    file_path: str,
    file_name: str,
    container_id: str,
    processing_options: Dict[str, Any],
    user_emp_no: str
) -> Dict[str, Any]:
    """
    파이프라인 라우터를 통한 문서 처리 (standalone 함수)
    
    Args:
        document_type: 문서 유형
        document_id: 문서 ID
        file_path: 문서 파일 경로
        file_name: 문서 파일명
        container_id: 컨테이너 ID
        processing_options: 문서 유형별 처리 옵션
        user_emp_no: 사용자 사번
    
    Returns:
        처리 결과 딕셔너리
    """
    return await PipelineRouter.process_document(
        document_type=document_type,
        document_id=document_id,
        file_path=file_path,
        file_name=file_name,
        container_id=container_id,
        processing_options=processing_options,
        user_emp_no=user_emp_no
    )
