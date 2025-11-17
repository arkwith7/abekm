"""
🔮 벡터 임베딩 서비스
==================

텍스트를 벡터로 변환하여 의미 검색을 가능하게 하는 서비스
- 다양한 임베딩 모델 지원 (AWS Bedrock, OpenAI, Local)
- 청킹 및 벡터 저장
- 유사도 검색
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import json
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

class VectorEmbeddingService:
    """벡터 임베딩 및 저장 서비스"""
    
    def __init__(self):
        self.chunk_size = 1000  # 기본 청크 크기
        self.chunk_overlap = 200  # 청크 오버랩
        self.max_chunks = 50  # 최대 청크 수
        
    async def process_document_for_search(
        self, 
        text: str, 
        document_id: int,
        container_id: str
    ) -> Dict[str, Any]:
        """
        문서를 검색 가능한 형태로 처리합니다.
        
        Args:
            text: 문서 텍스트
            document_id: 문서 ID
            container_id: 컨테이너 ID
            
        Returns:
            Dict containing processing results
        """
        try:
            if not text or not text.strip():
                return self._empty_processing_result()
            
            # 1단계: 텍스트 청킹
            chunks = self._chunk_text(text)
            
            # 2단계: 벡터 임베딩 생성 (현재는 모의 처리)
            embeddings = await self._create_embeddings(chunks)
            
            # 3단계: 메타데이터 생성
            chunk_metadata = self._create_chunk_metadata(chunks, document_id, container_id)
            
            result = {
                "success": True,
                "chunk_count": len(chunks),
                "embedding_count": len(embeddings),
                "chunks": chunks,
                "embeddings": embeddings,
                "metadata": chunk_metadata,
                "processing_time": datetime.now().isoformat(),
                "total_tokens": sum(len(chunk.split()) for chunk in chunks)
            }
            
            logger.info(f"벡터 처리 완료 - 문서 ID: {document_id}, 청크 수: {len(chunks)}")
            return result
            
        except Exception as e:
            logger.error(f"벡터 처리 실패 - 문서 ID: {document_id}, 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                **self._empty_processing_result()
            }
    
    def _chunk_text(self, text: str) -> List[str]:
        """텍스트를 의미 단위로 청킹"""
        if not text:
            return []
        
        # 문장 단위로 분할
        sentences = self._split_into_sentences(text)
        
        chunks = []
        current_chunk = ""
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # 청크 크기 초과 시 새 청크 시작
            if current_size + sentence_size > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
                current_size = sentence_size
            else:
                current_chunk += " " + sentence if current_chunk else sentence
                current_size += sentence_size
        
        # 마지막 청크 추가
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # 최대 청크 수 제한
        if len(chunks) > self.max_chunks:
            chunks = chunks[:self.max_chunks]
            logger.warning(f"청크 수가 {self.max_chunks}개로 제한됨")
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """텍스트를 문장으로 분할"""
        import re
        
        # 한국어 문장 분할 패턴
        sentence_endings = r'[.!?]+'
        sentences = re.split(sentence_endings, text)
        
        # 빈 문장 제거 및 정리
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    async def _create_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """청크들에 대한 임베딩 벡터 생성 (현재는 모의 처리)"""
        embeddings = []
        
        for i, chunk in enumerate(chunks):
            # TODO: 실제 임베딩 모델 호출
            # 현재는 청크 길이와 해시를 기반으로 한 가상 벡터 생성
            mock_vector = self._create_mock_vector(chunk, vector_dim=settings.get_current_embedding_dimension())
            embeddings.append(mock_vector)
        
        return embeddings
    
    def _create_mock_vector(self, text: str, vector_dim: int = None) -> List[float]:
        """모의 벡터 생성 (실제 구현 전까지 사용)"""
        if vector_dim is None:
            vector_dim = settings.get_current_embedding_dimension()
        import hashlib
        import struct
        
        # 텍스트 해시를 기반으로 시드 생성
        text_hash = hashlib.md5(text.encode()).digest()
        seed = struct.unpack('I', text_hash[:4])[0]
        
        # 시드를 이용한 의사 랜덤 벡터 생성
        import random
        random.seed(seed)
        
        vector = [random.uniform(-1.0, 1.0) for _ in range(vector_dim)]
        
        # 벡터 정규화
        magnitude = sum(x * x for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
        
        return vector
    
    def _create_chunk_metadata(
        self, 
        chunks: List[str], 
        document_id: int, 
        container_id: str
    ) -> List[Dict[str, Any]]:
        """청크별 메타데이터 생성"""
        metadata_list = []
        
        for i, chunk in enumerate(chunks):
            metadata = {
                "chunk_id": f"{document_id}_chunk_{i+1}",
                "document_id": document_id,
                "container_id": container_id,
                "chunk_sequence": i + 1,
                "chunk_text": chunk,
                "chunk_length": len(chunk),
                "word_count": len(chunk.split()),
                "created_at": datetime.now().isoformat(),
                "embedding_model": settings.get_current_embedding_model(),
                "embedding_dimension": settings.get_current_embedding_dimension()
            }
            metadata_list.append(metadata)
        
        return metadata_list
    
    def _empty_processing_result(self) -> Dict[str, Any]:
        """빈 처리 결과 반환"""
        return {
            "chunk_count": 0,
            "embedding_count": 0,
            "chunks": [],
            "embeddings": [],
            "metadata": [],
            "processing_time": datetime.now().isoformat(),
            "total_tokens": 0
        }
    
    async def store_vectors_to_database(
        self, 
        embeddings: List[List[float]], 
        metadata: List[Dict[str, Any]],
        session  # AsyncSession
    ) -> bool:
        """
        벡터와 메타데이터를 데이터베이스에 저장
        TODO: PostgreSQL pgvector 테이블에 저장 구현
        """
        try:
            # TODO: TbDocumentSearchIndex 및 VsDocContentsChunks 테이블에 저장
            # 현재는 로그만 출력
            logger.info(f"벡터 저장 시뮬레이션 - 벡터 수: {len(embeddings)}, 메타데이터 수: {len(metadata)}")
            
            for i, (embedding, meta) in enumerate(zip(embeddings, metadata)):
                logger.debug(f"청크 {i+1} 저장 - 벡터 차원: {len(embedding)}, 텍스트 길이: {meta['chunk_length']}")
            
            return True
            
        except Exception as e:
            logger.error(f"벡터 저장 실패: {e}")
            return False
    
    async def search_similar_documents(
        self, 
        query_text: str, 
        container_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        유사한 문서 검색
        TODO: 실제 벡터 유사도 검색 구현
        """
        try:
            # TODO: 쿼리 벡터화 및 유사도 검색
            logger.info(f"문서 검색 시뮬레이션 - 쿼리: {query_text[:50]}..., 컨테이너: {container_id}")
            
            # 모의 검색 결과
            mock_results = [
                {
                    "document_id": 1,
                    "chunk_id": "1_chunk_1",
                    "similarity_score": 0.85,
                    "chunk_text": "관련 문서 내용 예시...",
                    "container_id": container_id or "WJ_HR"
                }
            ]
            
            return mock_results
            
        except Exception as e:
            logger.error(f"문서 검색 실패: {e}")
            return []

# 전역 인스턴스
vector_embedding_service = VectorEmbeddingService()
