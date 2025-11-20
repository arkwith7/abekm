#!/usr/bin/env python3
"""문서 20번 재처리 스크립트 (S3 이미지 다운로드 테스트)"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
from sqlalchemy import select
from app.core.database import get_async_session_local
from app.models import TbFileBssInfo
from app.tasks.document_tasks import process_document_async

async def reprocess_document_20():
    """문서 20번 재처리"""
    async_session = get_async_session_local()
    
    async with async_session() as session:
        # 파일 정보 조회
        stmt = select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == 20)
        result = await session.execute(stmt)
        file_info = result.scalar_one_or_none()
        
        if not file_info:
            print("❌ 문서 20번을 찾을 수 없습니다.")
            return
        
        print(f"📄 문서 정보:")
        print(f"   - 파일명: {file_info.file_lgc_nm}")
        print(f"   - 경로: {file_info.path}")
        print(f"   - 컨테이너: {file_info.knowledge_container_id}")
        print(f"   - 소유자: {file_info.owner_emp_no}")
        
        # Celery 태스크 실행
        print("\n🚀 문서 재처리 시작 (비동기)...")
        task = process_document_async.delay(
            file_path=file_info.path,
            file_bss_info_sno=20,
            container_id=file_info.knowledge_container_id,
            user_emp_no=file_info.owner_emp_no,
            provider="upstage",  # 또는 azure_di
            document_type="academic_paper"
        )
        
        print(f"✅ Celery 태스크 시작됨: {task.id}")
        print(f"\n📋 로그 확인:")
        print(f"   tail -f /home/admin/Dev/abekm/logs/celery.log | grep -E '(CLIP|Marengo|S3|이미지.*다운로드)'")
        print(f"\n🔍 DB 확인 (처리 완료 후):")
        print(f"""   docker exec abekm-postgres psql -U abekm_user -d abekm_db -c "
   SELECT 
       de.chunk_id,
       de.modality,
       length(de.aws_marengo_vector_512) as marengo_len,
       substring(dc.content_text, 1, 50) as caption
   FROM doc_embedding de
   JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
   WHERE dc.file_bss_info_sno = 20 AND de.modality = 'image';"
""")

if __name__ == "__main__":
    asyncio.run(reprocess_document_20())
