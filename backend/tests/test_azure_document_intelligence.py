"""
Azure Document Intelligence 통합 테스트
"""

import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from app.services.document.extraction.azure_document_intelligence_service import (
    AzureDocumentIntelligenceService,
    DocumentIntelligenceResult
)
from app.services.document.extraction.text_extractor_service import TextExtractorService
from app.core.config import settings


class TestAzureDocumentIntelligenceService:
    """Azure Document Intelligence 서비스 테스트"""
    
    @pytest.fixture
    def di_service(self):
        """DI 서비스 인스턴스"""
        return AzureDocumentIntelligenceService()
    
    @pytest.fixture
    def mock_analyze_result(self):
        """모의 분석 결과"""
        mock_result = Mock()
        mock_result.content = "테스트 문서 내용입니다.\n두 번째 페이지 내용."
        
        # 페이지 모의 데이터
        mock_page1 = Mock()
        mock_page1.width = 612
        mock_page1.height = 792
        mock_page1.angle = 0
        mock_page1.unit = "pixel"
        
        # 라인 모의 데이터
        mock_line1 = Mock()
        mock_line1.content = "테스트 문서 내용입니다."
        mock_line1.confidence = 0.95
        mock_line1.bounding_regions = [Mock()]
        mock_line1.bounding_regions[0].polygon = [100, 100, 200, 100, 200, 120, 100, 120]
        
        mock_page1.lines = [mock_line1]
        mock_page1.figures = []
        
        mock_result.pages = [mock_page1]
        mock_result.tables = []
        
        return mock_result
    
    def test_service_initialization(self, di_service):
        """서비스 초기화 테스트"""
        assert di_service.endpoint == settings.azure_document_intelligence_endpoint
        assert di_service.default_model == settings.azure_document_intelligence_default_model
        assert di_service.max_pages == settings.azure_document_intelligence_max_pages
    
    def test_is_available(self, di_service):
        """서비스 사용 가능 여부 테스트"""
        with patch.object(settings, 'use_azure_document_intelligence_pdf', True):
            with patch.object(di_service, '_client', Mock()):
                with patch.object(di_service, 'endpoint', 'https://test.cognitiveservices.azure.com/'):
                    assert di_service.is_available() == True
    
    def test_extract_bbox(self, di_service):
        """bounding box 추출 테스트"""
        mock_element = Mock()
        mock_region = Mock()
        mock_region.polygon = [10, 20, 30, 20, 30, 40, 10, 40]
        mock_element.bounding_regions = [mock_region]
        
        bbox = di_service._extract_bbox(mock_element)
        expected = [[10, 20], [30, 20], [30, 40], [10, 40]]
        assert bbox == expected
    
    def test_convert_di_result(self, di_service, mock_analyze_result):
        """DI 결과 변환 테스트"""
        result = di_service._convert_di_result(mock_analyze_result, "prebuilt-layout")
        
        assert result.success == True
        assert result.text == "테스트 문서 내용입니다.\n두 번째 페이지 내용."
        assert len(result.pages) == 1
        assert result.pages[0]['page_no'] == 1
        assert result.pages[0]['width'] == 612
        assert result.pages[0]['height'] == 792
        assert result.metadata['extraction_method'] == 'azure_document_intelligence'
    
    @pytest.mark.asyncio
    async def test_analyze_pdf_unavailable(self, di_service):
        """서비스 사용 불가 시 테스트"""
        with patch.object(di_service, 'is_available', return_value=False):
            result = await di_service.analyze_pdf("test.pdf")
            
            assert result.success == False
            assert "사용할 수 없습니다" in result.error
            assert result.extraction_method == "azure_document_intelligence_unavailable"
    
    @pytest.mark.asyncio
    async def test_analyze_pdf_page_limit_exceeded(self, di_service):
        """페이지 수 제한 초과 테스트"""
        with patch.object(di_service, 'is_available', return_value=True):
            with patch.object(di_service, '_check_page_limit', return_value=True):
                result = await di_service.analyze_pdf("test.pdf")
                
                assert result.success == False
                assert "페이지 수가 제한" in result.error
                assert result.extraction_method == "azure_document_intelligence_page_limit_exceeded"
    
    @pytest.mark.asyncio
    async def test_analyze_with_retry_success(self, di_service, mock_analyze_result):
        """재시도 로직 성공 테스트"""
        mock_client = Mock()
        mock_poller = Mock()
        mock_poller.done.return_value = True
        mock_poller.result.return_value = mock_analyze_result
        mock_client.begin_analyze_document.return_value = mock_poller
        
        di_service._client = mock_client
        
        with patch.object(di_service, '_poll_result', return_value=mock_analyze_result):
            result = await di_service._analyze_with_retry(b"test content", "prebuilt-layout")
            
            assert result.success == True
            assert result.text == "테스트 문서 내용입니다.\n두 번째 페이지 내용."
    
    @pytest.mark.asyncio
    async def test_analyze_with_retry_auth_error(self, di_service):
        """인증 오류 테스트"""
        from azure.core.exceptions import ClientAuthenticationError
        
        mock_client = Mock()
        mock_client.begin_analyze_document.side_effect = ClientAuthenticationError("인증 실패")
        di_service._client = mock_client
        
        result = await di_service._analyze_with_retry(b"test content", "prebuilt-layout")
        
        assert result.success == False
        assert "인증 실패" in result.error
        assert result.extraction_method == "azure_document_intelligence_auth_error"
    
    @pytest.mark.asyncio 
    async def test_analyze_with_retry_http_429(self, di_service, mock_analyze_result):
        """HTTP 429 재시도 테스트"""
        from azure.core.exceptions import HttpResponseError
        
        mock_client = Mock()
        # 첫 번째 시도에서 429, 두 번째 시도에서 성공
        mock_poller = Mock()
        mock_poller.done.return_value = True
        mock_poller.result.return_value = mock_analyze_result
        
        mock_client.begin_analyze_document.side_effect = [
            HttpResponseError("Too Many Requests", response=Mock(status_code=429)),
            mock_poller
        ]
        di_service._client = mock_client
        di_service.retry_max_attempts = 2
        
        with patch.object(di_service, '_poll_result', return_value=mock_analyze_result):
            with patch('asyncio.sleep', new_callable=AsyncMock):  # 대기 시간 모의
                result = await di_service._analyze_with_retry(b"test content", "prebuilt-layout")
                
                assert result.success == True
                assert mock_client.begin_analyze_document.call_count == 2


