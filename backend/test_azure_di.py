#!/usr/bin/env python3
"""
Azure Document Intelligence 연결 테스트
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.services.document.extraction.azure_document_intelligence_service import azure_document_intelligence_service

async def test_azure_di_connection():
    """Azure Document Intelligence 연결 및 설정 테스트"""
    
    print("🧪 Azure Document Intelligence 연결 테스트")
    print("=" * 50)
    
    # 1. 설정 확인
    print(f"✅ 사용 활성화: {settings.use_azure_document_intelligence_pdf}")
    print(f"✅ 엔드포인트: {settings.azure_document_intelligence_endpoint}")
    print(f"✅ API 버전: {settings.azure_document_intelligence_api_version}")
    print(f"✅ 기본 모델: {settings.azure_document_intelligence_default_model}")
    print(f"✅ 레이아웃 모델: {settings.azure_document_intelligence_layout_model}")
    print(f"✅ 최대 페이지: {settings.azure_document_intelligence_max_pages}")
    print(f"✅ 타임아웃: {settings.azure_document_intelligence_timeout_seconds}초")
    print(f"✅ 재시도 횟수: {settings.azure_document_intelligence_retry_max_attempts}")
    print(f"✅ 신뢰도 임계값: {settings.azure_document_intelligence_confidence_threshold}")
    
    # API 키는 보안상 일부만 표시
    api_key = settings.azure_document_intelligence_api_key
    if api_key:
        print(f"✅ API 키: {api_key[:8]}...{api_key[-8:] if len(api_key) > 16 else '***'}")
    else:
        print("❌ API 키가 설정되지 않았습니다.")
    
    print()
    
    # 2. 서비스 가용성 확인
    print("🔍 서비스 가용성 확인:")
    is_available = azure_document_intelligence_service.is_available()
    print(f"   상태: {'✅ 사용 가능' if is_available else '❌ 사용 불가'}")
    
    if not is_available:
        print("   원인: 설정 누락 또는 클라이언트 초기화 실패")
        return False
    
    print()
    
    # 3. 테스트 PDF 파일 확인
    test_pdf_files = [
        "../test_template3.pdf",
        "../test_template2.pdf", 
        "test_document.pdf"
    ]
    
    test_file = None
    for pdf_path in test_pdf_files:
        if Path(pdf_path).exists():
            test_file = pdf_path
            break
    
    if not test_file:
        print("⚠️  테스트할 PDF 파일을 찾을 수 없습니다.")
        print("   간단한 연결 테스트만 수행합니다.")
        return True
    
    print(f"📄 테스트 파일: {test_file}")
    file_size = Path(test_file).stat().st_size
    print(f"   크기: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
    
    # 4. 실제 분석 테스트
    print()
    print("🚀 Azure Document Intelligence 분석 테스트:")
    
    try:
        result = await azure_document_intelligence_service.analyze_pdf(test_file)
        
        if result.success:
            print("✅ 분석 성공!")
            print(f"   추출된 텍스트 길이: {len(result.text):,}자")
            print(f"   페이지 수: {len(result.pages)}")
            print(f"   표 수: {len(result.tables)}")
            print(f"   그림 수: {len(result.figures)}")
            print(f"   처리 시간: {result.metadata.get('di_processing_time_seconds', 'N/A')}초")
            
            # 텍스트 미리보기
            if result.text:
                preview = result.text[:200].replace('\n', ' ')
                print(f"   텍스트 미리보기: {preview}...")
            
            return True
        else:
            print("❌ 분석 실패!")
            print(f"   오류: {result.error}")
            return False
            
    except Exception as e:
        print(f"💥 분석 중 예외 발생: {str(e)}")
        return False

async def main():
    """메인 테스트 함수"""
    success = await test_azure_di_connection()
    
    print()
    print("=" * 50)
    if success:
        print("🎉 Azure Document Intelligence가 정상적으로 설정되고 작동합니다!")
    else:
        print("❌ Azure Document Intelligence 설정 또는 연결에 문제가 있습니다.")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)