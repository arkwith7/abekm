"""
Office Generator Service Client

Handles communication with the Office Generator Service (Node.js)
for PPTX conversion from StructuredOutline
"""

import httpx
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from app.core.config import settings
from app.models.presentation import StructuredOutline

logger = logging.getLogger(__name__)


class OfficeGeneratorClient:
    """
    Client for Office Generator Service
    """
    
    def __init__(self):
        self.base_url = settings.office_generator_url
        self.timeout = settings.office_generator_timeout
        
    async def convert_to_pptx(
        self,
        outline: StructuredOutline,
        theme: Optional[str] = None
    ) -> bytes:
        """
        Convert StructuredOutline to PPTX
        
        Args:
            outline: StructuredOutline object
            theme: Optional theme override
            
        Returns:
            bytes: PPTX file binary data
            
        Raises:
            httpx.HTTPError: If request fails
            ValueError: If response is invalid
        """
        try:
            logger.info(
                "Converting StructuredOutline to PPTX",
                extra={
                    "title": outline.title,
                    "slide_count": len(outline.slides),
                    "theme": theme or outline.theme
                }
            )
            
            # Prepare request payload
            payload = {
                "outlineJson": outline.model_dump(mode="json"),
                "options": {}
            }
            
            if theme:
                payload["options"]["theme"] = theme
            
            # Call Office Generator Service
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/pptx/convert",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                response.raise_for_status()
                
                # Check response is binary
                if not response.content:
                    raise ValueError("Empty response from Office Generator")
                
                pptx_data = response.content
                
                logger.info(
                    "PPTX conversion successful",
                    extra={
                        "size_bytes": len(pptx_data),
                        "duration_ms": response.headers.get("X-Generation-Time-Ms")
                    }
                )
                
                return pptx_data
                
        except httpx.HTTPStatusError as e:
            logger.error(
                "Office Generator HTTP error",
                extra={
                    "status_code": e.response.status_code,
                    "response": e.response.text[:500]
                },
                exc_info=True
            )
            raise
            
        except httpx.RequestError as e:
            logger.error(
                "Office Generator request error",
                extra={"error": str(e)},
                exc_info=True
            )
            raise
            
        except Exception as e:
            logger.error(
                "Unexpected error during PPTX conversion",
                extra={"error": str(e)},
                exc_info=True
            )
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check Office Generator Service health
        
        Returns:
            dict: Health status
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/pptx/health")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Office Generator health check failed: {e}")
            return {"status": "error", "message": str(e)}


# Singleton instance
office_generator_client = OfficeGeneratorClient()
