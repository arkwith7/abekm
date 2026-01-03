"""PPT generation graphs (LangGraph 1.x).

This module implements the Phase 1 portion of
01.docs/13.2.PPT_Agent_LangGraph_Production_Upgrade.md:

- Fixed-step workflows are encoded as a StateGraph.
- Request state is carried in the graph state (TypedDict) rather than instance fields.

Scope (intentional):
- Quick (outline → build → optional validate)
- Template (analyze → outline → match → map → build → optional validate)

Persistence/checkpointing (Phase 2):
- Prefer Postgres checkpointer (production single-DB) when configured.
- Fall back to local SQLite when Postgres checkpointer isn't available.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from loguru import logger
from langgraph.graph import END, StateGraph

from app.agents.presentation.ppt_checkpointer import get_checkpointer

from app.agents.features.presentation.tools.content_mapping_tool import content_mapping_tool
from app.agents.features.presentation.tools.outline_generation_tool import outline_generation_tool
from app.agents.features.presentation.tools.ppt_quality_validator_tool import ppt_quality_validator_tool
from app.agents.features.presentation.tools.quick_pptx_builder_tool import quick_pptx_builder_tool
from app.agents.features.presentation.tools.slide_type_matcher_tool import slide_type_matcher_tool
from app.agents.features.presentation.tools.template_analyzer_tool import template_analyzer_tool
from app.agents.features.presentation.tools.templated_pptx_builder_tool import templated_pptx_builder_tool


class PPTAgentState(TypedDict, total=False):
	# Identity
	request_id: str
	user_id: Optional[int]

	# Inputs
	mode: str  # "quick" | "template"
	topic: str
	context_text: str
	max_slides: int
	template_id: Optional[str]
	validate: bool

	# Intermediates
	deck_spec: Dict[str, Any]
	template_structure: Dict[str, Any]
	template_metadata: Dict[str, Any]
	slide_matches: List[Dict[str, Any]]
	mappings: List[Dict[str, Any]]

	# Outputs
	file_path: Optional[str]
	file_name: Optional[str]
	slide_count: Optional[int]
	quality_report: Dict[str, Any]

	# Observability
	tools_used: List[str]
	steps: List[Dict[str, Any]]
	errors: List[str]


def _now_iso() -> str:
	return datetime.utcnow().isoformat()


async def _ainvoke_with_fallback(
	graph: Any,
	state: PPTAgentState,
	*,
	config: Dict[str, Any],
	interrupt_after: Optional[List[str]] = None,
) -> PPTAgentState:
	"""Invoke a compiled graph with robust compatibility handling.

	Some checkpointers (notably sync Postgres savers) do not implement async
	checkpoint APIs, which can surface as NotImplementedError during `ainvoke()`.
	Since this graph uses async-only nodes, falling back to sync `invoke()` will
	fail; instead we raise a clear configuration error.
	"""
	try:
		if interrupt_after:
			return await graph.ainvoke(state, config=config, interrupt_after=interrupt_after)
		return await graph.ainvoke(state, config=config)
	except NotImplementedError:
		raise RuntimeError(
			"LangGraph checkpointer does not support async checkpoint APIs. "
			"Configure an async-capable checkpointer (e.g. AsyncPostgresSaver) "
			"or set PPT_CHECKPOINTER_BACKEND=sqlite/none."
		)


_FILENAME_REPLACE = {":": "_", "\\": "_", "/": "_", "\n": "_", "\r": "_"}


def _safe_file_basename(name: str) -> str:
	"""Make a safe file basename for tools that write into /app/uploads.

	Prevents accidental path traversal or invalid filenames when topic/message
	contains characters like '/' or ':' (common in URLs).
	"""
	safe = (name or "").strip().replace("\r", "")
	for k, v in _FILENAME_REPLACE.items():
		safe = safe.replace(k, v)
	# Defensive: strip path-like segments
	safe = safe.replace("..", "_")
	if not safe:
		safe = "presentation"
	# Avoid extremely long filenames
	return safe[:120]


def _short_id(value: str) -> str:
	"""Return a short stable suffix for filenames."""
	val = (value or "").strip()
	if not val:
		return ""
	hex_only = re.sub(r"[^0-9a-fA-F]", "", val)
	if len(hex_only) >= 8:
		return hex_only[:8].lower()
	alnum = re.sub(r"[^0-9a-zA-Z]", "", val)
	return (alnum[:8] if alnum else "")


def _build_output_basename(state: PPTAgentState, deck_spec: Dict[str, Any]) -> str:
	base_title = (deck_spec or {}).get("topic") or state.get("topic") or "presentation"
	safe_base = _safe_file_basename(str(base_title))
	suffix = _short_id(str(state.get("request_id") or ""))
	if not suffix:
		suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
	return f"{safe_base}_{suffix}"


def _append_step(
	state: PPTAgentState,
	step_type: str,
	content: str,
	metadata: Optional[Dict[str, Any]] = None,
) -> None:
	state.setdefault("steps", []).append(
		{
			"step_type": step_type,
			"content": content,
			"timestamp": _now_iso(),
			"metadata": metadata or {},
		}
	)


async def _run_tool(
	state: PPTAgentState,
	tool_name: str,
	tool: Any,
	tool_kwargs: Dict[str, Any],
) -> Dict[str, Any]:
	state.setdefault("tools_used", []).append(tool_name)
	_append_step(state, "ACTION", tool_name, {"input_keys": list(tool_kwargs.keys())})

	if hasattr(tool, "_arun"):
		result = await tool._arun(**tool_kwargs)
	else:
		result = tool._run(**tool_kwargs)

	ok = bool(result.get("success", False)) if isinstance(result, dict) else True
	_append_step(
		state,
		"OBSERVATION",
		f"{tool_name} success={ok}",
		{"result_keys": list(result.keys()) if isinstance(result, dict) else []},
	)
	return result


async def _quick_generate_outline(state: PPTAgentState) -> PPTAgentState:
	_append_step(state, "THOUGHT", "Quick: generate outline")
	result = await _run_tool(
		state,
		"outline_generation_tool",
		outline_generation_tool,
		{
			"topic": state["topic"],
			"context_text": state["context_text"],
			"max_slides": state.get("max_slides", 8),
		},
	)
	if not result.get("success"):
		state.setdefault("errors", []).append(result.get("error", "outline_generation_tool failed"))
		return state
	state["deck_spec"] = result.get("deck_spec", {})
	return state


async def _quick_build_pptx(state: PPTAgentState) -> PPTAgentState:
	_append_step(state, "THOUGHT", "Quick: build PPTX")
	deck_spec = state.get("deck_spec")
	if not deck_spec:
		state.setdefault("errors", []).append("Missing deck_spec")
		return state

	result = await _run_tool(
		state,
		"quick_pptx_builder_tool",
		quick_pptx_builder_tool,
		{
			"deck_spec": deck_spec,
			"file_basename": _build_output_basename(state, deck_spec),
		},
	)
	if not result.get("success"):
		state.setdefault("errors", []).append(result.get("error", "quick_pptx_builder_tool failed"))
		return state

	state["file_path"] = result.get("file_path")
	state["file_name"] = result.get("file_name")
	state["slide_count"] = result.get("slide_count")
	return state


async def _template_analyze(state: PPTAgentState) -> PPTAgentState:
	_append_step(state, "THOUGHT", "Template: analyze template")
	template_id = state.get("template_id")
	if not template_id:
		state.setdefault("errors", []).append("template_id is required")
		return state

	result = await _run_tool(
		state,
		"template_analyzer_tool",
		template_analyzer_tool,
		{
			"template_id": template_id,
			"user_id": state.get("user_id"),
		},
	)
	if not result.get("success"):
		state.setdefault("errors", []).append(result.get("error", "template_analyzer_tool failed"))
		return state

	state["template_structure"] = result.get("template_structure", {})
	state["template_metadata"] = result.get("template_metadata", {})
	# If max_slides isn't provided, derive it from the template slide count.
	if not state.get("max_slides"):
		try:
			slides = (state.get("template_metadata") or {}).get("slides") or []
			if isinstance(slides, list) and slides:
				state["max_slides"] = len(slides)
		except Exception:
			pass
	return state


async def _template_generate_outline(state: PPTAgentState) -> PPTAgentState:
	_append_step(state, "THOUGHT", "Template: generate outline")
	result = await _run_tool(
		state,
		"outline_generation_tool",
		outline_generation_tool,
		{
			"topic": state["topic"],
			"context_text": state["context_text"],
			"max_slides": state.get("max_slides", 8),
			"template_structure": state.get("template_structure"),
		},
	)
	if not result.get("success"):
		state.setdefault("errors", []).append(result.get("error", "outline_generation_tool failed"))
		return state

	state["deck_spec"] = result.get("deck_spec", {})
	return state


async def _template_match_slide_types(state: PPTAgentState) -> PPTAgentState:
	_append_step(state, "THOUGHT", "Template: match slide types")
	deck_spec = state.get("deck_spec")
	template_metadata = state.get("template_metadata")
	if not deck_spec or not template_metadata:
		state.setdefault("errors", []).append("Missing deck_spec/template_metadata")
		return state

	result = await _run_tool(
		state,
		"slide_type_matcher_tool",
		slide_type_matcher_tool,
		{
			"deck_spec": deck_spec,
			"template_metadata": template_metadata,
		},
	)
	if not result.get("success"):
		state.setdefault("errors", []).append(result.get("error", "slide_type_matcher_tool failed"))
		return state

	state["slide_matches"] = result.get("slide_matches", [])
	return state


async def _template_map_content(state: PPTAgentState) -> PPTAgentState:
	_append_step(state, "THOUGHT", "Template: map content")
	deck_spec = state.get("deck_spec")
	template_structure = state.get("template_structure")
	slide_matches = state.get("slide_matches")
	if not deck_spec or not template_structure:
		state.setdefault("errors", []).append("Missing deck_spec/template_structure")
		return state

	result = await _run_tool(
		state,
		"content_mapping_tool",
		content_mapping_tool,
		{
			"deck_spec": deck_spec,
			"template_structure": template_structure,
			"slide_matches": slide_matches,
		},
	)
	if not result.get("success"):
		state.setdefault("errors", []).append(result.get("error", "content_mapping_tool failed"))
		return state

	state["mappings"] = result.get("mappings", [])
	return state


async def _template_build_pptx(state: PPTAgentState) -> PPTAgentState:
	_append_step(state, "THOUGHT", "Template: build PPTX")
	template_id = state.get("template_id")
	deck_spec = state.get("deck_spec")
	mappings = state.get("mappings")
	slide_matches = state.get("slide_matches")

	if not template_id or not deck_spec:
		state.setdefault("errors", []).append("Missing template_id/deck_spec")
		return state

	result = await _run_tool(
		state,
		"templated_pptx_builder_tool",
		templated_pptx_builder_tool,
		{
			"deck_spec": deck_spec,
			"template_id": template_id,
			"mappings": mappings,
			"slide_matches": slide_matches,
			"file_basename": _build_output_basename(state, deck_spec),
			"user_id": state.get("user_id"),
		},
	)
	if not result.get("success"):
		state.setdefault("errors", []).append(result.get("error", "templated_pptx_builder_tool failed"))
		return state

	state["file_path"] = result.get("file_path")
	state["file_name"] = result.get("file_name") or result.get("filename")
	state["slide_count"] = result.get("slide_count")
	return state


async def _validate_ppt(state: PPTAgentState) -> PPTAgentState:
	if not state.get("validate", False):
		return state

	file_path = state.get("file_path")
	if not file_path:
		return state

	_append_step(state, "THOUGHT", "Validate generated PPT")
	result = await _run_tool(
		state,
		"ppt_quality_validator_tool",
		ppt_quality_validator_tool,
		{
			"file_path": file_path,
			"source_content": state.get("context_text", ""),
			"source_outline": state.get("deck_spec"),
		},
	)
	if result.get("success"):
		state["quality_report"] = result.get("report", {})
	else:
		state.setdefault("errors", []).append(result.get("error", "ppt_quality_validator_tool failed"))
	return state


def _should_validate(state: PPTAgentState) -> bool:
	return bool(state.get("validate", False))


def _build_quick_graph() -> StateGraph:
	workflow = StateGraph(PPTAgentState)
	workflow.add_node("generate_outline", _quick_generate_outline)
	workflow.add_node("build", _quick_build_pptx)
	workflow.add_node("validate", _validate_ppt)

	workflow.set_entry_point("generate_outline")
	workflow.add_edge("generate_outline", "build")

	workflow.add_conditional_edges(
		"build",
		lambda s: "validate" if _should_validate(s) else END,
	)
	workflow.add_edge("validate", END)
	return workflow


def _build_template_graph() -> StateGraph:
	workflow = StateGraph(PPTAgentState)
	workflow.add_node("analyze_template", _template_analyze)
	workflow.add_node("generate_outline", _template_generate_outline)
	workflow.add_node("match_slide_types", _template_match_slide_types)
	workflow.add_node("map_content", _template_map_content)
	workflow.add_node("build", _template_build_pptx)
	workflow.add_node("validate", _validate_ppt)

	workflow.set_entry_point("analyze_template")
	workflow.add_edge("analyze_template", "generate_outline")
	workflow.add_edge("generate_outline", "match_slide_types")
	workflow.add_edge("match_slide_types", "map_content")
	workflow.add_edge("map_content", "build")

	workflow.add_conditional_edges(
		"build",
		lambda s: "validate" if _should_validate(s) else END,
	)
	workflow.add_edge("validate", END)
	return workflow


def _get_checkpointer():
	"""Return the configured checkpointer (Postgres preferred, SQLite fallback)."""
	return get_checkpointer()


_QUICK_GRAPH: Any | None = None
_TEMPLATE_GRAPH: Any | None = None


def _get_compiled_graphs() -> tuple[Any, Any]:
	"""Compile graphs lazily to avoid import-time side effects.

	Import-time compilation previously initialized the Postgres async pool even
	when PPT flows weren't invoked (e.g. during unrelated API tests).
	"""
	global _QUICK_GRAPH, _TEMPLATE_GRAPH
	if _QUICK_GRAPH is not None and _TEMPLATE_GRAPH is not None:
		return _QUICK_GRAPH, _TEMPLATE_GRAPH

	checkpointer = _get_checkpointer()
	if checkpointer is not None:
		_QUICK_GRAPH = _build_quick_graph().compile(checkpointer=checkpointer)
		_TEMPLATE_GRAPH = _build_template_graph().compile(checkpointer=checkpointer)
	else:
		_QUICK_GRAPH = _build_quick_graph().compile()
		_TEMPLATE_GRAPH = _build_template_graph().compile()

	return _QUICK_GRAPH, _TEMPLATE_GRAPH


async def run_ppt_generation_graph(
	*,
	mode: str,
	topic: str,
	context_text: str,
	max_slides: int = 8,
	template_id: Optional[str] = None,
	user_id: Optional[int] = None,
	request_id: Optional[str] = None,
	run_id: Optional[str] = None,
	validate: bool = False,
) -> Dict[str, Any]:
	"""Run the PPT generation graph and return a stable dict payload."""

	state: PPTAgentState = {
		"request_id": request_id or "",
		"mode": mode,
		"topic": topic,
		"context_text": context_text,
		"max_slides": max_slides,
		"template_id": template_id,
		"user_id": user_id,
		"validate": validate,
		"tools_used": [],
		"steps": [],
		"errors": [],
	}

	quick_graph, template_graph = _get_compiled_graphs()
	graph = template_graph if mode == "template" else quick_graph

	logger.info(
		"🧩 [PPTGraph] start: mode=%s, topic='%s', validate=%s, request_id=%s",
		mode,
		(topic or "")[:50],
		validate,
		request_id,
	)

	# Thread id is required for persistence to work.
	thread_id = request_id or f"ppt:{(user_id or 'anon')}:{mode}:{_now_iso()}"
	# Phase 3 observability: pass run_id/tags/metadata through runnable config.
	graph_config: Dict[str, Any] = {
		"configurable": {"thread_id": thread_id},
		"tags": ["ppt", "ppt_generation_graph", f"mode:{mode}"],
		"metadata": {
			"mode": mode,
			"template_id": template_id,
			"user_id": user_id,
			"thread_id": thread_id,
		},
	}
	if run_id:
		graph_config["run_id"] = run_id
	final_state: PPTAgentState = await _ainvoke_with_fallback(graph, state, config=graph_config)

	errors = final_state.get("errors", [])
	success = bool(final_state.get("file_path")) and not errors

	payload: Dict[str, Any] = {
		"success": success,
		"file_path": final_state.get("file_path"),
		"file_name": final_state.get("file_name"),
		"slide_count": final_state.get("slide_count") or 0,
		"deck_spec": final_state.get("deck_spec"),
		"template_id": final_state.get("template_id"),
		"quality_report": final_state.get("quality_report"),
		"tools_used": final_state.get("tools_used", []),
		"steps": final_state.get("steps", []),
		"thread_id": thread_id,
	}

	if errors:
		payload["error"] = "; ".join([str(e) for e in errors if e])

	return payload


async def run_template_wizard_until_mapped(
	*,
	thread_id: str,
	template_id: str,
	topic: str,
	context_text: str,
	user_id: Optional[int] = None,
	request_id: Optional[str] = None,
) -> Dict[str, Any]:
	"""Run the template graph up to (and including) content mapping.

	This supports the UI wizard flow: generate content → user edits → build.
	"""
	state: PPTAgentState = {
		"request_id": request_id or "",
		"mode": "template",
		"topic": topic,
		"context_text": context_text,
		"template_id": template_id,
		"user_id": user_id,
		"validate": False,
		"tools_used": [],
		"steps": [],
		"errors": [],
	}

	config = {"configurable": {"thread_id": thread_id}}
	final_state: PPTAgentState = await _ainvoke_with_fallback(
		_template_graph,
		state,
		config=config,
		interrupt_after=["map_content"],
	)

	errors = final_state.get("errors", [])
	success = (not errors) and bool(final_state.get("deck_spec")) and bool(final_state.get("mappings"))
	return {
		"success": success,
		"thread_id": thread_id,
		"template_id": template_id,
		"deck_spec": final_state.get("deck_spec"),
		"slide_matches": final_state.get("slide_matches"),
		"mappings": final_state.get("mappings"),
		"tools_used": final_state.get("tools_used", []),
		"steps": final_state.get("steps", []),
		"error": "; ".join([str(e) for e in errors if e]) if errors else None,
	}


async def resume_template_wizard_build(
	*,
	thread_id: str,
	state_updates: Dict[str, Any],
) -> Dict[str, Any]:
	"""Resume the template graph from a saved checkpoint and run to END."""
	config = {"configurable": {"thread_id": thread_id}}
	try:
		_template_graph.get_state(config)
	except Exception as e:
		return {"success": False, "error": f"No checkpoint for thread_id={thread_id}: {e}"}

	try:
		_template_graph.update_state(config, state_updates)
		final_state: PPTAgentState = await _template_graph.ainvoke(None, config=config)
		errors = final_state.get("errors", [])
		success = bool(final_state.get("file_path")) and not errors
		payload: Dict[str, Any] = {
			"success": success,
			"file_path": final_state.get("file_path"),
			"file_name": final_state.get("file_name"),
			"slide_count": final_state.get("slide_count") or 0,
			"tools_used": final_state.get("tools_used", []),
			"steps": final_state.get("steps", []),
		}
		if errors:
			payload["error"] = "; ".join([str(e) for e in errors if e])
		return payload
	except Exception as e:
		return {"success": False, "error": str(e)}