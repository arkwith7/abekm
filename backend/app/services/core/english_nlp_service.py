"""
영어 NLP 처리 서비스

역할:
1. 영어 텍스트 토크나이징 (NLTK)
2. 영어 키워드 추출 (명사/동사/형용사)
3. 불용어 제거
4. 언어 감지 (영어 판별)

Dependencies:
- nltk: 경량 NLP 라이브러리
"""
import logging
import re
from typing import List, Dict, Optional
import asyncio

logger = logging.getLogger(__name__)

# NLTK import (경량, 빠름)
try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    from nltk.tag import pos_tag
    
    # 필요한 데이터 다운로드 (초기 1회만)
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        logger.info("📥 NLTK punkt tokenizer 다운로드 중...")
        nltk.download('punkt', quiet=True)
    
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        logger.info("📥 NLTK stopwords 다운로드 중...")
        nltk.download('stopwords', quiet=True)
    
    try:
        nltk.data.find('taggers/averaged_perceptron_tagger')
    except LookupError:
        logger.info("📥 NLTK POS tagger 다운로드 중...")
        nltk.download('averaged_perceptron_tagger', quiet=True)
    
    NLTK_AVAILABLE = True
    logger.info("✅ NLTK 로드 완료")
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("⚠️ NLTK 로드 실패 - pip install nltk 필요")


class EnglishNLPService:
    """
    영어 NLP 서비스
    
    특징:
    - NLTK 기반 토크나이징 (빠르고 가벼움)
    - 품사 태깅 (POS Tagging)
    - 불용어 제거
    - 영어 키워드 추출
    
    성능:
    - 토크나이징: ~10ms (100단어 기준)
    - 품사 태깅: ~50ms (100단어 기준)
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EnglishNLPService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if EnglishNLPService._initialized:
            return
        
        self.available = NLTK_AVAILABLE
        
        if self.available:
            # 영어 불용어 세트
            self.stopwords = set(stopwords.words('english'))
            
            # 추가 불용어 (검색에서 제외할 단어)
            self.stopwords.update([
                'will', 'can', 'may', 'must', 'would', 'could', 'should',
                'also', 'however', 'therefore', 'thus', 'furthermore',
                'said', 'says', 'like', 'get', 'got', 'getting', 'using',
                'used', 'use', 'make', 'made', 'makes', 'include', 'includes'
            ])
            
            logger.info("✅ EnglishNLPService 초기화 완료")
            print("✅ EnglishNLPService 초기화 완료")
        else:
            logger.warning("⚠️ EnglishNLPService 사용 불가 - NLTK 미설치")
            print("⚠️ EnglishNLPService 사용 불가 - pip install nltk 실행 필요")
        
        EnglishNLPService._initialized = True
    
    def is_english(self, text: str) -> bool:
        """
        텍스트가 영어인지 판단
        
        Args:
            text: 입력 텍스트
            
        Returns:
            bool: 영어 텍스트 여부
        """
        if not text:
            return False
        
        # 영어 알파벳 비율 계산
        english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in text if c.isalpha())
        
        if total_chars == 0:
            return False
        
        # 영어 비율 70% 이상이면 영어로 판단
        return (english_chars / total_chars) >= 0.7
    
    async def analyze_english_text(self, text: str) -> Dict:
        """
        영어 텍스트 분석
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            dict: {
                'tokens': List[str],  # 토큰 목록
                'keywords': List[str],  # 키워드 목록
                'pos_tags': List[Tuple[str, str]]  # (토큰, 품사) 쌍
            }
        """
        if not self.available:
            return self._fallback_analysis(text)
        
        try:
            # 동기 함수를 비동기로 실행
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._analyze_sync, text)
            return result
        except Exception as e:
            logger.error(f"영어 분석 실패: {e}, 폴백 사용")
            return self._fallback_analysis(text)
    
    def _analyze_sync(self, text: str) -> Dict:
        """
        동기 영어 분석 (NLTK)
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            dict: 분석 결과
        """
        # 토큰화 (소문자 변환)
        tokens = word_tokenize(text.lower())
        
        # 품사 태깅
        pos_tags = pos_tag(tokens)
        
        # 키워드 추출 전략:
        # 1. 명사 (NN, NNS, NNP, NNPS)
        # 2. 동사 (VB, VBD, VBG, VBN, VBP, VBZ)
        # 3. 형용사 (JJ, JJR, JJS)
        # 4. 최소 2글자 이상
        # 5. 불용어 제외
        
        keyword_pos = {
            'NN', 'NNS', 'NNP', 'NNPS',  # 명사
            'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ',  # 동사
            'JJ', 'JJR', 'JJS'  # 형용사
        }
        
        keywords = []
        for token, pos in pos_tags:
            # 알파벳만 포함된 단어
            if not token.isalpha():
                continue
            
            # 최소 길이 체크
            if len(token) < 2:
                continue
            
            # 품사 체크
            if pos not in keyword_pos:
                continue
            
            # 불용어 체크
            if token in self.stopwords:
                continue
            
            keywords.append(token)
        
        # 중복 제거 (순서 유지)
        unique_keywords = []
        seen = set()
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        logger.info(f"✅ 영어 분석: {len(tokens)}개 토큰 → {len(unique_keywords)}개 키워드")
        
        return {
            'tokens': tokens,
            'keywords': unique_keywords[:30],  # 최대 30개
            'pos_tags': pos_tags
        }
    
    def _fallback_analysis(self, text: str) -> Dict:
        """
        폴백: 정규식 기반 간단 분석
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            dict: 분석 결과
        """
        # 단순 단어 분리
        tokens = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        
        # 기본 불용어 제거
        basic_stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
            'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was',
            'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'that', 'this', 'these', 'those', 'it', 'its', 'they', 'their'
        }
        
        keywords = [t for t in tokens if t not in basic_stopwords]
        
        # 중복 제거
        unique_keywords = list(dict.fromkeys(keywords))
        
        logger.info(f"✅ 영어 분석(폴백): {len(tokens)}개 토큰 → {len(unique_keywords)}개 키워드")
        
        return {
            'tokens': tokens,
            'keywords': unique_keywords[:30],
            'pos_tags': []
        }
