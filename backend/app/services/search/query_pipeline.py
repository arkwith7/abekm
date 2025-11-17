"""
통합 질의 처리 파이프라인
일반 검색 + RAG 검색 공통 사용

사용 예시:
    # 일반 검색
    from app.services.search.query_pipeline import process_user_query
    result = await process_user_query("혁신에 대해 뭐라 이야기 하나요", search_type="general")
    
    # RAG 검색
    result = await process_user_query("혁신에 대해 뭐라 이야기 하나요", search_type="rag")
"""

import time
import re
import logging
from typing import Dict, Any, Optional, List

from .query_models import ProcessedQuery, IntentType
from .query_config import (
    UNIFIED_STOPWORDS, 
    INTENT_SEARCH_STRATEGIES, 
    RAG_SEARCH_STRATEGIES,
    INTENT_PATTERNS,
    LANGUAGE_SETTINGS
)
from ..core.korean_nlp_service import korean_nlp_service
from ..core.embedding_service import embedding_service
from .spell_checker import apply_spell_correction

logger = logging.getLogger(__name__)


async def process_user_query(
    query: str,
    search_type: str = "general",  # "general" or "rag"
    **kwargs
) -> ProcessedQuery:
    """
    사용자 질의 통합 처리
    
    Args:
        query: 사용자 질의 텍스트
        search_type: "general" (일반 검색) or "rag" (RAG 검색)
    
    Returns:
        ProcessedQuery: 처리된 질의
    
    처리 단계:
        1. 입력 정규화 (공백, 특수문자 제거)
        2. 의도 분류 (keyword_search, document_search, qa_question, ...)
        3. 형태소 분석 및 키워드 추출
        4. 불용어 제거 (UNIFIED_STOPWORDS 사용)
        5. 검색 쿼리 생성 (fulltext, keyword, vector)
        6. 검색 전략 설정 (가중치, 임계값)
    """
    start_time = time.time()
    
    try:
        logger.info(f"🔍 [QueryPipeline] 질의 처리 시작: '{query[:50]}...' (type: {search_type})")
        
        # Step 1: 입력 정규화
        normalized_text = _normalize_text(query)
        language = _detect_language(normalized_text)
        logger.info(f"✓ 정규화 완료: '{normalized_text}' (언어: {language})")
        
        # Step 2: 스펠링 교정 (영어/혼합 어절만 대상)
        spell_corrections = {}
        if language in ("en", "mixed"):
            corrected_text, spell_corrections = apply_spell_correction(normalized_text)
            if spell_corrections:
                logger.info(f"✓ 오탈자 보정: {spell_corrections}")
                normalized_text = corrected_text

        # Step 3: 의도 분류
        intent_type, intent_confidence = _classify_intent(normalized_text)
        logger.info(f"✓ 의도 분류: {intent_type} (confidence: {intent_confidence:.2f})")
        
        # Step 4: 형태소 분석 및 키워드 추출
        keywords = await _extract_keywords(normalized_text)
        logger.info(f"✓ 키워드 추출: {len(keywords)}개 → {keywords}")
        
        # Step 5: 불용어 제거
        filtered_keywords = _filter_stopwords(keywords, intent_type, language)
        logger.info(f"✓ 불용어 제거: {len(keywords)}개 → {len(filtered_keywords)}개 → {filtered_keywords}")

        if spell_corrections:
            # 교정된 단어를 키워드에 보강 (중복 제거)
            corrected_terms = list(spell_corrections.values())
            filtered_keywords = list(dict.fromkeys(filtered_keywords + corrected_terms))
            keywords = list(dict.fromkeys(keywords + corrected_terms))
            logger.info(f"✓ 교정 단어 보강 후 키워드: {filtered_keywords}")
        
        # Step 6: 검색 쿼리 생성
        fulltext_query = _generate_fulltext_query(filtered_keywords)
        keyword_query = _generate_keyword_query(filtered_keywords)
        logger.info(f"✓ 검색 쿼리 생성: fulltext='{fulltext_query}'")
        
        # Step 7: 벡터 임베딩 생성 (옵션)
        vector_embedding = None
        if filtered_keywords and search_type in ["rag", "general"]:
            try:
                embedding_text = " ".join(filtered_keywords)
                vector_embedding = await embedding_service.get_embedding(embedding_text)
                logger.info(f"✓ 벡터 임베딩 생성 완료")
            except Exception as e:
                logger.warning(f"⚠ 벡터 임베딩 생성 실패: {e}")
        
        # Step 8: 검색 전략 설정
        strategy = _get_search_strategy(intent_type, search_type)
        
        processing_time = (time.time() - start_time) * 1000
        
        result = ProcessedQuery(
            original_text=query,
            normalized_text=normalized_text,
            language=language,
            intent=intent_type,
            intent_confidence=intent_confidence,
            keywords=keywords,
            filtered_keywords=filtered_keywords,
            fulltext_query=fulltext_query,
            keyword_query=keyword_query,
            vector_embedding=vector_embedding,
            weights=strategy["weights"],
            similarity_threshold=strategy["similarity_threshold"],
            max_results=strategy.get("max_results", 15),
            processing_time_ms=processing_time,
            spell_corrections=spell_corrections
        )
        
        logger.info(f"✅ [QueryPipeline] 처리 완료: {processing_time:.1f}ms")
        logger.debug(f"📊 처리 결과: {result.to_dict()}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [QueryPipeline] 처리 실패: {str(e)}", exc_info=True)
        
        # Fallback: 최소 기능 제공
        processing_time = (time.time() - start_time) * 1000
        return ProcessedQuery(
            original_text=query,
            normalized_text=query,
            language="ko",
            intent=IntentType.KEYWORD_SEARCH.value,
            intent_confidence=0.5,
            keywords=query.split(),
            filtered_keywords=query.split(),
            fulltext_query=query,
            keyword_query=query,
            vector_embedding=None,
            weights={"vector": 0.4, "keyword": 0.4, "fulltext": 0.2},
            similarity_threshold=0.4,
            processing_time_ms=processing_time
        )


