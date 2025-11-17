"""
WKMS 데이터베이스 모델 패키지
업무 기능별로 구조화된 모델 아키텍처
"""

# SQLAlchemy Base 클래스
from app.core.database import Base

# 인증 및 권한 관리 모델
from .auth import (
    TbSapHrInfo,
    User,
    TbKnowledgeContainers,
    TbUserRoles,
    TbUserPermissions,
    TbPermissionRequests,
    TbPermissionAuditLog,
    TbPermissionManagementInfo,
    TbUserPermissionView,
    TbAutoApprovalRules
)

# 핵심 시스템 모델
from .core import (
    TbCmnsCdGrpItem,
    TbKnowledgeCategories,
    TbContainerCategories,
    TbSystemSettings
)

# 문서 관리 모델 (문서 처리 파이프라인 핵심)
from .document import (
    TbFileBssInfo,
    TbFileDtlInfo,
    VsDocContentsChunks,
    TbDocumentSearchIndex  # 통합검색 모델 추가
)

# 멀티모달 RAG 모델
from .document.multimodal_models import (
    DocExtractionSession,
    DocExtractedObject,
    DocChunkSession,
    DocChunk,
    DocEmbedding
)

# 검색 및 분석 모델
from .search import (
    TbKnowledgeAccessLog,
    TbKnowledgeSharingLog,
    TbSearchAnalytics
)

# 학술 서지정보 모델
from .academic import (
    TbAcademicDocumentMetadata,
    TbAcademicAuthors,
    TbAcademicAffiliations,
    TbAcademicDocumentAuthors,
    TbAcademicReferences,
)

# 채팅 및 대화 모델
from .chat import (
    TbChatHistory,
    TbChatSessions,
    TbChatFeedback
)

__all__ = [
    # SQLAlchemy Base 클래스
    "Base",
    
    # 인증 및 권한 관리 모델
    "TbSapHrInfo",
    "User",
    "TbKnowledgeContainers",
    "TbUserRoles",
    "TbUserPermissions",
    "TbPermissionRequests",
    "TbPermissionAuditLog",
    "TbPermissionManagementInfo",
    "TbUserPermissionView",
    
    # 핵심 시스템 모델
    "TbCmnsCdGrpItem",
    "TbKnowledgeCategories",
    "TbContainerCategories",
    "TbSystemSettings",
    
    # 문서 관리 모델 (문서 처리 파이프라인 핵심)
    "TbFileBssInfo",
    "TbFileDtlInfo", 
    "VsDocContentsChunks",
    "TbDocumentSearchIndex",  # 통합검색 모델
    
    # 검색 및 분석 모델
    "TbKnowledgeAccessLog",
    "TbKnowledgeSharingLog",
    "TbSearchAnalytics",
    
    # 학술 서지정보 모델
    "TbAcademicDocumentMetadata",
    "TbAcademicAuthors",
    "TbAcademicAffiliations",
    "TbAcademicDocumentAuthors",
    "TbAcademicReferences",
    
    # 채팅 및 대화 모델
    "TbChatHistory",
    "TbChatSessions",
    "TbChatFeedback",
]