class TestTextExtractorServiceIntegration:
    """텍스트 추출 서비스 통합 테스트"""
    
    @pytest.fixture
    def extractor_service(self):
        """텍스트 추출 서비스 인스턴스"""
        return TextExtractorService()
    
    @pytest.mark.asyncio
    async def test_pdf_extraction_with_di_enabled(self, extractor_service):
        """DI 활성화 시 PDF 추출 테스트"""
        test_pdf_path = "test_document.pdf"
        
        # DI 성공 시나리오 모의
        mock_di_result = DocumentIntelligenceResult(
            success=True,
            text="Azure DI로 추출된 텍스트",
            metadata={'extraction_method': 'azure_document_intelligence'}
        )
        
        with patch.object(settings, 'use_azure_document_intelligence_pdf', True):
            with patch('app.services.document.extraction.azure_document_intelligence_service.azure_document_intelligence_service.analyze_pdf', 
                      return_value=mock_di_result):
                with patch('app.services.document.extraction.azure_document_intelligence_service.azure_document_intelligence_service.create_internal_extraction_result',
                          return_value={'success': True, 'text': 'Azure DI로 추출된 텍스트', 'metadata': {'extraction_method': 'azure_document_intelligence'}}):
                    with patch('os.path.exists', return_value=True):
                        with patch('os.stat', return_value=Mock(st_size=1000, st_mtime=1234567890)):
                            result = await extractor_service.extract_text(test_pdf_path, '.pdf')
                            
                            assert result['success'] == True
                            assert result['text'] == 'Azure DI로 추출된 텍스트'
                            assert result['metadata']['extraction_method'] == 'azure_document_intelligence'
    
    @pytest.mark.asyncio
    async def test_pdf_extraction_di_fallback_to_pdfplumber(self, extractor_service):
        """DI 실패 시 pdfplumber 폴백 테스트"""
        test_pdf_path = "test_document.pdf"
        
        # DI 실패 시나리오 모의
        mock_di_result = DocumentIntelligenceResult(
            success=False,
            error="DI 서비스 일시 중단"
        )
        
        with patch.object(settings, 'use_azure_document_intelligence_pdf', True):
            with patch('app.services.document.extraction.azure_document_intelligence_service.azure_document_intelligence_service.analyze_pdf',
                      return_value=mock_di_result):
                with patch.object(extractor_service, '_extract_pdf_with_pdfplumber') as mock_pdfplumber:
                    mock_pdfplumber.return_value = {
                        'success': True, 
                        'text': 'pdfplumber로 추출된 텍스트',
                        'metadata': {'extraction_method': 'pdfplumber_fallback'}
                    }
                    
                    with patch('os.path.exists', return_value=True):
                        with patch('os.stat', return_value=Mock(st_size=1000, st_mtime=1234567890)):
                            result = await extractor_service.extract_text(test_pdf_path, '.pdf')
                            
                            assert result['success'] == True
                            assert result['text'] == 'pdfplumber로 추출된 텍스트'
                            assert result['metadata']['extraction_method'] == 'pdfplumber_fallback'
                            mock_pdfplumber.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pdf_extraction_di_disabled(self, extractor_service):
        """DI 비활성화 시 직접 pdfplumber 사용 테스트"""
        test_pdf_path = "test_document.pdf"
        
        with patch.object(settings, 'use_azure_document_intelligence_pdf', False):
            with patch.object(extractor_service, '_extract_pdf_with_pdfplumber') as mock_pdfplumber:
                mock_pdfplumber.return_value = {
                    'success': True,
                    'text': 'pdfplumber로 추출된 텍스트',
                    'metadata': {'extraction_method': 'pdfplumber'}
                }
                
                with patch('os.path.exists', return_value=True):
                    with patch('os.stat', return_value=Mock(st_size=1000, st_mtime=1234567890)):
                        result = await extractor_service.extract_text(test_pdf_path, '.pdf')
                        
                        assert result['success'] == True
                        assert result['text'] == 'pdfplumber로 추출된 텍스트'
                        assert result['metadata']['extraction_method'] == 'pdfplumber'
                        mock_pdfplumber.assert_called_once()


