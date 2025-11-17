"""
문서 접근 제어 모델
Phase 2: 문서 접근 관리 기능
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class AccessLevel(str, enum.Enum):
    """문서 접근 레벨"""
    PUBLIC = "public"  # 모든 사용자 접근 가능
    RESTRICTED = "restricted"  # 특정 사용자/부서만 접근 가능
    PRIVATE = "private"  # 관리자만 접근 가능


class RuleType(str, enum.Enum):
    """접근 규칙 타입"""
    USER = "user"  # 개별 사용자
    DEPARTMENT = "department"  # 부서 단위


class PermissionLevel(str, enum.Enum):
    """권한 레벨"""
    VIEW = "view"  # 조회만 가능
    DOWNLOAD = "download"  # 조회 + 다운로드 가능
    EDIT = "edit"  # 조회 + 다운로드 + 편집 가능


class TbDocumentAccessRules(Base):
    """
    문서 접근 규칙 테이블
    
    설계 원칙:
    1. 컨테이너 기본 권한 + 문서별 예외 설정
    2. 문서가 컨테이너 권한 상속
    3. 부서 단위 권한 지원
    4. 기존 문서는 컨테이너 권한에 따라 자동 매핑
    """
    __tablename__ = "tb_document_access_rules"
    
    # 기본 키
    rule_id = Column(
        Integer, 
        primary_key=True, 
        autoincrement=True, 
        comment="접근 규칙 일련번호"
    )
    
    # 문서 정보
    file_bss_info_sno = Column(
        Integer,
        ForeignKey('tb_file_bss_info.file_bss_info_sno', ondelete='CASCADE'),
        nullable=False,
        comment="파일 기본 정보 일련번호"
    )
    
    # 접근 레벨 (문서 전체 레벨)
    access_level = Column(
        SQLEnum(AccessLevel, name='access_level_enum', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AccessLevel.PUBLIC,
        comment="접근 레벨 (public/restricted/private)"
    )
    
    # 규칙 타입 및 대상
    rule_type = Column(
        SQLEnum(RuleType, name='rule_type_enum', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,  # access_level이 PUBLIC이나 PRIVATE이면 null 가능
        comment="규칙 타입 (user/department)"
    )
    
    target_id = Column(
        String(100),
        nullable=True,  # access_level이 PUBLIC이나 PRIVATE이면 null
        comment="대상 ID (user: emp_no, department: dept_nm)"
    )
    
    # 권한 레벨
    permission_level = Column(
        SQLEnum(PermissionLevel, name='permission_level_enum', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,  # access_level이 PUBLIC이나 PRIVATE이면 null
        default=PermissionLevel.VIEW,
        comment="권한 레벨 (view/download/edit)"
    )
    
    # 컨테이너 상속 여부
    is_inherited = Column(
        String(1),  # 'Y' or 'N'
        nullable=False,
        default='Y',
        comment="컨테이너 권한 상속 여부 (Y/N)"
    )
    
    # 메타 정보
    rule_metadata = Column(
        'metadata',
        JSONB,
        nullable=True,
        comment="추가 메타데이터 (예: 규칙 설명, 유효기간 등)"
    )

    
    # 생성/수정 정보
    created_by = Column(
        String(50),
        nullable=False,
        comment="생성자 사번"
    )
    
    created_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성일시"
    )
    
    last_modified_by = Column(
        String(50),
        nullable=True,
        comment="최종 수정자 사번"
    )
    
    last_modified_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="최종 수정일시"
    )
    
    # 제약 조건
    __table_args__ = (
        # RESTRICTED일 때만 rule_type과 target_id가 필수
        CheckConstraint(
            """
            (access_level = 'restricted' AND rule_type IS NOT NULL AND target_id IS NOT NULL) OR
            (access_level != 'restricted')
            """,
            name='check_restricted_requires_target'
        ),
        # 인덱스
        Index('idx_document_access_file', 'file_bss_info_sno'),
        Index('idx_document_access_level', 'access_level'),
        Index('idx_document_access_target', 'rule_type', 'target_id'),
        Index('idx_document_access_composite', 'file_bss_info_sno', 'access_level'),
        Index('idx_document_access_inherited', 'is_inherited'),
        Index('idx_document_access_created', 'created_date'),
    )
    
    # 관계 정의
    file_info = relationship(
        "TbFileBssInfo",
        foreign_keys=[file_bss_info_sno],
        backref="access_rules"
    )
    
    def __repr__(self):
        return (
            f"<TbDocumentAccessRules("
            f"rule_id={self.rule_id}, "
            f"file_bss_info_sno={self.file_bss_info_sno}, "
            f"access_level={self.access_level}, "
            f"rule_type={self.rule_type}, "
            f"target_id={self.target_id}, "
            f"permission_level={self.permission_level}"
            f")>"
        )


class TbDocumentAccessLog(Base):
    """
    문서 접근 로그 테이블
    문서 접근 이력 추적 (감사 목적)
    """
    __tablename__ = "tb_document_access_log"
    
    log_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="로그 일련번호"
    )
    
    file_bss_info_sno = Column(
        Integer,
        ForeignKey('tb_file_bss_info.file_bss_info_sno', ondelete='CASCADE'),
        nullable=False,
        comment="파일 기본 정보 일련번호"
    )
    
    user_emp_no = Column(
        String(20),
        nullable=False,
        comment="접근 사용자 사번"
    )
    
    access_type = Column(
        String(20),
        nullable=False,
        comment="접근 타입 (view/download/edit)"
    )
    
    access_granted = Column(
        String(1),
        nullable=False,
        comment="접근 허용 여부 (Y/N)"
    )
    
    denial_reason = Column(
        String(500),
        nullable=True,
        comment="접근 거부 사유"
    )
    
    accessed_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="접근 일시"
    )
    
    access_metadata = Column(
        'metadata',
        JSONB,
        nullable=True,
        comment="추가 메타데이터 (IP, User-Agent 등)"
    )

    
    __table_args__ = (
        Index('idx_access_log_file', 'file_bss_info_sno'),
        Index('idx_access_log_user', 'user_emp_no'),
        Index('idx_access_log_date', 'accessed_date'),
        Index('idx_access_log_granted', 'access_granted'),
    )
    
    # 관계 정의
    file_info = relationship(
        "TbFileBssInfo",
        foreign_keys=[file_bss_info_sno],
        backref="access_logs"
    )
    
    def __repr__(self):
        return (
            f"<TbDocumentAccessLog("
            f"log_id={self.log_id}, "
            f"file_bss_info_sno={self.file_bss_info_sno}, "
            f"user_emp_no={self.user_emp_no}, "
            f"access_type={self.access_type}, "
            f"access_granted={self.access_granted}"
            f")>"
        )
