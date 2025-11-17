"""
질문 유형 분류 서비스
사용자 질문이 문서 검색이 필요한지, 일반 대화인지 분류
"""

import logging
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.services.core.korean_nlp_service import korean_nlp_service

logger = logging.getLogger(__name__)

@dataclass
class QueryClassification:
    """질문 분류 결과"""
    query_type: str  # "document_search", "general_chat", "greeting", "system_inquiry", "summarization", "comparison"
    confidence: float  # 0.0 ~ 1.0
    reasoning: str
    needs_rag: bool
    suggested_response_type: str

class QueryClassificationService:
    """질문 유형 분류 서비스"""
    
    def __init__(self):
        # 인사말 패턴
        self.greeting_patterns = [
            r'안녕[하세요]*',
            r'반갑[습니다]*',
            r'안녕하세요',
            r'처음[이에요]*',
            r'시작[해요합니다]*',
            r'새로운?\s*대화',
            r'어서오세요',
            r'만나서\s*반갑',
            r'좋은\s*[아침점심저녁하루]',
            r'잘\s*부탁'
        ]
        
        # 일반 대화 패턴
        self.general_chat_patterns = [
            r'어떻게\s*지내[세요]*',
            r'오늘\s*날씨',
            r'기분[이좋은나쁜어떤]*',
            r'[뭔뭐무엇].*[하고있어요하고있나요하세요하십니까]',
            r'고마워[요]*',
            r'감사[합니다해요]',
            r'수고[하세요했어요]',
            r'[정말진짜].*[좋아요멋져요대단해요]',
            r'도움[이되었어요주셔서]',
            r'잘했[어요습니다네요]',
            r'^네[,.]?$',
            r'^아[,.]?$', 
            r'^응[,.]?$',
            r'^그래[요]?[,.]?$',
            r'^알겠[어요습니다][,.]?$',
            r'^좋[아요습니다][,.]?$',
            r'^오케이?[,.]?$',
            r'^[OoKk]+[,.]?$'
        ]
        
        # 시스템 문의 패턴 (더 구체적으로 변경하여 오탐 감소)
        self.system_inquiry_patterns = [
            r'무슨\s*일[을\s*]*할\s*수\s*있[어요니닝가요]',
            r'어떤\s*기능',
            r'기능\s*설명',
            r'사용법|사용방법',
            r'도움말',
            r'너는\s*누구',
            r'넌\s*누구',
            r'무엇을\s*도와줄\s*수',
            r'너의\s*기능'
        ]
        
        # 문서 검색 키워드
        self.document_search_keywords = [
            '문서', '파일', '자료', '보고서', '제안서', '계획서', '매뉴얼', '가이드',
            '프로젝트', '업무', '회사', '부서', '팀', '조직',
            '정책', '규정', '지침', '절차', '프로세스',
            '시스템', '서비스', '솔루션', '아키텍처',
            '분석', '현황', '실적', '성과', '결과',
            '일정', '계획', '목표', '전략', '방향',
            '예산', '비용', '투자', '수익',
            '기술', '개발', '구축', '운영', '관리',
            '고객', '사용자', '이용자', '클라이언트'
        ]
        
        # 요약 요청 패턴
        self.summarization_patterns = [
            r'요약[해줘해주세요해봐해보세요해달라해줄래요]',
            r'정리[해줘해주세요해봐해보세요해달라해줄래요]',
            r'요점[만을]*\s*[말해알려]',
            r'핵심[만을]*\s*[말해알려정리요약]',
            r'간단[히하게]*\s*[설명말해알려요약정리]',
            r'[내용을]\s*요약',
            r'[내용을]\s*정리',
            r'[주요중요핵심]\s*내용',
            r'개요[를]?\s*[알려말해]',
            r'[전체내용]\s*[설명요약정리]',
            r'[뭔뭘무엇]\s*담고있[어는]',
            r'[뭐무엇]에\s*대한\s*[문서논문자료]',
        ]
        
        # 비교 요청 패턴
        self.comparison_patterns = [
            r'비교[해줘해주세요해봐해보세요]',
            r'차이[점은가]',
            r'[뭐무엇]가\s*다른[가지]',
            r'어떻게\s*다른[가지]',
            r'[와과]\s*[비교대조]',
            r'공통점[과]?\s*차이점',
            r'유사점[과]?\s*차이점',
        ]
    
    async def classify_query(self, query: str) -> QueryClassification:
        """
        사용자 질문 분류
        
        Args:
            query: 사용자 질문
            
        Returns:
            QueryClassification: 분류 결과
        """
        try:
            query = query.strip()
            
            # 1. 빈 질문 처리
            if not query or len(query) < 2:
                return QueryClassification(
                    query_type="general_chat",
                    confidence=1.0,
                    reasoning="빈 질문",
                    needs_rag=False,
                    suggested_response_type="simple_greeting"
                )
            
            # 2. 인사말 검사 (임계값 낮춤)
            greeting_result = self._check_greeting(query)
            if greeting_result.confidence >= 0.5:  # 0.7 → 0.5로 낮춤
                return greeting_result
            
            # 3. 일반 대화 검사 (임계값 낮춤)
            general_chat_result = self._check_general_chat(query)
            if general_chat_result.confidence > 0.4:  # 0.6 → 0.4로 낮춤
                return general_chat_result
            
            # 4. 시스템 문의 검사 (임계값 낮춤)
            system_inquiry_result = self._check_system_inquiry(query)
            if system_inquiry_result.confidence > 0.4:  # 0.6 → 0.4로 낮춤
                return system_inquiry_result
            
            # 5. 요약 요청 검사 (우선순위 높음)
            summarization_result = self._check_summarization_request(query)
            if summarization_result.confidence > 0.6:
                return summarization_result
            
            # 6. 비교 요청 검사
            comparison_result = self._check_comparison_request(query)
            if comparison_result.confidence > 0.6:
                return comparison_result
            
            # 7. 문서 검색 필요성 검사
            document_search_result = await self._check_document_search_need(query)
            if document_search_result.confidence > 0.4:
                return document_search_result
            
            # 6. 기본값: 문서 검색 (확신이 없는 경우)
            return QueryClassification(
                query_type="document_search",
                confidence=0.3,
                reasoning="명확하지 않은 질문이므로 문서 검색 시도",
                needs_rag=True,
                suggested_response_type="rag_search"
            )
            
        except Exception as e:
            logger.error(f"❌ 질문 분류 실패: {e}")
            # 오류 시 안전하게 일반 대화로 분류
            return QueryClassification(
                query_type="general_chat",
                confidence=0.5,
                reasoning=f"분류 오류: {str(e)}",
                needs_rag=False,
                suggested_response_type="general_response"
            )
    
    def _check_greeting(self, query: str) -> QueryClassification:
        """인사말 검사"""
        score = 0.0
        matched_patterns = []
        
        for pattern in self.greeting_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                score += 0.4
                matched_patterns.append(pattern)
        
        # 짧은 문장일수록 인사말 가능성 증가
        if len(query) <= 10:
            score += 0.3
        elif len(query) <= 20:
            score += 0.1
        
        # 특정 키워드가 있으면 인사말 가능성 감소
        business_keywords = ['문서', '자료', '프로젝트', '업무', '회사']
        for keyword in business_keywords:
            if keyword in query:
                score -= 0.2
        
        return QueryClassification(
            query_type="greeting",
            confidence=min(score, 1.0),
            reasoning=f"인사말 패턴 매칭: {matched_patterns}",
            needs_rag=False,
            suggested_response_type="friendly_greeting"
        )
    
    def _check_general_chat(self, query: str) -> QueryClassification:
        """일반 대화 검사"""
        score = 0.0
        matched_patterns = []
        
        for pattern in self.general_chat_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                score += 0.3
                matched_patterns.append(pattern)
        
        # 감사 표현
        gratitude_words = ['고마워', '감사', '수고', '잘했', '좋아', '훌륭', '멋져', '대단']
        for word in gratitude_words:
            if word in query:
                score += 0.2
                break
        
        return QueryClassification(
            query_type="general_chat",
            confidence=min(score, 1.0),
            reasoning=f"일반 대화 패턴 매칭: {matched_patterns}",
            needs_rag=False,
            suggested_response_type="conversational_response"
        )
    
    def _check_system_inquiry(self, query: str) -> QueryClassification:
        """시스템 문의 검사"""
        score = 0.0
        matched_patterns = []
        
        for pattern in self.system_inquiry_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                score += 0.4
                matched_patterns.append(pattern)
        
        # 시스템 관련 키워드
        system_keywords = ['기능', '사용법', '도움', '도와', '어떻게', '뭐', '무엇']
        for keyword in system_keywords:
            if keyword in query:
                score += 0.1
        
        return QueryClassification(
            query_type="system_inquiry",
            confidence=min(score, 1.0),
            reasoning=f"시스템 문의 패턴 매칭: {matched_patterns}",
            needs_rag=False,
            suggested_response_type="system_guide"
        )
    
    async def _check_document_search_need(self, query: str) -> QueryClassification:
        """문서 검색 필요성 검사"""
        score = 0.0
        found_keywords = []
        
        # 비즈니스 키워드 검사
        for keyword in self.document_search_keywords:
            if keyword in query:
                score += 0.2
                found_keywords.append(keyword)
        
        # NLP 분석으로 키워드 추출
        try:
            analysis = await korean_nlp_service.analyze_korean_text(query)
            extracted_keywords = analysis.get("keywords", [])
            
            # 추출된 키워드가 비즈니스 용어인지 확인
            business_keyword_count = 0
            for keyword in extracted_keywords:
                if len(keyword) > 2 and any(biz_word in keyword for biz_word in self.document_search_keywords):
                    business_keyword_count += 1
            
            if business_keyword_count > 0:
                score += 0.3 * business_keyword_count
                
        except Exception as e:
            logger.warning(f"NLP 분석 실패: {e}")
        
        # 질문 형태 분석
        question_words = ['무엇', '뭐', '어떻게', '어떤', '언제', '어디서', '왜', '누가', '얼마']
        for word in question_words:
            if word in query:
                score += 0.1
                break
        
        # 긴 문장일수록 문서 검색 가능성 증가
        if len(query) > 30:
            score += 0.2
        elif len(query) > 15:
            score += 0.1
        
        return QueryClassification(
            query_type="document_search",
            confidence=min(score, 1.0),
            reasoning=f"비즈니스 키워드 발견: {found_keywords}",
            needs_rag=score > 0.4,
            suggested_response_type="rag_search"
        )
    
    def _check_summarization_request(self, query: str) -> QueryClassification:
        """요약 요청 검사"""
        score = 0.0
        matched_patterns = []
        
        for pattern in self.summarization_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                score += 0.4
                matched_patterns.append(pattern)
        
        # 요약 관련 키워드
        summarization_keywords = ['요약', '정리', '요점', '핵심', '간단', '개요', '주요']
        for keyword in summarization_keywords:
            if keyword in query:
                score += 0.2
        
        # 문서 선택 맥락 (첨부, 선택, 위 등)
        context_words = ['첨부', '선택', '위', '아래', '이', '해당', '문서', '논문']
        context_count = sum(1 for word in context_words if word in query)
        if context_count > 0:
            score += 0.2 * min(context_count, 2)  # 최대 0.4
        
        return QueryClassification(
            query_type="summarization",
            confidence=min(score, 1.0),
            reasoning=f"요약 요청 패턴 매칭: {matched_patterns}",
            needs_rag=True,  # 문서 로드 필요
            suggested_response_type="document_summarization"
        )
    
    def _check_comparison_request(self, query: str) -> QueryClassification:
        """비교 요청 검사"""
        score = 0.0
        matched_patterns = []
        
        for pattern in self.comparison_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                score += 0.5
                matched_patterns.append(pattern)
        
        # 비교 관련 키워드
        comparison_keywords = ['비교', '차이', '다른', '유사', '공통', '대조']
        for keyword in comparison_keywords:
            if keyword in query:
                score += 0.2
        
        return QueryClassification(
            query_type="comparison",
            confidence=min(score, 1.0),
            reasoning=f"비교 요청 패턴 매칭: {matched_patterns}",
            needs_rag=True,
            suggested_response_type="comparative_analysis"
        )

# 전역 인스턴스
query_classification_service = QueryClassificationService()
