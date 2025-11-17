"""
자연어 쿼리 처리 서비스
사용자의 자연어 검색 쿼리를 의미있는 검색 키워드로 변환
"""
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class QueryComponents:
    """쿼리 분석 결과"""
    original_query: str
    main_keywords: List[str]
    context_keywords: List[str]
    intent: str
    search_operators: List[str]
    excluded_terms: List[str]

class NaturalLanguageQueryProcessor:
    """자연어 쿼리 분석 및 변환 서비스"""
    
    def __init__(self):
        # 한국어 불용어 (검색에서 제외할 단어들)
        self.stopwords = {
            '을', '를', '이', '가', '은', '는', '의', '에', '에서', '와', '과', '으로', '로',
            '에게', '께', '부터', '까지', '처럼', '같이', '보다', '만', '도', '라도', '조차',
            '마저', '밖에', '뿐', '하고', '그리고', '또는', '혹은', '아니면', '그러나',
            '하지만', '그런데', '따라서', '그래서', '왜냐하면', '때문에', '위해', '위한',
            '관련', '대한', '에서의', '에의', '에도', '에게도', '에서도', '도록', '되도록',
            '같은', '다른', '새로운', '기존', '현재', '이번', '다음', '지난', '최근',
            '문서', '자료', '파일', '정보', '내용', '데이터', '찾아줘', '찾아', '검색',
            '보여줘', '알려줘', '가져와', '확인', '조회', '찾기', '있는', '없는', '되는',
            '안되는', '할', '수', '있는', '있어', '있다', '한다', '된다', '이다', '아니다'
        }
        
        # 검색 의도 패턴 (정규표현식)
        self.intent_patterns = {
            'find_document': [
                r'.*찾아.*',
                r'.*검색.*',
                r'.*조회.*',
                r'.*확인.*',
                r'.*보여.*',
                r'.*알려.*',
                r'.*가져.*'
            ],
            'comparison': [
                r'.*비교.*',
                r'.*차이.*',
                r'.*vs.*',
                r'.*대비.*'
            ],
            'analysis': [
                r'.*분석.*',
                r'.*평가.*',
                r'.*검토.*',
                r'.*연구.*'
            ],
            'procedure': [
                r'.*절차.*',
                r'.*과정.*',
                r'.*방법.*',
                r'.*단계.*',
                r'.*프로세스.*'
            ],
            'policy': [
                r'.*정책.*',
                r'.*규정.*',
                r'.*지침.*',
                r'.*가이드.*',
                r'.*매뉴얼.*'
            ]
        }
        
        # 기술/산업 도메인 키워드 (가중치 높음)
        self.domain_keywords = {
            'manufacturing': ['제조', '생산', '공장', '현장', '공정', '품질'],
            'automation': ['자동화', '로봇', '시스템', '설비', 'AI', '인공지능'],
            'management': ['관리', '운영', '계획', '전략', '정책', '프로세스'],
            'technology': ['기술', '개발', '연구', '혁신', '디지털', 'IT'],
            'finance': ['재무', '회계', '예산', '비용', '투자', '수익'],
            'hr': ['인사', '교육', '훈련', '평가', '복리후생', '급여'],
            'safety': ['안전', '보안', '위험', '관리', '점검', '규정'],
            'quality': ['품질', '검사', '시험', '인증', '표준', '규격']
        }
        
        # 동의어 매핑 (검색 확장용)
        self.synonyms = {
            '로봇': ['robot', 'robotic', '자동화', 'automation'],
            '제조': ['manufacturing', '생산', 'production', '공장'],
            '현장': ['site', 'field', '작업장', 'workplace'],
            '도입': ['도입', '적용', '설치', '구축', 'implementation'],
            '관리': ['management', '운영', 'operation', '제어'],
            '시스템': ['system', 'solution', '솔루션', '체계'],
            '문서': ['document', 'doc', '자료', 'material', '파일'],
            '교육': ['training', '훈련', 'education', '학습'],
            '평가': ['evaluation', 'assessment', '검토', 'review'],
            '정책': ['policy', '지침', 'guideline', '규정']
        }
    
    async def process_query(self, query: str) -> QueryComponents:
        """자연어 쿼리를 분석하여 검색 가능한 형태로 변환"""
        try:
            # 1. 기본 전처리
            normalized_query = self._normalize_query(query)
            
            # 2. 핵심 키워드 추출
            main_keywords = self._extract_main_keywords(normalized_query)
            
            # 3. 컨텍스트 키워드 추출 (도메인 관련)
            context_keywords = self._extract_context_keywords(normalized_query)
            
            # 4. 검색 의도 파악
            intent = self._detect_intent(normalized_query)
            
            # 5. 검색 연산자 생성
            search_operators = self._generate_search_operators(main_keywords, context_keywords)
            
            # 6. 제외할 용어 식별
            excluded_terms = self._identify_excluded_terms(normalized_query)
            
            return QueryComponents(
                original_query=query,
                main_keywords=main_keywords,
                context_keywords=context_keywords,
                intent=intent,
                search_operators=search_operators,
                excluded_terms=excluded_terms
            )
            
        except Exception as e:
            logger.error(f"쿼리 처리 실패: {str(e)}")
            # 실패 시 기본 키워드만 반환
            simple_keywords = query.replace('찾아줘', '').replace('검색', '').strip().split()
            return QueryComponents(
                original_query=query,
                main_keywords=simple_keywords,
                context_keywords=[],
                intent='find_document',
                search_operators=simple_keywords,
                excluded_terms=[]
            )
    
    def _normalize_query(self, query: str) -> str:
        """쿼리 정규화"""
        # 공백 정리
        normalized = re.sub(r'\s+', ' ', query.strip())
        
        # 특수문자 정리 (일부만)
        normalized = re.sub(r'[^\w\s가-힣]', ' ', normalized)
        
        return normalized.lower()
    
    def _extract_main_keywords(self, query: str) -> List[str]:
        """핵심 키워드 추출"""
        words = query.split()
        
        # 불용어 제거
        keywords = [word for word in words if word not in self.stopwords and len(word) > 1]
        
        # 도메인 키워드 우선순위
        prioritized_keywords = []
        regular_keywords = []
        
        for keyword in keywords:
            is_domain_keyword = False
            for domain, domain_words in self.domain_keywords.items():
                if keyword in domain_words:
                    prioritized_keywords.append(keyword)
                    is_domain_keyword = True
                    break
            
            if not is_domain_keyword:
                regular_keywords.append(keyword)
        
        # 우선순위 키워드를 앞에 배치
        return prioritized_keywords + regular_keywords[:5]  # 최대 8개까지
    
    def _extract_context_keywords(self, query: str) -> List[str]:
        """컨텍스트 키워드 추출 (도메인별)"""
        context_keywords = []
        
        for domain, keywords in self.domain_keywords.items():
            for keyword in keywords:
                if keyword in query:
                    # 동의어도 포함
                    if keyword in self.synonyms:
                        context_keywords.extend(self.synonyms[keyword])
                    context_keywords.append(keyword)
        
        return list(set(context_keywords))  # 중복 제거
    
    def _detect_intent(self, query: str) -> str:
        """검색 의도 파악"""
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.match(pattern, query):
                    return intent
        
        return 'find_document'  # 기본값
    
    def _generate_search_operators(self, main_keywords: List[str], context_keywords: List[str]) -> List[str]:
        """검색 연산자 생성"""
        operators = []
        
        # 1. 핵심 키워드 조합
        if len(main_keywords) >= 2:
            operators.append(' '.join(main_keywords[:3]))  # 최대 3개 조합
        
        # 2. 개별 키워드
        operators.extend(main_keywords)
        
        # 3. 컨텍스트 키워드 (가중치 낮음)
        operators.extend(context_keywords[:3])
        
        return operators
    
    def _identify_excluded_terms(self, query: str) -> List[str]:
        """제외할 용어 식별"""
        excluded = []
        
        # "~가 아닌", "~없는" 패턴
        if '아닌' in query or '없는' in query:
            # 간단한 패턴 매칭으로 제외 용어 추출
            pass
        
        return excluded
    
    def get_expanded_keywords(self, keywords: List[str]) -> List[str]:
        """키워드 확장 (동의어 포함)"""
        expanded = []
        
        for keyword in keywords:
            expanded.append(keyword)
            if keyword in self.synonyms:
                expanded.extend(self.synonyms[keyword])
        
        return list(set(expanded))

# 전역 인스턴스
natural_language_processor = NaturalLanguageQueryProcessor()
