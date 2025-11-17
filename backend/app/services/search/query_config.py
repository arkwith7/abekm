"""
통합 검색 설정 및 불용어 리스트
일반 검색 + RAG 검색 모두 사용
"""

# ====================================================================
# 통합 불용어 리스트 (Unified Stopwords)
# search_service.py와 rag_search_service.py 모두 사용
# ====================================================================

UNIFIED_STOPWORDS = {
    # 조사 (Particles)
    "을", "를", "이", "가", "은", "는", "의", "에", "에서", "에게", "께",
    "으로", "로", "와", "과", "부터", "까지", "처럼", "같이", "보다",
    "만", "도", "라도", "조차", "마저", "밖에", "뿐",
    
    # 의문사 (Interrogatives) - 의미가 약한 것들
    "뭐", "뭐라", "뭐라고", "무엇", "어떤", "어떻게",
    
    # 보조용언 (Auxiliary Verbs/Adjectives)
    "대해", "대한", "관해", "관한", "하나요", "있나요", "있어요", 
    "되나요", "됩니까", "입니까", "인가요", "일까요",
    
    # 검색 관련 동사 (Search Verbs) - 의도 파악 후 제거
    "찾아줘", "찾아", "찾기", "검색", "조회", "보여줘", "보여", 
    "알려줘", "알려", "가져와", "확인",
    
    # 지시어 (Demonstratives)
    "이", "그", "저", "이런", "그런", "저런", "이것", "그것", "저것",
    
    # 기타
    "등", "및", "또", "또는", "혹은", "그리고", "하지만", "그러나",
    "같은", "같이", "처럼"
}

# ====================================================================
# 의도별 검색 전략 (Intent-based Search Strategies)
# ====================================================================

INTENT_SEARCH_STRATEGIES = {
    # 키워드 검색: "AWS Lambda"
    "keyword_search": {
        "weights": {
            "vector": 0.3,      # 벡터 유사도 30%
            "keyword": 0.6,     # 키워드 매칭 60%
            "fulltext": 0.1     # 전문검색 10%
        },
        "similarity_threshold": 0.3,
        "use_expansion": False,
        "search_mode": "precise",
        "max_results": 20
    },
    
    # 문서 검색: "혁신 관련 문서 찾아줘"
    "document_search": {
        "weights": {
            "vector": 0.5,
            "keyword": 0.3,
            "fulltext": 0.2
        },
        "similarity_threshold": 0.4,
        "use_expansion": True,
        "search_mode": "hybrid",
        "max_results": 15
    },
    
    # 질의응답: "Lambda 비용은 얼마인가요?"
    "qa_question": {
        "weights": {
            "vector": 0.6,
            "keyword": 0.2,
            "fulltext": 0.2
        },
        "similarity_threshold": 0.5,
        "use_expansion": True,
        "search_mode": "semantic",
        "max_results": 10
    },
    
    # 요약: "이 문서 요약해줘"
    "summarization": {
        "weights": {
            "vector": 0.5,
            "keyword": 0.3,
            "fulltext": 0.2
        },
        "similarity_threshold": 0.4,
        "use_expansion": False,
        "search_mode": "hybrid",
        "max_results": 5
    },
    
    # 비교: "EKS vs ECS 비교"
    "comparison": {
        "weights": {
            "vector": 0.6,
            "keyword": 0.3,
            "fulltext": 0.1
        },
        "similarity_threshold": 0.45,
        "use_expansion": True,
        "search_mode": "semantic",
        "max_results": 10
    },
    
    # 프레젠테이션 생성: "PPT 만들어줘"
    "presentation": {
        "weights": {
            "vector": 0.5,
            "keyword": 0.3,
            "fulltext": 0.2
        },
        "similarity_threshold": 0.4,
        "use_expansion": True,
        "search_mode": "hybrid",
        "max_results": 20
    }
}

# ====================================================================
# RAG 검색 전략 (RAG-specific Strategies)
# ====================================================================

RAG_SEARCH_STRATEGIES = {
    "document_search": {
        "weights": {
            "vector": 0.6,
            "keyword": 0.2,
            "fulltext": 0.2
        },
        "similarity_threshold": 0.42,
        "max_chunks": 10,
        "use_reranking": True
    },
    
    "qa_question": {
        "weights": {
            "vector": 0.7,
            "keyword": 0.15,
            "fulltext": 0.15
        },
        "similarity_threshold": 0.45,
        "max_chunks": 10,
        "use_reranking": True
    },
    
    "comparison": {
        "weights": {
            "vector": 0.6,
            "keyword": 0.2,
            "fulltext": 0.2
        },
        "similarity_threshold": 0.4,
        "max_chunks": 15,
        "use_reranking": True
    }
}

# ====================================================================
# 의도 분류 패턴 (Intent Classification Patterns)
# ====================================================================

INTENT_PATTERNS = {
    "keyword_search": [
        r"^[A-Za-z0-9_\-\s]+$",      # 영문/숫자만
        r"^[\w가-힣]{1,15}$",        # 단일 단어/짧은 문구
    ],
    
    "document_search": [
        r".*(찾|검색|조회).*",
        r".*(관련|대한|관한).*문서.*",
        r".*자료.*보여.*",
        r".*(문서|파일|자료).*있.*",
    ],
    
    "qa_question": [
        r".*(무엇|뭐|어떻게|왜|언제|어디|누가|얼마).*",
        r".*(인가요|입니까|일까요|되나요)$",
        r".*\?+\s*$",
    ],
    
    "summarization": [
        r".*(요약|정리).*",
        r".*요약해.*",
    ],
    
    "comparison": [
        r".*(비교|차이).*",
        r".*vs.*",
        r".*대비.*",
    ],
    
    "presentation": [
        r".*(PPT|ppt|발표|슬라이드|프레젠테이션).*만들.*",
        r".*(PPT|ppt).*생성.*",
    ]
}

# ====================================================================
# 언어별 설정 (Language-specific Settings)
# ====================================================================

LANGUAGE_SETTINGS = {
    "ko": {
        "use_morpheme_analysis": True,
        "use_josa_removal": True,
        "min_keyword_length": 2,
        "tsquery_config": "korean"
    },
    "en": {
        "use_morpheme_analysis": False,
        "use_josa_removal": False,
        "min_keyword_length": 3,
        "tsquery_config": "english"
    },
    "mixed": {
        "use_morpheme_analysis": True,
        "use_josa_removal": True,
        "min_keyword_length": 2,
        "tsquery_config": "simple"
    }
}
