"""
파일 처리 상태 확인 스크립트
"""
import asyncio
import sys
from sqlalchemy import select, and_

sys.path.append('/home/admin/wkms-aws/backend')

from app.core.database import get_async_session_local
from app.models import TbFileBssInfo

async def check_file_status():
    """파일 처리 상태 확인"""
    async_session_local = get_async_session_local()
    async with async_session_local() as db:
        print("=" * 100)
        print("파일 처리 상태 확인")
        print("=" * 100)
        
        # 최근 업로드된 파일 조회
        query = select(TbFileBssInfo).order_by(TbFileBssInfo.created_date.desc()).limit(10)
        result = await db.execute(query)
        files = result.scalars().all()
        
        for file in files:
            print(f"\n📄 파일: {file.file_lgc_nm}")
            print(f"   ID: {file.file_bss_info_sno}")
            print(f"   컨테이너: {file.knowledge_container_id}")
            print(f"   업로드일: {file.created_date}")
            print(f"   파일크기: {file.korean_metadata.get('file_size', 0) if file.korean_metadata else 0} bytes")
            print(f"   문서타입: {file.document_type}")
            
            # 처리 상태 정보
            print(f"\n   📊 처리 상태:")
            print(f"      processing_status: {file.processing_status}")
            print(f"      processing_started_at: {file.processing_started_at}")
            print(f"      processing_completed_at: {file.processing_completed_at}")
            print(f"      processing_error: {file.processing_error}")
            
            # 청크 정보
            print(f"\n   📦 청크 정보:")
            print(f"      chunk_count: {file.chunk_count}")
            
            # 검색 인덱스 확인
            print(f"\n   🔍 검색 가능 여부:")
            searchable = (
                file.processing_status == 'completed' and 
                file.chunk_count > 0 and
                file.processing_completed_at is not None
            )
            print(f"      검색 가능: {'✅ YES' if searchable else '❌ NO'}")
            
            if not searchable:
                print(f"      문제점:")
                if file.processing_status != 'completed':
                    print(f"         - 처리 상태가 'completed'가 아님: {file.processing_status}")
                if file.chunk_count == 0:
                    print(f"         - 청크가 생성되지 않음")
                if file.processing_completed_at is None:
                    print(f"         - 처리 완료 시간이 기록되지 않음")
                if file.processing_error:
                    print(f"         - 에러 발생: {file.processing_error}")
            
            print("-" * 100)

if __name__ == "__main__":
    asyncio.run(check_file_status())
