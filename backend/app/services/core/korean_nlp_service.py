"""
한국어 NLP 처리 서비스 (with kiwipiepy)

변경 사항 (2025-10-17):
- kiwipiepy 재도입 (형태소 분석 정확도 향상)
- 규칙 기반 → 형태소 분석 기반으로 전환
- 검색 품질 개선 목표

역할:
1. 한국어 형태소 분석 (kiwipiepy)
2. 키워드 추출 (명사/동사/형용사 기반)
3. 한국어 텍스트 임베딩 생성 (Azure OpenAI text-embedding-3-small)
4. 배치 임베딩 생성 (성능 최적화)
"""
import logging
from typing import List, Optional, Tuple
import hashlib
import struct
import random

# kiwipiepy import
try:
    from kiwipiepy import Kiwi
    KIWI_AVAILABLE = True
except ImportError:
    KIWI_AVAILABLE = False
    print("⚠️ kiwipiepy 로드 실패")

# 임베딩 서비스 import
try:
    from app.services.core.embedding_service import EmbeddingService
    EMBEDDING_SERVICE_AVAILABLE = True
except ImportError:
    EMBEDDING_SERVICE_AVAILABLE = False
    print("⚠️ EmbeddingService 로드 실패")

# 로거 설정
logger = logging.getLogger(__name__)


