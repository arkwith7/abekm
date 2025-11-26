"""
Paper Search Agent - 논문/문서 검색 전문 에이전트
동적 도구 선택과 전략 기반 검색 수행
"""
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.contracts import (
    AgentIntent, AgentConstraints, AgentResult, AgentStep,
    SearchChunk, ToolResult
)
from app.tools.retrieval.vector_search_tool import vector_search_tool
from app.tools.retrieval.keyword_search_tool import keyword_search_tool
from app.tools.retrieval.fulltext_search_tool import fulltext_search_tool
from app.tools.retrieval.internet_search_tool import internet_search_tool
from app.tools.retrieval.multimodal_search_tool import multimodal_search_tool  # 🆕 멀티모달 검색 도구
from app.tools.processing.deduplicate_tool import deduplicate_tool
from app.tools.processing.rerank_tool import rerank_tool
from app.tools.context.context_builder_tool import context_builder_tool
from app.tools.vision.image_analysis_tool import get_image_analysis_tool  # 🆕 이미지 분석 도구
from app.services.core.korean_nlp_service import korean_nlp_service
from app.services.core.ai_service import ai_service
from app.services.document.extraction.text_extractor_service import TextExtractorService
from app.services.chat.chat_attachment_service import chat_attachment_service


class PaperSearchAgent:
    """
    논문/문서 검색 에이전트
    
    역할:
    1. 질의 분석 (의도 분류, 키워드 추출, 언어 감지)
    2. 검색 전략 선택 (의도와 제약에 따라 도구 조합 결정)
    3. 도구 순차 실행 (각 도구는 독립적)
    4. 컨텍스트 구성 및 답변 생성
    
    도구 목록:
    - vector_search: 의미 기반 검색
    - keyword_search: 키워드 매칭
    - fulltext_search: 전문검색 (tsvector)
    - deduplicate: 중복 제거
    - context_builder: 컨텍스트 토큰 패킹
    """
    
    name: str = "paper_search_agent"
    description: str = "논문/문서 검색 및 QA 전문 에이전트"
    version: str = "1.0.0"
    
    def __init__(self):
        # 도구 등록 (느슨한 결합) - 전역 인스턴스 사용
        self.tools = {
            "vector_search": vector_search_tool,
            "keyword_search": keyword_search_tool,
            "rerank": rerank_tool,
            "fulltext_search": fulltext_search_tool,
            "internet_search": internet_search_tool,
            "multimodal_search": multimodal_search_tool,  # 🆕 멀티모달 검색 도구
            "deduplicate": deduplicate_tool,
            "context_builder": context_builder_tool,
            "image_analysis": get_image_analysis_tool(),  # 🆕 이미지 분석 도구
            # TODO: PPT 생성 도구 추가 예정
            # "ppt_generator": ppt_generator_tool,
            # - 검색 결과를 받아 슬라이드 구조 생성
            # - general.prompt의 PPT 모드 규칙을 tool 내부로 캡슐화
            # - Agent는 PPT 요청 감지 시 이 도구를 전략에 포함
        }
        
        self.nlp_service = korean_nlp_service
        self.ai_service = ai_service
        self.text_extractor = TextExtractorService()
        self._steps: List[AgentStep] = []
        self._start_time: Optional[datetime] = None
    
    async def execute(
        self,
        query: str,
        db_session: AsyncSession,
        constraints: Optional[AgentConstraints] = None,
        context: Optional[Dict[str, Any]] = None,
        history: List[Dict[str, str]] = [],
        images: List[str] = [],
        attachments: List[Dict[str, Any]] = []  # 🆕 첨부 파일 목록 추가
    ) -> AgentResult:
        """
        에이전트 실행
        
        Args:
            query: 사용자 질의
            db_session: DB 세션
            constraints: 제약 조건
            context: 추가 컨텍스트 (user_emp_no 등)
            history: 대화 히스토리 (멀티턴 지원)
            images: 이미지 목록 (Base64)
            attachments: 첨부 파일 메타데이터 목록
        """
        self._start_time = datetime.utcnow()
        self._steps = []
        
        if constraints is None:
            constraints = AgentConstraints()
        
        try:
            logger.info(f"🤖 [PaperSearchAgent] 실행 시작: '{query[:50]}...'")
            
            # 🆕 이미지 분석
            image_description = ""
            if images:
                image_description = await self.analyze_images(images, query)
            
            # 🆕 문서 첨부 처리 (Chat with File)
            attached_document_context = ""
            if attachments:
                # 문서 파일 필터링 (이미지/오디오 제외)
                doc_attachments = [
                    att for att in attachments 
                    if not att.get('mime_type', '').startswith('image/') and not att.get('mime_type', '').startswith('audio/')
                ]
                
                if doc_attachments:
                    logger.info(f"📎 문서 첨부 감지 ({len(doc_attachments)}개) - 텍스트 추출 및 컨텍스트 주입 시도")
                    extracted_texts = []
                    
                    for doc_att in doc_attachments:
                        asset_id = doc_att.get('asset_id')
                        if not asset_id:
                            continue
                            
                        stored_file = chat_attachment_service.get(asset_id)
                        if not stored_file:
                            logger.warning(f"⚠️ 첨부 파일 찾을 수 없음: {asset_id}")
                            continue
                            
                        # 파일 크기 제한 (10MB)
                        MAX_FILE_SIZE = 10 * 1024 * 1024
                        if stored_file.size > MAX_FILE_SIZE:
                            logger.warning(f"⚠️ 파일 크기 초과 ({stored_file.size} bytes) - 처리 건너뜀: {stored_file.file_name}")
                            extracted_texts.append(f"[파일: {stored_file.file_name}]\n(파일이 너무 커서 내용을 읽을 수 없습니다. 10MB 이하의 파일만 지원합니다.)")
                            continue
                            
                        try:
                            # 텍스트 추출
                            extraction_result = await self.text_extractor.extract_text_from_file(
                                file_path=str(stored_file.path),
                                file_extension=stored_file.path.suffix
                            )
                            
                            if extraction_result.get('success') and extraction_result.get('text'):
                                text_content = extraction_result['text']
                                # 텍스트 길이 제한 (30,000자)
                                MAX_TEXT_LENGTH = 30000
                                if len(text_content) > MAX_TEXT_LENGTH:
                                    text_content = text_content[:MAX_TEXT_LENGTH] + "\n...(내용이 너무 길어 생략됨)"
                                    
                                extracted_texts.append(f"[첨부 파일 내용: {stored_file.file_name}]\n{text_content}")
                                logger.info(f"✅ 문서 텍스트 추출 성공: {stored_file.file_name} ({len(text_content)}자)")
                            else:
                                logger.warning(f"⚠️ 텍스트 추출 실패: {stored_file.file_name}")
                        except Exception as e:
                            logger.error(f"❌ 문서 처리 중 오류: {e}")
                            
                    if extracted_texts:
                        attached_document_context = "\n\n".join(extracted_texts)
            
            # 🆕 Query Rewrite (이미지 설명 포함)
            rewritten_query = query
            if history or image_description:
                rewritten_query = await self.rewrite_query(query, history, image_description)
                if rewritten_query != query:
                    logger.info(f"   ✍️ 질의 재작성: '{query}' → '{rewritten_query}'")
            
            # Step 1: 질의 분석
            intent = await self.classify_intent(rewritten_query)
            keywords = await self._extract_keywords(rewritten_query)
            
            logger.info(f"   - 의도: {intent}, 키워드: {keywords}")
            
            # Step 2: 전략 선택
            strategy = self.select_strategy(intent, constraints)
            
            # 🆕 첨부 문서가 있으면 검색 전략 수정 (검색 최소화 또는 생략)
            if attached_document_context:
                logger.info("📎 첨부 문서 컨텍스트 존재 - 외부 검색 전략 조정")
                # 첨부 문서가 있으면 검색 도구를 줄이거나 제거할 수 있음
                # 여기서는 검색 도구는 유지하되, 컨텍스트 빌더에 첨부 내용을 전달하는 방식 사용
                pass
                
            logger.info(f"   - 전략: {strategy}")
            
            # Step 3: 도구 실행 (병렬 처리 적용)
            all_chunks: List[SearchChunk] = []
            search_results_by_type = {}  # 검색 타입별 결과 추적
            
            # 검색 도구와 후처리 도구 분리
            search_tools = ["vector_search", "keyword_search", "fulltext_search", "internet_search", "multimodal_search"]
            parallel_tasks = []
            parallel_tool_names = []
            
            # 전략에 포함된 검색 도구 수집
            for tool_name in strategy:
                if tool_name in search_tools:
                    tool = self.tools.get(tool_name)
                    if tool:
                        parallel_tasks.append(self._execute_tool(
                            tool_name=tool_name,
                            query=rewritten_query,
                            db_session=db_session,
                            keywords=keywords,
                            constraints=constraints,
                            chunks=[],  # 검색 도구는 이전 청크 불필요
                            context=context
                        ))
                        parallel_tool_names.append(tool_name)
            
            # 검색 도구 병렬 실행
            if parallel_tasks:
                logger.info(f"   🚀 검색 도구 병렬 실행: {parallel_tool_names}")
                results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
                
                for tool_name, result in zip(parallel_tool_names, results):
                    if isinstance(result, Exception):
                        logger.error(f"❌ 도구 실행 실패: {tool_name} - {result}")
                        continue
                        
                    if result.success and hasattr(result, 'data'):
                        new_chunks = result.data
                        all_chunks.extend(new_chunks)
                        search_results_by_type[tool_name] = len(new_chunks)
                        logger.info(f"   ✅ {tool_name}: {len(new_chunks)}개 청크 추가")
                    
                    # 🆕 인터넷 검색 결과가 있으면 로깅
                    if tool_name == "internet_search" and result.success:
                        logger.info(f"   🌐 인터넷 검색 결과: {len(new_chunks)}건")

            # 🆕 Fallback Search: 검색 결과가 없고 임계값이 높은 경우 완화하여 재시도
            if not all_chunks and constraints.similarity_threshold > 0.25:
                logger.info(f"⚠️ 검색 결과 0건. 임계값 완화하여 재검색 시도 ({constraints.similarity_threshold} → 0.2)")
                
                # 임계값 임시 수정
                original_threshold = constraints.similarity_threshold
                constraints.similarity_threshold = 0.2
                
                # Vector Search만 재시도 (가장 효과적)
                if "vector_search" in strategy:
                    try:
                        retry_result = await self._execute_tool(
                            tool_name="vector_search",
                            query=rewritten_query,
                            db_session=db_session,
                            keywords=keywords,
                            constraints=constraints,
                            chunks=[],
                            context=context
                        )
                        
                        if retry_result.success and hasattr(retry_result, 'data'):
                            new_chunks = retry_result.data
                            if new_chunks:
                                all_chunks.extend(new_chunks)
                                search_results_by_type["vector_search_retry"] = len(new_chunks)
                                logger.info(f"   ✅ 재검색 성공: {len(new_chunks)}개 청크 확보")
                    except Exception as e:
                        logger.error(f"❌ 재검색 실패: {e}")
                
                # 임계값 복구
                constraints.similarity_threshold = original_threshold

            # 후처리 도구 순차 실행 (deduplicate, rerank 등)
            # context_builder는 Step 4에서 별도로 실행하므로 여기서 제외
            processing_tools = [t for t in strategy if t not in search_tools and t != "context_builder"]
            
            for tool_name in processing_tools:
                tool = self.tools.get(tool_name)
                if not tool:
                    logger.warning(f"⚠ 도구 없음: {tool_name}")
                    continue
                
                try:
                    tool_result = await self._execute_tool(
                        tool_name=tool_name,
                        query=rewritten_query,
                        db_session=db_session,
                        keywords=keywords,
                        constraints=constraints,
                        chunks=all_chunks,  # 누적된 청크 전달
                        context=context
                    )
                    
                    if tool_result.success and hasattr(tool_result, 'data'):
                        before_count = len(all_chunks)
                        all_chunks = tool_result.data
                        logger.info(f"   ✅ {tool_name}: {before_count}개 → {len(all_chunks)}개")
                        
                except Exception as e:
                    logger.error(f"❌ 도구 실행 실패: {tool_name} - {e}")
                    continue
            
            # 🆕 하이브리드 검색 결과 로깅
            if search_results_by_type:
                logger.info(f"   📊 하이브리드 검색 완료: {search_results_by_type}")
            
            # 🆕 검색 결과 품질 검증 (Step 3.5)
            if all_chunks:
                all_chunks = await self._validate_search_quality(all_chunks, rewritten_query)
            
            # Step 4: 컨텍스트 구성
            context_result = await self._execute_tool(
                tool_name="context_builder",
                query=rewritten_query,
                db_session=db_session,
                keywords=keywords,
                constraints=constraints,
                chunks=all_chunks,
                context=None
            )
            
            if not context_result.success:
                raise Exception("컨텍스트 구성 실패")
            
            # ContextResult는 ToolResult의 서브클래스이므로 속성에 직접 접근
            context_text = context_result.data if isinstance(context_result.data, str) else ""
            used_chunks = getattr(context_result, 'used_chunks', all_chunks[:5])
            
            # 🆕 첨부 문서 컨텍스트 추가
            if attached_document_context:
                context_text = f"""[첨부된 문서 내용]
{attached_document_context}

[검색된 관련 문서]
{context_text}"""
            
            # Step 5: 답변 생성
            answer = await self.generate_answer(rewritten_query, context_text, intent, history)
            
            # Step 6: 결과 반환
            latency_ms = (datetime.utcnow() - self._start_time).total_seconds() * 1000
            
            logger.info(f"✅ [PaperSearchAgent] 완료: {latency_ms:.1f}ms, {len(used_chunks)}개 참조")
            
            return AgentResult(
                answer=answer,
                references=used_chunks,
                steps=self._steps,
                metrics={
                    "total_latency_ms": latency_ms,
                    "tools_used": len(self._steps),
                    "chunks_found": len(all_chunks),
                    "chunks_used": len(used_chunks),
                    "total_tokens": getattr(context_result, 'total_tokens', 0)
                },
                intent=intent,
                strategy_used=strategy,
                success=True,
                errors=[]
            )
            
        except Exception as e:
            logger.error(f"❌ [PaperSearchAgent] 실패: {e}", exc_info=True)
            latency_ms = (datetime.utcnow() - self._start_time).total_seconds() * 1000 if self._start_time else 0
            
            return AgentResult(
                answer=f"죄송합니다. 검색 중 오류가 발생했습니다: {str(e)}",
                references=[],
                steps=self._steps,
                metrics={"total_latency_ms": latency_ms},
                intent=AgentIntent.FACTUAL_QA,
                strategy_used=[],
                success=False,
                errors=[str(e)]
            )
    
    async def analyze_images(self, images: List[str], query: str) -> str:
        """이미지 분석 (VLM 사용)"""
        if not images:
            return ""
            
        try:
            content = [{"type": "text", "text": f"사용자의 질문: {query}\n\n이 이미지들의 내용을 상세히 묘사하고, 사용자의 질문과 관련된 정보를 추출해주세요."}]
            
            for img_base64 in images:
                # 헤더가 포함되어 있는지 확인 (data:image/...)
                if "base64," in img_base64:
                    url = img_base64
                else:
                    url = f"data:image/jpeg;base64,{img_base64}"
                    
                content.append({
                    "type": "image_url",
                    "image_url": {"url": url}
                })
            
            messages = [{"role": "user", "content": content}]
            
            # VLM 호출 (max_tokens 넉넉히)
            response = await self.ai_service.chat_completion(
                messages,
                max_tokens=1000,
                temperature=0.0
            )
            
            description = response.get("response", "").strip()
            logger.info(f"🖼️ 이미지 분석 완료: {description[:100]}...")
            return description
            
        except Exception as e:
            logger.error(f"❌ 이미지 분석 실패: {e}")
            return ""

    async def rewrite_query(self, query: str, history: List[Dict[str, str]], image_description: str = "") -> str:
        """
        대화 히스토리 및 이미지 정보를 기반으로 질의 재작성 (Query Rewrite)
        """
        if not history and not image_description:
            return query
            
        try:
            # 최근 3턴만 사용
            recent_history = history[-6:]
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])
            
            prompt = f"""당신은 검색 최적화를 위한 질의 재작성 전문가입니다.
사용자의 질문이 이전 대화 문맥이나 첨부된 이미지 정보에 의존적인 경우, 이를 독립적인 완전한 질문으로 재작성하세요.
문맥 의존성이 없다면 원본 질문을 그대로 유지하세요.

이전 대화:
{history_text}

첨부 이미지 설명:
{image_description if image_description else "(없음)"}

현재 질문: {query}

규칙:
1. 지시대명사(그것, 이것, 그 기술, 이 그림 등)를 구체적인 명사나 이미지 설명 내용으로 치환
2. 이미지에 대한 질문인 경우, 이미지 설명의 핵심 내용을 검색 질의에 포함
   예) "이 차트의 추세는?" -> "[이미지 설명의 차트 주제]의 추세는?"
3. 생략된 주어나 목적어를 복원
4. 검색 엔진이 이해하기 쉬운 형태로 명확화
5. 답변은 재작성된 질문만 출력 (설명 금지)

재작성된 질문:"""

            messages = [{"role": "user", "content": prompt}]
            
            response = await self.ai_service.chat_completion(
                messages,
                max_tokens=200,
                temperature=0.0
            )
            
            rewritten = response.get("response", "").strip()
            
            # 원본과 너무 다르면 로깅
            if rewritten and rewritten != query:
                logger.info(f"✍️ [QueryRewrite] '{query}' → '{rewritten}'")
                return rewritten
                
            return query
            
        except Exception as e:
            logger.error(f"❌ Query Rewrite 실패: {e}")
            return query

    async def classify_intent(self, query: str) -> AgentIntent:
        """의도 분류 (LLM 기반 + 룰 기반 백업)"""
        try:
            # 1. LLM을 사용한 의도 분류
            system_prompt = """You are a query intent classifier. Classify the user query into one of the following categories:
- FACTUAL_QA: General questions asking for facts or information.
- KEYWORD_SEARCH: Requests to find specific documents or keywords.
- COMPARISON: Questions asking to compare two or more things.
- SUMMARIZATION: Requests to summarize a topic or document.
- EXPLORATORY: Broad or open-ended questions requiring exploration.
- WEB_SEARCH: Requests for latest news, external information, or internet search.

Return ONLY the category name (e.g., FACTUAL_QA)."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            
            response = await self.ai_service.chat_completion(
                messages,
                max_tokens=10,
                temperature=0.0
            )
            
            intent_str = response.get("response", "").strip().upper()
            
            # 매칭되는 Enum 찾기
            for intent in AgentIntent:
                if intent.name == intent_str:
                    return intent
                    
            logger.warning(f"⚠️ LLM 의도 분류 실패 또는 알 수 없는 의도: {intent_str}, 룰 기반으로 전환")
            
        except Exception as e:
            logger.error(f"❌ LLM 의도 분류 중 오류: {e}, 룰 기반으로 전환")
            
        # 2. 룰 기반 분류 (백업)
        q = query.lower()
        
        # 인터넷 검색
        if any(kw in q for kw in ["인터넷", "웹검색", "구글", "최신", "뉴스", "외부"]):
            return AgentIntent.WEB_SEARCH

        # 키워드 검색
        if any(kw in q for kw in ["검색", "찾아", "찾기", "있나", "있는지"]):
            return AgentIntent.KEYWORD_SEARCH
        
        # 비교
        if any(kw in q for kw in ["비교", "차이", "다른점", "vs"]):
            return AgentIntent.COMPARISON
        
        # 요약
        if any(kw in q for kw in ["요약", "정리", "개요"]):
            return AgentIntent.SUMMARIZATION
        
        # 기본: 사실 확인 질문
        return AgentIntent.FACTUAL_QA
    
    def select_strategy(
        self,
        intent: AgentIntent,
        constraints: AgentConstraints
    ) -> List[str]:
        """
        전략 선택 - 핵심 에이전트 로직
        의도와 제약에 따라 도구 조합 동적 결정
        
        🆕 모든 전략에 하이브리드 검색 적용 (벡터 + 키워드 동시 실행)
        """
        # 🆕 특정 문서가 지정된 경우 (Chat with File)
        # 인터넷 검색 등 외부 검색을 배제하고, 지정된 문서 내에서만 검색하도록 유도
        if constraints.document_ids and len(constraints.document_ids) > 0:
            logger.info(f"📂 특정 문서 대상 검색: {constraints.document_ids}")
            # 문서 내 검색은 벡터+키워드+전문검색 모두 활용하여 정확도 높임
            return ["vector_search", "keyword_search", "fulltext_search", "deduplicate", "rerank", "context_builder"]

        if intent == AgentIntent.FACTUAL_QA:
            # 🆕 사실 확인 → 하이브리드 검색 (벡터 + 키워드) + 중복제거 + 리랭킹
            return ["vector_search", "keyword_search", "deduplicate", "rerank", "context_builder"]
        
        elif intent == AgentIntent.KEYWORD_SEARCH:
            # 키워드 중심 → 키워드 + 전문검색 + 중복제거 + 리랭킹
            return ["keyword_search", "fulltext_search", "deduplicate", "rerank", "context_builder"]
        
        elif intent == AgentIntent.EXPLORATORY:
            # 탐색 → 하이브리드 (벡터 + 키워드 + 전문검색) + 리랭킹
            return ["vector_search", "keyword_search", "fulltext_search", "deduplicate", "rerank", "context_builder"]
        
        elif intent == AgentIntent.COMPARISON:
            # 비교 → 하이브리드 (벡터 + 키워드) + 풍부한 컨텍스트 + 리랭킹
            return ["vector_search", "keyword_search", "deduplicate", "rerank", "context_builder"]
        
        elif intent == AgentIntent.SUMMARIZATION:
            # 요약 → 하이브리드 검색으로 광범위한 자료 수집
            return ["vector_search", "keyword_search", "deduplicate", "rerank", "context_builder"]
        
        elif intent == AgentIntent.WEB_SEARCH:
            # 🆕 인터넷 검색 → 인터넷 검색 + 컨텍스트 구성
            return ["internet_search", "context_builder"]
        
        else:
            # 기본 전략: 하이브리드 검색 + 리랭킹
            return ["vector_search", "keyword_search", "deduplicate", "rerank", "context_builder"]
    
    async def _execute_tool(
        self,
        tool_name: str,
        query: str,
        db_session: AsyncSession,
        keywords: List[str],
        constraints: AgentConstraints,
        chunks: List[SearchChunk],
        context: Optional[Dict[str, Any]]
    ) -> ToolResult:
        """도구 실행 헬퍼"""
        tool = self.tools[tool_name]
        
        if tool_name == "vector_search":
            tool_input = {
                "query": query,
                "db_session": db_session,
                "top_k": constraints.max_chunks,
                "similarity_threshold": constraints.similarity_threshold,
                "container_ids": constraints.container_ids,
                "document_ids": constraints.document_ids,
                "user_emp_no": context.get("user_emp_no") if context else None
            }
            reasoning = "의미 기반 유사 문서 검색"
        
        elif tool_name == "keyword_search":
            tool_input = {
                "query": query,
                "db_session": db_session,
                "keywords": keywords,
                "top_k": constraints.max_chunks,
                "container_ids": constraints.container_ids,
                "document_ids": constraints.document_ids,
                "user_emp_no": context.get("user_emp_no") if context else None
            }
            reasoning = "키워드 직접 매칭"
        
        elif tool_name == "fulltext_search":
            tool_input = {
                "query": query,
                "db_session": db_session,
                "tsquery_str": " | ".join(keywords) if keywords else None,
                "top_k": constraints.max_chunks,
                "container_ids": constraints.container_ids,
                "document_ids": constraints.document_ids,
                "user_emp_no": context.get("user_emp_no") if context else None
            }
            reasoning = "PostgreSQL 전문검색"
        
        elif tool_name == "internet_search":
            tool_input = {
                "query": query,
                "top_k": 5  # 인터넷 검색은 상위 5개만
            }
            reasoning = "외부 인터넷 검색 (DuckDuckGo)"
        
        elif tool_name == "multimodal_search":
            # 🆕 멀티모달 검색 (이미지 유사도)
            tool_input = {
                "image_data": context.get("image_data") if context else None,
                "query": query,
                "db_session": db_session,
                "top_k": context.get("top_k", 10) if context else 10,
                "container_ids": constraints.container_ids
            }
            reasoning = "CLIP 기반 이미지 유사도 검색"
        
        elif tool_name == "deduplicate":
            tool_input = {
                "chunks": chunks,
                "similarity_threshold": 0.95
            }
            reasoning = "중복 청크 제거"
        
        elif tool_name == "rerank":
            tool_input = {
                "chunks": chunks,
                "query": query,
                "top_k": constraints.max_chunks,
                "threshold": 0.3  # 🆕 관련성 임계값 (0.3 미만 제외)
            }
            reasoning = "LLM 기반 관련도 재평가"
        
        elif tool_name == "context_builder":
            tool_input = {
                "chunks": chunks,
                "max_tokens": constraints.max_tokens,
                "include_metadata": True,
                "format_style": "citation"
            }
            reasoning = "토큰 제한 내에서 컨텍스트 구성"
        
        else:
            tool_input = {}
            reasoning = f"{tool_name} 실행"
        
        result = await tool._arun(**tool_input)
        
        self._log_step(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=result,
            reasoning=reasoning
        )
        
        return result
    
    async def _extract_keywords(self, query: str) -> List[str]:
        """키워드 추출"""
        try:
            analysis = await self.nlp_service.analyze_text_for_search(query)
            return analysis.get("keywords", [])
        except Exception as e:
            logger.warning(f"형태소 분석 실패, 공백 분리 사용: {e}")
            return [w.strip() for w in query.split() if len(w.strip()) >= 2]
    
    async def generate_answer(
        self,
        query: str,
        context: str,
        intent: AgentIntent,
        history: List[Dict[str, str]] = []
    ) -> str:
        """
        답변 생성 (general.prompt 기반)
        
        Note: PPT 생성 관련 로직은 향후 별도 tool로 분리 예정
        - 현재: general.prompt의 모든 규칙 적용 (일반 답변 + PPT 모드 포함)
        - 향후: ppt_generator_tool 분리 후 Agent가 도구로 호출하는 구조로 변경
        """
        from pathlib import Path
        
        # 컨텍스트 없을 때 처리
        if not context or context.strip() == "":
            return "죄송합니다. 질문과 관련된 문서를 찾을 수 없습니다. 다른 키워드로 검색해 주세요."
        
        # 🆕 general.prompt 로드 (일반 채팅과 동일한 품질 보장)
        system_prompt = None
        try:
            # 현재 파일의 위치를 기준으로 상대 경로 계산
            current_dir = Path(__file__).parent  # backend/app/agents
            backend_dir = current_dir.parent.parent  # backend
            prompt_path = backend_dir / "prompts" / "general.prompt"
            
            if prompt_path.exists():
                system_prompt = prompt_path.read_text(encoding='utf-8').strip()
                logger.info(f"✅ Agent: general.prompt 로드 성공 ({prompt_path})")
            else:
                logger.warning(f"⚠️ general.prompt 파일 없음 ({prompt_path}), 기본 프롬프트 사용")
                system_prompt = "논문/문서 검색 전문가. 제공된 문서를 바탕으로 간결하게 답변."
        except Exception as e:
            logger.error(f"❌ general.prompt 로드 실패: {e}, 기본 프롬프트 사용")
            system_prompt = "논문/문서 검색 전문가. 제공된 문서를 바탕으로 간결하게 답변."
        
        # 참조 문서 개수 계산 (general.prompt의 참조문서 개수 확인 원칙 준수)
        doc_count = len([c for c in context.split('---') if c.strip()])
        
        # User 메시지 구성 (참조문서 개수 명시)
        user_message = f"""질문: {query}

