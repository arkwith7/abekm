"""
Patent Core Interfaces - 특허 데이터 소스 추상 인터페이스

모든 특허 데이터 소스 클라이언트가 구현해야 하는 인터페이스 정의
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import (
    PatentData,
    PatentSearchQuery,
    SearchResult,
    LegalStatus,
    PatentCitation,
)


class BasePatentClient(ABC):
    """
    특허 데이터 소스 추상 클라이언트
    
    모든 특허 DB 클라이언트(KIPRIS, USPTO, EPO 등)가 구현해야 하는 인터페이스.
    새로운 데이터 소스 추가 시 이 클래스를 상속하여 구현.
    """
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """
        데이터 소스 이름
        
        Returns:
            str: 소스 이름 (예: 'KIPRIS', 'USPTO', 'EPO')
        """
        pass
    
    @property
    @abstractmethod
    def supported_jurisdictions(self) -> List[str]:
        """
        지원하는 관할권 목록
        
        Returns:
            List[str]: 관할권 코드 목록 (예: ['KR'], ['US'], ['EP', 'WO'])
        """
        pass
    
    @property
    def is_available(self) -> bool:
        """
        클라이언트 사용 가능 여부 (API 키 설정 등)
        
        Returns:
            bool: 사용 가능 여부
        """
        return True
    
    # =========================================================================
    # 검색 메서드
    # =========================================================================
    
    @abstractmethod
    async def search(self, query: PatentSearchQuery) -> SearchResult:
        """
        특허 검색
        
        Args:
            query: 검색 쿼리
            
        Returns:
            SearchResult: 검색 결과
        """
        pass
    
    async def search_by_applicant(
        self,
        applicant: str,
        max_results: int = 50,
    ) -> SearchResult:
        """
        출원인으로 검색
        
        Args:
            applicant: 출원인명
            max_results: 최대 결과 수
            
        Returns:
            SearchResult: 검색 결과
        """
        query = PatentSearchQuery(
            query="",
            applicant=applicant,
            max_results=max_results,
        )
        return await self.search(query)
    
    async def search_by_ipc(
        self,
        ipc_code: str,
        max_results: int = 50,
    ) -> SearchResult:
        """
        IPC 코드로 검색
        
        Args:
            ipc_code: IPC 분류 코드
            max_results: 최대 결과 수
            
        Returns:
            SearchResult: 검색 결과
        """
        query = PatentSearchQuery(
            query="",
            ipc_code=ipc_code,
            max_results=max_results,
        )
        return await self.search(query)
    
    # =========================================================================
    # 상세 조회 메서드
    # =========================================================================
    
    @abstractmethod
    async def get_detail(self, patent_number: str) -> Optional[PatentData]:
        """
        특허 상세 정보 조회
        
        Args:
            patent_number: 특허번호
            
        Returns:
            Optional[PatentData]: 특허 상세 정보 (없으면 None)
        """
        pass
    
    async def get_claims(self, patent_number: str) -> List[str]:
        """
        청구항 목록 조회
        
        Args:
            patent_number: 특허번호
            
        Returns:
            List[str]: 청구항 목록
        """
        detail = await self.get_detail(patent_number)
        return detail.claims if detail and detail.claims else []
    
    # =========================================================================
    # 인용 관계 메서드
    # =========================================================================
    
    @abstractmethod
    async def get_citations(self, patent_number: str) -> List[PatentCitation]:
        """
        인용 특허 조회 (이 특허가 인용한 특허들)
        
        Args:
            patent_number: 특허번호
            
        Returns:
            List[PatentCitation]: 인용 목록
        """
        pass
    
    async def get_cited_by(self, patent_number: str) -> List[PatentCitation]:
        """
        피인용 특허 조회 (이 특허를 인용한 특허들)
        
        Args:
            patent_number: 특허번호
            
        Returns:
            List[PatentCitation]: 피인용 목록
        """
        # 기본 구현: 빈 리스트 (하위 클래스에서 오버라이드)
        return []
    
    # =========================================================================
    # 법적 상태 메서드
    # =========================================================================
    
    @abstractmethod
    async def get_legal_status(self, patent_number: str) -> Optional[LegalStatus]:
        """
        법적 상태 조회
        
        Args:
            patent_number: 특허번호
            
        Returns:
            Optional[LegalStatus]: 법적 상태 정보
        """
        pass
    
    # =========================================================================
    # 패밀리 메서드
    # =========================================================================
    
    async def get_family_members(self, patent_number: str) -> List[str]:
        """
        패밀리 특허 조회
        
        Args:
            patent_number: 특허번호
            
        Returns:
            List[str]: 패밀리 특허번호 목록
        """
        detail = await self.get_detail(patent_number)
        return detail.family_members if detail and detail.family_members else []
    
    # =========================================================================
    # 유틸리티 메서드
    # =========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """
        API 상태 확인
        
        Returns:
            Dict[str, Any]: 상태 정보
        """
        return {
            "source": self.source_name,
            "available": self.is_available,
            "jurisdictions": self.supported_jurisdictions,
        }
    
    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        API 호출 제한 상태 확인
        
        Returns:
            Dict[str, Any]: 호출 제한 정보
        """
        return {
            "remaining_calls": None,
            "reset_time": None,
        }


