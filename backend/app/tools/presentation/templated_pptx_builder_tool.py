"""Templated PPTX Builder Tool - Build PPTX using template with mappings."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.services.presentation.templated_ppt_generator_service import templated_ppt_service
from app.services.presentation.ppt_models import DeckSpec


class TemplatedPPTXBuilderInput(BaseModel):
    """Input schema for TemplatedPPTXBuilderTool."""

    deck_spec: Dict[str, Any] = Field(..., description="DeckSpec dictionary")
    template_id: str = Field(..., description="Template ID to use")
    mappings: Optional[List[Dict[str, Any]]] = Field(default=None, description="Content mappings")
    file_basename: Optional[str] = Field(default=None, description="Base filename")


class TemplatedPPTXBuilderTool(BaseTool):
    """
    Build PPTX file using template with content mappings.
    
    Applies AI-generated outline to a pre-designed template while
    preserving the template's styling and layout.
    """

    name: str = "templated_pptx_builder_tool"
    description: str = (
        "Builds a PPTX file using a template with content mappings. "
        "Applies outline content to template elements while preserving "
        "template design and styling."
    )
    args_schema: Type[BaseModel] = TemplatedPPTXBuilderInput

    async def _arun(
        self,
        deck_spec: Dict[str, Any],
        template_id: str,
        mappings: Optional[List[Dict[str, Any]]] = None,
        file_basename: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build PPTX file asynchronously.

        Args:
            deck_spec: DeckSpec dictionary
            template_id: Template identifier
            mappings: Content-to-template mappings
            file_basename: Optional base filename

        Returns:
            Dict with file path and metadata
        """
        logger.info(
            f"🏗️ [TemplatedBuilder] 시작: template_id='{template_id}', "
            f"mappings={len(mappings) if mappings else 0}"
        )

        try:
            # Parse DeckSpec
            spec = DeckSpec(**deck_spec)
            
            # Get template details
            from app.services.presentation.ppt_template_manager import template_manager
            template_details = template_manager.get_template_details(template_id)
            
            if not template_details:
                return {
                    "success": False,
                    "error": f"Template not found: {template_id}",
                    "file_path": None,
                }
            
            # Get template path
            template_path = template_details.get('cleaned_template_path') or template_details.get('path')
            
            if not template_path or not Path(template_path).exists():
                return {
                    "success": False,
                    "error": f"Template file not found: {template_path}",
                    "file_path": None,
                }
            
            # Build PPTX with mappings
            file_path = templated_ppt_service.build_enhanced_pptx_with_slide_management(
                spec=spec,
                file_basename=file_basename,
                custom_template_path=template_path,
                user_template_id=template_details.get('dynamic_template_id'),
                text_box_mappings=mappings,
                content_segments=None,
                slide_management=None
            )
            
            logger.info(f"✅ [TemplatedBuilder] 완료: {file_path}")
            
            return {
                "success": True,
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "slide_count": len(spec.slides),
                "template_used": template_id,
                "mappings_applied": len(mappings) if mappings else 0,
                "message": f"Template PPT generation complete. File saved at {file_path}. Please output Final Answer with this path."
            }

        except Exception as e:
            logger.error(f"❌ [TemplatedBuilder] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": None,
            }

    def _run(self, *args, **kwargs):
        """Synchronous wrapper for async _arun."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._arun(*args, **kwargs))


# Singleton instance
templated_pptx_builder_tool = TemplatedPPTXBuilderTool()
