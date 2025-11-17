"""
WKMS 공통 코드 및 시스템 설정 모델
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class TbCmnsCdGrpItem(Base):
    """공통 코드 그룹 아이템 테이블 (카테고리)"""
    __tablename__ = "tb_cmns_cd_grp_item"
    
    # 컬럼 정의 (명세서와 동일한 컬럼명 사용)
    grp_cd = Column(String(20), primary_key=True, comment="그룹 코드")
    item_cd = Column(String(20), primary_key=True, comment="아이템 코드")
    item_nm = Column(String(100), nullable=False, comment="아이템명")
    item_desc = Column(String(500), nullable=True, comment="아이템 설명")
    sort_ord = Column(Integer, nullable=True, comment="정렬 순서")
    use_yn = Column(String(1), nullable=False, default='Y', comment="사용 여부")
    created_by = Column(String(50), nullable=True, comment="생성자")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일")
    updated_by = Column(String(50), nullable=True, comment="수정자")
    updated_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="수정일")


class TbKnowledgeCategories(Base):
    """지식 카테고리 테이블"""
    __tablename__ = "tb_knowledge_categories"
    
    # 기본 정보
    category_id = Column(String(20), primary_key=True, comment="카테고리 ID")
    category_name = Column(String(100), nullable=False, comment="카테고리명")
    category_description = Column(Text, nullable=True, comment="카테고리 설명")
    
    # 계층 구조
    parent_category_id = Column(String(20), nullable=True, comment="상위 카테고리 ID")
    category_level = Column(Integer, nullable=False, default=1, comment="카테고리 레벨")
    category_path = Column(String(500), nullable=True, comment="카테고리 경로")
    
    # 설정
    sort_order = Column(Integer, nullable=False, default=0, comment="정렬 순서")
    is_active = Column(Boolean, nullable=False, default=True, comment="활성화 여부")
    
    # 통계
    document_count = Column(Integer, nullable=False, default=0, comment="문서 수")
    
    # 시스템 필드
    created_by = Column(String(20), nullable=True, comment="생성자")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일")
    last_modified_by = Column(String(20), nullable=True, comment="최종 수정자")
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="최종 수정일")


class TbContainerCategories(Base):
    """컨테이너 카테고리 연결 테이블"""
    __tablename__ = "tb_container_categories"
    
    # 기본 정보
    container_category_id = Column(Integer, primary_key=True, autoincrement=True, comment="컨테이너 카테고리 ID")
    container_id = Column(String(50), nullable=False, comment="컨테이너 ID")
    category_id = Column(String(20), nullable=False, comment="카테고리 ID")
    
    # 설정
    is_primary = Column(Boolean, nullable=False, default=False, comment="주 카테고리 여부")
    is_active = Column(Boolean, nullable=False, default=True, comment="활성화 여부")
    
    # 시스템 필드
    created_by = Column(String(20), nullable=True, comment="생성자")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일")


class TbSystemSettings(Base):
    """시스템 설정 테이블"""
    __tablename__ = "tb_system_settings"
    
    # 기본 정보
    setting_id = Column(Integer, primary_key=True, autoincrement=True, comment="설정 ID")
    setting_key = Column(String(100), nullable=False, unique=True, comment="설정 키")
    setting_value = Column(Text, nullable=True, comment="설정 값")
    setting_type = Column(String(20), nullable=False, comment="설정 타입 (string/int/boolean/json)")
    
    # 메타데이터
    setting_category = Column(String(50), nullable=True, comment="설정 카테고리")
    setting_description = Column(Text, nullable=True, comment="설정 설명")
    is_encrypted = Column(Boolean, nullable=False, default=False, comment="암호화 여부")
    is_system = Column(Boolean, nullable=False, default=False, comment="시스템 설정 여부")
    
    # 시스템 필드
    created_by = Column(String(20), nullable=True, comment="생성자")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일")
    last_modified_by = Column(String(20), nullable=True, comment="최종 수정자")
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="최종 수정일")
