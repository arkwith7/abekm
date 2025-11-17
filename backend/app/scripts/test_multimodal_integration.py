#!/usr/bin/env python3
"""멀티모달 파이프라인 통합 테스트
===================================

새로 개선된 멀티모달 파이프라인의 전체 워크플로우를 테스트:
1. 테스트 문서 업로드
2. 고급 청킹 검증
3. 임베딩 생성 확인
4. 검색 기능 테스트
5. 통계 및 메타데이터 검증
"""

import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_async_engine
from app.models.document.multimodal_models import (
    DocExtractionSession, DocExtractedObject, DocChunkSession, DocChunk, DocEmbedding
)
from app.models import TbFileBssInfo
from app.services.document.multimodal_document_service import multimodal_document_service
from app.services.document.search.multimodal_search_service import multimodal_search_service

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultimodalPipelineIntegrationTest:
    """멀티모달 파이프라인 통합 테스트"""
    
    def __init__(self):
        self.test_file_id = None
        self.test_container_id = None
        self.extraction_session_id = None
        self.chunk_session_id = None
        
    async def run_full_test(self):
        """전체 테스트 실행"""
        logger.info("🚀 멀티모달 파이프라인 통합 테스트 시작")
        
        async with AsyncSession(get_async_engine()) as session:
            try:
                # 1. 기존 테스트 파일 찾기
                await self._find_test_file(session)
                if not self.test_file_id:
                    logger.error("❌ 테스트용 파일을 찾을 수 없습니다.")
                    return False
                
                # 2. 파이프라인 실행 전 상태 확인
                before_stats = await self._get_current_stats(session)
                logger.info(f"📊 실행 전 상태: {before_stats}")
                
                # 3. 멀티모달 파이프라인 실행
                pipeline_result = await self._run_pipeline(session)
                if not pipeline_result.get("success"):
                    logger.error(f"❌ 파이프라인 실패: {pipeline_result.get('error')}")
                    return False
                
                # 4. 파이프라인 실행 후 상태 확인
                after_stats = await self._get_current_stats(session)
                logger.info(f"📊 실행 후 상태: {after_stats}")
                
                # 5. 결과 검증
                await self._verify_results(session, pipeline_result)
                
                # 6. 검색 기능 테스트
                await self._test_search_functionality(session)
                
                # 7. 최종 요약
                await self._generate_summary(before_stats, after_stats, pipeline_result)
                
                logger.info("✅ 멀티모달 파이프라인 통합 테스트 완료")
                return True
                
            except Exception as e:
                logger.error(f"💥 테스트 실행 중 오류: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False
    
    async def _find_test_file(self, session: AsyncSession):
        """테스트용 파일 찾기"""
        logger.info("🔍 테스트용 파일 검색 중...")
        
        stmt = select(TbFileBssInfo).where(
            TbFileBssInfo.del_yn == 'N'
        ).order_by(TbFileBssInfo.file_bss_info_sno.desc()).limit(1)
        
        result = await session.execute(stmt)
        file_info = result.scalar_one_or_none()
        
        if file_info:
            # SQLAlchemy 모델 인스턴스에서 실제 값 가져오기
            self.test_file_id = file_info.file_bss_info_sno
            self.test_container_id = file_info.knowledge_container_id or "test_container"
            logger.info(f"📄 테스트 파일 선택: ID={self.test_file_id}, 파일명={file_info.file_lgc_nm}")
        else:
            logger.warning("⚠️ 사용 가능한 테스트 파일이 없습니다.")
    
    async def _get_current_stats(self, session: AsyncSession) -> dict:
        """현재 멀티모달 데이터 통계 조회"""
        stats = {}
        
        # 추출 세션 수
        stmt = select(func.count()).select_from(DocExtractionSession)
        result = await session.execute(stmt)
        stats["extraction_sessions"] = result.scalar()
        
        # 추출 객체 수
        stmt = select(func.count()).select_from(DocExtractedObject)
        result = await session.execute(stmt)
        stats["extracted_objects"] = result.scalar()
        
        # 청크 세션 수
        stmt = select(func.count()).select_from(DocChunkSession)
        result = await session.execute(stmt)
        stats["chunk_sessions"] = result.scalar()
        
        # 청크 수
        stmt = select(func.count()).select_from(DocChunk)
        result = await session.execute(stmt)
        stats["chunks"] = result.scalar()
        
        # 임베딩 수
        stmt = select(func.count()).select_from(DocEmbedding)
        result = await session.execute(stmt)
        stats["embeddings"] = result.scalar()
        
        return stats
    
    async def _run_pipeline(self, session: AsyncSession) -> dict:
        """멀티모달 파이프라인 실행"""
        logger.info(f"🎨 멀티모달 파이프라인 실행 - 파일 ID: {self.test_file_id}")
        
        # 테스트 파일 정보 조회
        stmt = select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == self.test_file_id)
        result = await session.execute(stmt)
        file_info = result.scalar_one()
        
        # 테스트용 실제 파일 경로 사용
        test_file_path = "/home/wjadmin/Dev/InsightBridge/backend/test_document.txt"
        
        # 파이프라인 실행
        result = await multimodal_document_service.process_document_multimodal(
            file_path=test_file_path,
            file_bss_info_sno=self.test_file_id,
            container_id=self.test_container_id,
            user_emp_no="test_user",
            session=session,
            provider="azure",
            model_profile="test"
        )
        
        if result.get("success"):
            self.extraction_session_id = result.get("extraction_session_id")
            self.chunk_session_id = result.get("chunk_session_id")
            logger.info(f"✅ 파이프라인 성공 - 추출 세션: {self.extraction_session_id}, 청크 세션: {self.chunk_session_id}")
        
        return result
    
    async def _verify_results(self, session: AsyncSession, pipeline_result: dict):
        """파이프라인 결과 검증"""
        logger.info("🔍 파이프라인 결과 검증 중...")
        
        # 추출 세션 검증
        if self.extraction_session_id:
            stmt = select(DocExtractionSession).where(
                DocExtractionSession.extraction_session_id == self.extraction_session_id
            )
            result = await session.execute(stmt)
            extraction_session = result.scalar_one_or_none()
            
            if extraction_session:
                logger.info(f"✅ 추출 세션 검증 성공: 상태={extraction_session.status}")
            else:
                logger.error("❌ 추출 세션을 찾을 수 없습니다.")
        
        # 청크 세션 검증
        if self.chunk_session_id:
            stmt = select(DocChunkSession).where(
                DocChunkSession.chunk_session_id == self.chunk_session_id
            )
            result = await session.execute(stmt)
            chunk_session = result.scalar_one_or_none()
            
            if chunk_session:
                logger.info(f"✅ 청크 세션 검증 성공: 청크 수={chunk_session.chunk_count}")
            else:
                logger.error("❌ 청크 세션을 찾을 수 없습니다.")
        
        # 청크 내용 샘플 확인
        stmt = select(DocChunk).where(
            DocChunk.file_bss_info_sno == self.test_file_id
        ).limit(3)
        result = await session.execute(stmt)
        sample_chunks = result.scalars().all()
        
        logger.info(f"📄 샘플 청크 {len(sample_chunks)}개:")
        for i, chunk in enumerate(sample_chunks):
            logger.info(f"  청크 {i+1}: 토큰={chunk.token_count}, 길이={len(chunk.content_text or '')}")
    
    async def _test_search_functionality(self, session: AsyncSession):
        """검색 기능 테스트"""
        logger.info("🔍 검색 기능 테스트 시작...")
        
        test_queries = [
            "테스트",
            "문서",
            "내용"
        ]
        
        for query in test_queries:
            try:
                search_results = await multimodal_search_service.search_similar_chunks(
                    query_text=query,
                    session=session,
                    top_k=5,
                    file_ids=[self.test_file_id],
                    similarity_threshold=0.1
                )
                
                logger.info(f"🔍 쿼리 '{query}': {len(search_results)}개 결과")
                if search_results:
                    best_result = search_results[0]
                    logger.info(f"  최고 유사도: {best_result['similarity_score']:.4f}")
                
            except Exception as e:
                logger.warning(f"⚠️ 검색 테스트 실패 ('{query}'): {e}")
    
    async def _generate_summary(self, before_stats: dict, after_stats: dict, pipeline_result: dict):
        """최종 요약 생성"""
        logger.info("📋 === 멀티모달 파이프라인 테스트 요약 ===")
        
        # 증가량 계산
        deltas = {key: after_stats[key] - before_stats[key] for key in before_stats}
        
        logger.info(f"📊 데이터 증가량:")
        for key, delta in deltas.items():
            if delta > 0:
                logger.info(f"  {key}: +{delta}")
        
        # 파이프라인 통계
        stats = pipeline_result.get("stats", {})
        if stats:
            logger.info(f"⏱️ 처리 시간: {stats.get('elapsed_seconds', 0):.2f}초")
            logger.info(f"🔢 벡터 차원: {stats.get('vector_dimension', 0)}")
            logger.info(f"📊 평균 청크 토큰: {stats.get('avg_chunk_tokens', 0):.1f}")
            logger.info(f"🖼️ 이미지: {stats.get('images', 0)}개")
            logger.info(f"📋 표: {stats.get('tables', 0)}개")
            logger.info(f"📈 차트: {stats.get('figures', 0)}개")
        
        # 파이프라인 단계별 결과
        stages = pipeline_result.get("stages", [])
        if stages:
            logger.info("🔄 파이프라인 단계:")
            for stage in stages:
                status = "✅" if stage["success"] else "❌"
                logger.info(f"  {status} {stage['name']}")

async def main():
    """메인 실행 함수"""
    test = MultimodalPipelineIntegrationTest()
    success = await test.run_full_test()
    
    if success:
        logger.info("🎉 모든 테스트가 성공적으로 완료되었습니다!")
        return 0
    else:
        logger.error("💥 테스트 실패!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())