# ========================================================================
# Internal Helper Functions
# ========================================================================

def _normalize_text(text: str) -> str:
    """텍스트 정규화"""
    # 공백 정리
    cleaned = re.sub(r'\s+', ' ', text.strip())
    
    # 이모지 제거
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "]+", flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub('', cleaned)
    
    # 불필요한 특수문자 제거 (?, !, . 등은 유지)
    cleaned = re.sub(r'[^\w\s가-힣\?\!\.\,\-]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


def _detect_language(text: str) -> str:
    """언어 감지"""
    korean_chars = len(re.findall(r'[가-힣]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    total_chars = len(re.sub(r'\s+', '', text))
    
    if total_chars == 0:
        return "ko"
    
    korean_ratio = korean_chars / total_chars
    english_ratio = english_chars / total_chars
    
    if korean_ratio > 0.5:
        return "ko"
    elif english_ratio > 0.5:
        return "en"
    else:
        return "mixed"


def _classify_intent(text: str) -> tuple[str, float]:
    """
    의도 분류 (규칙 기반)
    
    Returns:
        (intent_type, confidence)
    """
    scores = {}
    
    for intent_type, patterns in INTENT_PATTERNS.items():
        score = 0.0
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                score += 0.3
        scores[intent_type] = score
    
    if scores:
        best_intent = max(scores.items(), key=lambda x: x[1])
        intent_type, score = best_intent
        
        if score > 0:
            confidence = min(0.5 + score, 0.9)
            return intent_type, confidence
    
    # 기본값
    return IntentType.KEYWORD_SEARCH.value, 0.5


async def _extract_keywords(text: str) -> List[str]:
    """키워드 추출 (형태소 분석)"""
    try:
        analysis_result = await korean_nlp_service.analyze_text_for_search(text)
        keywords = analysis_result.get("keywords", [])
        return keywords
    except Exception as e:
        logger.warning(f"형태소 분석 실패, 단순 분리 사용: {e}")
        return text.split()


def _filter_stopwords(
    keywords: List[str], 
    intent: str, 
    language: str
) -> List[str]:
    """
    불용어 제거
    
    Args:
        keywords: 원본 키워드 리스트
        intent: 의도 타입
        language: 언어
    
    Returns:
        불용어가 제거된 키워드 리스트
    """
    lang_settings = LANGUAGE_SETTINGS.get(language, LANGUAGE_SETTINGS["ko"])
    min_length = lang_settings["min_keyword_length"]
    
    filtered = []
    
    for word in keywords:
        # 불용어 체크
        if word.lower() in UNIFIED_STOPWORDS:
            logger.debug(f"  - 불용어 제거: '{word}'")
            continue
        
        # 길이 체크
        if len(word) < min_length:
            logger.debug(f"  - 길이 부족: '{word}' (< {min_length})")
            continue
        
        filtered.append(word)
    
    # 키워드 검색인 경우 덜 엄격하게
    if intent == IntentType.KEYWORD_SEARCH.value and not filtered:
        # 불용어 제거 없이 길이만 체크
        filtered = [w for w in keywords if len(w) >= min_length]
    
    return filtered


def _generate_fulltext_query(keywords: List[str]) -> str:
    """
    전문검색 쿼리 생성 (tsquery)
    
    Args:
        keywords: 필터링된 키워드 리스트
    
    Returns:
        "키워드1 | 키워드2 | 키워드3" (OR 검색)
    """
    if not keywords:
        return ""
    
    return " | ".join(keywords)


def _generate_keyword_query(keywords: List[str]) -> str:
    """
    키워드 검색 쿼리 생성 (ILIKE)
    
    Args:
        keywords: 필터링된 키워드 리스트
    
    Returns:
        "%키워드1% OR %키워드2%" 형식
    """
    if not keywords:
        return ""
    
    return " OR ".join([f"%{kw}%" for kw in keywords])


def _get_search_strategy(intent: str, search_type: str) -> Dict[str, Any]:
    """
    검색 전략 선택
    
    Args:
        intent: 의도 타입
        search_type: "general" or "rag"
    
    Returns:
        검색 전략 (weights, threshold, etc.)
    """
    if search_type == "rag":
        return RAG_SEARCH_STRATEGIES.get(
            intent,
            RAG_SEARCH_STRATEGIES["document_search"]
        )
    else:
        return INTENT_SEARCH_STRATEGIES.get(
            intent,
            INTENT_SEARCH_STRATEGIES["document_search"]
        )