class PatentAnalyzer(ABC):
    """
    특허 분석 추상 인터페이스
    
    특허 데이터에 대한 분석 기능을 정의.
    """
    
    @abstractmethod
    async def analyze_portfolio(
        self,
        patents: List[PatentData],
    ) -> Dict[str, Any]:
        """
        포트폴리오 분석
        
        Args:
            patents: 특허 목록
            
        Returns:
            Dict[str, Any]: 분석 결과
        """
        pass
    
    @abstractmethod
    async def compare_competitors(
        self,
        our_patents: List[PatentData],
        competitor_patents: List[PatentData],
    ) -> Dict[str, Any]:
        """
        경쟁사 비교 분석
        
        Args:
            our_patents: 우리 특허 목록
            competitor_patents: 경쟁사 특허 목록
            
        Returns:
            Dict[str, Any]: 비교 분석 결과
        """
        pass
    
    @abstractmethod
    async def extract_topics(
        self,
        patents: List[PatentData],
        num_topics: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        기술 토픽 추출
        
        Args:
            patents: 특허 목록
            num_topics: 추출할 토픽 수
            
        Returns:
            List[Dict[str, Any]]: 토픽 목록
        """
        pass


class PriorArtSearcher(ABC):
    """
    선행기술 조사 추상 인터페이스
    
    선행기술 조사 특화 기능을 정의.
    """
    
    @abstractmethod
    async def search_prior_art(
        self,
        claims: List[str],
        title: str,
        abstract: str,
        jurisdictions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        선행기술 검색
        
        Args:
            claims: 청구항 목록
            title: 발명의 명칭
            abstract: 초록
            jurisdictions: 검색 관할권 (None이면 전체)
            
        Returns:
            Dict[str, Any]: 선행기술 검색 결과
        """
        pass
    
    @abstractmethod
    async def screen_novelty(
        self,
        target_patent: PatentData,
        prior_art_candidates: List[PatentData],
    ) -> Dict[str, Any]:
        """
        신규성 스크리닝
        
        Args:
            target_patent: 대상 특허
            prior_art_candidates: 선행기술 후보 목록
            
        Returns:
            Dict[str, Any]: 스크리닝 결과
        """
        pass
    
    @abstractmethod
    async def compare_claims(
        self,
        target_claims: List[str],
        prior_art_claims: List[str],
    ) -> Dict[str, Any]:
        """
        청구항 대비 분석
        
        Args:
            target_claims: 대상 청구항
            prior_art_claims: 선행기술 청구항
            
        Returns:
            Dict[str, Any]: 대비 분석 결과
        """
        pass
