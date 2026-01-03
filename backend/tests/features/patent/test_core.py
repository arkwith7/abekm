"""
Patent Core 모듈 테스트

models, interfaces, utils 테스트
"""
import pytest
from datetime import datetime, date

from app.agents.features.patent.core import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    AggregatedSearchResult,
    PatentJurisdiction,
    PatentStatus,
    PatentCitation,
    LegalStatus,
)
from app.agents.features.patent.core.utils import (
    parse_ipc_code,
    normalize_patent_number,
    parse_patent_date,
    clean_text,
    extract_keywords,
)


class TestPatentModels:
    """특허 모델 테스트"""
    
    def test_patent_data_creation(self):
        """PatentData 생성 테스트"""
        patent = PatentData(
            patent_number="10-2023-0123456",
            title="인공지능 기반 반도체 설계 방법",
            applicant="삼성전자",
            jurisdiction=PatentJurisdiction.KR,
        )
        
        assert patent.patent_number == "10-2023-0123456"
        assert patent.title == "인공지능 기반 반도체 설계 방법"
        assert patent.applicant == "삼성전자"
        assert patent.jurisdiction == PatentJurisdiction.KR
        assert patent.status == PatentStatus.APPLICATION  # 기본값
    
    def test_patent_data_with_full_fields(self):
        """PatentData 전체 필드 테스트"""
        patent = PatentData(
            patent_number="US11734097B1",
            title="Battery Management System",
            abstract="A system for managing battery cells...",
            applicant="Tesla, Inc.",
            inventors=["Elon Musk", "John Doe"],
            ipc_codes=["H01M10/42", "H02J7/00"],
            application_date="2023-01-15",
            publication_date="2023-07-20",
            grant_date="2024-01-10",
            status=PatentStatus.GRANTED,
            claims_count=20,
            jurisdiction=PatentJurisdiction.US,
            relevance_score=0.95,
        )
        
        assert patent.status == PatentStatus.GRANTED
        assert len(patent.inventors) == 2
        assert len(patent.ipc_codes) == 2
        assert patent.relevance_score == 0.95
    
    def test_patent_search_query(self):
        """PatentSearchQuery 생성 테스트 - query 필드 사용"""
        query = PatentSearchQuery(
            query="배터리 관리 시스템",
            applicant="삼성전자",
            ipc_code="H01M",
            jurisdictions=[PatentJurisdiction.KR, PatentJurisdiction.US],
            max_results=100,
        )
        
        assert "배터리" in query.query
        assert query.applicant == "삼성전자"
        assert PatentJurisdiction.KR in query.jurisdictions
    
    def test_search_result(self):
        """SearchResult 생성 테스트"""
        patents = [
            PatentData(
                patent_number="10-2023-0001",
                title="테스트 특허 1",
                applicant="테스트 회사",
            ),
            PatentData(
                patent_number="10-2023-0002",
                title="테스트 특허 2",
                applicant="테스트 회사",
            ),
        ]
        
        result = SearchResult(
            patents=patents,
            total_count=2,
            source="kipris",
        )
        
        assert len(result.patents) == 2
        assert result.total_count == 2
        assert result.source == "kipris"
    
    def test_patent_citation(self):
        """PatentCitation 테스트 - citing/cited 필드 사용"""
        citation = PatentCitation(
            citing_patent="US10000001",
            cited_patent="US9999999",
            citation_type="patent",
            citation_category="X",
            cited_by_examiner=True,
        )
        
        assert citation.citing_patent == "US10000001"
        assert citation.cited_patent == "US9999999"
        assert citation.citation_category == "X"
    
    def test_legal_status(self):
        """LegalStatus 테스트 - current_status 필드 사용"""
        status = LegalStatus(
            patent_number="10-2023-0001",
            current_status=PatentStatus.GRANTED,
            status_date="2024-01-01",
            remaining_term=15,
        )
        
        assert status.remaining_term == 15
        assert status.current_status == PatentStatus.GRANTED


