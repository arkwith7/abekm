"""Presentation services - feature-pack internal.

Services for PPT generation, template management, and slide processing.
"""

# Main services
from app.agents.features.presentation.services.quick_ppt_generator_service import quick_ppt_service
from app.agents.features.presentation.services.templated_ppt_generator_service import templated_ppt_service
from app.agents.features.presentation.services.simple_ppt_builder import SimplePPTBuilder
from app.agents.features.presentation.services.ai_ppt_builder import AIPPTBuilder, build_ppt_from_ai_mappings
from app.agents.features.presentation.services.ppt_template_manager import template_manager
from app.agents.features.presentation.services.user_template_manager import user_template_manager
from app.agents.features.presentation.services.dynamic_slide_manager import DynamicSlideManager

__all__ = [
    "quick_ppt_service",
    "templated_ppt_service",
    "SimplePPTBuilder",
    "AIPPTBuilder",
    "build_ppt_from_ai_mappings",
    "template_manager",
    "user_template_manager",
    "DynamicSlideManager",
]