@pytest.mark.skipif(
    not (
        os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT') and 
        os.getenv('AZURE_DOCUMENT_INTELLIGENCE_API_KEY')
    ),
    reason="Azure Document Intelligence 환경 설정이 필요합니다"
)
class TestAzureDocumentIntelligenceIntegration:
    """실제 Azure DI 서비스 통합 테스트 (환경 설정 필요)"""
    
    @pytest.mark.asyncio
    async def test_real_pdf_analysis(self):
        """실제 PDF 파일 분석 테스트"""
        # 테스트용 PDF 파일이 있는 경우에만 실행
        test_pdf = Path("test_template.pdf")
        if not test_pdf.exists():
            pytest.skip("테스트용 PDF 파일이 없습니다")
        
        di_service = AzureDocumentIntelligenceService()
        if not di_service.is_available():
            pytest.skip("Azure Document Intelligence 서비스를 사용할 수 없습니다")
        
        result = await di_service.analyze_pdf(str(test_pdf))
        
        # 기본 검증
        assert isinstance(result, DocumentIntelligenceResult)
        if result.success:
            assert len(result.text) > 0
            assert len(result.pages) > 0
            assert result.metadata['extraction_method'] == 'azure_document_intelligence'
        else:
            # 실패한 경우 오류 정보 확인
            assert result.error is not None
            print(f"DI 분석 실패: {result.error}")


if __name__ == "__main__":
    # 개별 테스트 실행
    pytest.main([__file__, "-v"])