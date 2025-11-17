"""
문서 처리 파이프라인 기본 클래스
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class DocumentPipeline(ABC):
    """
    문서 처리 파이프라인 추상 클래스
    
    모든 문서 유형별 파이프라인은 이 클래스를 상속받아 구현해야 함.
    Template Method 패턴을 사용하여 공통 처리 흐름을 정의하고,
    유형별 특화 로직은 서브클래스에서 구현.
    
    처리 단계:
    1. extract: 문서에서 텍스트, 이미지, 메타데이터 추출
    2. chunk: 추출된 콘텐츠를 검색 가능한 청크로 분할
    3. embed: 청크를 벡터로 임베딩
    4. index: 벡터 DB에 인덱싱
    """
    
    def __init__(
        self,
        document_id: int,
        file_path: str,
        file_name: str,
        container_id: str,
        processing_options: Dict[str, Any],
        user_emp_no: str
    ):
        """
        파이프라인 초기화
        
        Args:
            document_id: 문서 ID (file_bss_info_sno)
            file_path: 문서 파일 경로 (로컬 or S3/Blob)
            file_name: 문서 파일명
            container_id: 컨테이너 ID
            processing_options: 문서 유형별 처리 옵션
            user_emp_no: 사용자 사번
        """
        self.document_id = document_id
        self.file_path = file_path
        self.file_name = file_name
        self.container_id = container_id
        self.processing_options = processing_options or {}
        self.user_emp_no = user_emp_no
        
        # 파일 확장자
        self.file_extension = Path(file_name).suffix.lower()
        
        logger.info(f"🏭 [{self.__class__.__name__}] 파이프라인 초기화: {file_name}")
        logger.info(f"   📄 문서 ID: {document_id}")
        logger.info(f"   📁 컨테이너: {container_id}")
        logger.info(f"   ⚙️ 처리 옵션: {processing_options}")
    
    async def process(self) -> Dict[str, Any]:
        """
        전체 파이프라인 실행 (Template Method)
        
        Returns:
            Dict containing:
                - success: bool
                - statistics: Dict with processing stats
                - error: Optional error message
        """
        logger.info(f"🚀 [{self.__class__.__name__}] 파이프라인 시작: {self.file_name}")
        
        try:
            # 1단계: 문서에서 객체 추출
            logger.info(f"📤 [{self.__class__.__name__}] 1단계: 객체 추출")
            extraction_result = await self.extract()
            
            if not extraction_result.get("success"):
                return {
                    "success": False,
                    "error": f"추출 실패: {extraction_result.get('error')}",
                    "statistics": {}
                }
            
            # 2단계: 청킹
            logger.info(f"✂️ [{self.__class__.__name__}] 2단계: 청킹")
            chunking_result = await self.chunk(extraction_result)
            
            if not chunking_result.get("success"):
                return {
                    "success": False,
                    "error": f"청킹 실패: {chunking_result.get('error')}",
                    "statistics": {}
                }
            
            # 3단계: 임베딩
            logger.info(f"🔢 [{self.__class__.__name__}] 3단계: 임베딩")
            embedding_result = await self.embed(chunking_result)
            
            if not embedding_result.get("success"):
                return {
                    "success": False,
                    "error": f"임베딩 실패: {embedding_result.get('error')}",
                    "statistics": {}
                }
            
            # 4단계: 인덱싱
            logger.info(f"💾 [{self.__class__.__name__}] 4단계: 인덱싱")
            indexing_result = await self.index(embedding_result)
            
            if not indexing_result.get("success"):
                return {
                    "success": False,
                    "error": f"인덱싱 실패: {indexing_result.get('error')}",
                    "statistics": {}
                }
            
            # 통계 집계
            statistics = self._aggregate_statistics(
                extraction_result,
                chunking_result,
                embedding_result,
                indexing_result
            )
            
            logger.info(f"✅ [{self.__class__.__name__}] 파이프라인 완료")
            logger.info(f"   📊 통계: {statistics}")
            
            return {
                "success": True,
                "statistics": statistics
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.__class__.__name__}] 파이프라인 오류: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "statistics": {}
            }
    
    @abstractmethod
    async def extract(self) -> Dict[str, Any]:
        """
        문서에서 텍스트, 이미지, 메타데이터 추출
        
        Returns:
            Dict containing:
                - success: bool
                - extracted_objects: List[Dict] - 추출된 객체들
                - metadata: Dict - 문서 메타데이터
                - error: Optional error message
        """
        pass
    
    @abstractmethod
    async def chunk(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        추출된 객체들을 검색 가능한 청크로 분할
        
        Args:
            extraction_result: extract() 메서드의 반환값
        
        Returns:
            Dict containing:
                - success: bool
                - chunks: List[Dict] - 청크 리스트
                - error: Optional error message
        """
        pass
    
    @abstractmethod
    async def embed(self, chunking_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        청크들을 벡터로 임베딩
        
        Args:
            chunking_result: chunk() 메서드의 반환값
        
        Returns:
            Dict containing:
                - success: bool
                - embeddings: List[Dict] - 임베딩된 청크들
                - error: Optional error message
        """
        pass
    
    @abstractmethod
    async def index(self, embedding_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        임베딩된 청크들을 벡터 DB에 인덱싱
        
        Args:
            embedding_result: embed() 메서드의 반환값
        
        Returns:
            Dict containing:
                - success: bool
                - indexed_count: int - 인덱싱된 청크 수
                - error: Optional error message
        """
        pass
    
    def _aggregate_statistics(
        self,
        extraction_result: Dict[str, Any],
        chunking_result: Dict[str, Any],
        embedding_result: Dict[str, Any],
        indexing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        각 단계의 통계 집계
        
        Returns:
            Dict with aggregated statistics
        """
        return {
            "total_objects_extracted": len(extraction_result.get("extracted_objects", [])),
            "total_chunks": len(chunking_result.get("chunks", [])),
            "total_embeddings": len(embedding_result.get("embeddings", [])),
            "total_indexed": indexing_result.get("indexed_count", 0),
            "pipeline_type": self.__class__.__name__
        }
    
    def _get_option(self, key: str, default: Any = None) -> Any:
        """
        처리 옵션 값 가져오기 (헬퍼 메서드)
        
        Args:
            key: 옵션 키
            default: 기본값
        
        Returns:
            옵션 값 또는 기본값
        """
        return self.processing_options.get(key, default)
