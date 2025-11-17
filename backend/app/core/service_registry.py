"""
Service Registry - External service configuration and discovery
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ServiceType(str, Enum):
    """External service types"""
    OFFICE_GENERATOR = "office_generator"
    # 향후 확장 가능: TRANSLATION_SERVICE, OCR_SERVICE, etc.


class ServiceConfig(BaseModel):
    """Configuration for an external service"""
    name: str
    enabled: bool = True
    base_url: str
    api_key: Optional[str] = None
    timeout: int = 60
    retry_count: int = 3
    health_check_path: str = "/health"
    
    # Service-specific capabilities
    capabilities: Dict[str, Any] = Field(default_factory=dict)


class OfficeGeneratorConfig(ServiceConfig):
    """Office Generator specific configuration"""
    name: str = "Office Generator Service"
    capabilities: Dict[str, Any] = Field(default_factory=lambda: {
        "formats": ["pptx"],  # 향후 ["pptx", "docx", "xlsx"]
        "max_slides": 100,
        "supported_charts": ["bar", "line", "pie", "doughnut", "area", "scatter"],
        "themes": ["business", "modern", "playful", "minimal", "dark", "vibrant"]
    })


class ServiceRegistry:
    """
    Central registry for all external services
    
    Usage:
        registry = ServiceRegistry.from_settings(settings)
        office_service = registry.get_service(ServiceType.OFFICE_GENERATOR)
        
        if office_service.enabled:
            url = f"{office_service.base_url}/api/pptx/generate"
    """
    
    def __init__(self):
        self._services: Dict[ServiceType, ServiceConfig] = {}
    
    def register(self, service_type: ServiceType, config: ServiceConfig):
        """Register a service"""
        self._services[service_type] = config
        logger.info(f"📝 Registered service: {service_type.value} -> {config.base_url}")
    
    def get_service(self, service_type: ServiceType) -> Optional[ServiceConfig]:
        """Get service configuration"""
        return self._services.get(service_type)
    
    def is_enabled(self, service_type: ServiceType) -> bool:
        """Check if service is enabled"""
        service = self.get_service(service_type)
        return service is not None and service.enabled
    
    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """List all registered services"""
        return {
            stype.value: {
                "base_url": cfg.base_url,
                "enabled": cfg.enabled,
                "capabilities": cfg.capabilities
            }
            for stype, cfg in self._services.items()
        }
    
    @classmethod
    def from_settings(cls, settings):
        """Create registry from application settings"""
        registry = cls()
        
        # Office Generator Service
        if hasattr(settings, 'pptxgenjs_service_url'):
            office_config = OfficeGeneratorConfig(
                base_url=settings.pptxgenjs_service_url,
                api_key=getattr(settings, 'pptxgenjs_api_key', ''),
                enabled=True,  # 향후 settings.enable_office_generator_service로 제어
            )
            registry.register(ServiceType.OFFICE_GENERATOR, office_config)
        
        return registry


# Global singleton
_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """Get global service registry singleton"""
    global _registry
    if _registry is None:
        from app.core.config import settings
        _registry = ServiceRegistry.from_settings(settings)
    return _registry


def reset_service_registry():
    """Reset registry (for testing)"""
    global _registry
    _registry = None
