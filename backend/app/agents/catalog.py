"""Unified catalog facade for agent implementations.

This module is intentionally import-safe and lightweight.

Primary responsibility (active path):
- Provide Supervisor worker discovery via feature-pack modules under
	`app.agents.features`.

Compatibility (legacy / deprecated path):
- `AgentCatalog.get_tool()` keeps a minimal shim for any remaining callers that
	still expect a tool-like agent by type.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import pkgutil
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage


class WorkerState(TypedDict):
    """Minimal worker state interface."""
    messages: Sequence[BaseMessage]
    next: str
    shared_context: Dict[str, Any]


NodeFunc = Callable[[WorkerState], Awaitable[Dict[str, Any]]]


@dataclass(frozen=True)
class CatalogItem:
	key: str
	kind: str  # "tool" | "autonomous" | "worker"
	display_name: str
	description: str
	capabilities: List[str]
	priority: int
	enabled: bool


@dataclass(frozen=True)
class WorkerSpec:
	"""Supervisor worker specification."""
	name: str
	description: str
	node: NodeFunc


class AgentCatalog:
	"""Read-only facade over agents.

	The active runtime path should use `get_workers()`.
	"""

	def get_tool(self, agent_type: str) -> Optional[Any]:
		"""Return a tool-like agent by type (deprecated).

		This exists only for backward compatibility with older multi-agent codepaths.
		The main system should route through `get_workers()`.
		"""
		if agent_type == "presentation":
			from app.agents.features.presentation import presentation_agent_tool

			return presentation_agent_tool

		return None

	def get_workers(self) -> Dict[str, WorkerSpec]:
		"""Get all available Supervisor workers dynamically.
		
		Phase 2: prefer feature-pack discovery under `app.agents.features`.
		Falls back to legacy defaults for compatibility.
		"""
		# Import inside method to keep catalog import-safe
		from app.agents.core.workers import get_default_workers

		workers: Dict[str, WorkerSpec] = dict(get_default_workers())

		# Discover feature packs without importing them eagerly.
		try:
			import app.agents.features as features_pkg
		except Exception:
			return workers

		for modinfo in pkgutil.iter_modules(getattr(features_pkg, "__path__", [])):
			feature_name = modinfo.name
			worker_module_name = f"app.agents.features.{feature_name}.worker"

			try:
				worker_mod = importlib.import_module(worker_module_name)
			except Exception:
				continue

			get_specs = getattr(worker_mod, "get_worker_specs", None)
			if not callable(get_specs):
				continue

			try:
				feature_workers = dict(get_specs())
			except Exception:
				continue

			# Feature-pack workers override legacy defaults of same key.
			workers.update(feature_workers)

		return workers


agent_catalog = AgentCatalog()

__all__ = ["CatalogItem", "AgentCatalog", "agent_catalog", "WorkerSpec", "NodeFunc"]
