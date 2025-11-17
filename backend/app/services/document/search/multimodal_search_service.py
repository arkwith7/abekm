"""멀티모달 검색 서비스
===========================

고급 벡터 검색 기능을 제공하는 서비스
- pgvector 기반 유사도 검색
- CLIP 멀티모달 검색 (이미지/텍스트 크로스 모달)
- 컨테이너별 필터링
- 하이브리드 검색 (텍스트 + CLIP)
"""

from typing import List, Dict, Any, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.document.multimodal_models import DocEmbedding, DocChunk
from app.models import TbFileBssInfo
from app.services.core.korean_nlp_service import korean_nlp_service
from app.core.config import settings

# CLIP 임베딩 서비스
try:
    from app.services.document.vision.image_embedding_service import ImageEmbeddingService
    image_embedding_service = ImageEmbeddingService()
except ImportError:
    image_embedding_service = None

logger = logging.getLogger(__name__)

class MultimodalSearchService:
    """멀티모달 검색 서비스"""
    
    async def search_similar_chunks(
        self,
        query_text: str,
        session: AsyncSession,
        top_k: int = 10,
        container_ids: Optional[List[str]] = None,
        file_ids: Optional[List[int]] = None,
        similarity_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """유사도 기반 청크 검색
        
        Args:
            query_text: 검색 쿼리
            session: DB 세션
            top_k: 반환할 최대 결과 수
            container_ids: 필터링할 컨테이너 ID 목록
            file_ids: 필터링할 파일 ID 목록
            similarity_threshold: 최소 유사도 임계값
            
        Returns:
            검색 결과 리스트
        """
        try:
            # 1. 쿼리 임베딩 생성
            query_embedding = await korean_nlp_service.generate_korean_embedding(query_text)
            if not query_embedding:
                logger.warning("쿼리 임베딩 생성 실패")
                return []
            
            # 2. 차원 조정 (제로 패딩)
            max_dim = settings.vector_dimension
            if len(query_embedding) < max_dim:
                query_embedding = query_embedding + [0.0] * (max_dim - len(query_embedding))
            elif len(query_embedding) > max_dim:
                query_embedding = query_embedding[:max_dim]
            
            # 3. pgvector 검색 쿼리 구성
            vector_literal = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # 기본 검색 쿼리
            base_query = f"""
            SELECT 
                de.embedding_id,
                dc.chunk_id,
                dc.file_bss_info_sno,
                dc.chunk_index,
                dc.content_text,
                dc.token_count,
                dc.modality,
                fbf.file_lgc_nm as file_name,
                fbf.knowledge_container_id,
                de.vector <=> '{vector_literal}'::vector as distance
            FROM doc_embedding de
            JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
            JOIN tb_file_bss_info fbf ON dc.file_bss_info_sno = fbf.file_bss_info_sno
            WHERE fbf.del_yn = 'N'
            """
            
            # 필터 조건 추가
            conditions = []
            if container_ids:
                container_filter = "'" + "','".join(container_ids) + "'"
                conditions.append(f"fbf.knowledge_container_id IN ({container_filter})")
            
            if file_ids:
                file_filter = ",".join(map(str, file_ids))
                conditions.append(f"dc.file_bss_info_sno IN ({file_filter})")
            
            if conditions:
                base_query += " AND " + " AND ".join(conditions)
            
            # 정렬 및 제한
            base_query += f"""
            ORDER BY distance ASC
            LIMIT {top_k}
            """
            
            # 4. 쿼리 실행
            result = await session.execute(text(base_query))
            rows = result.fetchall()
            
            # 5. 결과 포맷팅
            search_results = []
            for row in rows:
                similarity_score = 1.0 - float(row.distance)  # 거리를 유사도로 변환
                
                if similarity_score < similarity_threshold:
                    continue
                
                search_results.append({
                    "chunk_id": row.chunk_id,
                    "embedding_id": row.embedding_id,
                    "file_id": row.file_bss_info_sno,
                    "chunk_index": row.chunk_index,
                    "content": row.content_text,
                    "token_count": row.token_count,
                    "modality": row.modality,
                    "file_name": row.file_name,
                    "container_id": row.knowledge_container_id,
                    "similarity_score": similarity_score,
                    "distance": float(row.distance)
                })
            
            logger.info(f"유사도 검색 완료: {len(search_results)}개 결과 (임계값: {similarity_threshold})")
            return search_results
            
        except Exception as e:
            logger.error(f"유사도 검색 실패: {e}")
            return []
    
    async def get_chunk_context(
        self,
        chunk_id: int,
        session: AsyncSession,
        context_window: int = 2
    ) -> Dict[str, Any]:
        """청크 주변 컨텍스트 조회
        
        Args:
            chunk_id: 대상 청크 ID
            session: DB 세션
            context_window: 앞뒤로 가져올 청크 수
            
        Returns:
            컨텍스트 정보
        """
        try:
            # 대상 청크 정보 조회
            stmt = select(DocChunk).where(DocChunk.chunk_id == chunk_id)
            result = await session.execute(stmt)
            target_chunk = result.scalar_one_or_none()
            
            if not target_chunk:
                return {"error": "청크를 찾을 수 없습니다."}
            
            # 같은 파일의 인접 청크들 조회
            context_stmt = select(DocChunk).where(
                DocChunk.file_bss_info_sno == target_chunk.file_bss_info_sno
            ).where(
                DocChunk.chunk_index >= target_chunk.chunk_index - context_window
            ).where(
                DocChunk.chunk_index <= target_chunk.chunk_index + context_window
            ).order_by(DocChunk.chunk_index)
            
            context_result = await session.execute(context_stmt)
            context_chunks = context_result.scalars().all()
            
            return {
                "target_chunk": {
                    "chunk_id": target_chunk.chunk_id,
                    "chunk_index": target_chunk.chunk_index,
                    "content": target_chunk.content_text,
                    "token_count": target_chunk.token_count
                },
                "context_chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content_text,
                        "is_target": chunk.chunk_id == chunk_id
                    }
                    for chunk in context_chunks
                ],
                "total_context_length": sum(len(chunk.content_text or "") for chunk in context_chunks)
            }
            
        except Exception as e:
            logger.error(f"컨텍스트 조회 실패: {e}")
            return {"error": str(e)}
    
    async def search_multimodal_clip(
        self,
        query: str,
        session: AsyncSession,
        query_type: str = "text",
        top_k: int = 10,
        container_ids: Optional[List[str]] = None,
        file_ids: Optional[List[int]] = None,
        similarity_threshold: float = 0.3,
        modality_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """CLIP 기반 멀티모달 검색
        
        Args:
            query: 검색 쿼리 (텍스트 또는 이미지 경로)
            session: DB 세션
            query_type: 쿼리 유형 ('text' 또는 'image')
            top_k: 반환할 최대 결과 수
            container_ids: 필터링할 컨테이너 ID 목록
            file_ids: 필터링할 파일 ID 목록
            similarity_threshold: 최소 유사도 임계값
            modality_filter: 검색 대상 모달리티 ('text', 'image', None=모두)
            
        Returns:
            CLIP 검색 결과 리스트
        """
        try:
            if not image_embedding_service:
                logger.error("CLIP 임베딩 서비스가 초기화되지 않았습니다")
                return []
            
            # 1. CLIP 임베딩 생성
            clip_embedding = None
            if query_type == "text":
                # 텍스트 쿼리 → CLIP 텍스트 임베딩
                logger.info(f"[CLIP] 텍스트 쿼리 임베딩 생성: {query[:50]}...")
                clip_embedding = await image_embedding_service.generate_text_embedding(query)
            elif query_type == "image":
                # 이미지 쿼리 → CLIP 이미지 임베딩
                logger.info(f"[CLIP] 이미지 쿼리 임베딩 생성: {query}")
                clip_embedding = await image_embedding_service.generate_image_embedding(query)
            
            if not clip_embedding:
                logger.warning("CLIP 임베딩 생성 실패")
                return []
            
            # 2. 차원 조정 (CLIP은 512차원)
            clip_dim = 512
            if len(clip_embedding) < clip_dim:
                clip_embedding = clip_embedding + [0.0] * (clip_dim - len(clip_embedding))
            elif len(clip_embedding) > clip_dim:
                clip_embedding = clip_embedding[:clip_dim]
            
            # 3. pgvector CLIP 검색 쿼리 구성
            vector_literal = "[" + ",".join(map(str, clip_embedding)) + "]"
            
            # 기본 검색 쿼리 (clip_vector 컬럼 사용)
            base_query = f"""
            SELECT 
                de.embedding_id,
                dc.chunk_id,
                dc.file_bss_info_sno,
                dc.chunk_index,
                dc.content_text,
                dc.token_count,
                dc.modality,
                fbf.file_lgc_nm as file_name,
                fbf.knowledge_container_id,
                de.clip_vector <=> '{vector_literal}'::vector as distance
            FROM doc_embedding de
            JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
            JOIN tb_file_bss_info fbf ON dc.file_bss_info_sno = fbf.file_bss_info_sno
            WHERE fbf.del_yn = 'N'
            AND de.clip_vector IS NOT NULL
            """
            
            # 필터 조건 추가
            conditions = []
            
            # 컨테이너 필터
            if container_ids:
                container_filter = "'" + "','".join(container_ids) + "'"
                conditions.append(f"fbf.knowledge_container_id IN ({container_filter})")
            
            # 파일 필터
            if file_ids:
                file_filter = ",".join(map(str, file_ids))
                conditions.append(f"dc.file_bss_info_sno IN ({file_filter})")
            
            # 모달리티 필터
            if modality_filter:
                conditions.append(f"dc.modality = '{modality_filter}'")
            
            if conditions:
                base_query += " AND " + " AND ".join(conditions)
            
            # 정렬 및 제한
            base_query += f"""
            ORDER BY distance ASC
            LIMIT {top_k}
            """
            
            # 4. 쿼리 실행
            logger.info(f"[CLIP] 검색 실행 - 쿼리 타입: {query_type}, 모달리티: {modality_filter or '전체'}")
            result = await session.execute(text(base_query))
            rows = result.fetchall()
            
            # 5. 결과 포맷팅
            search_results = []
            for row in rows:
                similarity_score = 1.0 - float(row.distance)  # 거리를 유사도로 변환
                
                if similarity_score < similarity_threshold:
                    continue
                
                search_results.append({
                    "chunk_id": row.chunk_id,
                    "embedding_id": row.embedding_id,
                    "file_id": row.file_bss_info_sno,
                    "chunk_index": row.chunk_index,
                    "content": row.content_text,
                    "token_count": row.token_count,
                    "modality": row.modality,
                    "file_name": row.file_name,
                    "container_id": row.knowledge_container_id,
                    "similarity_score": similarity_score,
                    "distance": float(row.distance)
                })
            
            logger.info(f"[CLIP] 검색 완료: {len(search_results)}개 결과 (임계값: {similarity_threshold})")
            return search_results
            
        except Exception as e:
            logger.error(f"[CLIP] 검색 실패: {e}", exc_info=True)
            return []
    
    async def search_hybrid(
        self,
        query_text: str,
        session: AsyncSession,
        top_k: int = 20,
        container_ids: Optional[List[str]] = None,
        file_ids: Optional[List[int]] = None,
        text_weight: float = 0.6,
        clip_weight: float = 0.4,
        similarity_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """하이브리드 검색 (텍스트 벡터 + CLIP)
        
        Args:
            query_text: 검색 쿼리
            session: DB 세션
            top_k: 반환할 최대 결과 수
            container_ids: 필터링할 컨테이너 ID 목록
            file_ids: 필터링할 파일 ID 목록
            text_weight: 텍스트 검색 가중치 (0.0 ~ 1.0)
            clip_weight: CLIP 검색 가중치 (0.0 ~ 1.0)
            similarity_threshold: 최소 유사도 임계값
            
        Returns:
            하이브리드 검색 결과 리스트
        """
        try:
            # 1. 텍스트 벡터 검색
            logger.info(f"[HYBRID] 텍스트 검색 시작 (weight={text_weight})")
            text_results = await self.search_similar_chunks(
                query_text=query_text,
                session=session,
                top_k=top_k * 2,  # 더 많이 가져와서 통합
                container_ids=container_ids,
                file_ids=file_ids,
                similarity_threshold=similarity_threshold * 0.8  # 임계값 완화
            )
            
            # 2. CLIP 검색
            logger.info(f"[HYBRID] CLIP 검색 시작 (weight={clip_weight})")
            clip_results = await self.search_multimodal_clip(
                query=query_text,
                session=session,
                query_type="text",
                top_k=top_k * 2,
                container_ids=container_ids,
                file_ids=file_ids,
                similarity_threshold=similarity_threshold * 0.8
            )
            
            # 3. 결과 통합 (chunk_id 기준)
            merged_results = {}
            
            # 텍스트 검색 결과 추가
            for result in text_results:
                chunk_id = result['chunk_id']
                merged_results[chunk_id] = {
                    **result,
                    'text_score': result['similarity_score'],
                    'clip_score': 0.0,
                    'hybrid_score': result['similarity_score'] * text_weight
                }
            
            # CLIP 검색 결과 병합
            for result in clip_results:
                chunk_id = result['chunk_id']
                clip_score = result['similarity_score']
                
                if chunk_id in merged_results:
                    # 이미 있는 경우 CLIP 점수 추가
                    merged_results[chunk_id]['clip_score'] = clip_score
                    merged_results[chunk_id]['hybrid_score'] += clip_score * clip_weight
                else:
                    # 새로운 경우 추가
                    merged_results[chunk_id] = {
                        **result,
                        'text_score': 0.0,
                        'clip_score': clip_score,
                        'hybrid_score': clip_score * clip_weight
                    }
            
            # 4. 하이브리드 점수로 정렬
            sorted_results = sorted(
                merged_results.values(),
                key=lambda x: x['hybrid_score'],
                reverse=True
            )[:top_k]
            
            # 5. 최종 필터링 (임계값)
            filtered_results = [
                result for result in sorted_results
                if result['hybrid_score'] >= similarity_threshold
            ]
            
            logger.info(f"[HYBRID] 검색 완료: 텍스트={len(text_results)}, CLIP={len(clip_results)}, 통합={len(filtered_results)}개")
            return filtered_results
            
        except Exception as e:
            logger.error(f"[HYBRID] 검색 실패: {e}", exc_info=True)
            return []

# 전역 인스턴스
multimodal_search_service = MultimodalSearchService()