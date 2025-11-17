"""
WKMS Services Package
====================

업무 기능별로 분류된 서비스들:

📄 Document Management:
  - document.document_service

🔍 Search System:  
  - search.search_service

💬 Chat & RAG System:
  - chat.unified_chat_service

🔐 Auth & Permission:
  - auth.*

🔧 Core Services:
  - core.*
"""

# 메인 통합 서비스들만 최상위에서 import
from .document import document_service
from .search import search_service  
from .chat import unified_chat_service
from .core import ai_service, korean_nlp_service, EmbeddingService

# 기존 호환성 유지 (추후 제거 예정)
from .auth.permission_service import PermissionService
from .auth.permission_request_service import PermissionRequestService  
from .auth.container_service import ContainerService

def get_permission_service():
    from .auth.permission_service import PermissionService
    return PermissionService

def get_permission_request_service():
    from .auth.permission_request_service import PermissionRequestService
    return PermissionRequestService
    
def get_container_service():
    from .auth.container_service import ContainerService
    return ContainerService

__all__ = [
    # 통합 서비스들 (메인)
    "document_service",
    "search_service", 
    "unified_chat_service",
    
    # 핵심 서비스들
    "ai_service",
    "korean_nlp_service",
    "EmbeddingService",
    
    # 기존 호환성 유지
    "PermissionService",
    "get_permission_service",
    "PermissionRequestService", 
    "get_permission_request_service",
    "ContainerService",
    "get_container_service"
]