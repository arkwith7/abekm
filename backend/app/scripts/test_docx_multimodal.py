#!/usr/bin/env python
"""
DOCX 멀티모달 파이프라인 테스트
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session_local
from app.services.document.multimodal_document_service import MultimodalDocumentService
from app.services.core.azure_blob_service import get_azure_blob_service
from app.core.config import settings

async def test_docx_multimodal():
    docx_path = "/home/wjadmin/Dev/InsightBridge/backend/uploads/e8512fb195af403287a52819b7d49317_20251002_011609.docx"
    file_bss_info_sno = 1  # existing file id assumed
    container_id = "TEST"  # placeholder
    user_emp_no = "tester"
    
    if not os.path.exists(docx_path):
        print(f"❌ 파일을 찾을 수 없습니다: {docx_path}")
        return
    
    file_size = os.path.getsize(docx_path)
    print(f"📄 Testing DOCX: {os.path.basename(docx_path)} ({file_size:,} bytes)")
    print("🚀 Running multimodal processing...")
    
    try:
        async_session_local = get_async_session_local()
        async with async_session_local() as session:  # type: AsyncSession
            service = MultimodalDocumentService()
            
            result = await service.process_document_multimodal(
                file_path=docx_path,
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
    result = asyncio.run(test_docx_multimodal())