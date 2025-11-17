"""
기존 문서의 접근 레벨 자동 설정 스크립트
Phase 2: 컨테이너 권한 기반 문서 접근 레벨 마이그레이션

실행 방법:
    python migrate_document_access_levels.py

기능:
1. 모든 기존 문서 조회
2. 컨테이너 권한 기반으로 접근 레벨 자동 매핑
3. 접근 규칙 자동 생성 (is_inherited='Y')
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_async_session_context
from app.models.document.file_models import TbFileBssInfo
from app.models.document.document_access import TbDocumentAccessRules, AccessLevel
from app.services.document.document_access_service import DocumentAccessService
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_document_access_levels():
    """모든 기존 문서의 접근 레벨을 컨테이너 권한 기반으로 설정"""
    
    async with get_async_session_context() as db:
        try:
            # 1. 접근 규칙이 없는 모든 문서 조회
            logger.info("📋 접근 규칙이 없는 문서 조회 중...")
            
            # 서브쿼리: 이미 접근 규칙이 있는 문서 ID들
            subquery = select(TbDocumentAccessRules.file_bss_info_sno).distinct()
            
            # 접근 규칙이 없고 삭제되지 않은 문서 조회
            query = select(TbFileBssInfo).where(
                TbFileBssInfo.del_yn == 'N',
                ~TbFileBssInfo.file_bss_info_sno.in_(subquery)
            )
            
            result = await db.execute(query)
            documents = result.scalars().all()
            
            total_count = len(documents)
            logger.info(f"✅ 총 {total_count}개 문서를 발견했습니다.")
            
            if total_count == 0:
                logger.info("✨ 모든 문서에 이미 접근 규칙이 설정되어 있습니다.")
                return
            
            # 2. 각 문서에 대해 접근 레벨 설정
            service = DocumentAccessService(db)
            success_count = 0
            error_count = 0
            
            logger.info("🔄 접근 레벨 설정 시작...")
            
            for idx, document in enumerate(documents, 1):
                try:
                    # 컨테이너 권한 기반 접근 규칙 생성
                    access_rule = await service.set_document_access_from_container(
                        file_bss_info_sno=document.file_bss_info_sno,
                        created_by='SYSTEM_MIGRATION'
                    )
                    
                    if access_rule:
                        success_count += 1
                        logger.info(
                            f"  [{idx}/{total_count}] ✅ 문서 {document.file_bss_info_sno} "
                            f"({document.file_lgc_nm}): {access_rule.access_level.value} "
                            f"(컨테이너: {document.permission_level})"
                        )
                    else:
                        error_count += 1
                        logger.warning(
                            f"  [{idx}/{total_count}] ⚠️ 문서 {document.file_bss_info_sno} "
                            f"({document.file_lgc_nm}): 규칙 생성 실패"
                        )
                    
                    # 10개마다 진행 상황 출력
                    if idx % 10 == 0:
                        logger.info(f"  진행: {idx}/{total_count} ({idx/total_count*100:.1f}%)")
                    
                except Exception as e:
                    error_count += 1
                    logger.error(
                        f"  [{idx}/{total_count}] ❌ 문서 {document.file_bss_info_sno} "
                        f"({document.file_lgc_nm}): {str(e)}"
                    )
            
            # 3. 결과 요약
            logger.info("\n" + "="*60)
            logger.info("📊 마이그레이션 완료 요약")
            logger.info("="*60)
            logger.info(f"총 문서 수:        {total_count}")
            logger.info(f"성공:             {success_count}")
            logger.info(f"실패:             {error_count}")
            logger.info(f"성공률:           {success_count/total_count*100:.1f}%")
            logger.info("="*60)
            
            # 4. 접근 레벨별 통계
            logger.info("\n📈 접근 레벨별 문서 분포")
            logger.info("-"*60)
            
            for access_level in AccessLevel:
                count_query = select(func.count()).select_from(TbDocumentAccessRules).where(
                    TbDocumentAccessRules.access_level == access_level
                )
                count_result = await db.execute(count_query)
                count = count_result.scalar()
                
                logger.info(f"  {access_level.value.upper():15s}: {count:5d} 문서")
            
            logger.info("-"*60)
            logger.info("✨ 마이그레이션이 완료되었습니다!\n")
            
        except Exception as e:
            logger.error(f"❌ 마이그레이션 실패: {str(e)}")
            raise


async def verify_migration():
    """마이그레이션 결과 검증"""
    
    async with get_async_session_context() as db:
        try:
            logger.info("🔍 마이그레이션 결과 검증 중...")
            
            # 1. 접근 규칙이 없는 문서 수
            subquery = select(TbDocumentAccessRules.file_bss_info_sno).distinct()
            
            query = select(func.count()).select_from(TbFileBssInfo).where(
                TbFileBssInfo.del_yn == 'N',
                ~TbFileBssInfo.file_bss_info_sno.in_(subquery)
            )
            
            result = await db.execute(query)
            missing_count = result.scalar()
            
            if missing_count > 0:
                logger.warning(f"⚠️ 아직 접근 규칙이 없는 문서: {missing_count}개")
            else:
                logger.info("✅ 모든 문서에 접근 규칙이 설정되었습니다!")
            
            # 2. 상속된 규칙 수
            inherited_query = select(func.count()).select_from(TbDocumentAccessRules).where(
                TbDocumentAccessRules.is_inherited == 'Y'
            )
            
            inherited_result = await db.execute(inherited_query)
            inherited_count = inherited_result.scalar()
            
            logger.info(f"📋 컨테이너 상속 규칙: {inherited_count}개")
            
            # 3. 수동 설정 규칙 수
            manual_query = select(func.count()).select_from(TbDocumentAccessRules).where(
                TbDocumentAccessRules.is_inherited == 'N'
            )
            
            manual_result = await db.execute(manual_query)
            manual_count = manual_result.scalar()
            
            logger.info(f"✏️  수동 설정 규칙: {manual_count}개")
            
        except Exception as e:
            logger.error(f"❌ 검증 실패: {str(e)}")
            raise


async def main():
    """메인 실행 함수"""
    logger.info("="*60)
    logger.info("🚀 문서 접근 레벨 마이그레이션 시작")
    logger.info("="*60)
    logger.info("")
    
    try:
        # 마이그레이션 실행
        await migrate_document_access_levels()
        
        # 결과 검증
        await verify_migration()
        
        logger.info("✨ 모든 작업이 완료되었습니다!")
        
    except Exception as e:
        logger.error(f"❌ 오류 발생: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
