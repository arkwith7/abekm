"""PPT Wizard persistence via LangGraph checkpointer.

Implements Phase 2 of 01.docs/13.2.PPT_Agent_LangGraph_Production_Upgrade.md
for the Template wizard flow (generate-content → user edits → build-from-data).

Persistence:
- Prefer Postgres (production single DB) via `langgraph-checkpoint-postgres`.
- Fall back to SQLite if Postgres checkpointer isn't available.

Execution model:
- Uses the sync saver and runs graph ops in a thread (`asyncio.to_thread`).
	This avoids async driver compatibility issues while keeping HTTP handlers async.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.presentation.ppt_checkpointer import get_checkpointer


class PPTWizardState(TypedDict, total=False):
	# Identity
	user_id: str
	session_id: str
	template_id: str
	thread_id: str

	# Generate-content artifacts
	pipeline: str  # "ai_first" | "legacy" | "langgraph"	
	deck_spec: Dict[str, Any]
	slide_matches: Any
	mappings: Any

	# AI-first extras (optional)
	slide_replacements: Any
	content_plan: Any
	dynamic_slides: Any
	presentation_title: Optional[str]

	# Build output
	file_path: Optional[str]
	file_name: Optional[str]
	slide_count: Optional[int]
def make_thread_id(*, user_id: str, session_id: str, template_id: str) -> str:
	# deterministic, stable across restarts
	return f"pptwiz:{user_id}:{session_id}:{template_id}"
def is_enabled() -> bool:
	return get_checkpointer() is not None



def _sqlite_db_path() -> str:
	tmp_dir = os.getenv("PPT_GRAPH_CHECKPOINT_DIR", "/app/tmp")
	os.makedirs(tmp_dir, exist_ok=True)
	return os.path.join(tmp_dir, "ppt_wizard_checkpoints.sqlite")


def _compile_graph():
	if not is_enabled():
		return None

	saver = get_checkpointer()
	if saver is None:
		return None

	g = StateGraph(PPTWizardState)

	def _checkpoint(state: PPTWizardState) -> PPTWizardState:
		return state

	g.add_node("checkpoint", _checkpoint)
	g.set_entry_point("checkpoint")
	g.add_edge("checkpoint", END)
	return g.compile(checkpointer=saver)


_GRAPH = _compile_graph()


async def ensure_saved(*, thread_id: str, state: Dict[str, Any]) -> None:
	"""Create or overwrite the wizard checkpoint for thread_id."""
	if _GRAPH is None:
		raise RuntimeError("Wizard checkpointer is not available")

	config = {"configurable": {"thread_id": thread_id}}
	await asyncio.to_thread(
		_GRAPH.invoke,
		state,
		config,
		interrupt_after=["checkpoint"],
	)


async def load(*, thread_id: str) -> Optional[Dict[str, Any]]:
	"""Load the latest persisted state for thread_id."""
	if _GRAPH is None:
		return None

	config = {"configurable": {"thread_id": thread_id}}
	try:
		snap = await asyncio.to_thread(_GRAPH.get_state, config)
		return dict(getattr(snap, "values", None) or {})
	except Exception:
		return None


async def update(*, thread_id: str, values: Dict[str, Any]) -> None:
	"""Merge-update the persisted state for thread_id."""
	if _GRAPH is None:
		raise RuntimeError("Wizard checkpointer is not available")

	config = {"configurable": {"thread_id": thread_id}}
	await asyncio.to_thread(_GRAPH.update_state, config, values)
