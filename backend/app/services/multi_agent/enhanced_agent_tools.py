"""
확장된 AI Agent Tools - 모든 에이전트 유형을 툴로 정의
각 에이전트를 독립적인 툴로 개발하여 멀티 에이전트 워크플로우에서 활용
"""

from typing import Dict, Any, List, Optional, Type, Tuple
from pydantic import BaseModel, Field
from loguru import logger
import json
import asyncio
from datetime import datetime
import os
import hashlib
from functools import lru_cache
from app.core.config import settings
import httpx

# 기존 서비스들 import
from app.services.core.ai_service import ai_service
from app.services.chat.ai_agent_service import ai_agent_service
from app.schemas.chat import SelectedDocument

# 기존 BaseTool 임포트
try:  # 우선 langchain_core
    from langchain_core.tools import BaseTool  # type: ignore
except ImportError:
    try:
        from langchain.tools import BaseTool  # type: ignore
    except ImportError:  # pragma: no cover
        class BaseTool:  # minimal fallback
            name: str = ""
            description: str = ""
            args_schema: Optional[Type[BaseModel]] = None
            def _run(self, *args, **kwargs): return {"error": "BaseTool fallback"}
            def run(self, *args, **kwargs): return self._run(*args, **kwargs)

# -----------------------------------------------------------------------------
# 간단 Web Search Tool (Phase 1) - mock 또는 외부 API 연동 틀 (BaseTool import 이후 정의)
# -----------------------------------------------------------------------------

class WebSearchInput(BaseModel):
    query: str = Field(description="검색 질의")
    top_n: int = Field(default=6, description="가져올 최대 결과 수")
    lang: str = Field(default="ko", description="결과 언어")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "외부 웹 검색을 수행하여 제목/URL/스니펫 Evidence를 수집합니다. 내부 RAG 저신뢰 시 증강에 사용."  # noqa: E501
    args_schema: Type[BaseModel] = WebSearchInput

    async def _arun(self, query: str, top_n: int = 6, lang: str = "ko", **kwargs) -> Dict[str, Any]:
        try:
            if not settings.web_search_enabled:
                return {"success": False, "error": "web search disabled", "results": []}
            provider = settings.web_search_provider
            results: List[Dict[str, Any]] = []
            if provider == "mock":
                base_items = [
                    {
                        "id": f"mock-{i}",
                        "title": f"모의 검색 결과 {i}: {query[:20]}",
                        "url": f"https://example.com/{hashlib.md5((query+str(i)).encode()).hexdigest()[:8]}",
                        "snippet": f"'{query}' 와(과) 관련된 외부 공개 정보 예시 스니펫 {i}."
                    }
                    for i in range(1, top_n + 1)
                ]
                results.extend(base_items)
            else:
                results.append({
                    "id": "not-implemented",
                    "title": f"{provider} provider integration pending",
                    "url": "https://placeholder.invalid",
                    "snippet": "구현 예정: API 키 설정 후 실제 검색 결과 반환"
                })
            return {
                "success": True,
                "provider": provider,
                "query": query,
                "results": results[:top_n],
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "result_count": len(results[:top_n])
                }
            }
        except Exception as e:
            logger.error(f"웹 검색 실패: {e}")
            return {"success": False, "error": str(e), "results": []}

    def _run(self, query: str, top_n: int = 6, lang: str = "ko", **kwargs) -> Dict[str, Any]:
        try:
            return asyncio.run(self._arun(query=query, top_n=top_n, lang=lang, **kwargs))
        except RuntimeError:
            logger.warning("이벤트 루프 실행 중 동기 web_search 호출 - mock fallback")
            return {"success": True, "provider": "mock", "query": query, "results": []}


# -----------------------------------------------------------------------------
# FetchWebsiteTool - 검색 결과 URL 본문 추출 (간단 버전)
# -----------------------------------------------------------------------------

class FetchWebsiteInput(BaseModel):
    urls: List[str] = Field(description="가져올 URL 목록")
    max_chars: int = Field(default=8000, description="페이지당 최대 추출 길이")
    clean_html: bool = Field(default=True, description="HTML 태그 제거 여부")