class TestPatentUtils:
    """특허 유틸리티 테스트"""
    
    def test_parse_ipc_code_valid(self):
        """IPC 코드 파싱 - 유효한 코드"""
        result = parse_ipc_code("H01M10/42")
        
        assert result is not None
        assert result["section"] == "H"
        assert result["class"] == "01"
        assert result["subclass"] == "M"
    
    def test_parse_ipc_code_short(self):
        """IPC 코드 파싱 - 짧은 코드"""
        result = parse_ipc_code("H01")
        
        assert result is not None
        assert result["section"] == "H"
        assert result["class"] == "01"
    
    def test_parse_ipc_code_invalid(self):
        """IPC 코드 파싱 - 무효한 코드는 빈 값의 dict 반환"""
        result = parse_ipc_code("")
        # 빈 문자열은 빈 값의 dict 반환
        assert result["section"] == ""
        assert result["class"] == ""
        assert result["full"] == ""
        
        result = parse_ipc_code("X")
        # 유효하지 않은 코드도 빈 값의 dict 반환
        assert result["section"] == ""
        assert "full" in result
    
    def test_normalize_patent_number(self):
        """특허번호 정규화 - 공백과 하이픈 제거"""
        # 한국 특허 - 하이픈 제거
        assert normalize_patent_number("10-2023-0123456") == "1020230123456"
        
        # 미국 특허 - 공백 제거, 콤마는 유지될 수 있음
        result = normalize_patent_number("US 11,734,097 B1")
        assert " " not in result
        
        # 공백/하이픈 제거
        assert normalize_patent_number("US-11-734-097") == "US11734097"
    
    def test_parse_patent_date(self):
        """특허 날짜 파싱 - date 객체 또는 문자열 반환"""
        # YYYYMMDD 형식 -> date 객체
        result = parse_patent_date("20230115")
        # 결과가 date 객체이거나 "2023-01-15" 문자열
        assert result == date(2023, 1, 15) or result == "2023-01-15"
        
        # YYYY-MM-DD 형식
        result = parse_patent_date("2023-01-15")
        assert result == date(2023, 1, 15) or result == "2023-01-15"
        
        # 빈 문자열
        result = parse_patent_date("")
        assert result is None
    
    def test_clean_text(self):
        """텍스트 정제"""
        # 연속 공백 제거
        result = clean_text("테스트   텍스트  입니다")
        assert result == "테스트 텍스트 입니다"
        
        # 앞뒤 공백 제거
        result = clean_text("  테스트  ")
        assert result == "테스트"
    
    def test_extract_keywords(self):
        """키워드 추출"""
        text = "인공지능 기반 배터리 관리 시스템 및 그 방법"
        keywords = extract_keywords(text, max_keywords=5)
        
        assert len(keywords) <= 5
        assert isinstance(keywords, list)
        # 불용어 제거 확인 (및, 그 등)
        assert "및" not in keywords
        assert "그" not in keywords


class TestPatentJurisdiction:
    """관할권 Enum 테스트"""
    
    def test_jurisdiction_values(self):
        """관할권 값 테스트"""
        assert PatentJurisdiction.KR.value == "KR"
        assert PatentJurisdiction.US.value == "US"
        assert PatentJurisdiction.EP.value == "EP"
        assert PatentJurisdiction.WO.value == "WO"
        assert PatentJurisdiction.JP.value == "JP"
        assert PatentJurisdiction.CN.value == "CN"
    
    def test_jurisdiction_from_string(self):
        """문자열에서 관할권 생성"""
        assert PatentJurisdiction("KR") == PatentJurisdiction.KR
        assert PatentJurisdiction("US") == PatentJurisdiction.US


class TestPatentStatus:
    """특허 상태 Enum 테스트"""
    
    def test_status_values(self):
        """상태 값 테스트"""
        assert PatentStatus.APPLICATION.value == "application"
        assert PatentStatus.PUBLISHED.value == "published"
        assert PatentStatus.GRANTED.value == "granted"
        assert PatentStatus.EXPIRED.value == "expired"
        assert PatentStatus.WITHDRAWN.value == "withdrawn"
