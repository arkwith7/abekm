#!/usr/bin/env python3
"""
문서 17번 재처리 스크립트
목적: Upstage FIGURE 객체 바이너리 저장 로직 개선 후 테스트
"""

import asyncio
import sys
import os

# Django 설정 로드
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.config.settings')

import django
django.setup()

from sqlalchemy import select
from app.database.session import AsyncSessionLocal
from app.database.models import TbFileBssInfo
from app.tasks.document_tasks import process_document_async


async def reprocess_document_17():
    """문서 17번 재처리"""
    print("=" * 80)
    print("문서 17번 재처리 시작")
    print("=" * 80)
    
    async with AsyncSessionLocal() as session:
        # 문서 17번 정보 조회
        result = await session.execute(
            select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == 17)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            print("❌ 문서 17번을 찾을 수 없습니다.")
            return
        
        print(f"✅ 문서 발견: {doc.file_nm}")
        print(f"   - Container: {doc.data_container_nm}")
        print(f"   - 업로드: {doc.reg_dt}")
        print(f"   - 상태: {doc.doc_prc_state_cd}")
        print()
        
        # Celery 비동기 태스크 실행
        print("📤 Celery 태스크 큐에 등록 중...")
        task = process_document_async.delay(
            file_bss_info_sno=17,
            container_name=doc.data_container_nm
        )
        
        print(f"✅ 태스크 등록 완료: task_id={task.id}")
        print()
        print("📊 처리 상태 확인:")
        print(f"   - Celery 로그: tail -f logs/celery.log | grep 'doc_id=17'")
        print(f"   - 태스크 상태: task.state (task_id={task.id})")
        print()
        print("🔍 완료 후 검증 쿼리:")
        print("""
        -- 이미지 청크 생성 확인
        SELECT modality, COUNT(*) 
        FROM doc_chunk 
        WHERE file_bss_info_sno = 17 
        GROUP BY modality;
        
        -- 임베딩 상태 확인
        SELECT 
            de.modality,
            COUNT(*) as total,
            COUNT(de.aws_marengo_vector_512) as has_marengo
        FROM doc_embedding de
        JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
        WHERE dc.file_bss_info_sno = 17
        GROUP BY de.modality;
        """)


if __name__ == "__main__":
    asyncio.run(reprocess_document_17())
