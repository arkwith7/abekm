"""Deprecated legacy agent_tools file.

모든 기능은 enhanced_agent_tools.enhanced_tool_registry 로 이전되었습니다.
이 파일은 기존 import 경로 호환을 위한 프록시만 제공합니다.
"""

from typing import Dict
from loguru import logger
from .enhanced_agent_tools import enhanced_tool_registry

_DEPRECATION_LOGGED = False


class _LegacyToolRegistryProxy:
    def _warn(self):
        global _DEPRECATION_LOGGED
        if not _DEPRECATION_LOGGED:
            logger.warning("[DEPRECATION] agent_tools.tool_registry -> enhanced_agent_tools.enhanced_tool_registry 사용 전환 권장")
            _DEPRECATION_LOGGED = True

    def get_tool(self, tool_name: str):
        self._warn()
        return enhanced_tool_registry.get_tool(tool_name)

    def get_all_tools(self):
        self._warn()
        return enhanced_tool_registry.get_all_tools()

    def get_tool_descriptions(self) -> Dict[str, str]:
        self._warn()
        return enhanced_tool_registry.get_tool_descriptions()


tool_registry = _LegacyToolRegistryProxy()

__all__ = ["tool_registry"]
