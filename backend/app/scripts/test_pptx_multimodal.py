#!/usr/bin/env python
"""
PPTX 멀티모달 파이프라인 테스트
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session_local
from app.services.document.multimodal_document_service import MultimodalDocumentService

PPTX_PATH = "/home/wjadmin/Dev/InsightBridge/backend/uploads/ea34ac05939346e886305c623dbcd8e0_20251002_011503.pptx"

async def test_pptx_multimodal():
    file_bss_info_sno = 2  # 가상의 파일 식별자 (실제 환경에 맞게 조정)
    container_id = "TEST-PPTX"
    user_emp_no = "tester"

    if not os.path.exists(PPTX_PATH):
        print(f"❌ 파일을 찾을 수 없습니다: {PPTX_PATH}")
        return

    file_size = os.path.getsize(PPTX_PATH)
    print(f"📄 Testing PPTX: {os.path.basename(PPTX_PATH)} ({file_size:,} bytes)")
    print("🚀 Running multimodal processing...")

    try:
        async_session_local = get_async_session_local()
        async with async_session_local() as session:
            service = MultimodalDocumentService()
            result = await service.process_document_multimodal(
                file_path=PPTX_PATH,
                file_bss_info_sno=file_bss_info_sno,
                container_id=container_id,
                user_emp_no=user_emp_no,
                session=session
            )

            print("\n=== PIPELINE RESULT ===")
            print(f"success: {result.get('success', False)}")
            print(f"extraction_session_id: {result.get('extraction_session_id')}")
            print(f"chunk_session_id: {result.get('chunk_session_id')}")
            print(f"objects_count: {result.get('objects_count', 0)}")
            print(f"chunks_count: {result.get('chunks_count', 0)}")
            print(f"embeddings_count: {result.get('embeddings_count', 0)}")
            print(f"stats: {result.get('stats', {})}")
            print(f"error: {result.get('error')}")
            if result.get('stages'):
                print("Stages:")
                for stage in result['stages']:
                    print(f"  - {stage}")
            return result
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(test_pptx_multimodal())
