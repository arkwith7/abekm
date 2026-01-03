"""
Patent Clients - Base Client

모든 특허 데이터 소스 클라이언트의 추상 베이스
"""

from ..core.interfaces import BasePatentClient

# Re-export for convenience
__all__ = ["BasePatentClient"]
