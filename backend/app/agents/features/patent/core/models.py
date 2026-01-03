"""
Patent Core Models - 특허 공통 데이터 모델

모든 특허 관련 에이전트와 도구가 공유하는 데이터 구조 정의
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class PatentJurisdiction(str, Enum):
    """특허 관할권"""
    KR = "KR"      # 한국 (KIPRIS)
    US = "US"      # 미국 (USPTO)
    EP = "EP"      # 유럽 (EPO)
    WO = "WO"      # 국제 (WIPO PCT)
    CN = "CN"      # 중국 (CNIPA)
    JP = "JP"      # 일본 (JPO)
    ALL = "ALL"    # 모든 관할권


class PatentStatus(str, Enum):
    """특허 상태"""
    APPLICATION = "application"    # 출원
    PUBLISHED = "published"        # 공개
    GRANTED = "granted"           # 등록
    EXPIRED = "expired"           # 만료
    WITHDRAWN = "withdrawn"       # 취하
    REJECTED = "rejected"         # 거절
    ABANDONED = "abandoned"       # 포기


class PatentDocumentType(str, Enum):
    """특허 문서 유형"""
    APPLICATION = "application"    # 출원서
    PUBLICATION = "publication"    # 공개공보
    GRANT = "grant"               # 등록공보
    AMENDMENT = "amendment"       # 보정서


# =============================================================================
# Core Data Models
# =============================================================================

class PatentData(BaseModel):
    """특허 데이터 모델 (통합)"""
    
    # 기본 식별 정보
    patent_number: str = Field(description="특허번호 (출원번호/등록번호)")
    title: str = Field(description="발명의 명칭")
    abstract: str = Field(default="", description="초록")
    
    # 당사자 정보
    applicant: str = Field(description="출원인")
    applicants: List[str] = Field(default_factory=list, description="출원인 목록 (공동 출원)")
    inventors: List[str] = Field(default_factory=list, description="발명자 목록")
    assignee: Optional[str] = Field(default=None, description="양수인/권리자")
    
    # 분류 정보
    ipc_codes: List[str] = Field(default_factory=list, description="IPC 분류 코드")
    cpc_codes: List[str] = Field(default_factory=list, description="CPC 분류 코드")
    
    # 날짜 정보
    application_date: Optional[str] = Field(default=None, description="출원일 (YYYY-MM-DD)")
    publication_date: Optional[str] = Field(default=None, description="공개일")
    grant_date: Optional[str] = Field(default=None, description="등록일")
    priority_date: Optional[str] = Field(default=None, description="우선일")
    expiration_date: Optional[str] = Field(default=None, description="만료일")
    
    # 상태 정보
    status: PatentStatus = Field(default=PatentStatus.APPLICATION, description="특허 상태")
    jurisdiction: PatentJurisdiction = Field(default=PatentJurisdiction.KR, description="관할권")
    
    # 청구항 정보
    claims_count: Optional[int] = Field(default=None, description="청구항 수")
    claims: Optional[List[str]] = Field(default=None, description="청구항 목록")
    independent_claims: Optional[List[int]] = Field(default=None, description="독립항 번호 목록")
    
    # 인용 정보
    citations: Optional[List[str]] = Field(default=None, description="인용 특허 번호")
    cited_by: Optional[List[str]] = Field(default=None, description="피인용 특허 번호")
    cited_by_count: Optional[int] = Field(default=None, description="피인용 횟수")
    
    # 패밀리 정보
    family_id: Optional[str] = Field(default=None, description="패밀리 ID")
    family_members: Optional[List[str]] = Field(default=None, description="패밀리 특허 번호")
    
    # 링크
    url: Optional[str] = Field(default=None, description="특허 상세 URL")
    pdf_url: Optional[str] = Field(default=None, description="PDF 다운로드 URL")
    
    # 메타데이터
    source: Optional[str] = Field(default=None, description="데이터 소스 (KIPRIS, USPTO 등)")
    relevance_score: float = Field(default=0.0, description="검색 관련성 점수")
    retrieved_at: Optional[datetime] = Field(default=None, description="조회 시각")
    
    class Config:
        json_schema_extra = {
            "example": {
                "patent_number": "10-2023-0123456",
                "title": "인공지능 기반 반도체 설계 방법",
                "applicant": "삼성전자",
                "jurisdiction": "KR",
                "status": "granted",
            }
        }


class PatentCitation(BaseModel):
    """특허 인용 정보"""
    citing_patent: str = Field(description="인용 특허 번호")
    cited_patent: str = Field(description="피인용 특허 번호")
    citation_type: str = Field(default="patent", description="인용 유형 (patent/npl)")
    citation_category: Optional[str] = Field(default=None, description="인용 카테고리 (X/Y/A 등)")
    cited_by_examiner: bool = Field(default=False, description="심사관 인용 여부")


class LegalStatus(BaseModel):
    """법적 상태 정보"""
    patent_number: str = Field(description="특허번호")
    current_status: PatentStatus = Field(description="현재 상태")
    status_date: Optional[str] = Field(default=None, description="상태 변경일")
    next_fee_date: Optional[str] = Field(default=None, description="다음 연차료 납부일")
    remaining_term: Optional[int] = Field(default=None, description="잔여 존속기간 (년)")
    
    # 이력
    status_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="상태 변경 이력"
    )
    
    # 권리 관계
    assignments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="권리 이전 이력"
    )
    licenses: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="실시권 설정 정보"
    )


# =============================================================================
# Search Models
# =============================================================================

class PatentSearchQuery(BaseModel):
    """특허 검색 쿼리"""
    
    # 기본 검색
    query: str = Field(description="검색 키워드")
    search_fields: List[str] = Field(
        default=["title", "abstract", "claims"],
        description="검색 대상 필드"
    )
    
    # 필터
    applicant: Optional[str] = Field(default=None, description="출원인")
    inventor: Optional[str] = Field(default=None, description="발명자")
    ipc_code: Optional[str] = Field(default=None, description="IPC 분류 코드")
    
    # 날짜 범위
    date_from: Optional[str] = Field(default=None, description="시작일 (YYYY-MM-DD)")
    date_to: Optional[str] = Field(default=None, description="종료일 (YYYY-MM-DD)")
    date_field: str = Field(default="application", description="날짜 기준 필드")
    
    # 관할권
    jurisdictions: List[PatentJurisdiction] = Field(
        default=[PatentJurisdiction.KR],
        description="검색 관할권"
    )
    
    # 페이징
    max_results: int = Field(default=50, ge=1, le=500, description="최대 결과 수")
    offset: int = Field(default=0, ge=0, description="시작 위치")
    
    # 정렬
    sort_by: str = Field(default="relevance", description="정렬 기준")
    sort_order: str = Field(default="desc", description="정렬 방향")


class SearchResult(BaseModel):
    """검색 결과"""
    patents: List[PatentData] = Field(default_factory=list, description="검색된 특허 목록")
    total_count: int = Field(default=0, description="총 결과 수")
    returned_count: int = Field(default=0, description="반환된 결과 수")
    query: Optional[PatentSearchQuery] = Field(default=None, description="검색 쿼리")
    source: Optional[str] = Field(default=None, description="데이터 소스")
    search_time_ms: float = Field(default=0.0, description="검색 소요 시간 (ms)")


class AggregatedSearchResult(BaseModel):
    """다중 소스 통합 검색 결과"""
    patents: List[PatentData] = Field(default_factory=list, description="통합 특허 목록")
    total_count: int = Field(default=0, description="총 결과 수 (중복 제거 전)")
    unique_count: int = Field(default=0, description="고유 결과 수 (중복 제거 후)")
    
    # 소스별 결과
    source_results: Dict[str, SearchResult] = Field(
        default_factory=dict,
        description="소스별 검색 결과"
    )
    
    # 메타데이터
    search_time_ms: float = Field(default=0.0, description="총 검색 소요 시간")
    sources_queried: List[str] = Field(default_factory=list, description="조회한 소스 목록")
    sources_failed: List[str] = Field(default_factory=list, description="실패한 소스 목록")


# =============================================================================
# Analysis Models
# =============================================================================

class TechnologyTopic(BaseModel):
    """기술 토픽"""
    name: str = Field(description="토픽 이름")
    keywords: List[str] = Field(default_factory=list, description="관련 키워드")
    ipc_codes: List[str] = Field(default_factory=list, description="관련 IPC 코드")
    patent_count: int = Field(default=0, description="관련 특허 수")
    trend: str = Field(default="stable", description="트렌드 (growing/stable/declining)")


class CompetitorMetrics(BaseModel):
    """경쟁사 지표"""
    name: str = Field(description="회사명")
    total_patents: int = Field(default=0, description="총 특허 수")
    granted_patents: int = Field(default=0, description="등록 특허 수")
    pending_patents: int = Field(default=0, description="출원 중 특허 수")
    avg_citations: float = Field(default=0.0, description="평균 피인용 수")
    top_ipc_codes: List[str] = Field(default_factory=list, description="주요 IPC 코드")
    key_technologies: List[str] = Field(default_factory=list, description="핵심 기술")
    recent_growth_rate: float = Field(default=0.0, description="최근 성장률 (%)")


class PriorArtCandidate(BaseModel):
    """선행기술 후보"""
    patent: PatentData = Field(description="특허 데이터")
    relevance_score: float = Field(default=0.0, description="관련성 점수")
    novelty_impact: str = Field(default="low", description="신규성 영향 (high/medium/low)")
    matching_claims: List[int] = Field(default_factory=list, description="관련 청구항 번호")
    analysis_notes: Optional[str] = Field(default=None, description="분석 메모")


class PriorArtSearchResult(BaseModel):
    """선행기술 조사 결과"""
    candidates: List[PriorArtCandidate] = Field(
        default_factory=list,
        description="선행기술 후보 목록"
    )
    x_references: List[PriorArtCandidate] = Field(
        default_factory=list,
        description="X 인용 (신규성 영향 높음)"
    )
    y_references: List[PriorArtCandidate] = Field(
        default_factory=list,
        description="Y 인용 (진보성 영향)"
    )
    a_references: List[PriorArtCandidate] = Field(
        default_factory=list,
        description="A 인용 (기술 배경)"
    )
    search_strategy: Optional[str] = Field(default=None, description="검색 전략")
    coverage_assessment: Optional[str] = Field(default=None, description="커버리지 평가")