참조 문서:
{context}

참조문서 개수: {doc_count}개

위 문서를 바탕으로 질문에 답변하세요. 출처는 (파일명) 형식으로 표기하세요."""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # 🆕 대화 히스토리 추가 (최근 5개 턴만 유지하여 토큰 절약)
        if history:
            # 시스템 프롬프트 다음에 히스토리 삽입
            # 히스토리는 [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}] 형태
            recent_history = history[-10:] # 최근 10개 메시지 (5턴)
            messages.extend(recent_history)
            logger.info(f"📚 대화 히스토리 {len(recent_history)}개 메시지 포함")
            
        messages.append({"role": "user", "content": user_message})
        
        # max_tokens 증가 (general.prompt의 상세 답변 지원을 위해)
        response = await self.ai_service.chat_completion(
            messages,
            max_tokens=2000,  # 800 → 2000 (일반 채팅과 동일하게 상세 답변 가능)
            temperature=0.3  # 낮은 temperature로 일관성 향상
        )
        return response.get("response", "답변 생성 실패")
    
    def _log_step(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: ToolResult,
        reasoning: str
    ):
        """실행 단계 로깅"""
        step = AgentStep(
            step_number=len(self._steps) + 1,
            tool_name=tool_name,
            tool_input={k: str(v)[:100] for k, v in tool_input.items()},  # 긴 값 자르기
            tool_output=tool_output,
            reasoning=reasoning
        )
        self._steps.append(step)
    
    async def _validate_search_quality(self, chunks: List[SearchChunk], query: str) -> List[SearchChunk]:
        """
        검색 결과 품질 검증 (LLM 평가)
        
        각 청크가 질문에 답변하는데 유용한지 1-5점으로 평가하고,
        2점 이하인 청크는 제외합니다.
        """
        if not chunks:
            return []
            
        # 비용 절감을 위해 상위 5개만 검증
        candidates = chunks[:5]
        
        if not candidates:
            return chunks
            
        try:
            # 검증 프롬프트
            chunks_text = "\n\n".join([
                f"문서 {i+1}:\n{chunk.content[:500]}"
                for i, chunk in enumerate(candidates)
            ])
            
            prompt = f"""질문: "{query}"

