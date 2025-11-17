"""
WKMS 파일 관리 모델
database_schema_specification.md 명세서에 따른 정확한 구현
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, CHAR, Boolean
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.core.database import Base
from app.core.config import settings

class TbFileBssInfo(Base):
    """파일 기본 정보 테이블"""
    __tablename__ = "tb_file_bss_info"
    
    # 컬럼 정의 (실제 데이터베이스 컬럼명과 일치하도록 수정)
    file_bss_info_sno = Column(Integer, primary_key=True, autoincrement=True, comment="파일 기본 정보 일련번호")
    drcy_sno = Column(Integer, nullable=False, comment="디렉토리 일련번호")
    file_dtl_info_sno = Column(Integer, nullable=True, comment="파일 상세 정보 일련번호")
    file_lgc_nm = Column(String(255), nullable=False, comment="파일 논리명")
    file_psl_nm = Column(String(255), nullable=False, comment="파일 물리명")
    file_extsn = Column(String(10), nullable=False, comment="파일 확장자")
    path = Column(String(500), nullable=False, comment="파일 저장 경로")
    del_yn = Column(CHAR(1), nullable=False, default='N', comment="삭제 여부 (Y/N)")
    created_by = Column(String(50), nullable=True, comment="생성자 ID")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일시")
    last_modified_by = Column(String(50), nullable=True, comment="최종 수정자 ID")
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="최종 수정일시")
    
    # 추가 컬럼들 (실제 데이터베이스에 맞춤)
    korean_metadata = Column(JSON, nullable=True, comment="한국어 메타데이터")
    chunk_count = Column(Integer, default=0, comment="청크 개수")
    knowledge_container_id = Column(String(50), nullable=True, comment="지식 컨테이너 ID")
    permission_level = Column(String(20), nullable=False, default='INTERNAL', comment="권한 레벨")
    access_restrictions = Column(JSONB, nullable=True, comment="접근 제한")
    owner_emp_no = Column(String(20), nullable=True, comment="소유자 사번")
    last_accessed_date = Column(DateTime(timezone=True), nullable=True, comment="마지막 접근일")
    access_count = Column(Integer, nullable=False, default=0, comment="접근 횟수")
    
    # 비동기 처리 상태 관리 (2025-10-14 추가)
    processing_status = Column(String(20), default='pending', comment="처리 상태 (pending/processing/completed/failed)")
    processing_error = Column(Text, nullable=True, comment="처리 오류 메시지")
    processing_started_at = Column(DateTime(timezone=True), nullable=True, comment="처리 시작 시간")
    processing_completed_at = Column(DateTime(timezone=True), nullable=True, comment="처리 완료 시간")
    
    # 🎯 문서 유형별 파이프라인 지원 (2025-10-20 추가)
    document_type = Column(
        String(50), 
        default='general', 
        nullable=False,
        comment="문서 유형 (general/academic_paper/patent/technical_report/business_document/presentation)"
    )
    processing_options = Column(
        JSONB, 
        default={}, 
        nullable=False,
        comment="문서 유형별 처리 옵션 (extract_figures, parse_references 등)"
    )
    
    # 인덱스 정의 (실제 데이터베이스에 맞춤)
    __table_args__ = (
        Index('idx_tb_file_bss_info_del_yn', 'del_yn'),
        Index('idx_file_bss_info_container', 'knowledge_container_id'),
        Index('idx_file_bss_info_document_type', 'document_type'),  # 🎯 문서 유형 인덱스
        Index('idx_file_bss_info_container_type', 'knowledge_container_id', 'document_type'),  # 🎯 복합 인덱스
        Index('idx_file_bss_info_owner', 'owner_emp_no'),
        Index('idx_file_bss_info_permission', 'permission_level'),
        Index('idx_file_bss_info_accessed', 'last_accessed_date'),
        Index('idx_file_bss_info_processing_status', 'processing_status'),  # 상태 조회 최적화
    )
    
    # 관계 정의
    search_indexes = relationship("TbDocumentSearchIndex", back_populates="file_info")

class TbFileDtlInfo(Base):
    """파일 상세 정보 테이블"""
    __tablename__ = "tb_file_dtl_info"
    
    # 컬럼 정의 (실제 데이터베이스 컬럼명과 일치하도록 수정)
    file_dtl_info_sno = Column(Integer, primary_key=True, autoincrement=True, comment="파일 상세 정보 일련번호")
    sj = Column(String(500), nullable=True, comment="파일 제목")
    cn = Column(Text, nullable=True, comment="파일 내용 요약")
    kwrd = Column(String(1000), nullable=True, comment="키워드 (콤마 구분)")
    authr = Column(String(100), nullable=True, comment="작성자")
    wrt_de = Column(String(8), nullable=True, comment="작성일 (YYYYMMDD)")
    updt_de = Column(String(8), nullable=True, comment="수정일 (YYYYMMDD)")
    ctgry_cd = Column(String(20), nullable=True, comment="카테고리 코드")
    ctgry_nm = Column(String(100), nullable=True, comment="카테고리명")
    file_sz = Column(Integer, nullable=True, comment="파일 크기 (bytes)")
    page_co = Column(Integer, nullable=True, comment="페이지 수")
    lang_cd = Column(String(10), nullable=True, comment="언어 코드")
    secrty_lvl = Column(String(10), nullable=True, comment="보안 등급")
    vrsn = Column(String(20), nullable=True, comment="버전")
    tag = Column(String(500), nullable=True, comment="태그 (콤마 구분)")
    sumry = Column(Text, nullable=True, comment="요약")
    del_yn = Column(CHAR(1), nullable=False, default='N', comment="삭제 여부 (Y/N)")
    created_by = Column(String(50), nullable=True, comment="생성자 ID")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일시")
    last_modified_by = Column(String(50), nullable=True, comment="최종 수정자 ID")
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="최종 수정일시")
    
    # 인덱스 정의 (실제 데이터베이스에 맞춤)
    __table_args__ = (
        Index('idx_tb_file_dtl_info_sj', 'sj'),
        Index('idx_tb_file_dtl_info_authr', 'authr'),
        Index('idx_tb_file_dtl_info_ctgry_cd', 'ctgry_cd'),
        Index('idx_tb_file_dtl_info_del_yn', 'del_yn'),
    )