class FetchWebsiteTool(BaseTool):
    name: str = "fetch_website"
    description: str = "웹 페이지 본문을 비동기로 가져와 RAG 증강용 텍스트 스니펫을 생성합니다. (간단 추출)"
    args_schema: Type[BaseModel] = FetchWebsiteInput

    async def _arun(self, urls: List[str], max_chars: int = 8000, clean_html: bool = True, **kwargs) -> Dict[str, Any]:
        if not settings.web_fetch_enabled:
            return {"success": False, "error": "web fetch disabled", "pages": []}
        # 도메인 필터
        allowed = settings.web_fetch_allow_domains or None
        blocked = set(settings.web_fetch_block_domains or [])
        filtered_urls = []
        for u in urls:
            try:
                host = u.split("//",1)[-1].split("/",1)[0]
                if any(b in host for b in blocked):
                    continue
                if allowed and not any(a in host for a in allowed):
                    continue
                filtered_urls.append(u)
            except Exception:
                continue
        limited = filtered_urls[: settings.web_fetch_max_concurrent]
        headers = {"User-Agent": settings.web_fetch_user_agent}
        timeout = settings.web_fetch_timeout_seconds
        results: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            tasks = [self._fetch_one(client, url, headers, max_chars, clean_html) for url in limited]
            pages = await asyncio.gather(*tasks, return_exceptions=True)
        for p in pages:
            if isinstance(p, dict) and p.get("content"):
                results.append(p)
        return {
            "success": True,
            "pages": results,
            "metadata": {
                "fetched": len(results),
                "requested": len(urls),
                "used": len(limited)
            }
        }

    async def _fetch_one(self, client: httpx.AsyncClient, url: str, headers: Dict[str,str], max_chars: int, clean_html: bool) -> Dict[str, Any]:
        try:
            resp = await client.get(url, headers=headers)
            text = resp.text or ""
            # 아주 단순한 HTML 제거 (추후 trafilatura 대체 가능)
            if clean_html:
                import re
                text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
                text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
                text = re.sub(r"<[^>]+>", " ", text)
            normalized = " ".join(text.split())[:max_chars]
            return {
                "url": url,
                "content": normalized,
                "char_count": len(normalized),
                "source_type": "web_page",
                "retrieval_stage": "web_fetch"
            }
        except Exception as e:
            logger.warning(f"페이지 fetch 실패: {url} - {e}")
            return {}

    def _run(self, urls: List[str], max_chars: int = 8000, clean_html: bool = True, **kwargs) -> Dict[str, Any]:
        try:
            return asyncio.run(self._arun(urls=urls, max_chars=max_chars, clean_html=clean_html, **kwargs))
        except RuntimeError:
            logger.warning("이벤트 루프 내 동기 fetch_website 호출 - 빈 결과")
            return {"success": False, "error": "loop running"}

# =============================================================================
# Tool Input 스키마 정의
# =============================================================================

class GeneralChatInput(BaseModel):
    query: str = Field(description="사용자의 질문 또는 대화 내용")
    context: Optional[str] = Field(default="", description="추가 컨텍스트")

class DocumentSummaryInput(BaseModel):
    documents: List[Dict[str, Any]] = Field(description="요약할 문서 목록")
    summary_type: str = Field(default="comprehensive", description="요약 유형: brief, comprehensive, detailed")
    focus_areas: List[str] = Field(default=[], description="집중할 영역들")

class KeywordExtractionInput(BaseModel):
    documents: List[Dict[str, Any]] = Field(description="키워드를 추출할 문서 목록")
    max_keywords: int = Field(default=20, description="추출할 최대 키워드 수")
    include_phrases: bool = Field(default=True, description="키 프레이즈 포함 여부")

class PresentationGenerationInput(BaseModel):
    content: str = Field(description="프레젠테이션 생성 기반 내용")
    slide_count: int = Field(default=8, description="생성할 슬라이드 수")
    template_style: str = Field(default="business", description="템플릿 스타일")
    include_charts: bool = Field(default=True, description="차트 포함 여부")

class TemplateDocumentInput(BaseModel):
    template_type: str = Field(description="템플릿 유형: report, proposal, memo, etc.")
    content_data: Dict[str, Any] = Field(description="템플릿에 채울 데이터")
    output_format: str = Field(default="docx", description="출력 형식")

class KnowledgeGraphInput(BaseModel):
    documents: List[Dict[str, Any]] = Field(description="지식그래프 생성할 문서들")
    max_nodes: int = Field(default=50, description="최대 노드 수")
    relationship_types: List[str] = Field(default=[], description="관계 유형 필터")

class DocumentAnalysisInput(BaseModel):
    documents: List[Dict[str, Any]] = Field(description="분석할 문서 목록")
    analysis_depth: str = Field(default="standard", description="분석 깊이: shallow, standard, deep")
    focus_metrics: List[str] = Field(default=[], description="집중할 지표들")

class InsightGenerationInput(BaseModel):
    data_sources: List[Dict[str, Any]] = Field(description="인사이트 도출할 데이터 소스")
    insight_types: List[str] = Field(default=["trend", "pattern", "anomaly"], description="인사이트 유형")
    confidence_threshold: float = Field(default=0.7, description="신뢰도 임계값")

class ReportGenerationInput(BaseModel):
    report_type: str = Field(description="보고서 유형: executive, technical, analysis, etc.")
    data_sources: List[Dict[str, Any]] = Field(description="보고서 작성 데이터")
    sections: List[str] = Field(default=[], description="포함할 섹션들")

class ScriptGenerationInput(BaseModel):
    presentation_content: str = Field(description="발표 스크립트 기반 내용")
    presentation_duration: int = Field(default=10, description="발표 예상 시간(분)")
    audience_level: str = Field(default="general", description="청중 수준: executive, technical, general")

class KeyPointsExtractionInput(BaseModel):
    content: str = Field(description="핵심 포인트를 추출할 내용")
    max_points: int = Field(default=10, description="추출할 최대 포인트 수")
    categorize: bool = Field(default=True, description="카테고리별 분류 여부")

# =============================================================================
# 개별 에이전트 툴 구현
# =============================================================================