class KoreanNLPService:
    """
    한국어 NLP 서비스 (with kiwipiepy)
    
    역할:
    1. 형태소 분석 (kiwipiepy)
    2. 키워드 추출 (명사/동사/형용사)
    3. 임베딩 생성 (Azure OpenAI text-embedding-3-small)
    
    성능 측정:
    - 형태소 분석: ~50ms
    - 임베딩 생성: ~200ms
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KoreanNLPService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """초기화"""
        # 이미 초기화되었으면 스킵
        if KoreanNLPService._initialized:
            return
            
        self.kiwi = None
        self.embedding_service = None
        self.english_nlp = None
        
        # kiwipiepy 초기화
        if KIWI_AVAILABLE:
            try:
                self.kiwi = Kiwi()
                logger.info("✅ Kiwi 형태소 분석기 초기화 완료")
                print("✅ Kiwi 형태소 분석기 초기화 완료")
            except Exception as e:
                logger.error(f"Kiwi 초기화 실패: {e}")
                print(f"❌ Kiwi 초기화 실패: {e}")
        else:
            logger.warning("kiwipiepy 사용 불가, 규칙 기반 폴백 사용")
        
        # 임베딩 서비스 초기화
        if EMBEDDING_SERVICE_AVAILABLE:
            try:
                self.embedding_service = EmbeddingService()
                logger.info("✅ KoreanNLPService 초기화 완료 (Kiwi + 임베딩)")
                print("✅ KoreanNLPService 초기화 완료 (Kiwi + 임베딩)")
            except Exception as e:
                logger.error(f"EmbeddingService 초기화 실패: {e}")
                print(f"❌ EmbeddingService 초기화 실패: {e}")
        else:
            logger.warning("EmbeddingService 사용 불가, 더미 임베딩 사용")
        
        # 영어 NLP 서비스 초기화
        try:
            from app.services.core.english_nlp_service import EnglishNLPService
            self.english_nlp = EnglishNLPService()
            logger.info("✅ 영어 NLP 서비스 초기화 완료")
            print("✅ 영어 NLP 서비스 초기화 완료")
        except Exception as e:
            logger.warning(f"영어 NLP 서비스 초기화 실패: {e}")
            print(f"⚠️ 영어 NLP 서비스 초기화 실패: {e}")
        
        # 초기화 완료 플래그 설정
        KoreanNLPService._initialized = True
    
    async def generate_korean_embedding(self, text: str) -> Optional[List[float]]:
        """
        한국어 텍스트 임베딩 생성 (Azure OpenAI)
        
        Args:
            text: 임베딩을 생성할 텍스트
            
        Returns:
            1536차원 임베딩 벡터 또는 None
        """
        if not text or not text.strip():
            return None
            
        try:
            if self.embedding_service:
                # Azure OpenAI 임베딩 서비스 사용
                embedding = await self.embedding_service.get_embedding(text)
                logger.info(f"임베딩 생성 성공: {len(embedding)}차원")
                return embedding
            else:
                # 임베딩 서비스가 없는 경우 더미 벡터 반환 (개발/테스트용)
                logger.warning("임베딩 서비스 없음, 더미 벡터 반환")
                return self._create_dummy_embedding(text)
                
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            return self._create_dummy_embedding(text)
    
    async def generate_embeddings_batch(
        self, 
        texts: List[str], 
        batch_size: int = 16
    ) -> List[Optional[List[float]]]:
        """
        배치 임베딩 생성 (성능 최적화)
        
        Args:
            texts: 텍스트 리스트
            batch_size: 배치 크기 (Azure OpenAI는 최대 16개)
            
        Returns:
            임베딩 벡터 리스트
        """
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            try:
                if self.embedding_service and hasattr(self.embedding_service, 'get_embeddings_batch'):
                    # Azure OpenAI 배치 처리
                    batch_embeddings = await self.embedding_service.get_embeddings_batch(batch)
                    embeddings.extend(batch_embeddings)
                else:
                    # 개별 처리 폴백
                    for text in batch:
                        emb = await self.generate_korean_embedding(text)
                        embeddings.append(emb)
                        
            except Exception as e:
                logger.error(f"배치 임베딩 실패: {e}")
                # 실패 시 None으로 채우기
                embeddings.extend([None] * len(batch))
        
        logger.info(f"배치 임베딩 생성 완료: {len(embeddings)}개")
        return embeddings
    
    async def analyze_korean_text(self, text: str) -> dict:
        """
        한국어 텍스트 분석 (kiwipiepy 형태소 분석)
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            dict: {
                'tokens': List[str],  # 형태소 분석된 토큰
                'keywords': List[str],  # 추출된 키워드 (명사/동사/형용사)
                'pos_tags': List[Tuple[str, str]]  # (토큰, 품사) 쌍
            }
        """
        logger.info(f"✅ analyze_korean_text 호출 - 텍스트 길이: {len(text)}")
        
        # kiwipiepy 사용 (동기 함수를 비동기 컨텍스트에서 실행)
        if self.kiwi:
            try:
                import asyncio
                
                # 동기 함수를 비동기로 실행
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.kiwi.analyze, text)
                
                # 첫 번째 분석 결과 사용
                if result and len(result) > 0:
                    tokens = result[0][0]  # List[Token]
                    
                    # 품사 태깅
                    pos_tags = [(token.form, token.tag) for token in tokens]
                    
                    # 키워드 추출 전략:
                    # 1. 명사는 모두 포함 (NNG, NNP, NNB)
                    # 2. 동사/형용사는 어간만 (VV, VA) - 검색 정확도 향상
                    # 3. 복합명사 재구성 (연속된 명사 결합)
                    
                    # 단계 1: 기본 키워드 추출
                    noun_pos = ['NNG', 'NNP', 'NNB']  # 명사류
                    verb_adj_pos = ['VV', 'VA']  # 동사, 형용사
                    
                    keywords = []
                    compound_noun = []  # 복합명사 버퍼
                    
                    for i, token in enumerate(tokens):
                        # 명사인 경우
                        if token.tag in noun_pos and len(token.form) >= 2:
                            compound_noun.append(token.form)
                        else:
                            # 복합명사 완성
                            if compound_noun:
                                if len(compound_noun) == 1:
                                    keywords.append(compound_noun[0])
                                else:
                                    # 복합명사 결합 (예: ['혁신', '가'] → '혁신가')
                                    combined = ''.join(compound_noun)
                                    keywords.append(combined)
                                    # 개별 명사도 추가 (부분 매칭용)
                                    for noun in compound_noun:
                                        if len(noun) >= 2:
                                            keywords.append(noun)
                                compound_noun = []
                            
                            # 동사/형용사 어간 추가
                            if token.tag in verb_adj_pos and len(token.form) >= 2:
                                keywords.append(token.form)
                    
                    # 마지막 복합명사 처리
                    if compound_noun:
                        if len(compound_noun) == 1:
                            keywords.append(compound_noun[0])
                        else:
                            combined = ''.join(compound_noun)
                            keywords.append(combined)
                            for noun in compound_noun:
                                if len(noun) >= 2:
                                    keywords.append(noun)
                    
                    # 불용어 제거
                    stopwords = {
                        '것', '거', '수', '등', '란', '대해', '관해', '위해', '때문',
                        '그', '이', '저', '그것', '이것', '저것', '대하', '알리', '주'
                    }
                    keywords = [kw for kw in keywords if kw not in stopwords]
                    
                    # 중복 제거 (순서 유지)
                    seen = set()
                    unique_keywords = []
                    for kw in keywords:
                        if kw not in seen:
                            seen.add(kw)
                            unique_keywords.append(kw)
                    
                    logger.info(f"✅ Kiwi 분석: {len(tokens)}개 토큰 → {len(unique_keywords)}개 키워드")
                    
                    return {
                        'tokens': [token.form for token in tokens],
                        'keywords': unique_keywords[:30],
                        'pos_tags': pos_tags
                    }
                    
            except Exception as e:
                logger.error(f"Kiwi 분석 실패: {e}, 규칙 기반 폴백 사용")
        
        # 폴백: 규칙 기반 분석
        return self._analyze_korean_text_fallback(text)
    
    def _analyze_korean_text_fallback(self, text: str) -> dict:
        """
        규칙 기반 한국어 텍스트 분석 (폴백)
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            dict: analyze_korean_text와 동일한 형식
        """
        logger.info(f"⚠️ 규칙 기반 폴백 사용 - 텍스트 길이: {len(text)}")
        
        # 간단한 토큰 분리 (공백 기준)
        tokens = text.strip().split()
        
        # 한국어 조사 및 불용어 제거
        stopwords = {
            # 조사
            '은', '는', '이', '가', '을', '를', '에', '의', '와', '과', '도', 
            '로', '으로', '부터', '까지', '에서', '께서', '만', '라도', '이라도',
            # 의존명사/어미
            '것', '거', '수', '등', '란', '대해', '관해', '위해', '때문',
            # 대명사
            '그', '이', '저', '그것', '이것', '저것',
            # 어미
            '하나요', '한다', '했다', '합니다', '입니다'
        }
        
        # 한국어 조사 (어미에 붙는 형태)
        josa_suffixes = ['은', '는', '이', '가', '을', '를', '에', '의', '와', '과', '도', 
                         '로', '으로', '부터', '까지', '에서', '께서', '만', '라도', '이라도',
                         '에게', '한테', '보다', '처럼', '마저', '조차', '밖에']
        
        # 키워드 추출 (불용어 제거 + 조사 분리 + 길이 필터링)
        keywords = []
        for token in tokens:
            # 완전 일치 불용어 제거
            if token in stopwords:
                continue
            
            # 조사 분리 처리
            cleaned_token = token
            for josa in josa_suffixes:
                if token.endswith(josa) and len(token) > len(josa):
                    # 조사 제거
                    base = token[:-len(josa)]
                    # 어간이 2글자 이상인 경우만 유효
                    if len(base) >= 2:
                        cleaned_token = base
                        break
            
            # 너무 짧은 토큰 제거 (1글자)
            if len(cleaned_token) < 2:
                continue
            
            # 불용어 재확인 (조사 제거 후)
            if cleaned_token in stopwords:
                continue
            
            # 추가
            keywords.append(cleaned_token)
        
        logger.info(f"✅ 규칙 기반: {len(tokens)}개 토큰 → {len(keywords)}개 키워드")
        
        return {
            'tokens': tokens,
            'keywords': keywords[:30],  # 상위 30개
            'pos_tags': []  # 규칙 기반에서는 품사 정보 없음
        }
    
    async def analyze_text_for_search(self, text: str) -> dict:
        """
        검색을 위한 다국어 텍스트 분석 (RAG 검색 전용)
        
        언어 자동 감지:
        - 영어: NLTK 기반 키워드 추출
        - 한국어: Kiwi 기반 형태소 분석
        - 혼합: 두 분석 결과 병합
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            dict: {
                'language': str,  # 'ko', 'en', 'mixed'
                'keywords': List[str],  # 통합 키워드
                'korean_keywords': List[str],  # 한국어 키워드
                'english_keywords': List[str],  # 영어 키워드
                'proper_nouns': [],  # 빈 리스트
                'entities': {}  # 빈 딕셔너리
            }
        """
        logger.info(f"✅ analyze_text_for_search 호출 - 텍스트 길이: {len(text)}")
        
        # 언어 감지
        is_english = self.english_nlp.is_english(text) if self.english_nlp else False
        has_korean = self._has_korean(text)
        
        if is_english and not has_korean:
            language = 'en'
        elif has_korean and not is_english:
            language = 'ko'
        else:
            language = 'mixed'
        
        logger.info(f"📝 언어 감지: {language} (한국어: {has_korean}, 영어: {is_english})")
        
        # 한국어 분석
        korean_analysis = await self.analyze_korean_text(text)
        korean_keywords = korean_analysis['keywords']
        
        # 영어 분석
        english_keywords = []
        if self.english_nlp and (language == 'en' or language == 'mixed'):
            try:
                english_analysis = await self.english_nlp.analyze_english_text(text)
                english_keywords = english_analysis['keywords']
            except Exception as e:
                logger.warning(f"영어 분석 실패: {e}")
        
        # 키워드 통합 (중복 제거, 순서 유지)
        all_keywords = []
        seen = set()
        for kw in korean_keywords + english_keywords:
            if kw not in seen:
                seen.add(kw)
                all_keywords.append(kw)
        
        logger.info(f"✅ 통합 분석 완료: 한국어 {len(korean_keywords)}개 + "
                   f"영어 {len(english_keywords)}개 = 전체 {len(all_keywords)}개 키워드")
        
        return {
            'language': language,
            'keywords': all_keywords[:50],  # 최대 50개
            'korean_keywords': korean_keywords,
            'english_keywords': english_keywords,
            'proper_nouns': [],
            'entities': {}
        }
    
    def _has_korean(self, text: str) -> bool:
        """
        텍스트에 한국어가 포함되어 있는지 확인
        
        Args:
            text: 입력 텍스트
            
        Returns:
            bool: 한국어 포함 여부
        """
        import re
        # 한글 유니코드 범위: \uAC00-\uD7A3
        korean_pattern = re.compile(r'[\uAC00-\uD7A3]')
        return bool(korean_pattern.search(text))
    
    def _create_dummy_embedding(self, text: str, dimension: Optional[int] = None) -> List[float]:
        """
        더미 임베딩 벡터 생성 (개발/테스트용)
        
        Args:
            text: 입력 텍스트
            dimension: 벡터 차원 (기본값: settings.vector_dimension)
            
        Returns:
            정규화된 더미 임베딩 벡터
        """
        if dimension is None:
            try:
                from app.core.config import settings
                dimension = settings.vector_dimension
            except:
                dimension = 1536  # 기본값
        
        # 텍스트 해시를 기반으로 시드 생성
        text_hash = hashlib.md5(text.encode()).digest()
        seed = struct.unpack('I', text_hash[:4])[0]
        
        # 시드를 이용한 의사 랜덤 벡터 생성
        random.seed(seed)
        vector = [random.uniform(-1.0, 1.0) for _ in range(dimension)]
        
        # 벡터 정규화
        magnitude = sum(x * x for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
        
        return vector


# 전역 인스턴스
korean_nlp_service = KoreanNLPService()
logger.info("✅ korean_nlp_service 전역 인스턴스 생성 완료")
