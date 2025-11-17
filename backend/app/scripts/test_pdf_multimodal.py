import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session_local
from app.services.document.multimodal_document_service import MultimodalDocumentService
from app.services.core.azure_blob_service import get_azure_blob_service
from app.core.config import settings

PDF_PATH = "/home/wjadmin/Dev/InsightBridge/backend/uploads/pdf_cache/1_CaseStudies_SmartInsulinPump_KO_v0.2.pdf"
FILE_BSS_INFO_SNO = 1  # existing file id assumed
CONTAINER_ID = "TEST"  # placeholder
USER_EMP_NO = "tester"

async def run():
    if not os.path.exists(PDF_PATH):
        print(f"❌ PDF not found: {PDF_PATH}")
        return
    print(f"📄 Using PDF: {PDF_PATH} ({os.path.getsize(PDF_PATH)} bytes)")

    async_session_local = get_async_session_local()
    async with async_session_local() as session:  # type: AsyncSession
        service = MultimodalDocumentService()
        print("🚀 Running multimodal processing...")
        result = await service.process_document_multimodal(
            file_path=PDF_PATH,
            file_bss_info_sno=FILE_BSS_INFO_SNO,
            container_id=CONTAINER_ID,
            user_emp_no=USER_EMP_NO,
            session=session
        )
        print("\n=== PIPELINE RESULT ===")
        for k, v in result.items():
            if k != "stages":
                print(f"{k}: {v}")
        print("Stages:")
        for s in result.get("stages", []):
            print("  -", s)

    # Check blob contents
    try:
        if settings.storage_backend == 'azure_blob':
            azure = get_azure_blob_service()
            key = f"multimodal/{FILE_BSS_INFO_SNO}/extraction_full_text.txt"
            try:
                content = azure.download_text(key, purpose='intermediate')
                print(f"\n✅ Full text blob found: {key}")
                print(f"Length: {len(content)} chars; Preview:\n{content[:500]}\n...")
            except Exception as e:
                print(f"❌ Full text blob not found: {e}")
    except Exception as e:
        print(f"(Blob check skipped) {e}")

if __name__ == "__main__":
    asyncio.run(run())
