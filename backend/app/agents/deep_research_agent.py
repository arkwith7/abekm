"""Deep Research agent.

Implements an agentic RAG workflow (plan -> retrieve (web+internal) -> write -> critique loop)
and returns a cited long-form report.

This agent is invoked from the streaming API when tool='deep-research'.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.agents.base.agent_protocol import (
    AgentCapability,
    AgentExecutionContext,
    AgentExecutionResult,
    AgentMode,
    AgentStatus,
    AgentStep,
    BaseAutonomousAgent,
)
from app.agents.paper_search_agent import paper_search_agent
from app.services.core.ai_service import ai_service
from app.tools.contracts import AgentConstraints, SearchChunk

from langchain_core.messages import HumanMessage, SystemMessage


@dataclass
class DeepResearchPlan:
    sub_questions: List[str]


def _safe_json_loads(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except Exception:
        return None


def _dedupe_chunks(chunks: List[SearchChunk]) -> List[SearchChunk]:
    seen: set[tuple] = set()
    deduped: List[SearchChunk] = []
    for c in chunks:
        md = c.metadata or {}
        key = (
            (md.get("url") or ""),
            (md.get("document_id") or ""),
            (md.get("file_id") or ""),
            (md.get("file_name") or md.get("title") or ""),
            (c.content or "")[:2000],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def _format_sources(used_chunks: List[SearchChunk]) -> Tuple[str, List[Dict[str, Any]]]:
    sources: List[Dict[str, Any]] = []
    lines: List[str] = []
    for idx, chunk in enumerate(used_chunks, start=1):
        md = chunk.metadata or {}
        title = md.get("title") or md.get("file_name") or "Unknown"
        url = md.get("url")
        page = md.get("page_number")
        doc_id = md.get("document_id")
        file_id = md.get("file_id")

        entry: Dict[str, Any] = {
            "n": idx,
            "title": title,
            "url": url,
            "page_number": page,
            "document_id": doc_id,
            "file_id": file_id,
        }
        sources.append(entry)

        if url:
            lines.append(f"- [{idx}] {title} - {url}")
        else:
            suffix = f" (p.{page})" if page else ""
            lines.append(f"- [{idx}] {title}{suffix}")

    sources_md = "\n".join(lines)
    return sources_md, sources


def _inject_reference_section(report_md: str, sources_md: str) -> str:
    if not sources_md:
        return report_md

    lines = (report_md or "").splitlines()

    def is_reference_heading(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        # Matches:
        # - "## 5. 참고자료", "### 참고자료", "5. 참고자료", "참고자료"
        s = re.sub(r"^#{1,6}\s*", "", s)
        return bool(re.match(r"^(?:5\.)?\s*참고자료\s*$", s))

    def is_next_section_heading(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        if s.startswith("#"):
            return True
        # Handle numbered sections like "6. ..." when headings are not using '#'
        return bool(re.match(r"^\d+\.\s+\S", s))

    start_idx = None
    for i, line in enumerate(lines):
        if is_reference_heading(line):
            start_idx = i
            break

    rendered_section = ["## 5. 참고자료", *sources_md.splitlines()]

    if start_idx is None:
        # Append new section
        if report_md and not report_md.endswith("\n"):
            report_md += "\n"
        return report_md.rstrip() + "\n\n" + "\n".join(rendered_section) + "\n"

    # Replace existing section content until the next heading
    end_idx = start_idx + 1
    while end_idx < len(lines) and not is_next_section_heading(lines[end_idx]):
        end_idx += 1

    new_lines = lines[:start_idx] + rendered_section + lines[end_idx:]
    patched = "\n".join(new_lines)
    # Remove common placeholder text if present
    patched = patched.replace("[위 Sources 리스트 그대로 포함]", "").replace("[위 Sources 목록 그대로 포함]", "")
    return patched.strip() + "\n"


def _strip_reference_section(report_md: str) -> str:
    """Return report content excluding the reference section.

    This prevents citations inside the reference list itself from inflating the
    set of cited numbers.
    """
    lines = (report_md or "").splitlines()

    def is_reference_heading(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        s = re.sub(r"^#{1,6}\s*", "", s)
        return bool(re.match(r"^(?:5\.)?\s*참고자료\s*$", s))

    for i, line in enumerate(lines):
        if is_reference_heading(line):
            return "\n".join(lines[:i]).strip()
    return (report_md or "").strip()


def _extract_cited_numbers(report_md: str) -> set[int]:
    body = _strip_reference_section(report_md)
    nums = set()
    for m in re.finditer(r"\[(\d{1,4})\]", body):
        try:
            nums.add(int(m.group(1)))
        except Exception:
            continue
    return nums


def _filter_sources_by_citations(
    sources_md: str,
    sources: List[Dict[str, Any]],
    cited_numbers: set[int],
) -> Tuple[str, List[Dict[str, Any]]]:
    if not cited_numbers:
        return sources_md, sources

    filtered_sources = [s for s in sources if int(s.get("n") or 0) in cited_numbers]

    lines_out: List[str] = []
    for line in (sources_md or "").splitlines():
        m = re.match(r"^\s*-\s*\[(\d{1,4})\]\s+", line)
        if not m:
            continue
        n = int(m.group(1))
        if n in cited_numbers:
            lines_out.append(line)

    # Keep original numbering, but order by numeric id for readability.
    lines_out.sort(key=lambda x: int(re.match(r"^\s*-\s*\[(\d{1,4})\]", x).group(1)))

    return "\n".join(lines_out), filtered_sources


class DeepResearchAgent(BaseAutonomousAgent):
    name = "deep_research"
    description = "Deep Research style agentic RAG (web + internal) report generator"
    version = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        # We reuse the project's configured chat model.
        self.llm = ai_service.get_chat_model(max_tokens=4000)

    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(
                name="deep_research_report",
                description="웹 검색 + 내부 지식을 결합해 인용 포함 리서치 리포트를 생성",
                supported_modes=[AgentMode.GRAPH, AgentMode.REACT, AgentMode.PLAN_EXECUTE],
                requires_internet=True,
                requires_database=True,
            )
        ]

    async def _plan(self, query: str, *, max_sub_questions: int) -> DeepResearchPlan:
        if not self.llm:
            return DeepResearchPlan(sub_questions=[query])

        system = SystemMessage(
            content=(
                "너는 Deep Research 플래너다. 사용자의 질문을 심층 리서치하기 위한 하위 질문 목록을 만든다. "
                "출력은 반드시 JSON 하나만 반환한다.\n\n"
                "JSON 스키마:\n"
                "{\n  \"sub_questions\": [\"...\", ...]\n}\n\n"
                f"제약: sub_questions는 최대 {max_sub_questions}개, 중복 제거, 한국어로 작성."
            )
        )
        human = HumanMessage(content=f"사용자 질문: {query}")
        resp = await self.llm.ainvoke([system, human])
        text = getattr(resp, "content", "") or ""

        parsed = _safe_json_loads(text)
        if not parsed or not isinstance(parsed.get("sub_questions"), list):
            return DeepResearchPlan(sub_questions=[query])

        sq = [str(x).strip() for x in parsed["sub_questions"] if str(x).strip()]
        if not sq:
            sq = [query]
        return DeepResearchPlan(sub_questions=sq[:max_sub_questions])

    async def _retrieve_for_question(
        self,
        sub_question: str,
        *,
        db_session: Any,
        constraints: AgentConstraints,
        attached_document_context: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        keywords = await paper_search_agent._extract_keywords(sub_question)
        strategy = [
            "vector_search",
            "keyword_search",
            "fulltext_search",
            "internet_search",
            "deduplicate",
            "rerank",
            "context_builder",
        ]

        retrieval = await paper_search_agent.execute_strategy(
            strategy=strategy,
            query=sub_question,
            keywords=keywords,
            constraints=constraints,
            db_session=db_session,
            context=context,
            attached_document_context=attached_document_context,
        )
        return retrieval

    async def _write_report(
        self,
        query: str,
        *,
        evidence_context: str,
        sources_md: str,
        max_tokens: int,
    ) -> str:
        if not self.llm:
            return f"# Deep Research Report\n\n질문: {query}\n\n(LLM 미설정)"

        system = SystemMessage(
            content=(
                "너는 엔터프라이즈 리서치 리포트 작성자다. 아래 증거(evidence)를 기반으로만 리포트를 작성한다. "
                "모르는 내용은 추측하지 말고 '근거 부족'이라고 명시한다.\n\n"
                "요구사항:\n"
                "- 마크다운으로 작성\n"
                "- 섹션 구조 포함: 1) 요약 2) 핵심 포인트 3) 상세 설명 4) 시사점/권고 5) 참고자료\n"
                "- 본문에서 주장마다 가능한 한 [숫자] 형태로 인용(citation) 표시\n"
                "- 참고자료 섹션에는 제공된 Sources 목록을 그대로 포함 (새로 만들지 말 것)\n"
            )
        )

        human = HumanMessage(
            content=(
                f"[리서치 질문]\n{query}\n\n"
                f"[Evidence - 인용 번호 포함]\n{evidence_context}\n\n"
                f"[Sources - 그대로 참고자료에 포함]\n{sources_md}\n"
            )
        )

        model = ai_service.get_chat_model(max_tokens=max_tokens)
        resp = await model.ainvoke([system, human]) if model else await self.llm.ainvoke([system, human])
        return (getattr(resp, "content", "") or "").strip()

    async def _critique(self, query: str, report_md: str) -> Dict[str, Any]:
        if not self.llm:
            return {"needs_more": False}

        system = SystemMessage(
            content=(
                "너는 리서치 리포트 검증자다. 리포트가 질문을 충분히 커버하는지, 근거 인용이 부족한지 점검한다. "
                "출력은 반드시 JSON 하나만 반환한다.\n\n"
                "스키마:\n"
                "{\n  \"needs_more\": true|false,\n  \"missing_topics\": [\"...\"],\n  \"followup_questions\": [\"...\"]\n}\n\n"
                "followup_questions는 최대 3개."
            )
        )
        human = HumanMessage(content=f"질문: {query}\n\n리포트:\n{report_md}")
        resp = await self.llm.ainvoke([system, human])
        text = getattr(resp, "content", "") or ""
        parsed = _safe_json_loads(text) or {}
        needs_more = bool(parsed.get("needs_more"))
        followups = parsed.get("followup_questions")
        if not isinstance(followups, list):
            followups = []
        followups = [str(x).strip() for x in followups if str(x).strip()][:3]
        missing = parsed.get("missing_topics")
        if not isinstance(missing, list):
            missing = []
        missing = [str(x).strip() for x in missing if str(x).strip()][:5]
        return {"needs_more": needs_more, "followup_questions": followups, "missing_topics": missing}

    async def execute(
        self,
        input_data: Dict[str, Any],
        context: AgentExecutionContext,
        mode: AgentMode = AgentMode.GRAPH,
    ) -> AgentExecutionResult:
        start = datetime.utcnow()
        steps: List[AgentStep] = []
        tools_used: List[str] = []
        warnings: List[str] = []
        errors: List[str] = []

        query = str(input_data.get("query") or "").strip()
        if not query:
            return AgentExecutionResult(
                success=False,
                output={"report_markdown": ""},
                agent_name=self.name,
                mode=mode,
                status=AgentStatus.FAILED,
                steps=[],
                tools_used=[],
                total_latency_ms=0.0,
                errors=["query is required"],
                warnings=[],
                context=context,
            )

        db_session = input_data.get("db_session")
        constraints: AgentConstraints = input_data.get("constraints")
        attached_document_context = str(input_data.get("attached_document_context") or "")
        exec_ctx = dict(input_data.get("context") or {})

        max_sub_questions = int(input_data.get("max_sub_questions") or 5)
        max_loops = int(input_data.get("max_loops") or 2)

        # Step 1: Plan
        t0 = datetime.utcnow()
        plan = await self._plan(query, max_sub_questions=max_sub_questions)
        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                action="plan",
                reasoning=f"sub_questions={len(plan.sub_questions)}",
                tool_input={"query": query},
                tool_output={"sub_questions": plan.sub_questions},
                latency_ms=(datetime.utcnow() - t0).total_seconds() * 1000,
                success=True,
            )
        )

        # Step 2: Retrieve
        all_chunks: List[SearchChunk] = []
        per_question_contexts: List[str] = []

        for subq in plan.sub_questions:
            t1 = datetime.utcnow()
            try:
                retrieval = await self._retrieve_for_question(
                    subq,
                    db_session=db_session,
                    constraints=constraints,
                    attached_document_context=attached_document_context,
                    context=exec_ctx,
                )
                used = list(retrieval.get("used_chunks") or [])
                ctx_text = str(retrieval.get("context_text") or "")
                all_chunks.extend(used)
                per_question_contexts.append(ctx_text)
                tools_used.extend(["vector_search", "keyword_search", "fulltext_search", "internet_search", "rerank", "context_builder"])
                steps.append(
                    AgentStep(
                        step_number=len(steps) + 1,
                        action="retrieve",
                        reasoning=subq,
                        tool_input={"sub_question": subq},
                        tool_output={"used_chunks": len(used)},
                        latency_ms=(datetime.utcnow() - t1).total_seconds() * 1000,
                        success=True,
                    )
                )
            except Exception as e:
                errors.append(str(e))
                steps.append(
                    AgentStep(
                        step_number=len(steps) + 1,
                        action="retrieve",
                        reasoning=subq,
                        tool_input={"sub_question": subq},
                        tool_output=None,
                        latency_ms=(datetime.utcnow() - t1).total_seconds() * 1000,
                        success=False,
                        error=str(e),
                    )
                )

        all_chunks = _dedupe_chunks(all_chunks)

        # Build a unified evidence context (reuse ContextBuilder numbering by calling it through paper_search_agent)
        # We do this by invoking the context_builder tool directly.
        t2 = datetime.utcnow()
        try:
            ctx_tool = paper_search_agent.tools.get("context_builder")
            if not ctx_tool:
                raise RuntimeError("context_builder tool not available")
            ctx_result = await ctx_tool._arun(chunks=all_chunks, max_tokens=min(6000, context.max_tokens))
            evidence_context = getattr(ctx_result, "data", "") or ""
            used_chunks = getattr(ctx_result, "used_chunks", all_chunks)
        except Exception as e:
            warnings.append(f"evidence_context_build_failed: {e}")
            evidence_context = ""
            used_chunks = all_chunks

        steps.append(
            AgentStep(
                step_number=len(steps) + 1,
                action="evidence_pack",
                reasoning="pack evidence into context",
                tool_input={"chunks": len(all_chunks)},
                tool_output={"used_chunks": len(used_chunks)},
                latency_ms=(datetime.utcnow() - t2).total_seconds() * 1000,
                success=True,
            )
        )

        sources_md, sources = _format_sources(list(used_chunks))

        # Step 3: Write + Critique loop
        report_md = ""
        for loop_idx in range(max_loops):
            t3 = datetime.utcnow()
            report_md = await self._write_report(
                query,
                evidence_context=evidence_context,
                sources_md=sources_md,
                max_tokens=min(context.max_tokens, 6000),
            )
            steps.append(
                AgentStep(
                    step_number=len(steps) + 1,
                    action="write_report",
                    reasoning=f"loop={loop_idx + 1}",
                    tool_input={"query": query},
                    tool_output={"length": len(report_md)},
                    latency_ms=(datetime.utcnow() - t3).total_seconds() * 1000,
                    success=True,
                )
            )

            t4 = datetime.utcnow()
            critique = await self._critique(query, report_md)
            steps.append(
                AgentStep(
                    step_number=len(steps) + 1,
                    action="critique",
                    reasoning="validate coverage and citations",
                    tool_input=None,
                    tool_output=critique,
                    latency_ms=(datetime.utcnow() - t4).total_seconds() * 1000,
                    success=True,
                )
            )

            if not critique.get("needs_more"):
                break

            followups = critique.get("followup_questions") or []
            if not followups:
                break

            # Retrieve extra evidence for follow-ups (single loop)
            for fq in followups:
                try:
                    retrieval = await self._retrieve_for_question(
                        fq,
                        db_session=db_session,
                        constraints=constraints,
                        attached_document_context=attached_document_context,
                        context=exec_ctx,
                    )
                    used = list(retrieval.get("used_chunks") or [])
                    all_chunks.extend(used)
                except Exception as e:
                    warnings.append(f"followup_retrieve_failed: {e}")

            all_chunks = _dedupe_chunks(all_chunks)
            try:
                ctx_tool = paper_search_agent.tools.get("context_builder")
                ctx_result = await ctx_tool._arun(chunks=all_chunks, max_tokens=min(6000, context.max_tokens))
                evidence_context = getattr(ctx_result, "data", "") or ""
                used_chunks = getattr(ctx_result, "used_chunks", all_chunks)
                sources_md, sources = _format_sources(list(used_chunks))
            except Exception as e:
                warnings.append(f"followup_evidence_pack_failed: {e}")

        # Post-process references: keep only sources actually cited in the report body.
        cited_numbers = _extract_cited_numbers(report_md)
        filtered_sources_md, filtered_sources = _filter_sources_by_citations(
            sources_md,
            sources,
            cited_numbers,
        )

        # Ensure the report contains the (possibly filtered) sources list.
        report_md = _inject_reference_section(report_md, filtered_sources_md)

        total_latency_ms = (datetime.utcnow() - start).total_seconds() * 1000

        output = {
            "report_markdown": report_md,
            "sources": filtered_sources,
            "chunks_used": len(filtered_sources),
        }

        success = bool(report_md)
        status = AgentStatus.COMPLETED if success else AgentStatus.FAILED

        return AgentExecutionResult(
            success=success,
            output=output,
            agent_name=self.name,
            mode=mode,
            status=status,
            steps=steps,
            tools_used=sorted(set(tools_used)),
            total_latency_ms=total_latency_ms,
            llm_calls=0,
            tool_calls=0,
            tokens_used=0,
            errors=errors,
            warnings=warnings,
            context=context,
        )


deep_research_agent = DeepResearchAgent()
