"""
IPC (국제특허분류) 코드 체계 모델
International Patent Classification System Models

IPC는 계층 구조를 가진 특허 기술 분류 체계:
- Section (섹션): A, B, C, D, E, F, G, H (8개)
- Class (클래스): 섹션 + 2자리 숫자 (예: H04)
- Subclass (서브클래스): 클래스 + 1자리 문자 (예: H04W)
- Group (그룹): 서브클래스 + 숫자/숫자 (예: H04W 4/00)
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Index,
)
from sqlalchemy.sql import func
from app.core.database import Base


class TbIpcCode(Base):
    """
    IPC 분류 코드 마스터 테이블
    
    계층 구조:
    - level='SECTION': code='H', parent_code=NULL
    - level='CLASS': code='H04', parent_code='H'
    - level='SUBCLASS': code='H04W', parent_code='H04'
    - level='GROUP': code='H04W 4/00', parent_code='H04W'
    """
    __tablename__ = "tb_ipc_code"
    
    # 기본키
    code = Column(String(20), primary_key=True, comment="IPC 분류 코드 (예: H04W, H04W 4/00)")
    
    # 계층 정보
    level = Column(
        String(10), 
        nullable=False,
        comment="분류 레벨 (SECTION/CLASS/SUBCLASS/GROUP/SUBGROUP)"
    )
    parent_code = Column(
        String(20),
        nullable=True,
        comment="상위 분류 코드 (SECTION의 경우 NULL)"
    )
    
    # 분류 설명
    description_ko = Column(Text, nullable=True, comment="한글 설명")
    description_en = Column(Text, nullable=True, comment="영문 설명")
    
    # 추가 메타데이터
    section = Column(String(1), nullable=True, comment="섹션 (A~H)")
    class_code = Column(String(3), nullable=True, comment="클래스 (H04 등)")
    subclass_code = Column(String(4), nullable=True, comment="서브클래스 (H04W 등)")
    
    # 시스템 필드
    is_active = Column(String(1), nullable=False, default='Y', comment="활성화 여부 (Y/N)")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<TbIpcCode(code='{self.code}', level='{self.level}', desc='{self.description_ko[:30] if self.description_ko else ''}')>"


# 인덱스
Index('idx_ipc_level', TbIpcCode.level)
Index('idx_ipc_parent', TbIpcCode.parent_code)
Index('idx_ipc_section', TbIpcCode.section)
Index('idx_ipc_active', TbIpcCode.is_active)


class TbPatentMetadata(Base):
    """
    특허 메타데이터 테이블 (기존 문서 시스템과의 연계)
    
    tb_file_bss_info와 1:1 또는 1:N 관계로 특허 전용 메타데이터 저장
    """
    __tablename__ = "tb_patent_metadata"
    
    # 기본키
    metadata_id = Column(Integer, primary_key=True, autoincrement=True, comment="메타데이터 ID")
    
    # 문서 연계 (기존 시스템)
    file_bss_info_sno = Column(
        Integer,
        nullable=True,
        comment="파일 기본 정보 일련번호 (tb_file_bss_info FK, nullable for external patents)"
    )
    
    # 특허 식별 정보
    application_number = Column(String(50), nullable=False, comment="출원번호 (예: 10-2023-0123456)")
    publication_number = Column(String(50), nullable=True, comment="공개번호")
    registration_number = Column(String(50), nullable=True, comment="등록번호")
    
    # IPC 분류 (배열 대신 정규화된 연결 테이블 사용 권장이지만, 빠른 조회를 위해 중복 저장)
    ipc_codes = Column(Text, nullable=True, comment="IPC 코드 목록 (쉼표 구분, 예: H04W 4/00, G06N 3/08)")
    main_ipc_code = Column(String(20), nullable=True, comment="주 IPC 코드")
    
    # 출원인/발명자 (간소화된 버전, 상세는 별도 테이블)
    applicant = Column(String(200), nullable=True, comment="대표 출원인")
    inventor = Column(String(200), nullable=True, comment="대표 발명자")
    
    # 법적 상태
    legal_status = Column(
        String(50),
        nullable=False,
        default='APPLICATION',
        comment="법적 상태 (APPLICATION/PUBLISHED/GRANTED/REJECTED/WITHDRAWN/EXPIRED)"
    )
    status_date = Column(DateTime(timezone=True), nullable=True, comment="상태 변경일")
    
    # 날짜 정보
    application_date = Column(DateTime(timezone=True), nullable=True, comment="출원일")
    publication_date = Column(DateTime(timezone=True), nullable=True, comment="공개일")
    registration_date = Column(DateTime(timezone=True), nullable=True, comment="등록일")
    
    # 요약 정보 (빠른 조회용)
    abstract = Column(Text, nullable=True, comment="초록")
    claims_summary = Column(Text, nullable=True, comment="청구항 요약 (첫 독립항)")
    
    # 컨테이너 연계
    knowledge_container_id = Column(String(50), nullable=True, comment="지식 컨테이너 ID")
    
    # 시스템 필드
    created_by = Column(String(50), nullable=True, comment="생성자")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_by = Column(String(50), nullable=True, comment="최종 수정자")
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    del_yn = Column(String(1), nullable=False, default='N', comment="삭제 여부 (Y/N)")
    
    def __repr__(self):
        return f"<TbPatentMetadata(id={self.metadata_id}, app_no='{self.application_number}', ipc='{self.main_ipc_code}')>"


# 인덱스
Index('idx_patent_meta_file', TbPatentMetadata.file_bss_info_sno)
Index('idx_patent_meta_app_no', TbPatentMetadata.application_number, unique=True)
Index('idx_patent_meta_pub_no', TbPatentMetadata.publication_number)
Index('idx_patent_meta_reg_no', TbPatentMetadata.registration_number)
Index('idx_patent_meta_main_ipc', TbPatentMetadata.main_ipc_code)
Index('idx_patent_meta_status', TbPatentMetadata.legal_status)
Index('idx_patent_meta_container', TbPatentMetadata.knowledge_container_id)
Index('idx_patent_meta_del_yn', TbPatentMetadata.del_yn)
