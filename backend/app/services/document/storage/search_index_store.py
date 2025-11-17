"""
🔍 멀티모달 통합검색 인덱스 저장 서비스
=========================================

텍스트 + 이미지 + 테이블 멀티모달 검색 지원
- 키워드 검색 최적화 (Korean FTS)
- 하이브리드 검색 (벡터 + 키워드 + FTS)
- 이미지 검색 지원 (이미지 임베딩 + 메타데이터)
- PostgreSQL FTS + GIN 인덱스 + pgvector 활용
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document.unified_search_models import TbDocumentSearchIndex
from app.models.document.multimodal_models import DocEmbedding  # 이미지 임베딩 저장
from app.core.config import settings

logger = logging.getLogger(__name__)

class SearchIndexStoreService:
    """멀티모달 통합검색 인덱스 저장 서비스 - 텍스트 + 이미지 검색 지원"""
    
    def __init__(self):
        self.max_content_length = 50000  # 최대 내용 길이
        self.max_summary_length = 1000   # 요약 최대 길이
        self.image_embedding_model = "openai-clip"  # 이미지 임베딩 모델
        logger.info("🔍 SearchIndexStoreService 초기화 완료 - 멀티모달 검색 지원")
    
    async def store_document_for_search(
        self,
        session: AsyncSession,
        file_bss_info_sno: int,
        container_id: str,
        document_data: Dict[str, Any],
        nlp_analysis: Dict[str, Any],
        user_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        문서를 멀티모달 통합검색 인덱스에 저장 (텍스트 + 이미지)
        
        Args:
            session: 데이터베이스 세션
            file_bss_info_sno: 파일 기본 정보 일련번호
            container_id: 지식 컨테이너 ID
            document_data: 문서 전처리 데이터 (제목, 내용, 요약, 이미지 등)
            nlp_analysis: NLP 분석 결과 (키워드, 개체명 등)
            user_info: 사용자 정보 (권한 설정용)
        
        Returns:
            저장 결과 딕셔너리 (텍스트 + 이미지 인덱스 정보)
        """
        try:
            # 1. 기존 검색 인덱스 확인 및 삭제
            await self._remove_existing_index(session, file_bss_info_sno)
            
            # 2. 문서 내용 준비
            document_title = document_data.get('title', document_data.get('file_name', 'Untitled'))
            full_content = self._prepare_full_content(document_data)
            content_summary = self._create_content_summary(full_content)
            
            # 3. NLP 분석 결과 추출
            search_metadata = self._extract_search_metadata(nlp_analysis)
            
            # 4. 권한 정보 설정
            access_info = self._determine_access_level(container_id, user_info)
            
            # 5. 이미지 메타데이터 준비 (멀티모달 검색용)
            images_metadata = document_data.get('images', [])
            has_images = document_data.get('has_images', False)
            image_count = document_data.get('image_count', 0)
            
            logger.info(f"[MULTIMODAL_SEARCH] 문서 {file_bss_info_sno} - "
                       f"이미지: {image_count}개, "
                       f"텍스트 길이: {len(full_content)}")
            
            # 6. 새로운 검색 인덱스 생성
            search_index = TbDocumentSearchIndex(
                file_bss_info_sno=file_bss_info_sno,
                knowledge_container_id=container_id,
                document_title=document_title,
                full_content=full_content,
                content_summary=content_summary,
                
                # ❌ 제거: kiwipiepy 관련 필드
                # keywords=search_metadata.get('keywords', []),
                # proper_nouns=search_metadata.get('proper_nouns', []),
                # corp_names=search_metadata.get('corp_names', []),
                
                # ✅ 유지: 주제/카테고리
                main_topics=search_metadata.get('main_topics', []),
                
                # 멀티모달 메타데이터
                has_images=has_images,
                has_tables=document_data.get('has_tables', False),
                image_count=image_count,
                table_count=document_data.get('table_count', 0),
                
                # 메타데이터
                document_type=document_data.get('file_type', 'UNKNOWN').upper(),
                page_count=document_data.get('page_count'),
                content_length=len(full_content),
                language_code='ko',
                
                # 권한 정보
                access_level=access_info['access_level'],
                is_public=access_info['is_public'],
                
                # 시스템 정보
                indexing_status='indexed',
                search_weight=self._calculate_search_weight(document_data, search_metadata),
                created_date=datetime.now(),
                last_updated=datetime.now()
            )
            
            # 6. 이미지 메타데이터를 JSON으로 저장 (멀티모달 검색용)
            if images_metadata and len(images_metadata) > 0:
                images_json = json.dumps(images_metadata, ensure_ascii=False)
                search_index.images_metadata = images_json  # JSON 컬럼에 저장
                logger.info(f"[MULTIMODAL_SEARCH] 이미지 메타데이터 저장 완료 - {len(images_metadata)}개")
            
            # 7. 데이터베이스에 저장
            session.add(search_index)
            await session.flush()  # ID 생성을 위해 flush
            
            logger.info(f"🔍 멀티모달 검색 인덱스 저장 완료 - 파일: {file_bss_info_sno}, "
                       f"검색ID: {search_index.search_doc_id}, "
                       f"컨테이너: {container_id}, "
                       f"이미지: {image_count}개")
            
            # 8. 이미지 임베딩 저장 준비 (향후 이미지 검색용)
            image_embeddings_saved = 0
            if has_images and images_metadata:
                # 이미지 임베딩은 별도 프로세스에서 생성/저장
                # 현재는 메타데이터만 저장하고, 실제 임베딩은 이미지 업로드 시 처리
                logger.info(f"[MULTIMODAL_SEARCH] 이미지 임베딩 생성 대기 중 - {len(images_metadata)}개")
            
            return {
                "success": True,
                "search_doc_id": search_index.search_doc_id,
                "file_bss_info_sno": file_bss_info_sno,
                "container_id": container_id,
                "content_length": len(full_content),
                "image_count": image_count,
                "image_embeddings_saved": image_embeddings_saved,
                "indexing_status": "indexed",
                "multimodal_ready": has_images  # 멀티모달 검색 준비 여부
            }
            
        except Exception as e:
            logger.error(f"멀티모달 검색 인덱스 저장 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_bss_info_sno": file_bss_info_sno,
                "container_id": container_id
            }
    
    async def update_search_statistics(
        self,
        session: AsyncSession,
        search_doc_id: int,
        search_query: str
    ) -> None:
        """검색 통계 업데이트"""
        try:
            query = text("""
                UPDATE tb_document_search_index 
                SET search_count = search_count + 1,
                    last_searched_at = NOW()
                WHERE search_doc_id = :search_doc_id
            """)
            
            await session.execute(query, {"search_doc_id": search_doc_id})
            logger.debug(f"검색 통계 업데이트: 문서 {search_doc_id}")
            
        except Exception as e:
            logger.error(f"검색 통계 업데이트 실패: {str(e)}")
    
    async def keyword_search(
        self,
        session: AsyncSession,
        query_text: str,
        container_ids: Optional[List[str]] = None,
        access_level: str = 'normal',
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """키워드 기반 검색"""
        try:
            # 컨테이너 필터 조건
            container_filter = ""
            params = {"query_text": query_text, "access_level": access_level, "limit": limit}
            
            if container_ids:
                container_filter = "AND knowledge_container_id = ANY(:container_ids)"
                params["container_ids"] = container_ids
            
            # 키워드 검색 쿼리
            query = text(f"""
                SELECT 
                    search_doc_id,
                    file_bss_info_sno,
                    knowledge_container_id,
                    document_title,
                    content_summary,
                    keywords,
                    proper_nouns,
                    document_type,
                    -- 키워드 매칭 점수
                    ts_rank(keyword_tsvector, plainto_tsquery('korean', :query_text)) as keyword_score,
                    -- 내용 매칭 점수  
                    ts_rank(content_tsvector, plainto_tsquery('korean', :query_text)) as content_score,
                    last_updated
                FROM tb_document_search_index
                WHERE (keyword_tsvector @@ plainto_tsquery('korean', :query_text)
                       OR content_tsvector @@ plainto_tsquery('korean', :query_text))
                  AND access_level <= :access_level
                  AND indexing_status = 'indexed'
                  {container_filter}
                ORDER BY 
                    GREATEST(keyword_score, content_score) DESC,
                    search_weight DESC,
                    last_updated DESC
                LIMIT :limit
            """)
            
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            # 결과 포맷팅
            search_results = []
            for row in rows:
                search_results.append({
                    "search_doc_id": row[0],
                    "file_bss_info_sno": row[1],
                    "container_id": row[2],
                    "title": row[3],
                    "content_preview": row[4],
                    "keywords": row[5] if row[5] else [],
                    "proper_nouns": row[6] if row[6] else [],
                    "document_type": row[7],
                    "keyword_score": float(row[8]) if row[8] else 0.0,
                    "content_score": float(row[9]) if row[9] else 0.0,
                    "relevance_score": max(float(row[8]) if row[8] else 0.0, 
                                         float(row[9]) if row[9] else 0.0),
                    "last_updated": row[10].isoformat() if row[10] else None,
                    "search_type": "keyword"
                })
            
            logger.info(f"🔍 키워드 검색 완료: {len(search_results)}개 결과")
            return search_results
            
        except Exception as e:
            logger.error(f"키워드 검색 실패: {str(e)}")
            return []
    
    async def hybrid_search(
        self,
        session: AsyncSession,
        query_text: str,
        container_ids: Optional[List[str]] = None,
        access_level: str = 'normal',
        limit: int = 20,
        keyword_weight: float = 0.4,
        content_weight: float = 0.6
    ) -> List[Dict[str, Any]]:
        """하이브리드 검색 (키워드 + 내용)"""
        try:
            # 컨테이너 필터 조건
            container_filter = ""
            params = {
                "query_text": query_text, 
                "access_level": access_level, 
                "limit": limit,
                "keyword_weight": keyword_weight,
                "content_weight": content_weight
            }
            
            if container_ids:
                container_filter = "AND knowledge_container_id = ANY(:container_ids)"
                params["container_ids"] = container_ids
            
            # 하이브리드 검색 쿼리
            query = text(f"""
                SELECT 
                    search_doc_id,
                    file_bss_info_sno,
                    knowledge_container_id,
                    document_title,
                    content_summary,
                    keywords,
                    proper_nouns,
                    main_topics,
                    document_type,
                    -- 개별 점수
                    ts_rank(keyword_tsvector, plainto_tsquery('korean', :query_text)) as keyword_score,
                    ts_rank(content_tsvector, plainto_tsquery('korean', :query_text)) as content_score,
                    -- 하이브리드 점수 (가중치 적용)
                    (ts_rank(keyword_tsvector, plainto_tsquery('korean', :query_text)) * :keyword_weight +
                     ts_rank(content_tsvector, plainto_tsquery('korean', :query_text)) * :content_weight) as hybrid_score,
                    search_weight,
                    last_updated
                FROM tb_document_search_index
                WHERE (keyword_tsvector @@ plainto_tsquery('korean', :query_text)
                       OR content_tsvector @@ plainto_tsquery('korean', :query_text))
                  AND access_level <= :access_level
                  AND indexing_status = 'indexed'
                  {container_filter}
                ORDER BY 
                    hybrid_score DESC,
                    search_weight DESC,
                    last_updated DESC
                LIMIT :limit
            """)
            
            result = await session.execute(query, params)
            rows = result.fetchall()
            
            # 결과 포맷팅
            search_results = []
            for row in rows:
                search_results.append({
                    "search_doc_id": row[0],
                    "file_bss_info_sno": row[1],
                    "container_id": row[2],
                    "title": row[3],
                    "content_preview": row[4],
                    "keywords": row[5] if row[5] else [],
                    "proper_nouns": row[6] if row[6] else [],
                    "main_topics": row[7] if row[7] else [],
                    "document_type": row[8],
                    "keyword_score": float(row[9]) if row[9] else 0.0,
                    "content_score": float(row[10]) if row[10] else 0.0,
                    "hybrid_score": float(row[11]) if row[11] else 0.0,
                    "search_weight": row[12],
                    "last_updated": row[13].isoformat() if row[13] else None,
                    "search_type": "hybrid"
                })
            
            logger.info(f"🔍 하이브리드 검색 완료: {len(search_results)}개 결과")
            return search_results
            
        except Exception as e:
            logger.error(f"하이브리드 검색 실패: {str(e)}")
            return []
    
    # ==============================================
    # 내부 헬퍼 메서드들
    # ==============================================
    
    async def _remove_existing_index(self, session: AsyncSession, file_bss_info_sno: int):
        """기존 검색 인덱스 제거"""
        query = text("""
            DELETE FROM tb_document_search_index 
            WHERE file_bss_info_sno = :file_sno
        """)
        await session.execute(query, {"file_sno": file_bss_info_sno})
    
    def _prepare_full_content(self, document_data: Dict[str, Any]) -> str:
        """문서 전체 내용 준비"""
        # 청크가 있는 경우 합치기
        if 'chunks' in document_data:
            chunks = document_data['chunks']
            # 청크가 문자열 배열인 경우
            if chunks and isinstance(chunks[0], str):
                full_text = ' '.join(chunks)
            # 청크가 딕셔너리 배열인 경우
            elif chunks and isinstance(chunks[0], dict):
                full_text = ' '.join([chunk.get('content', '') for chunk in chunks])
            else:
                full_text = ''
        else:
            # full_content, full_text, content 키 순서로 찾기
            full_text = document_data.get('full_content', 
                                         document_data.get('full_text', 
                                                          document_data.get('content', '')))
        
        # 길이 제한
        if len(full_text) > self.max_content_length:
            full_text = full_text[:self.max_content_length] + '...'
        
        return full_text.strip()
    
    def _create_content_summary(self, full_content: str) -> str:
        """내용 요약 생성"""
        if len(full_content) <= self.max_summary_length:
            return full_content
        
        # 문장 단위로 자르기
        sentences = full_content.split('. ')
        summary = ""
        for sentence in sentences:
            if len(summary + sentence) <= self.max_summary_length - 10:
                summary += sentence + '. '
            else:
                break
        
        return summary.strip() + '...' if summary else full_content[:self.max_summary_length] + '...'
    
    def _extract_search_metadata(self, nlp_analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        NLP 분석 결과에서 검색 메타데이터 추출 (Simplified)
        
        변경 사항 (2025-10-16):
        - kiwipiepy 관련 필드 제거
        - keywords, proper_nouns, corp_names 제거
        - 주제/카테고리만 유지
        """
        return {
            'main_topics': nlp_analysis.get('topics', nlp_analysis.get('categories', []))[:10]  # 최대 10개
        }
    
    def _determine_access_level(self, container_id: str, user_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """접근 권한 레벨 결정"""
        # 기본 권한 설정 (실제 구현에서는 컨테이너별 권한 정책 적용)
        if container_id.endswith('_public'):
            return {'access_level': 'public', 'is_public': True}
        elif container_id.endswith('_hr'):
            return {'access_level': 'restricted', 'is_public': False}
        else:
            return {'access_level': 'normal', 'is_public': False}
    
    def _calculate_search_weight(self, document_data: Dict[str, Any], search_metadata: Dict[str, Any]) -> int:
        """
        검색 가중치 계산 (Simplified)
        
        변경 사항 (2025-10-16):
        - 키워드 수 기반 가중치 제거
        - 문서 타입과 내용 길이만 사용
        """
        weight = 1
        
        # 문서 타입별 가중치
        doc_type = document_data.get('file_type', '').upper()
        if doc_type in ['PDF', 'DOCX']:
            weight += 2
        elif doc_type in ['PPTX', 'XLSX']:
            weight += 1
        
        # 내용 길이에 따른 가중치
        content_length = document_data.get('content_length', len(document_data.get('content', '')))
        if content_length > 10000:
            weight += 2
        elif content_length > 5000:
            weight += 1
        
        return min(weight, 10)  # 최대 가중치 10

# 싱글톤 인스턴스 생성
search_index_store_service = SearchIndexStoreService()