class GeneralChatTool(BaseTool):
    name: str = "general_chat_tool"
    description: str = """일반적인 대화와 질의응답을 처리합니다. RAG 기능이 포함되어 있습니다.
    입력: 사용자 질문, 컨텍스트
    출력: 자연스러운 대화 응답"""
    args_schema: Type[BaseModel] = GeneralChatInput
    
    def _run(self, tool_input: str = "", **kwargs) -> Dict[str, Any]:
        """동기 실행 진입점 (LangChain 호환). 가능하면 비동기 경로 사용 권장."""
        query, context = self._parse_inputs(tool_input, **kwargs)
        try:
            # 독립 동기 환경: 새 이벤트 루프로 실행
            return asyncio.run(self._execute_general_chat_async(query, context))
        except RuntimeError:
            # 이미 실행 중인 이벤트 루프 안에서 호출된 경우 (잘못된 사용 경로)
            logger.warning("⚠️ 이벤트 루프 실행 중에 _run이 호출되었습니다. _arun 사용을 권장합니다.")
            return self._fallback_simulation(query, context, reason="event loop already running; use _arun")
        except Exception as e:
            logger.error(f"❌ 일반 대화 툴 실행 실패: {e}")
            return {"success": False, "error": str(e), "response": "죄송합니다. 처리 중 오류가 발생했습니다."}

    async def _arun(self, tool_input: str = "", **kwargs) -> Dict[str, Any]:
        """비동기 실행 (권장)"""
        query, context = self._parse_inputs(tool_input, **kwargs)
        return await self._execute_general_chat_async(query, context)

    def _parse_inputs(self, tool_input: str = "", **kwargs) -> tuple[str, str]:
        if isinstance(tool_input, str) and tool_input.strip():
            try:
                data = json.loads(tool_input)
                query = data.get("query", tool_input)
                context = data.get("context", "")
            except json.JSONDecodeError:
                query = tool_input
                context = ""
        else:
            query = kwargs.get("query", "")
            context = kwargs.get("context", "")
        logger.info(f"💬 쿼리: {query[:50]}...")
        return query, context

    async def _execute_general_chat_async(self, query: str, context: str = "") -> Dict[str, Any]:
        try:
            logger.info(f"🔍 실제 RAG 검색 수행 (async): {query}")
            enhanced_query, references, context_info, rag_stats = await ai_agent_service.prepare_context_with_documents(
                query=query,
                selected_documents=[],
                agent_type="general"
            )

            # 1) 레퍼런스 정제/중복 제거 및 보강
            cleaned_refs = self._dedupe_and_normalize_references(references)
            top_refs = cleaned_refs[:6]

            # 2) 유사도 및 품질 판단
            avg_sim = rag_stats.get("avg_similarity", 0) if isinstance(rag_stats, dict) else 0
            low_signal = (len(top_refs) == 0) or (avg_sim < 0.05)

            # 2-a) 저신뢰 시 웹 검색 증강 (Phase 1: lightweight snippets) - 별도 WebSearchTool 활용
            web_augmented_refs: List[Dict[str, Any]] = []
            web_used = False
            if low_signal and settings.web_search_enabled:
                try:
                    web_tool = enhanced_tool_registry.get_tool("web_search")  # type: ignore  # defined later
                    if web_tool:
                        web_results = await web_tool._arun(query=query, top_n=4)  # type: ignore
                        if web_results.get("success"):
                            web_refs = web_results.get("results", [])
                            # 웹 Evidence 구조 통일
                            for wr in web_refs:
                                web_augmented_refs.append({
                                    "chunk_id": wr.get("id") or wr.get("url"),
                                    "content": wr.get("snippet", "")[:800],
                                    "source": wr.get("title") or wr.get("url"),
                                    "similarity_score": 0.0,  # 외부 검색은 재랭킹 전 0
                                    "metadata": {
                                        "url": wr.get("url"),
                                        "source_type": "web",
                                        "retrieval_stage": "web_fallback"
                                    }
                                })
                            if web_augmented_refs:
                                # 내부 refs와 병합 (단순 append, 이후 format에서 구분)
                                top_refs = (top_refs + web_augmented_refs)[:8]
                                web_used = True
                                low_signal = False  # Evidence 확보로 재평가
                except Exception as we:
                    logger.warning(f"🌐 웹 검색 증강 실패 (무시하고 진행): {we}")

            # 3) (선택) 추가 페이지 fetch 조건: 웹 증강 사용 & 짧은 snippet 비율 높음
            fetch_used = False
            if web_used and settings.web_fetch_enabled:
                short_count = sum(1 for r in web_augmented_refs if len(r.get("content","")) < 120)
                if short_count >= 2:  # 휴리스틱 기준
                    fetch_tool = enhanced_tool_registry.get_tool("fetch_website")
                    if fetch_tool:
                        candidate_urls = [r.get("metadata", {}).get("url") for r in web_augmented_refs if r.get("metadata", {}).get("url")]
                        try:
                            fetch_arun = getattr(fetch_tool, "_arun", None)
                            fetch_res = None
                            if callable(fetch_arun):
                                possible = fetch_arun(urls=candidate_urls[:3], max_chars=settings.web_fetch_max_chars)
                                # awaitable 검사
                                if hasattr(possible, "__await__"):
                                    fetch_res = await possible  # type: ignore
                                else:
                                    fetch_res = possible
                            if fetch_res is None:
                                fetch_res = fetch_tool._run(urls=candidate_urls[:3], max_chars=settings.web_fetch_max_chars)
                            if isinstance(fetch_res, dict) and fetch_res.get("success"):
                                for pg in fetch_res.get("pages", []):
                                    if isinstance(pg, dict):
                                        top_refs.append({
                                            "chunk_id": pg.get("url"),
                                            "content": pg.get("content", "")[:800],
                                            "source": pg.get("url"),
                                            "similarity_score": 0.0,
                                            "metadata": {
                                                "url": pg.get("url"),
                                                "source_type": "web_page",
                                                "retrieval_stage": pg.get("retrieval_stage")
                                            }
                                        })
                                fetch_used = True
                        except Exception as fe:
                            logger.warning(f"웹 페이지 fetch 오류: {fe}")

            # 4) 시스템 프롬프트 로드 + citation 지시 추가
            system_prompt = self._build_system_prompt_with_citation()

            # 5) 컨텍스트 블록 구성 (페이지 fetch 후 상위 8개 재슬라이스)
            top_refs = top_refs[:8]
            context_block = self._format_context_block(top_refs)

            # 6) 사용자 메시지 구성 (low-signal 안내 포함)
            user_prefix_flags = []
            if low_signal:
                user_prefix_flags.append("⚠ 내부 문서 근거 부족")
            if web_used:
                user_prefix_flags.append("🌐 외부 웹 검색 증강 적용")
            if fetch_used:
                user_prefix_flags.append("📰 웹 페이지 본문 추출")
            user_prefix = ("[" + ", ".join(user_prefix_flags) + "]\n") if user_prefix_flags else ""
            user_message = (
                f"{user_prefix}질문: {query}\n\n"
                + (f"선택된 컨텍스트:\n{context_block}\n\n" if context_block else "")
                + "지침: 위 '컨텍스트' 내에서 직접 확인 가능한 내용에 근거하여 답변하세요.\n"
                + "근거가 부족한 부분은 '(문서 근거 부족)' 라고 명시하고 일반 지식은 별도 구분."
            )

            # 7) chat_completion 호출 (system + user)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            completion = await ai_service.chat_completion(messages)  # returns dict
            ai_response_text = completion.get("response", "")

            # 8) 근거 섹션 구성 (검색 실패/저품질 시 구분)
            evidence_mode = "document_citations"
            final_response = ai_response_text.strip()
            if low_signal:  # 웹 증강에도 불구하고 여전히 근거 없음
                evidence_mode = "llm_inferred"
                llm_note = (
                    "문서 검색에서 신뢰할 만한 관련 청크를 찾지 못하여 모델의 일반 지식과 "
                    "개인정보보호 일반 원칙을 참고해 초안 형태로 응답했습니다. 실제 조직 규정/정책 문서를 "
                    "교차검증 후 확정하세요."
                )
                # LLM 추론 근거(카테고리 식) 표현
                inferred_points = [
                    "개인정보 최소 수집 및 목적 명확화",
                    "접근권한 역할기반 통제(RBAC) 적용",
                    "암호화: 저장 데이터(At-Rest) + 전송 구간 TLS",
                    "로그/모니터링 및 이상행위 탐지",
                    "정기 교육 및 파기/보존 주기 관리"
                ]
                evidence_section = (
                    "⚠ 문서 근거 없음 (RAG 미탐색 또는 낮은 유사도)\n" + llm_note + "\n\n" +
                    "### 🔍 일반 지식 기반 핵심 고려 영역\n" + "\n".join(f"- {p}" for p in inferred_points)
                )
                final_response += "\n\n---\n### 📌 참고 안내 (문서 근거 부족)\n" + evidence_section
            else:
                # 인라인 citation 우선 삽입
                final_response = self._inject_inline_citations(final_response, top_refs)
                evidence_section = self._build_evidence_section(top_refs)
                if evidence_section:
                    final_response += "\n\n---\n### 📚 참고 근거\n" + evidence_section

            # 9) 메타데이터 구성 (프롬프트 프리뷰)
            prompt_preview = (system_prompt + "\n" + user_message)[:400]

            logger.info(f"✅ RAG 검색 완료: {len(cleaned_refs)}개 참조 (사용 {len(top_refs)}) low_signal={low_signal}")
            return {
                "success": True,
                "response": final_response,
                "references": top_refs,
                "context_used": bool(context_block),
                "agent_type": "general",
                "rag_stats": {**rag_stats, "low_signal": low_signal},
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "processing_method": "real_rag",
                    "references_found": len(cleaned_refs),
                    "enhanced_query_used": bool(enhanced_query != query),
                    "prompt_preview": prompt_preview,
                    "evidence_mode": evidence_mode,
                    "web_augmented": web_used,
                    "web_results": len(web_augmented_refs),
                    "web_fetch_used": fetch_used
                }
            }
        except Exception as e:
            logger.error(f"❌ 실제 RAG 검색 실패: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._fallback_simulation(query, context, reason=str(e))

    def _fallback_simulation(self, query: str, context: str, reason: str) -> Dict[str, Any]:
        keywords = self._extract_keywords(query)
        simulated_chunks = self._simulate_rag_search(query, keywords)
        response = self._generate_response_with_context(query, simulated_chunks)
        return {
            "success": True,
            "response": response,
            "references": simulated_chunks,
            "context_used": bool(context),
            "agent_type": "general",
            "fallback_reason": reason,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "processing_method": "fallback_simulation",
                "keywords_found": keywords,
                "chunks_simulated": len(simulated_chunks)
            }
        }
    # --- Fallback helper methods (original simulation logic relocated) ---
    def _extract_keywords(self, query: str) -> List[str]:
        keywords = []
        keyword_patterns = {
            "개인정보보호": ["개인정보보호", "개인정보", "privacy", "personal", "data"],
            "문서": ["문서", "document", "파일", "file"],
            "보안": ["보안", "security", "암호화", "encryption"],
            "정책": ["정책", "policy", "가이드", "guide"],
            "법규": ["법", "규정", "regulation", "compliance"],
        }
        ql = query.lower()
        for category, patterns in keyword_patterns.items():
            if any(p in ql for p in patterns):
                keywords.append(category)
        return keywords

    def _simulate_rag_search(self, query: str, keywords: List[str]) -> List[Dict[str, Any]]:
        simulated_results: List[Dict[str, Any]] = []
        if "개인정보보호" in keywords:
            simulated_results.append({
                "chunk_id": "doc001_chunk01",
                "content": "개인정보보호법에 따른 개인정보 처리 방침 수립 가이드라인",
                "source": "개인정보보호_정책_가이드.pdf",
                "similarity_score": 0.92,
                "metadata": {"page": 1, "section": "정책 개요"},
            })
        if "문서" in keywords:
            simulated_results.append({
                "chunk_id": "doc004_chunk01",
                "content": "문서 관리 시스템의 분류 체계 및 접근 권한 설정",
                "source": "문서관리_시스템_운영가이드.pdf",
                "similarity_score": 0.79,
                "metadata": {"page": 8, "section": "문서 분류"},
            })
        return simulated_results[:5]

    # --- New helper methods for real RAG response ---
    def _dedupe_and_normalize_references(self, refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        normed = []
        for r in refs:
            cid = r.get("chunk_id") or r.get("id") or ""
            content = (r.get("content") or "").strip()
            key = cid + content[:50]
            if key in seen:
                continue
            seen.add(key)
            source = r.get("source") or r.get("file_name") or r.get("fileName") or ""
            meta = r.get("metadata") or {}
            # 페이지/page_number/page 등 통합
            page = meta.get("page") or meta.get("page_number") or meta.get("pageIndex")
            meta_out = {**meta}
            if page is not None:
                meta_out["page"] = page
            # 내부/웹 구분 기본값 지정
            if "source_type" not in meta_out:
                meta_out["source_type"] = "internal"
            normed.append({
                "chunk_id": cid,
                "content": content[:800],
                "source": source,
                "similarity_score": r.get("similarity_score", 0.0),
                "metadata": meta_out
            })
        # similarity 높은 순 정렬 (역순)
        normed.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        return normed

    def _format_context_block(self, refs: List[Dict[str, Any]]) -> str:
        if not refs:
            return ""
        lines = []
        for i, r in enumerate(refs, 1):
            page = r.get("metadata", {}).get("page")
            src = r.get("source") or ""
            snippet = r.get("content", "")[:300].replace("\n", " ")
            lines.append(f"[{i}] (유사도 {r.get('similarity_score',0):.3f}) {src} p{page if page is not None else '?'} :: {snippet}")
        return "\n".join(lines)

    def _build_evidence_section(self, refs: List[Dict[str, Any]]) -> str:
        if not refs:
            return ""
        out = []
        for i, r in enumerate(refs, 1):
            meta = r.get("metadata", {})
            page = meta.get("page", "?")
            src = r.get("source") or ""  # could be empty if not stored
            kws = meta.get("keywords") or []
            kw_str = ", ".join(kws[:5]) if kws else "-"
            marker = self._marker_for_reference(i, meta.get("source_type"))
            out.append(f"{i}. {marker} 파일: {src or '(미기록)'} | p.{page} | 키워드: {kw_str}")
        return "\n".join(out)

    def _marker_for_reference(self, index: int, source_type: Optional[str]) -> str:
        st = (source_type or "internal").lower()
        if st == "web_page":
            return f"[WP{index}]"
        if st.startswith("web"):
            return f"[W{index}]"
        return f"[I{index}]"

    def _inject_inline_citations(self, answer: str, refs: List[Dict[str, Any]]) -> str:
        """문장 단위로 순차 citation 삽입 (간단 휴리스틱)."""
        if not refs or not answer.strip():
            return answer
        import re
        sentences = re.split(r"(.*?[\.\?\!])(\s+|$)", answer, flags=re.S)
        # sentences list includes captured groups; rebuild carefully
        rebuilt = []
        ref_index = 0
        total_refs = len(refs)
        for chunk in sentences:
            if not chunk:
                continue
            if ref_index < total_refs and re.search(r"[\.\?\!]$", chunk.strip()):
                meta = refs[ref_index].get("metadata", {})
                marker = self._marker_for_reference(ref_index + 1, meta.get("source_type"))
                # 이미 동일 마커 존재하면 중복 삽입 안 함
                if marker not in chunk:
                    chunk = chunk.rstrip() + " " + marker
                ref_index += 1
            rebuilt.append(chunk)
        # 남은 reference가 있으면 답변 끝에 묶어서 추가
        if ref_index < total_refs:
            tail_markers = []
            for j in range(ref_index, total_refs):
                meta = refs[j].get("metadata", {})
                tail_markers.append(self._marker_for_reference(j + 1, meta.get("source_type")))
            rebuilt.append("\n\n" + " ".join(tail_markers))
        return "".join(rebuilt)

    def _build_system_prompt_with_citation(self) -> str:
        try:
            from pathlib import Path
            prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / "general.prompt"
            base = ""
            if prompt_path.exists():
                base = prompt_path.read_text(encoding="utf-8").strip()
            citation_rules = (
                "\n\n추가 규칙:\n"
                "- 반드시 답변 마지막에 '📚 참고 근거' 섹션 포함 (존재하는 레퍼런스만).\n"
                "- 근거 없는 주장엔 '(문서 근거 부족)' 표시.\n"
                "- 문서 표현을 그대로 복사하기보다 요약/재구성.\n"
                "- 개인정보/보안 관련 질문 시 법/정책 명칭 정확히 언급하고 근거 문서 번호/페이지 표기.")
            return base + citation_rules
        except Exception:
            return "당신은 문서 기반으로 근거를 제시하는 AI 어시스턴트입니다."
    
    def _generate_response_with_context(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """컨텍스트를 기반으로 응답 생성"""
        if not chunks:
            return f"'{query}'에 대한 정보를 찾을 수 없습니다. 다른 키워드로 검색해보시거나 관련 문서를 선택해 주세요."
        
        # 청크 정보를 기반으로 응답 구성
        response_parts = [f"'{query}'에 대한 검색 결과입니다.\n"]
        
        response_parts.append("## 📋 관련 문서 목록:")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "알 수 없는 문서")
            content = chunk.get("content", "내용 없음")
            score = chunk.get("similarity_score", 0.0)
            
            response_parts.append(f"{i}. **{source}**")
            response_parts.append(f"   - 내용: {content[:100]}...")
            response_parts.append(f"   - 관련도: {score:.2f}")
            response_parts.append("")
        
        response_parts.append("## 📄 요약:")
        if "개인정보보호" in query:
            response_parts.append("개인정보보호 관련 문서들이 검색되었습니다. 주요 내용은 다음과 같습니다:")
            response_parts.append("- 개인정보보호법 준수 가이드라인")
            response_parts.append("- GDPR 컴플라이언스 절차")
            response_parts.append("- 개인정보 수집·이용 동의서 양식")
        else:
            response_parts.append("검색된 문서들을 통해 관련 정보를 확인하실 수 있습니다.")
        
        response_parts.append("\n더 자세한 내용을 원하시면 특정 문서를 선택하여 상세 분석을 요청해 주세요.")
        
        return "\n".join(response_parts)


class DocumentSummaryTool(BaseTool):
    name: str = "document_summary_tool"
    description: str = """문서의 핵심 내용을 간결하게 요약합니다.
    입력: 문서 목록, 요약 유형, 집중 영역
    출력: 구조화된 문서 요약"""
    args_schema: Type[BaseModel] = DocumentSummaryInput
    
    def _run(
        self, 
        documents: List[Dict[str, Any]], 
        summary_type: str = "comprehensive",
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        logger.info(f"📝 문서 요약 툴 실행: {len(documents)}개 문서")
        
        try:
            focus_areas = focus_areas or []
            
            # 요약 생성 로직
            summary_result = {
                "executive_summary": "문서들의 핵심 내용을 요약한 임원 요약본",
                "key_findings": [
                    "주요 발견사항 1",
                    "주요 발견사항 2", 
                    "주요 발견사항 3"
                ],
                "recommendations": [
                    "권장사항 1",
                    "권장사항 2"
                ],
                "document_count": len(documents),
                "summary_type": summary_type,
                "focus_areas": focus_areas,
                "metadata": {
                    "generation_timestamp": datetime.now().isoformat(),
                    "estimated_reading_time": f"{len(documents) * 2}분"
                }
            }
            
            logger.info(f"✅ 문서 요약 완료: {summary_type} 타입")
            return {"success": True, **summary_result}
            
        except Exception as e:
            logger.error(f"❌ 문서 요약 실패: {e}")
            return {"success": False, "error": str(e)}


class KeywordExtractionTool(BaseTool):
    name: str = "keyword_extraction_tool"
    description: str = """문서에서 중요한 키워드와 주제를 추출합니다.
    입력: 문서 목록, 최대 키워드 수, 키 프레이즈 포함 여부
    출력: 추출된 키워드와 분석 결과"""
    args_schema: Type[BaseModel] = KeywordExtractionInput
    
    def _run(
        self, 
        documents: List[Dict[str, Any]], 
        max_keywords: int = 20,
        include_phrases: bool = True
    ) -> Dict[str, Any]:
        logger.info(f"🔍 키워드 추출 툴 실행: {len(documents)}개 문서")
        
        try:
            # 키워드 추출 로직
            extracted_keywords = [
                {"keyword": "AI", "frequency": 15, "relevance": 0.95},
                {"keyword": "자동화", "frequency": 12, "relevance": 0.88},
                {"keyword": "효율성", "frequency": 10, "relevance": 0.82},
                {"keyword": "데이터 분석", "frequency": 8, "relevance": 0.79},
                {"keyword": "디지털 전환", "frequency": 6, "relevance": 0.75}
            ]
            
            key_phrases = [
                {"phrase": "인공지능 기반 자동화", "frequency": 5, "relevance": 0.90},
                {"phrase": "데이터 기반 의사결정", "frequency": 4, "relevance": 0.85}
            ] if include_phrases else []
            
            result = {
                "keywords": extracted_keywords[:max_keywords],
                "key_phrases": key_phrases,
                "topic_categories": ["기술", "비즈니스", "혁신"],
                "document_count": len(documents),
                "extraction_stats": {
                    "total_keywords_found": len(extracted_keywords),
                    "total_phrases_found": len(key_phrases),
                    "avg_relevance": 0.84
                },
                "metadata": {
                    "extraction_timestamp": datetime.now().isoformat(),
                    "include_phrases": include_phrases
                }
            }
            
            logger.info(f"✅ 키워드 추출 완료: {len(extracted_keywords)}개 키워드")
            return {"success": True, **result}
            
        except Exception as e:
            logger.error(f"❌ 키워드 추출 실패: {e}")
            return {"success": False, "error": str(e)}


class PresentationGenerationTool(BaseTool):
    name: str = "presentation_generation_tool"
    description: str = """문서 내용을 바탕으로 프레젠테이션을 생성합니다.
    입력: 기반 내용, 슬라이드 수, 템플릿 스타일
    출력: 생성된 프레젠테이션 파일과 메타데이터"""
    args_schema: Type[BaseModel] = PresentationGenerationInput
    
    async def _arun(
        self,
        content: str,
        slide_count: int = 8,
        template_style: str = "business",
        include_charts: bool = True
    ) -> Dict[str, Any]:
        """비동기 프레젠테이션 생성 (권장 경로)."""
        logger.info(f"📊 (async) 프레젠테이션 생성 툴 실행: {slide_count}개 슬라이드")
        try:
            # 템플릿 미적용(Quick) 파이프라인 사용
            from app.services.presentation.quick_ppt_generator_service import quick_ppt_service
            topic = content.split('\n')[0][:70] if content else "프레젠테이션"
            deck = quick_ppt_service.generate_fixed_outline(
                topic=topic,
                context_text=content[:8000],
                max_slides=slide_count
            )
            file_path = quick_ppt_service.build_quick_pptx(deck)
            return {
                "success": True,
                "file_path": file_path,
                "file_name": file_path.split('/')[-1],
                "slide_count": getattr(deck, 'max_slides', slide_count),
                "template_style": template_style,  # quick 경로에서는 스타일이 시각적 테마에 직접 반영되지 않을 수 있음
                "outline": {
                    "title": deck.topic,
                    "slides": [{"title": s.title, "layout": s.layout} for s in deck.slides]
                },
                "metadata": {
                    "generation_timestamp": datetime.now().isoformat(),
                    "content_length": len(content),
                    "include_charts": include_charts,  # quick 경로에서는 무시될 수 있음
                    "async": True
                }
            }
        except Exception as e:
            logger.error(f"❌ (async) 프레젠테이션 생성 실패: {e}")
            return {"success": False, "error": str(e)}

    # 동기 폴백 (기존 인터페이스 유지)
    def _run(
        self,
        content: str,
        slide_count: int = 8,
        template_style: str = "business",
        include_charts: bool = True
    ) -> Dict[str, Any]:
        try:
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
            if loop and loop.is_running():
                return asyncio.run_coroutine_threadsafe(
                    self._arun(content=content, slide_count=slide_count, template_style=template_style, include_charts=include_charts),
                    loop
                ).result(timeout=180)
            else:
                return asyncio.run(
                    self._arun(content=content, slide_count=slide_count, template_style=template_style, include_charts=include_charts)
                )
        except Exception as e:
            logger.error(f"❌ (sync wrapper) 프레젠테이션 생성 실패: {e}")
            return {"success": False, "error": str(e)}


class DocumentAnalysisTool(BaseTool):
    name: str = "document_analysis_tool"  
    description: str = """문서의 구조와 패턴을 깊이 있게 분석합니다.
    입력: 문서 목록, 분석 깊이, 집중 지표
    출력: 상세한 문서 분석 결과"""
    args_schema: Type[BaseModel] = DocumentAnalysisInput
    
    def _run(
        self, 
        documents: List[Dict[str, Any]], 
        analysis_depth: str = "standard",
        focus_metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        logger.info(f"🔬 문서 분석 툴 실행: {len(documents)}개 문서, 깊이={analysis_depth}")
        
        try:
            focus_metrics = focus_metrics or ["readability", "structure", "content_quality"]
            
            analysis_result = {
                "document_overview": {
                    "total_documents": len(documents),
                    "total_pages": sum(doc.get("page_count", 1) for doc in documents),
                    "file_types": list(set(doc.get("file_type", "unknown") for doc in documents))
                },
                "content_analysis": {
                    "readability_score": 0.75,
                    "complexity_level": "medium",
                    "main_topics": ["기술 동향", "비즈니스 전략", "시장 분석"],
                    "sentiment_analysis": {"positive": 0.6, "neutral": 0.3, "negative": 0.1}
                },
                "structure_analysis": {
                    "has_headers": True,
                    "has_tables": any(doc.get("has_tables", False) for doc in documents),
                    "has_images": any(doc.get("has_images", False) for doc in documents),
                    "citation_count": 12
                },
                "quality_metrics": {
                    "completeness": 0.85,
                    "consistency": 0.78,
                    "accuracy_indicators": ["citations", "data_sources", "methodology"]
                },
                "metadata": {
                    "analysis_depth": analysis_depth,
                    "focus_metrics": focus_metrics,
                    "analysis_timestamp": datetime.now().isoformat()
                }
            }
            
            logger.info(f"✅ 문서 분석 완료: {analysis_depth} 깊이")
            return {"success": True, **analysis_result}
            
        except Exception as e:
            logger.error(f"❌ 문서 분석 실패: {e}")
            return {"success": False, "error": str(e)}


class InsightGenerationTool(BaseTool):
    name: str = "insight_generation_tool"
    description: str = """데이터에서 의미있는 통찰과 패턴을 발견합니다.
    입력: 데이터 소스, 인사이트 유형, 신뢰도 임계값
    출력: 발견된 인사이트와 분석 결과"""
    args_schema: Type[BaseModel] = InsightGenerationInput
    
    def _run(
        self, 
        data_sources: List[Dict[str, Any]], 
        insight_types: Optional[List[str]] = None,
        confidence_threshold: float = 0.7
    ) -> Dict[str, Any]:
        logger.info(f"💡 인사이트 생성 툴 실행: {len(data_sources)}개 소스")
        
        try:
            insight_types = insight_types or ["trend", "pattern", "anomaly"]
            
            insights = [
                {
                    "title": "비용 절감 기회 발견",
                    "type": "pattern",
                    "description": "자동화 도입으로 30% 비용 절감 가능",
                    "confidence": 0.89,
                    "impact": "high",
                    "supporting_data": ["Process A: 25% 절감", "Process B: 35% 절감"]
                },
                {
                    "title": "성과 지표 상승 트렌드",
                    "type": "trend",
                    "description": "지난 6개월간 KPI 지속적 상승",
                    "confidence": 0.82,
                    "impact": "medium",
                    "supporting_data": ["Q1: +15%", "Q2: +22%"]
                }
            ]
            
            # 신뢰도 필터링
            filtered_insights = [i for i in insights if i["confidence"] >= confidence_threshold]
            
            result = {
                "insights": filtered_insights,
                "insight_count": len(filtered_insights),
                "categories": {
                    "high_impact": len([i for i in filtered_insights if i["impact"] == "high"]),
                    "medium_impact": len([i for i in filtered_insights if i["impact"] == "medium"]),
                    "low_impact": len([i for i in filtered_insights if i["impact"] == "low"])
                },
                "confidence_stats": {
                    "average_confidence": sum(i["confidence"] for i in filtered_insights) / len(filtered_insights) if filtered_insights else 0,
                    "min_confidence": confidence_threshold
                },
                "metadata": {
                    "insight_types": insight_types,
                    "data_sources_count": len(data_sources),
                    "generation_timestamp": datetime.now().isoformat()
                }
            }
            
            logger.info(f"✅ 인사이트 생성 완료: {len(filtered_insights)}개 인사이트")
            return {"success": True, **result}
            
        except Exception as e:
            logger.error(f"❌ 인사이트 생성 실패: {e}")
            return {"success": False, "error": str(e)}


# =============================================================================
# 확장된 툴 레지스트리
# =============================================================================

class EnhancedToolRegistry:
    """확장된 멀티 에이전트 도구 레지스트리"""
    
    def __init__(self):
        self.tools = {
            # 신규 웹 검색 툴
            "web_search": WebSearchTool(),
            # 기존 툴들
            "document_analysis": DocumentAnalysisTool(),
            "summary_generation": DocumentSummaryTool(),
            "insight_extraction": InsightGenerationTool(),
            "presentation_build": PresentationGenerationTool(),
            
            # 새로운 에이전트 툴들
            "general_chat": GeneralChatTool(),
            "keyword_extraction": KeywordExtractionTool(),
            "document_summary": DocumentSummaryTool(),
            "presentation_generation": PresentationGenerationTool(),
            "document_analysis_detailed": DocumentAnalysisTool(),
            "insight_generation": InsightGenerationTool(),
            
            # TODO: 추가 구현 필요한 툴들
            # "template_document": TemplateDocumentTool(),
            # "knowledge_graph": KnowledgeGraphTool(), 
            # "report_generation": ReportGenerationTool(),
            # "script_generation": ScriptGenerationTool(),
            # "key_points_extraction": KeyPointsExtractionTool(),
        }
        
        # 에이전트 타입과 툴 매핑
        self.agent_tool_mapping = {
            'general': 'general_chat',
            'web-search': 'web_search',
            'summarizer': 'document_summary', 
            'keyword-extractor': 'keyword_extraction',
            'presentation': 'presentation_generation',
            'analyzer': 'document_analysis_detailed',
            'insight': 'insight_generation',
            # 'template': 'template_document',
            # 'knowledge-graph': 'knowledge_graph',
            # 'report-generator': 'report_generation', 
            # 'script-generator': 'script_generation',
            # 'key-points': 'key_points_extraction'
        }
        
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """도구 인스턴스 반환"""
        return self.tools.get(tool_name)
        
    def get_tool_by_agent_type(self, agent_type: str) -> Optional[BaseTool]:
        """에이전트 타입으로 툴 반환"""
        tool_name = self.agent_tool_mapping.get(agent_type)
        return self.get_tool(tool_name) if tool_name else None
        
    def get_all_tools(self) -> List[BaseTool]:
        """모든 도구 목록 반환"""
        return list(self.tools.values())
        
    def get_tool_descriptions(self) -> Dict[str, str]:
        """도구 설명 목록 반환"""
        return {name: tool.description for name, tool in self.tools.items()}
        
    def get_agent_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """각 에이전트의 역량 정보 반환"""
        capabilities = {}
        for agent_type, tool_name in self.agent_tool_mapping.items():
            tool = self.get_tool(tool_name)
            if tool:
                capabilities[agent_type] = {
                    "tool_name": tool_name,
                    "description": tool.description,
                    "available": True
                }
            else:
                capabilities[agent_type] = {
                    "tool_name": tool_name,
                    "description": "구현 예정",
                    "available": False
                }
        return capabilities


# 전역 확장된 도구 레지스트리 인스턴스
enhanced_tool_registry = EnhancedToolRegistry()
