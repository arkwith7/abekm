"""
기존 파일들의 chunk_count 업데이트 스크립트
"""
import asyncio
import sys
from sqlalchemy import select, update, and_, func

sys.path.append('/home/admin/wkms-aws/backend')

from app.core.database import get_async_session_local
from app.models import TbFileBssInfo
from app.models.document.multimodal_models import DocChunk

async def fix_chunk_counts():
    """chunk_count가 0이지만 실제 청크가 있는 파일들을 수정"""
    async_session_local = get_async_session_local()
    async with async_session_local() as db:
        print("=" * 100)
        print("chunk_count 수정 작업 시작")
        print("=" * 100)
        
        # chunk_count가 0인 파일 조회
        query = select(TbFileBssInfo).where(
            and_(
                TbFileBssInfo.chunk_count == 0,
                TbFileBssInfo.processing_status == 'completed'
            )
        ).order_by(TbFileBssInfo.created_date.desc())
        
        result = await db.execute(query)
        files = result.scalars().all()
        
        print(f"\n✅ chunk_count=0이고 completed 상태인 파일: {len(files)}개\n")
        
        updated_count = 0
        no_chunks_count = 0
        
        for file in files:
            # 실제 청크 개수 확인
            chunk_count_query = select(func.count()).select_from(DocChunk).where(
                DocChunk.file_bss_info_sno == file.file_bss_info_sno
            )
            chunk_result = await db.execute(chunk_count_query)
            actual_chunk_count = chunk_result.scalar() or 0
            
            print(f"📄 파일: {file.file_lgc_nm[:50]}")
            print(f"   ID: {file.file_bss_info_sno}")
            print(f"   DB chunk_count: {file.chunk_count}")
            print(f"   실제 chunk 개수: {actual_chunk_count}")
            
            if actual_chunk_count > 0:
                # chunk_count 업데이트
                update_stmt = (
                    update(TbFileBssInfo)
                    .where(TbFileBssInfo.file_bss_info_sno == file.file_bss_info_sno)
                    .values(chunk_count=actual_chunk_count)
                )
                await db.execute(update_stmt)
                print(f"   ✅ chunk_count 업데이트: 0 → {actual_chunk_count}\n")
                updated_count += 1
            else:
                print(f"   ⚠️  실제 청크도 없음 - 처리 실패로 추정\n")
                no_chunks_count += 1
        
        await db.commit()
        
        print("=" * 100)
        print(f"✅ 작업 완료")
        print(f"   업데이트된 파일: {updated_count}개")
        print(f"   청크가 없는 파일: {no_chunks_count}개")
        print("=" * 100)

if __name__ == "__main__":
    asyncio.run(fix_chunk_counts())
