"""
PptxGenJS Tool - Python integration for Node.js PPTX generation service
"""
import aiohttp
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


class PptxGenJSConfig(BaseModel):
    """Configuration for PptxGenJS service"""
    service_url: str = Field(default="http://localhost:3001")
    api_key: str = Field(default="")
    timeout: int = Field(default=60)


class PptxGenJSTool:
    """
    Tool for generating PPTX files via Node.js PptxGenJS service
    """
    
    def __init__(self, config: Optional[PptxGenJSConfig] = None):
        self.config = config or PptxGenJSConfig(
            service_url=getattr(settings, 'PPTXGENJS_SERVICE_URL', 'http://localhost:3001'),
            api_key=getattr(settings, 'PPTXGENJS_API_KEY', ''),
            timeout=60
        )
    
    async def generate_pptx(self, deck_spec: Dict[str, Any]) -> bytes:
        """
        Generate PPTX file from DeckSpec
        
        Args:
            deck_spec: DeckSpec dictionary with structure:
                {
                    "title": str,
                    "style": str (business|modern|playful|minimal|dark|vibrant),
                    "metadata": {"author": str, "company": str},
                    "slides": [
                        {
                            "type": str (title|agenda|content|thanks),
                            "title": str,
                            "key_message": str (optional),
                            "bullets": List[str],
                            "diagram": {"chart": {...}}
                        }
                    ]
                }
        
        Returns:
            PPTX file content as bytes
        
        Raises:
            aiohttp.ClientError: Network or HTTP errors
            ValueError: Invalid response
        """
        url = f"{self.config.service_url}/api/pptx/generate"
        headers = {
            "Content-Type": "application/json"
        }
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        
        payload = {"deckSpec": deck_spec}
        
        logger.info(
            f"Calling PptxGenJS service at {url}",
            extra={
                "slide_count": len(deck_spec.get("slides", [])),
                "style": deck_spec.get("style", "business")
            }
        )
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    # Check status
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"PptxGenJS service error: {response.status}",
                            extra={"response": error_text}
                        )
                        raise ValueError(
                            f"PptxGenJS service returned {response.status}: {error_text}"
                        )
                    
                    # Read binary content
                    content = await response.read()
                    
                    # Validate content
                    if not content or len(content) < 1000:
                        raise ValueError(
                            f"Invalid PPTX content: too small ({len(content)} bytes)"
                        )
                    
                    logger.info(
                        "PPTX generated successfully",
                        extra={
                            "size_bytes": len(content),
                            "generation_time_ms": response.headers.get("X-Generation-Time-Ms")
                        }
                    )
                    
                    return content
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error calling PptxGenJS service: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in PptxGenJS tool: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of PptxGenJS service
        
        Returns:
            Health status dictionary
        """
        url = f"{self.config.service_url}/api/pptx/health"
        
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {
                            "status": "error",
                            "code": response.status,
                            "message": await response.text()
                        }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }


# Singleton instance
_pptxgenjs_tool = None


def get_pptxgenjs_tool() -> PptxGenJSTool:
    """Get singleton instance of PptxGenJSTool"""
    global _pptxgenjs_tool
    if _pptxgenjs_tool is None:
        _pptxgenjs_tool = PptxGenJSTool()
    return _pptxgenjs_tool
