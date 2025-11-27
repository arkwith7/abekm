from typing import Optional, Dict, Any, Type, List
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from app.services.presentation.enhanced_ppt_generator_service import EnhancedPPTGeneratorService
from app.services.presentation.ppt_models import DeckSpec
from loguru import logger

# 1. Generate Outline Tool
class GenerateOutlineInput(BaseModel):
    topic: str = Field(..., description="The topic of the presentation")
    context: Optional[str] = Field(None, description="Background knowledge or content to be included in the presentation")
    presentation_type: Optional[str] = Field("general", description="Type of presentation (general, product_introduction, etc.)")
    template_style: Optional[str] = Field("business", description="Style of the template (business, creative, minimal, etc.)")

class GenerateOutlineTool(BaseTool):
    name: str = "generate_outline"
    description: str = "Generates a presentation outline (DeckSpec) based on the topic and context."
    args_schema: Type[BaseModel] = GenerateOutlineInput
    
    def _run(self, topic: str, context: Optional[str] = None, presentation_type: str = "general", template_style: str = "business") -> Dict[str, Any]:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, topic: str, context: Optional[str] = None, presentation_type: str = "general", template_style: str = "business") -> Dict[str, Any]:
        service = EnhancedPPTGeneratorService()
        try:
            logger.info(f"Generating outline for topic: {topic}, type: {presentation_type}")
            deck_spec = await service.generate_enhanced_outline(
                topic=topic,
                context_text=context or "",
                presentation_type=presentation_type,
                template_style=template_style
            )
            
            # DeckSpec -> Dict conversion
            # Pydantic v1/v2 compatibility check might be needed, but assuming .dict() works
            return deck_spec.dict()
        except Exception as e:
            logger.error(f"Outline generation failed: {e}")
            return {"error": str(e)}

# 2. Create Slides Tool
class CreateSlidesInput(BaseModel):
    outline: Dict[str, Any] = Field(..., description="The structure of the presentation to generate (DeckSpec)")
    template_style: Optional[str] = Field("business", description="Style of the template")

class CreateSlidesTool(BaseTool):
    name: str = "create_slides"
    description: str = "Generates the actual PPT file based on the outline information and returns the download URL."
    args_schema: Type[BaseModel] = CreateSlidesInput

    def _run(self, outline: Dict[str, Any], template_style: str = "business") -> str:
        service = EnhancedPPTGeneratorService()
        try:
            logger.info(f"Creating slides with style: {template_style}")
            # Dict -> DeckSpec conversion
            deck_spec = DeckSpec(**outline)
            
            # Generate PPT
            # build_enhanced_pptx returns the file path or URL
            # Assuming it returns a relative path or URL string
            result = service.build_enhanced_pptx(
                spec=deck_spec,
                template_style=template_style
            )
            return str(result)
        except Exception as e:
            logger.error(f"Slide creation failed: {e}")
            return f"Error: {str(e)}"
            
    async def _arun(self, outline: Dict[str, Any], template_style: str = "business") -> str:
        # build_enhanced_pptx is synchronous, so wrap it or run directly
        # Since it's CPU bound (PPT generation), running in thread pool is better but for now direct call
        return self._run(outline, template_style)

def get_presentation_tools() -> List[BaseTool]:
    return [
        GenerateOutlineTool(),
        CreateSlidesTool()
    ]