다음 문서들이 질문에 답변하는데 얼마나 유용한지 평가하세요.

문서들:
{chunks_text}

지시사항:
1. 각 문서에 대해 1~5점 척도로 평가하세요 (1: 전혀 무관, 5: 매우 유용).
2. 답변 형식: 문서번호:점수 (예: 1:5, 2:3, 3:1)
3. 점수만 반환하세요.

평가:"""
            
            messages = [
                {"role": "user", "content": prompt}
            ]
            
            response = await self.ai_service.chat_completion(
                messages,
                max_tokens=100,
                temperature=0.0
            )
            
            content = response.get("response", "")
            logger.debug(f"🔍 품질 검증 응답: {content}")
            
            import re
            matches = re.findall(r'(\d+)\s*:\s*(\d+)', content)
            
            valid_indices = set()
            for idx_str, score_str in matches:
                idx = int(idx_str) - 1
                score = int(score_str)
                
                if score > 2:  # 2점 초과 (3, 4, 5)만 허용
                    valid_indices.add(idx)
                else:
                    logger.info(f"   ✂️ 품질 미달 문서 제외: {idx+1}번 (점수 {score})")
            
            validated_chunks = []
            for i, chunk in enumerate(candidates):
                if i in valid_indices:
                    validated_chunks.append(chunk)
            
            logger.info(f"✅ 품질 검증 완료: {len(candidates)}개 중 {len(validated_chunks)}개 통과")
            
            # 만약 검증 후 0개가 되면 최상위 1개 유지 (안전장치)
            if not validated_chunks and candidates:
                logger.warning("⚠️ 모든 문서가 품질 기준 미달. 최상위 1개 유지.")
                return [candidates[0]]
                
            return validated_chunks
            
        except Exception as e:
            logger.error(f"❌ 품질 검증 실패: {e}")
            return chunks  # 실패 시 원본 반환


# 전역 인스턴스
paper_search_agent = PaperSearchAgent()
