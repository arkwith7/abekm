"""
대화 컨텍스트 관리 서비스
멀티턴 대화에서 이전 컨텍스트를 활용하여 RAG 검색 품질 향상
"""

import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.core.korean_nlp_service import korean_nlp_service

logger = logging.getLogger(__name__)

@dataclass
class ConversationContext:
    """대화 컨텍스트 정보"""
    session_id: str
    turn_number: int
    accumulated_keywords: List[str]
    relevant_documents: List[str]  # 이전에 유용했던 문서 ID들
    topic_continuity_score: float
    last_intent: str
    conversation_summary: str

class ConversationContextService:
    """대화 컨텍스트 관리 서비스"""
    
    def __init__(self):
        self.max_history_turns = 5  # 최대 5턴까지 고려
        self.keyword_decay_factor = 0.8  # 이전 턴일수록 키워드 가중치 감소
        self.document_relevance_threshold = 0.6
        
        # 명시적 참조 표현 패턴
        self.explicit_reference_patterns = [
            # 시간적 참조
            "이전에", "앞에서", "방금", "아까", "전에", "먼저", 
            "처음에", "최근에", "지난번에", "예전에", "과거에",
            
            # 지시 대명사 및 지시어
            "그것", "그거", "이것", "이거", "그", "이", "저것", "저거", "저",
            "그런", "이런", "저런", "그같은", "이같은", "저같은",
            
            # 대화 연결 표현
            "말한", "이야기한", "언급한", "얘기한", "설명한", "답변한",
            "말씀", "이야기", "언급", "얘기", "설명", "답변",
            
            # 문맥 연결어
            "그래서", "그런데", "그러면", "그럼", "그렇다면", "따라서",
            "또한", "또", "추가로", "더불어", "게다가", "마찬가지로",
            
            # 내용 관련 참조
            "내용에서", "내용", "부분에서", "부분", "관련해서", "관련하여",
            "대해서", "대하여", "관해서", "관하여", "것에 대해", "것에 관해",
            
            # 대화 흐름 참조
            "계속해서", "이어서", "연결해서", "연장해서", "추가해서",
            "더 자세히", "더 구체적으로", "보충해서", "덧붙여서",
            
            # 🆕 첨부 파일 관련 참조
            "첨부", "첨부된", "첨부한", "첨부파일", "첨부 파일",
            "업로드", "업로드된", "업로드한", "올린", "올려진",
            "이미지", "사진", "그림", "파일", "문서",
            "위", "위의", "아래", "아래의", "다음", "다음의"
        ]
        
    async def enhance_query_with_context(
        self,
        current_query: str,
        session_id: str,
        db_session: AsyncSession
    ) -> Tuple[str, Dict[str, Any]]:
        """
        대화 컨텍스트를 활용하여 현재 쿼리 강화
        
        Returns:
            enhanced_query: 컨텍스트가 반영된 강화된 쿼리
            context_metadata: 컨텍스트 메타데이터
        """
        try:
            # 0. 명시적 참조 표현 확인
            has_explicit_reference = self._has_explicit_reference(current_query)
            
            if not has_explicit_reference:
                logger.info(f"📝 명시적 참조 없음 - 독립적 질문으로 처리: '{current_query[:30]}...'")
                return current_query, {"context_used": False, "reason": "no_explicit_reference"}
            
            logger.info(f"🔗 명시적 참조 탐지 - 멀티턴 컨텍스트 적용: '{current_query[:30]}...'")
            
            # 1. 대화 히스토리 조회
            conversation_history = await self._get_conversation_history(db_session, session_id)
            
            if not conversation_history:
                return current_query, {"context_used": False, "reason": "no_history"}
            
            # 2. 컨텍스트 분석
            context = await self._analyze_conversation_context(conversation_history, current_query)
            
            # 3. 쿼리 강화
            enhanced_query = await self._enhance_query(current_query, context)
            
            context_metadata = {
                "context_used": True,
                "original_query": current_query,
                "enhanced_query": enhanced_query,
                "accumulated_keywords": context.accumulated_keywords,
                "relevant_documents": context.relevant_documents,
                "topic_continuity": context.topic_continuity_score,
                "last_intent": context.last_intent
            }
            
            logger.info(f"🔗 쿼리 컨텍스트 강화: '{current_query}' → '{enhanced_query}'")
            return enhanced_query, context_metadata
            
        except Exception as e:
            logger.error(f"❌ 쿼리 컨텍스트 강화 실패: {e}")
            return current_query, {"context_used": False, "error": str(e)}
    
    async def _get_conversation_history(
        self, 
        session: AsyncSession, 
        session_id: str
    ) -> List[Dict[str, Any]]:
        """대화 히스토리 조회"""
        try:
            query = text("""
                SELECT 
                    user_message,
                    assistant_response,
                    created_date,
                    conversation_context
                FROM tb_chat_history 
                WHERE session_id = :session_id 
                ORDER BY created_date DESC 
                LIMIT :limit
            """)
            
            result = await session.execute(query, {
                "session_id": session_id,
                "limit": self.max_history_turns
            })
            
            history = []
            for row in result.fetchall():
                history.append({
                    "user_message": row.user_message,
                    "ai_response": row.assistant_response,
                    "created_at": row.created_date,
                    "metadata": row.conversation_context or {}
                })
            
            return list(reversed(history))  # 시간순 정렬
            
        except Exception as e:
            logger.error(f"❌ 대화 히스토리 조회 실패: {e}")
            return []
    
    async def _analyze_conversation_context(
        self,
        history: List[Dict[str, Any]],
        current_query: str
    ) -> ConversationContext:
        """대화 컨텍스트 분석"""
        try:
            # 1. 누적 키워드 추출
            accumulated_keywords = await self._extract_accumulated_keywords(history, current_query)
            
            # 2. 관련 문서 추출
            relevant_documents = self._extract_relevant_documents(history)
            
            # 3. 주제 연속성 점수 계산
            topic_continuity = await self._calculate_topic_continuity(history, current_query)
            
            # 4. 마지막 의도 추출
            last_intent = self._extract_last_intent(history)
            
            # 5. 대화 요약 생성
            conversation_summary = self._generate_conversation_summary(history)
            
            return ConversationContext(
                session_id="",  # 세션 ID는 상위에서 관리
                turn_number=len(history) + 1,
                accumulated_keywords=accumulated_keywords,
                relevant_documents=relevant_documents,
                topic_continuity_score=topic_continuity,
                last_intent=last_intent,
                conversation_summary=conversation_summary
            )
            
        except Exception as e:
            logger.error(f"❌ 대화 컨텍스트 분석 실패: {e}")
            return ConversationContext("", 0, [], [], 0.0, "unknown", "")
    
    async def _extract_accumulated_keywords(
        self,
        history: List[Dict[str, Any]],
        current_query: str
    ) -> List[str]:
        """대화에서 누적된 키워드 추출 (주제 전환 시 키워드 초기화)"""
        try:
            all_keywords = set()
            
            # 현재 쿼리에서 키워드 추출
            current_analysis = await korean_nlp_service.analyze_korean_text(current_query)
            current_keywords = current_analysis.get("keywords", [])
            current_domain_keywords = set()
            
            # 현재 질문의 도메인별 키워드 분류
            domain_categories = {
                "medical": {"의료", "병원", "치료", "질병", "약물", "의사", "환자", "건강", "인슐린", "펌프", "혈당", "당뇨"},
                "travel": {"여행", "관광", "호텔", "항공", "비자", "일본", "도쿄", "교토", "오사카", "관광지", "숙소"},
                "technology": {"IT", "컴퓨터", "소프트웨어", "프로그래밍", "개발", "시스템", "네트워크", "AI"},
                "business": {"사업", "회사", "경영", "마케팅", "영업", "제품", "서비스", "고객", "매출"},
                "education": {"교육", "학교", "학습", "수업", "강의", "시험", "졸업", "입학", "과정"}
            }
            
            current_domain = "general"
            for domain, domain_kws in domain_categories.items():
                if any(kw in current_query.lower() or kw in current_keywords for kw in domain_kws):
                    current_domain = domain
                    current_domain_keywords = domain_kws
                    break
            
            # 현재 질문 키워드 추가
            for keyword in current_keywords:
                all_keywords.add(keyword)
            
            # 이전 대화에서 키워드 추출 (도메인 일치 시에만)
            for i, exchange in enumerate(reversed(history)):
                weight = (self.keyword_decay_factor ** i)
                
                # 이전 메시지 도메인 확인
                prev_message = exchange["user_message"]
                prev_domain = "general"
                for domain, domain_kws in domain_categories.items():
                    if any(kw in prev_message.lower() for kw in domain_kws):
                        prev_domain = domain
                        break
                
                # 같은 도메인이거나 일반적인 경우에만 키워드 누적
                if prev_domain == current_domain or (prev_domain == "general" and current_domain == "general"):
                    # 사용자 메시지에서 키워드 추출
                    user_analysis = await korean_nlp_service.analyze_korean_text(exchange["user_message"])
                    user_keywords = user_analysis.get("keywords", [])
                    
                    for keyword in user_keywords:
                        if len(keyword) > 1:  # 단일 문자 제외
                            # 현재 도메인과 관련된 키워드만 누적
                            if current_domain == "general" or keyword in current_domain_keywords or any(kw in keyword for kw in current_domain_keywords):
                                all_keywords.add(keyword)
                else:
                    logger.info(f"🚫 도메인 불일치로 키워드 누적 제외: {prev_domain} vs {current_domain}")
                    break  # 도메인이 다르면 더 이전 기록은 보지 않음
            
            # 키워드 중요도 순으로 정렬
            sorted_keywords = sorted(
                all_keywords, 
                key=lambda x: len(x) + (1 if x in current_keywords else 0),
                reverse=True
            )
            
            result_keywords = sorted_keywords[:10]
            logger.info(f"🔑 누적 키워드 (도메인: {current_domain}): {result_keywords}")
            return result_keywords
            
        except Exception as e:
            logger.error(f"❌ 누적 키워드 추출 실패: {e}")
            return []
    
    def _extract_relevant_documents(self, history: List[Dict[str, Any]]) -> List[str]:
        """이전 대화에서 유용했던 문서 ID 추출"""
        document_scores = {}
        
        for exchange in history:
            metadata = exchange.get("metadata", {})
            references = metadata.get("references", [])
            
            for ref in references:
                doc_id = ref.get("document_id")
                if doc_id:
                    score = ref.get("similarity_score", 0)
                    if score > self.document_relevance_threshold:
                        document_scores[doc_id] = document_scores.get(doc_id, 0) + score
        
        # 점수 순으로 정렬하여 상위 문서 반환
        sorted_docs = sorted(
            document_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return [doc_id for doc_id, _ in sorted_docs[:5]]
    
    async def _calculate_topic_continuity(
        self,
        history: List[Dict[str, Any]],
        current_query: str
    ) -> float:
        """주제 연속성 점수 계산 (주제 전환 감지 강화)"""
        if not history:
            return 0.0
        
        try:
            # 최근 2개 대화와 현재 질문의 의미적 유사도 계산
            recent_messages = []
            for exchange in history[-2:]:
                recent_messages.append(exchange["user_message"])
            
            if not recent_messages:
                return 0.0
            
            # 도메인 카테고리 감지를 위한 키워드 그룹
            domain_categories = {
                "medical": {"의료", "병원", "치료", "질병", "약물", "의사", "환자", "건강", "인슐린", "펌프", "혈당", "당뇨", "수술", "진료"},
                "travel": {"여행", "관광", "호텔", "항공", "비자", "일본", "도쿄", "교토", "오사카", "관광지", "숙소", "여행지", "패키지", "투어"},
                "technology": {"IT", "컴퓨터", "소프트웨어", "프로그래밍", "개발", "시스템", "네트워크", "데이터베이스", "클라우드", "AI"},
                "business": {"사업", "회사", "경영", "마케팅", "영업", "제품", "서비스", "고객", "매출", "투자", "계약", "전략"},
                "education": {"교육", "학교", "학습", "수업", "강의", "시험", "졸업", "입학", "과정", "커리큘럼", "학생", "교사"}
            }
            
            # 현재 질문 도메인 분석
            current_analysis = await korean_nlp_service.analyze_korean_text(current_query)
            current_keywords = set(current_analysis.get("keywords", []))
            current_domain = self._detect_domain(current_query.lower(), current_keywords, domain_categories)
            
            # 이전 메시지들의 도메인 분석
            prev_domains = []
            keyword_similarities = []
            
            for message in recent_messages:
                message_analysis = await korean_nlp_service.analyze_korean_text(message)
                message_keywords = set(message_analysis.get("keywords", []))
                prev_domain = self._detect_domain(message.lower(), message_keywords, domain_categories)
                prev_domains.append(prev_domain)
                
                # 키워드 유사도 계산
                if current_keywords and message_keywords:
                    intersection = current_keywords.intersection(message_keywords)
                    union = current_keywords.union(message_keywords)
                    similarity = len(intersection) / len(union) if union else 0.0
                    keyword_similarities.append(similarity)
                else:
                    keyword_similarities.append(0.0)
            
            # 도메인 일치도 계산
            domain_consistency = sum(1 for prev_domain in prev_domains if prev_domain == current_domain and prev_domain != "general") / len(prev_domains)
            
            # 키워드 유사도 평균
            avg_keyword_similarity = sum(keyword_similarities) / len(keyword_similarities) if keyword_similarities else 0.0
            
            # 주제 전환 패턴 감지
            topic_shift_phrases = ["이제", "다음은", "그런데", "대신", "바꿔서", "새로운", "다른", "전혀 다른"]
            has_shift_indicator = any(phrase in current_query for phrase in topic_shift_phrases)
            
            # 최종 연속성 점수 계산
            continuity_score = (domain_consistency * 0.6 + avg_keyword_similarity * 0.4)
            
            # 주제 전환 지시어가 있으면 점수 크게 감소
            if has_shift_indicator:
                continuity_score *= 0.3
            
            # 완전히 다른 도메인이면 연속성 낮춤
            if current_domain != "general" and all(pd != current_domain and pd != "general" for pd in prev_domains):
                continuity_score *= 0.2
                logger.info(f"🔄 도메인 전환 감지: {prev_domains} → {current_domain}, 연속성={continuity_score:.2f}")
            
            return min(1.0, continuity_score)
            
        except Exception as e:
            logger.error(f"❌ 주제 연속성 계산 실패: {e}")
            return 0.0
    
    def _detect_domain(self, text: str, keywords: set, domain_categories: dict) -> str:
        """텍스트에서 도메인 카테고리 감지"""
        domain_scores = {}
        
        for domain, domain_keywords in domain_categories.items():
            score = 0
            # 직접 텍스트 매칭
            for keyword in domain_keywords:
                if keyword in text:
                    score += 2
            # 추출된 키워드 매칭
            for extracted_kw in keywords:
                if extracted_kw in domain_keywords:
                    score += 1
            domain_scores[domain] = score
        
        # 가장 높은 점수의 도메인 반환 (임계값 이상인 경우)
        max_domain = max(domain_scores.items(), key=lambda x: x[1])
        if max_domain[1] >= 2:  # 최소 2점 이상
            return max_domain[0]
        return "general"
    
    def _extract_last_intent(self, history: List[Dict[str, Any]]) -> str:
        """마지막 의도 추출"""
        if not history:
            return "unknown"
        
        last_message = history[-1]["user_message"].lower()
        
        # 간단한 의도 분류
        if any(word in last_message for word in ["요약", "정리", "설명"]):
            return "summarization"
        elif any(word in last_message for word in ["비교", "차이", "다른"]):
            return "comparison"
        elif any(word in last_message for word in ["방법", "어떻게", "절차"]):
            return "instruction"
        elif any(word in last_message for word in ["언제", "시기", "일정"]):
            return "temporal"
        else:
            return "information_seeking"
    
    def _generate_conversation_summary(self, history: List[Dict[str, Any]]) -> str:
        """대화 요약 생성"""
        if not history:
            return ""
        
        topics = []
        for exchange in history[-3:]:  # 최근 3개 대화만
            user_msg = exchange["user_message"]
            if len(user_msg) > 10:
                topics.append(user_msg[:50] + "...")
        
        return " → ".join(topics)
    
    async def _enhance_query(self, original_query: str, context: ConversationContext) -> str:
        """컨텍스트를 활용하여 쿼리 강화 (주제 전환 시 컨텍스트 무시)"""
        try:
            # 주제 연속성이 낮으면 컨텍스트 활용 제한
            if context.topic_continuity_score < 0.3:
                logger.info(f"🚫 주제 전환 감지 (연속성={context.topic_continuity_score:.2f}) - 컨텍스트 강화 생략")
                return original_query
            
            # 🆕 지시대명사가 많고 연속성이 높으면 LLM 기반 재작성 시도
            query_lower = original_query.lower()
            pronoun_count = sum(1 for p in ["그것", "그거", "이것", "이거", "그", "이"] if p in query_lower)
            
            if pronoun_count >= 2 and context.topic_continuity_score > 0.6:
                logger.info(f"🔄 지시대명사 다수 감지 ({pronoun_count}개) - LLM 기반 질의문 재작성 시도")
                llm_rewritten = await self._rewrite_query_with_llm(original_query, context)
                if llm_rewritten and llm_rewritten != original_query:
                    logger.info(f"✍️ LLM 재작성 성공: '{original_query}' → '{llm_rewritten}'")
                    return llm_rewritten
            
            enhanced_parts = [original_query]
            
            # 1. 누적 키워드 추가 (중요도 높은 순) - 연속성이 충분할 때만
            if context.accumulated_keywords and context.topic_continuity_score > 0.5:
                relevant_keywords = []
                for keyword in context.accumulated_keywords[:5]:
                    if keyword.lower() not in original_query.lower():
                        relevant_keywords.append(keyword)
                
                if relevant_keywords:
                    enhanced_parts.append(f"관련 키워드: {', '.join(relevant_keywords[:3])}")
            
            # 2. 주제 연속성이 높은 경우에만 이전 맥락 힌트 추가
            if context.topic_continuity_score > 0.6:
                enhanced_parts.append(f"(이전 대화 주제와 연관)")
            
            # 3. 의도별 힌트 추가 - 연속성 고려
            if context.topic_continuity_score > 0.4:
                if context.last_intent == "comparison" and "비교" not in original_query:
                    enhanced_parts.append("비교 분석")
                elif context.last_intent == "summarization" and "요약" not in original_query:
                    enhanced_parts.append("요약 정리")
            
            enhanced_query = " ".join(enhanced_parts)
            
            # 너무 길어지지 않도록 제한
            if len(enhanced_query) > 300:
                enhanced_query = enhanced_query[:300] + "..."
            
            return enhanced_query
            
        except Exception as e:
            logger.error(f"❌ 쿼리 강화 실패: {e}")
            return original_query
    
    async def _rewrite_query_with_llm(self, original_query: str, context: ConversationContext) -> Optional[str]:
        """
        LLM을 사용하여 지시대명사가 포함된 질의문을 명확한 질의문으로 재작성
        
        Args:
            original_query: 원본 질문 (지시대명사 포함)
            context: 대화 컨텍스트
            
        Returns:
            재작성된 질문 (실패 시 None)
        """
        try:
            from app.core.config import settings
            
            # 컨텍스트 요약 생성
            context_summary = context.conversation_summary or ""
            if context.accumulated_keywords:
                context_summary += f"\n이전 대화 주요 키워드: {', '.join(context.accumulated_keywords[:5])}"
            
            # LLM 프롬프트
            rewrite_prompt = f"""당신은 대화 문맥을 이해하고 질문을 명확하게 재작성하는 AI입니다.

이전 대화 내용:
{context_summary}

현재 질문:
{original_query}

위 질문에 포함된 지시대명사(그것, 이것, 그, 이 등)를 이전 대화 내용을 참고하여 구체적인 명사로 치환하고, 독립적으로 이해 가능한 명확한 질문으로 재작성해주세요.

재작성된 질문만 출력하세요. 추가 설명은 불필요합니다."""

            # 설정된 LLM 제공자에 따라 호출
            config = settings.get_query_rewrite_config()
            response = None
            
            if config["provider"] == "azure_openai":
                from app.services.ai_service import ai_service
                response = await ai_service.generate_completion(
                    prompt=rewrite_prompt,
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"]
                )
            elif config["provider"] == "bedrock":
                from app.services.core.bedrock_service import bedrock_service
                response = await bedrock_service.generate_text_claude(
                    prompt=rewrite_prompt,
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"]
                )
            
            if response and len(response.strip()) > 0:
                rewritten = response.strip()
                # 너무 길면 원본 반환
                if len(rewritten) > 300:
                    logger.warning(f"⚠️ 재작성 결과가 너무 김 ({len(rewritten)}자) - 원본 사용")
                    return None
                logger.info(f"✍️ 질의문 재작성 완료 ({config['provider']}): '{original_query[:30]}...' → '{rewritten[:50]}...'")
                return rewritten
            
            return None
            
        except Exception as e:
            logger.error(f"❌ LLM 질의문 재작성 실패: {e}")
            return None
    
    def _has_explicit_reference(self, query: str) -> bool:
        """
        질문에 이전 대화를 명시적으로 참조하는 표현이 있는지 확인
        
        Args:
            query: 현재 질문
            
        Returns:
            bool: 명시적 참조 표현이 있으면 True, 없으면 False
        """
        try:
            query_lower = query.lower().strip()
            
            # 1. 명시적 참조 패턴 확인
            for pattern in self.explicit_reference_patterns:
                if pattern in query_lower:
                    logger.info(f"🎯 명시적 참조 패턴 탐지: '{pattern}' in '{query[:50]}...'")
                    return True
            
            # 2. 문장 구조 기반 참조 확인
            reference_structures = [
                # "그 + 명사" 패턴
                "그 내용", "그 답변", "그 결과", "그 문서", "그 자료", "그 정보",
                "그 방법", "그 과정", "그 시스템", "그 제품", "그 서비스",
                
                # "이 + 명사" 패턴 (이전 대화 내용을 지칭)
                "이 문제", "이 사안", "이 주제", "이 건", "이 케이스",
                
                # 비교/대조 표현 (이전 내용과 연결)
                "반면에", "그에 비해", "이와 달리", "그와 반대로", "대신에",
                
                # 추가 질문 패턴
                "또 뭐가", "다른 점은", "추가로 알고 싶은", "더 궁금한",
                "그 외에", "그 밖에", "한편으로는", "다른 한편으로는"
            ]
            
            for structure in reference_structures:
                if structure in query_lower:
                    logger.info(f"🎯 참조 구조 탐지: '{structure}' in '{query[:50]}...'")
                    return True
            
            # 3. 문맥상 연속성을 나타내는 표현 확인
            continuity_indicators = [
                # 순서/단계 표현
                "다음으로", "그 다음", "두 번째로", "마지막으로", "첫 번째로",
                
                # 결과/결론 표현  
                "결과적으로", "따라서", "그러므로", "결국", "최종적으로",
                
                # 조건/가정 표현 (이전 내용 기반)
                "만약 그렇다면", "그 경우", "그런 상황에서", "그럴 때는"
            ]
            
            for indicator in continuity_indicators:
                if indicator in query_lower:
                    logger.info(f"🎯 연속성 지시어 탐지: '{indicator}' in '{query[:50]}...'")
                    return True
            
            # 4. 질문의 독립성 확인 (명확한 독립 질문 패턴)
            independent_patterns = [
                "이란", "는 무엇", "에 대해", "란 무엇", "의 정의", "라는 것",
                "설명해", "알려줘", "가르쳐", "소개해", "예시", "예를 들어"
            ]
            
            # 독립적 질문이면서 다른 참조 표현이 없는 경우
            is_likely_independent = any(pattern in query_lower for pattern in independent_patterns)
            if is_likely_independent and len(query.split()) <= 3:
                logger.info(f"📝 독립적 질문으로 판단: '{query}'")
                return False
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 명시적 참조 탐지 실패: {e}")
            # 에러 발생 시 안전하게 False 반환 (독립적 질문으로 처리)
            return False
    
    async def rewrite_query_for_image_search(
        self,
        original_query: str,
        image_count: int = 1,
        selected_documents: Optional[List[Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        이미지 첨부 시 질의문 재작성
        "첨부의 구체적인 내용" → "업로드된 이미지와 유사한 이미지 내용"
        
        Args:
            original_query: 원본 질문
            image_count: 첨부된 이미지 개수
            selected_documents: 선택된 문서 리스트
            
        Returns:
            rewritten_query: 재작성된 질문
            metadata: 재작성 메타데이터
        """
        try:
            query_lower = original_query.lower().strip()
            
            # 이미지 참조 패턴 감지
            image_reference_patterns = [
                "첨부", "업로드", "올린", "이미지", "사진", "그림"
            ]
            
            has_image_reference = any(pattern in query_lower for pattern in image_reference_patterns)
            
            if not has_image_reference:
                # 이미지 참조가 없으면 원본 반환
                return original_query, {"rewritten": False, "reason": "no_image_reference"}
            
            logger.info(f"🖼️ 이미지 참조 질문 감지: '{original_query}'")
            
            # 질의 유형 분석
            is_asking_content = any(word in query_lower for word in ["내용", "설명", "알려", "무엇", "뭐"])
            is_asking_comparison = any(word in query_lower for word in ["비교", "차이", "유사", "같은", "다른"])
            is_asking_explanation = any(word in query_lower for word in ["왜", "이유", "어떻게", "방법"])
            
            # 재작성 템플릿 선택
            if is_asking_content:
                rewritten_query = "업로드된 이미지와 시각적으로 유사한 이미지가 포함된 문서 내용을 찾아서 설명해주세요."
            elif is_asking_comparison:
                rewritten_query = "업로드된 이미지와 선택된 문서에 있는 이미지들을 비교하여 유사한 이미지와 그 내용을 설명해주세요."
            elif is_asking_explanation:
                rewritten_query = "업로드된 이미지와 관련된 문서 내용을 찾아서 상세하게 설명해주세요."
            else:
                rewritten_query = "업로드된 이미지와 시각적으로 유사한 이미지 및 관련 내용을 검색해주세요."
            
            # 선택된 문서 정보 추가
            if selected_documents and len(selected_documents) > 0:
                doc_names = [doc.fileName if hasattr(doc, 'fileName') else str(doc) for doc in selected_documents[:2]]
                if len(doc_names) == 1:
                    rewritten_query += f" 특히 '{doc_names[0]}' 문서를 중심으로 검색해주세요."
                else:
                    rewritten_query += f" 특히 '{doc_names[0]}' 등 선택된 문서들을 중심으로 검색해주세요."
            
            logger.info(f"✍️ 질의문 재작성: '{original_query}' → '{rewritten_query}'")
            
            return rewritten_query, {
                "rewritten": True,
                "original_query": original_query,
                "rewritten_query": rewritten_query,
                "image_count": image_count,
                "query_type": "image_search",
                "intent": "content" if is_asking_content else "comparison" if is_asking_comparison else "explanation"
            }
            
        except Exception as e:
            logger.error(f"❌ 이미지 질의문 재작성 실패: {e}")
            return original_query, {"rewritten": False, "reason": "error", "error": str(e)}
    
    async def analyze_query_with_intent(
        self,
        original_query: str,
        conversation_history: List[Dict[str, Any]],
        document_ids: Optional[List[int]] = None,
        container_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        LLM을 사용하여 질의문 재작성 + 의도 분류 + 필요 도구 판단
        
        Args:
            original_query: 원본 질의문
            conversation_history: 대화 히스토리
            document_ids: 선택된 문서 ID 리스트
            container_ids: 선택된 컨테이너 ID 리스트
            
        Returns:
            {
                "rewritten_query": str,  # 재작성된 질의문
                "intent": str,  # summarization | search | comparison | ppt_generation | unsupported
                "confidence": float,  # 의도 분류 신뢰도 (0~1)
                "required_tools": List[str],  # document_loader | hybrid_search | ppt_generator
                "parameters": dict,  # 도구별 파라미터
                "reasoning": str  # 판단 근거
            }
        """
        try:
            from app.core.config import settings
            import json
            
            # 대화 컨텍스트 분석
            context = await self._analyze_conversation_context(conversation_history, original_query)
            context_summary = context.conversation_summary or ""
            if context.accumulated_keywords:
                context_summary += f"\n이전 대화 키워드: {', '.join(context.accumulated_keywords[:5])}"
            
            # 문서/컨테이너 컨텍스트
            doc_context = ""
            if document_ids:
                doc_context = f"\n선택된 문서: {len(document_ids)}개 (ID: {document_ids})"
            if container_ids:
                doc_context += f"\n선택된 컨테이너: {len(container_ids)}개 (ID: {container_ids})"
            
            # 통합 분석 프롬프트
            analysis_prompt = f"""당신은 사용자 질의를 분석하여 의도를 파악하고 적절한 도구를 선택하는 AI입니다.

## 이전 대화 컨텍스트
{context_summary}

## 현재 컨텍스트
{doc_context}

## 사용자 질의
{original_query}

## 사용 가능한 도구 및 조건
1. **document_loader**: 특정 문서의 전체 내용을 로드
   - 조건: "요약", "정리", "내용 확인" 등 + 문서가 명시적으로 선택됨
   - 의도: summarization

2. **hybrid_search**: 벡터 검색 + 키워드 검색으로 관련 문서 탐색
   - 조건: 일반적인 질문, 정보 검색, 비교 분석
   - 의도: search, comparison

3. **ppt_generator**: PowerPoint 프레젠테이션 생성
   - 조건: "PPT 만들어줘", "슬라이드 생성", "발표 자료" 등
   - 의도: ppt_generation

4. **unsupported**: 위 도구로 처리 불가능한 요청
   - 조건: 도구 범위를 벗어나는 요청

## 분석 지침
- 지시대명사(그것, 이것, 첨부, 위 등)는 구체적으로 대체
- 문서 선택 + 요약/정리 요청 = document_loader 사용
- 탐색적 질문 = hybrid_search 사용
- 의도 신뢰도는 0~1 범위로 평가

## 출력 형식 (JSON만 반환, 다른 텍스트 없이)
{{
  "rewritten_query": "명확하게 재작성된 질의문",
  "intent": "summarization | search | comparison | ppt_generation | unsupported",
  "confidence": 0.95,
  "required_tools": ["document_loader"],
  "parameters": {{
    "document_ids": [5],
    "summarization_type": "comprehensive"
  }},
  "reasoning": "판단 근거 설명"
}}"""

            # 설정된 LLM 제공자에 따라 호출
            config = settings.get_query_rewrite_config()
            response_text = None
            
            if config["provider"] == "azure_openai":
                from app.services.ai_service import ai_service
                response_text = await ai_service.generate_completion(
                    prompt=analysis_prompt,
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"]
                )
            elif config["provider"] == "bedrock":
                from app.services.core.bedrock_service import bedrock_service
                response_text = await bedrock_service.generate_text_claude(
                    prompt=analysis_prompt,
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"]
                )
            
            if not response_text:
                raise ValueError("LLM 응답이 비어있습니다")
            
            # JSON 파싱
            response_text = response_text.strip()
            # JSON 코드 블록 제거
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            result = json.loads(response_text)
            
            # 기본값 설정
            result.setdefault("rewritten_query", original_query)
            result.setdefault("intent", "search")
            result.setdefault("confidence", 0.5)
            result.setdefault("required_tools", ["hybrid_search"])
            result.setdefault("parameters", {})
            result.setdefault("reasoning", "기본 검색 처리")
            
            logger.info(f"🎯 질의 분석 완료 ({config['provider']}): intent={result['intent']}, confidence={result['confidence']}, tools={result['required_tools']}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 파싱 실패: {e}, 응답: {response_text[:200]}")
            return {
                "rewritten_query": original_query,
                "intent": "search",
                "confidence": 0.3,
                "required_tools": ["hybrid_search"],
                "parameters": {},
                "reasoning": f"JSON 파싱 실패 - 기본 검색으로 폴백: {e}"
            }
        except Exception as e:
            logger.error(f"❌ 질의 분석 실패: {e}")
            return {
                "rewritten_query": original_query,
                "intent": "search",
                "confidence": 0.3,
                "required_tools": ["hybrid_search"],
                "parameters": {},
                "reasoning": f"분석 실패 - 기본 검색으로 폴백: {e}"
            }

# 전역 인스턴스
conversation_context_service = ConversationContextService()
