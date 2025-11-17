#!/usr/bin/env python
"""
DOCX 직접 추출 테스트 - 이미지 감지 확인
"""
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.services.document.extraction.text_extractor_service import text_extractor_service

async def test_docx_extraction():
    docx_path = "/home/wjadmin/Dev/InsightBridge/backend/uploads/e8512fb195af403287a52819b7d49317_20251002_011609.docx"
    
    if not os.path.exists(docx_path):
        print(f"❌ 파일을 찾을 수 없습니다: {docx_path}")
        return
    
    print(f"📄 Testing raw DOCX extraction: {os.path.basename(docx_path)}")
    
    try:
        result = await text_extractor_service.extract_text_from_file(docx_path)
        
        print("\n=== RAW EXTRACTION RESULT ===")
        print(f"Keys: {list(result.keys())}")
        
        # Check text
        if 'text' in result:
            text = result['text']
            print(f"\nText length: {len(text)} characters")
            print(f"Text preview: {text[:300]}...")
            
            # Look for image references
            import re
            img_refs = re.findall(r'그림 \d+[^\n]*', text)
            if img_refs:
                print(f"\n🖼️  Found {len(img_refs)} image references:")
                for ref in img_refs:
                    print(f"  - {ref}")
        
        # Check pages structure  
        if 'pages' in result:
            pages = result['pages']
            print(f"\nPages: {len(pages)}")
            for i, page in enumerate(pages):
                print(f"  Page {i+1}: {list(page.keys())}")
                if 'images_metadata' in page:
                    imgs = page['images_metadata']
                    print(f"    Images: {len(imgs)}")
                    for j, img in enumerate(imgs):
                        print(f"      Image {j+1}: {img}")
        
        # Check metadata
        if 'metadata' in result:
            metadata = result['metadata']
            print(f"\nMetadata: {metadata}")
            
        return result
        
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_docx_extraction())