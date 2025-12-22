"""
특허 서지정보 관리 SQLAlchemy 모델
KIPRIS, USPTO, EPO 등 다양한 특허 데이터 소스 지원
"""
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    CheckConstraint,
    Float,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, ENUM
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base


# =============================================================================
# 1. 특허 서지정보 메인 테이블
# =============================================================================

class TbPatentBibliographicInfo(Base):
    """
    특허 서지정보 메인 테이블
    
    국가별 특허 시스템(KIPRIS, USPTO, EPO 등)에서 수집한 특허 서지정보를 통합 관리
    """
    __tablename__ = "tb_patent_bibliographic_info"
    
    # 기본키
    patent_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="특허 내부 ID")
    
    # 특허 식별 정보
    application_number = Column(String(50), nullable=False, comment="출원번호 (예: 10-2023-1234567)")
    publication_number = Column(String(50), nullable=True, comment="공개번호")
    registration_number = Column(String(50), nullable=True, comment="등록번호")
    
    # 국가 및 관할권
    jurisdiction = Column(
        String(10), 
        nullable=False, 
        default='KR',
        comment="관할권 코드 (KR/US/EP/JP/CN/WO 등)"
    )
    
    # 특허 제목 및 요약
    title = Column(String(1000), nullable=False, comment="발명의 명칭")
    title_en = Column(String(1000), nullable=True, comment="영문 발명의 명칭")
    abstract = Column(Text, nullable=True, comment="초록")
    abstract_en = Column(Text, nullable=True, comment="영문 초록")
    
    # 날짜 정보
    application_date = Column(Date, nullable=True, comment="출원일")
    publication_date = Column(Date, nullable=True, comment="공개일")
    registration_date = Column(Date, nullable=True, comment="등록일")
    priority_date = Column(Date, nullable=True, comment="우선일")
    expiration_date = Column(Date, nullable=True, comment="만료일")
    
    # 법적 상태
    legal_status = Column(
        String(50), 
        nullable=False, 
        default='APPLICATION',
        comment="법적 상태 (APPLICATION/PUBLISHED/GRANTED/REJECTED/WITHDRAWN/EXPIRED)"
    )
    current_status_date = Column(Date, nullable=True, comment="현재 상태 변경일")
    
    # 청구항 정보
    claims_text = Column(Text, nullable=True, comment="청구항 전문")
    claims_count = Column(Integer, nullable=True, default=0, comment="청구항 수")
    independent_claims_count = Column(Integer, nullable=True, default=0, comment="독립항 수")
    
    # 명세서 전문 (선택적 저장)
    description = Column(Text, nullable=True, comment="발명의 상세한 설명")
    background = Column(Text, nullable=True, comment="발명의 배경")
    technical_field = Column(String(500), nullable=True, comment="기술 분야")
    
    # 패밀리 정보
    family_id = Column(String(100), nullable=True, comment="패밀리 ID (동일 발명의 각국 출원)")
    
    # 인용 통계
    cited_by_count = Column(Integer, nullable=False, default=0, comment="피인용 횟수")
    cites_count = Column(Integer, nullable=False, default=0, comment="인용 횟수")
    
    # 데이터 소스 정보
    data_source = Column(
        String(20), 
        nullable=False, 
        default='KIPRIS',
        comment="데이터 소스 (KIPRIS/USPTO/EPO/GOOGLE_PATENTS)"
    )
    source_url = Column(String(500), nullable=True, comment="원본 URL")
    
    # 메타데이터 (JSON)
    additional_metadata = Column(JSONB, nullable=True, comment="추가 메타데이터 (기술 분류, 키워드 등)")
    
    # 임베딩 벡터 (전체 특허 내용 기반)
    embedding_vector = Column(
        Vector(1536), 
        nullable=True, 
        comment="특허 전체 내용 임베딩 (제목+초록+청구항)"
    )
    
    # 시스템 관리 정보
    knowledge_container_id = Column(String(50), nullable=True, comment="지식 컨테이너 ID")
    imported_by = Column(String(50), nullable=True, comment="수집한 사용자 ID")
    imported_date = Column(DateTime(timezone=True), server_default=func.now(), comment="수집일시")
    last_synced_date = Column(DateTime(timezone=True), nullable=True, comment="마지막 동기화 일시")
    
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    del_yn = Column(String(1), nullable=False, default='N', comment="삭제 여부")
    
    # 관계 정의
    inventors = relationship("TbPatentInventors", back_populates="patent", cascade="all, delete-orphan")
    applicants = relationship("TbPatentApplicants", back_populates="patent", cascade="all, delete-orphan")
    ipc_classifications = relationship("TbPatentIpcClassifications", back_populates="patent", cascade="all, delete-orphan")
    citations_given = relationship(
        "TbPatentCitations", 
        foreign_keys="TbPatentCitations.citing_patent_id",
        back_populates="citing_patent",
        cascade="all, delete-orphan"
    )
    citations_received = relationship(
        "TbPatentCitations",
        foreign_keys="TbPatentCitations.cited_patent_id",
        back_populates="cited_patent"
    )
    legal_status_history = relationship("TbPatentLegalStatus", back_populates="patent", cascade="all, delete-orphan")
    family_members = relationship("TbPatentFamilyMembers", back_populates="patent", cascade="all, delete-orphan")
    search_results = relationship("TbPatentSearchResults", back_populates="candidate_patent", cascade="all, delete-orphan")


# 인덱스
Index('idx_patent_application_number', TbPatentBibliographicInfo.application_number, unique=True)
Index('idx_patent_jurisdiction', TbPatentBibliographicInfo.jurisdiction)
Index('idx_patent_legal_status', TbPatentBibliographicInfo.legal_status)
Index('idx_patent_application_date', TbPatentBibliographicInfo.application_date)
Index('idx_patent_container', TbPatentBibliographicInfo.knowledge_container_id)
Index('idx_patent_family', TbPatentBibliographicInfo.family_id)
Index('idx_patent_del_yn', TbPatentBibliographicInfo.del_yn)
Index('idx_patent_embedding', TbPatentBibliographicInfo.embedding_vector, postgresql_using='ivfflat', postgresql_ops={'embedding_vector': 'vector_cosine_ops'})


# =============================================================================
# 2. 발명자 테이블
# =============================================================================

class TbPatentInventors(Base):
    """특허 발명자 정보"""
    __tablename__ = "tb_patent_inventors"
    
    inventor_id = Column(BigInteger, primary_key=True, autoincrement=True)
    patent_id = Column(BigInteger, ForeignKey('tb_patent_bibliographic_info.patent_id', ondelete='CASCADE'), nullable=False)
    
    inventor_name = Column(String(300), nullable=False, comment="발명자 이름")
    inventor_name_en = Column(String(300), nullable=True, comment="영문 이름")
    inventor_order = Column(Integer, nullable=False, comment="발명자 순서")
    
    # 소속 정보
    country = Column(String(100), nullable=True, comment="국가")
    address = Column(String(500), nullable=True, comment="주소")
    
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    patent = relationship("TbPatentBibliographicInfo", back_populates="inventors")


Index('idx_patent_inventor_name', TbPatentInventors.inventor_name)
Index('idx_patent_inventor_patent', TbPatentInventors.patent_id)


# =============================================================================
# 3. 출원인 테이블
# =============================================================================

class TbPatentApplicants(Base):
    """특허 출원인 정보"""
    __tablename__ = "tb_patent_applicants"
    
    applicant_id = Column(BigInteger, primary_key=True, autoincrement=True)
    patent_id = Column(BigInteger, ForeignKey('tb_patent_bibliographic_info.patent_id', ondelete='CASCADE'), nullable=False)
    
    applicant_name = Column(String(300), nullable=False, comment="출원인 명칭")
    applicant_name_en = Column(String(300), nullable=True, comment="영문 명칭")
    applicant_type = Column(String(50), nullable=True, comment="출원인 유형 (개인/법인/대학/연구소)")
    applicant_order = Column(Integer, nullable=False, comment="출원인 순서")
    
    # KIPRIS 출원인 코드 (검색 정확도 향상)
    customer_no = Column(String(50), nullable=True, comment="KIPRIS 출원인 코드")
    
    # 소속 정보
    country = Column(String(100), nullable=True, comment="국가")
    address = Column(String(500), nullable=True, comment="주소")
    
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    patent = relationship("TbPatentBibliographicInfo", back_populates="applicants")


Index('idx_patent_applicant_name', TbPatentApplicants.applicant_name)
Index('idx_patent_applicant_patent', TbPatentApplicants.patent_id)
Index('idx_patent_applicant_customer_no', TbPatentApplicants.customer_no)


# =============================================================================
# 4. IPC 분류 테이블
# =============================================================================

class TbPatentIpcClassifications(Base):
    """IPC/CPC 분류 코드"""
    __tablename__ = "tb_patent_ipc_classifications"
    
    classification_id = Column(BigInteger, primary_key=True, autoincrement=True)
    patent_id = Column(BigInteger, ForeignKey('tb_patent_bibliographic_info.patent_id', ondelete='CASCADE'), nullable=False)
    
    classification_type = Column(String(10), nullable=False, default='IPC', comment="분류 타입 (IPC/CPC)")
    classification_code = Column(String(50), nullable=False, comment="분류 코드 (예: G06N3/08)")
    
    # IPC 계층 구조
    section = Column(String(1), nullable=True, comment="섹션 (A-H)")
    class_code = Column(String(3), nullable=True, comment="클래스 (예: 06)")
    subclass = Column(String(4), nullable=True, comment="서브클래스 (예: N)")
    main_group = Column(String(10), nullable=True, comment="메인 그룹 (예: 3)")
    subgroup = Column(String(20), nullable=True, comment="서브 그룹 (예: 08)")
    
    classification_order = Column(Integer, nullable=False, comment="분류 순서")
    is_main_classification = Column(Boolean, nullable=False, default=False, comment="주 분류 여부")
    
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    patent = relationship("TbPatentBibliographicInfo", back_populates="ipc_classifications")


Index('idx_patent_ipc_code', TbPatentIpcClassifications.classification_code)
Index('idx_patent_ipc_patent', TbPatentIpcClassifications.patent_id)
Index('idx_patent_ipc_section', TbPatentIpcClassifications.section)


# =============================================================================
# 5. 인용 관계 테이블
# =============================================================================

class TbPatentCitations(Base):
    """특허 인용 관계"""
    __tablename__ = "tb_patent_citations"
    
    citation_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    citing_patent_id = Column(BigInteger, ForeignKey('tb_patent_bibliographic_info.patent_id', ondelete='CASCADE'), nullable=False, comment="인용하는 특허")
    cited_patent_id = Column(BigInteger, ForeignKey('tb_patent_bibliographic_info.patent_id', ondelete='CASCADE'), nullable=False, comment="피인용 특허")
    
    citation_type = Column(String(50), nullable=True, comment="인용 유형 (심사관인용/출원인인용)")
    citation_category = Column(String(50), nullable=True, comment="인용 범주 (X/Y/A 등)")
    
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    citing_patent = relationship("TbPatentBibliographicInfo", foreign_keys=[citing_patent_id], back_populates="citations_given")
    cited_patent = relationship("TbPatentBibliographicInfo", foreign_keys=[cited_patent_id], back_populates="citations_received")


Index('idx_citation_citing', TbPatentCitations.citing_patent_id)
Index('idx_citation_cited', TbPatentCitations.cited_patent_id)
UniqueConstraint(TbPatentCitations.citing_patent_id, TbPatentCitations.cited_patent_id, name='uq_citation_pair')


# =============================================================================
# 6. 법적 상태 이력 테이블
# =============================================================================

class TbPatentLegalStatus(Base):
    """특허 법적 상태 변경 이력"""
    __tablename__ = "tb_patent_legal_status"
    
    status_id = Column(BigInteger, primary_key=True, autoincrement=True)
    patent_id = Column(BigInteger, ForeignKey('tb_patent_bibliographic_info.patent_id', ondelete='CASCADE'), nullable=False)
    
    status_code = Column(String(50), nullable=False, comment="상태 코드 (출원/공개/등록/거절/취하/소멸)")
    status_date = Column(Date, nullable=False, comment="상태 변경일")
    status_description = Column(Text, nullable=True, comment="상태 설명")
    
    # 심사 이력 상세
    event_type = Column(String(100), nullable=True, comment="이벤트 유형 (의견제출통지/보정서제출 등)")
    event_code = Column(String(50), nullable=True, comment="이벤트 코드")
    
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    patent = relationship("TbPatentBibliographicInfo", back_populates="legal_status_history")


Index('idx_legal_status_patent', TbPatentLegalStatus.patent_id)
Index('idx_legal_status_date', TbPatentLegalStatus.status_date)


# =============================================================================
# 7. 패밀리 특허 테이블
# =============================================================================

class TbPatentFamilyMembers(Base):
    """특허 패밀리 구성원 (동일 발명의 각국 출원)"""
    __tablename__ = "tb_patent_family_members"
    
    family_member_id = Column(BigInteger, primary_key=True, autoincrement=True)
    patent_id = Column(BigInteger, ForeignKey('tb_patent_bibliographic_info.patent_id', ondelete='CASCADE'), nullable=False)
    
    family_id = Column(String(100), nullable=False, comment="패밀리 ID")
    member_application_number = Column(String(50), nullable=False, comment="패밀리 구성원 출원번호")
    member_jurisdiction = Column(String(10), nullable=False, comment="패밀리 구성원 관할권")
    
    priority_claim = Column(Boolean, nullable=False, default=False, comment="우선권 주장 여부")
    
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    patent = relationship("TbPatentBibliographicInfo", back_populates="family_members")


Index('idx_family_members_family', TbPatentFamilyMembers.family_id)
Index('idx_family_members_patent', TbPatentFamilyMembers.patent_id)


# =============================================================================
# 8. 선행기술조사 세션 테이블
# =============================================================================

class TbPatentSearchSessions(Base):
    """
    선행기술조사 세션 테이블
    
    사용자가 수행한 선행기술조사의 전체 맥락을 저장
    """
    __tablename__ = "tb_patent_search_sessions"
    
    session_id = Column(String(50), primary_key=True, comment="세션 UUID")
    
    # 사용자 정보
    user_emp_no = Column(String(20), nullable=False, comment="사용자 사번")
    knowledge_container_id = Column(String(50), nullable=True, comment="지식 컨테이너 ID")
    
    # 검색 대상 정보
    target_type = Column(
        String(50), 
        nullable=False, 
        comment="대상 유형 (EXISTING_PATENT/IDEA_DOCUMENT/TEXT_INPUT)"
    )
    target_document_id = Column(String(100), nullable=True, comment="대상 문서 ID (file_bss_info_sno 또는 patent_id)")
    target_patent_id = Column(BigInteger, ForeignKey('tb_patent_bibliographic_info.patent_id'), nullable=True, comment="대상 특허 ID")
    target_text = Column(Text, nullable=True, comment="직접 입력한 아이디어 텍스트")
    
    # 추출된 특허 정보 (TargetPatentSpec)
    extracted_patent_info = Column(JSONB, nullable=True, comment="추출된 특허 정보 (서지/청구항/핵심요소)")
    
    # 검색 전략
    search_plan = Column(JSONB, nullable=True, comment="검색 계획 (SearchPlan)")
    search_iterations = Column(JSONB, nullable=True, comment="ReAct 반복 검색 이력")
    
    # 세션 상태
    session_status = Column(
        String(20), 
        nullable=False, 
        default='IN_PROGRESS',
        comment="세션 상태 (IN_PROGRESS/COMPLETED/FAILED)"
    )
    
    # 시간 정보
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    completed_date = Column(DateTime(timezone=True), nullable=True)
    
    # 관계
    search_results = relationship("TbPatentSearchResults", back_populates="session", cascade="all, delete-orphan")
    reports = relationship("TbPatentPriorArtReports", back_populates="session", cascade="all, delete-orphan")


Index('idx_search_session_user', TbPatentSearchSessions.user_emp_no)
Index('idx_search_session_container', TbPatentSearchSessions.knowledge_container_id)
Index('idx_search_session_status', TbPatentSearchSessions.session_status)
Index('idx_search_session_date', TbPatentSearchSessions.created_date)


# =============================================================================
# 9. 선행기술조사 결과 테이블
# =============================================================================

class TbPatentSearchResults(Base):
    """
    선행기술조사 후보 특허 테이블
    
    검색 세션에서 발견한 후보 특허들과 유사도/근거 정보
    """
    __tablename__ = "tb_patent_search_results"
    
    result_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    session_id = Column(String(50), ForeignKey('tb_patent_search_sessions.session_id', ondelete='CASCADE'), nullable=False)
    candidate_patent_id = Column(BigInteger, ForeignKey('tb_patent_bibliographic_info.patent_id', ondelete='CASCADE'), nullable=False)
    
    # 순위 및 점수
    rank_order = Column(Integer, nullable=False, comment="순위")
    similarity_score = Column(Float, nullable=True, comment="유사도 점수 (0.0-1.0)")
    
    # 유사도 근거
    matched_components = Column(ARRAY(Text), nullable=True, comment="매칭된 핵심 구성요소")
    matched_ipc_codes = Column(ARRAY(String), nullable=True, comment="매칭된 IPC 코드")
    key_snippets = Column(JSONB, nullable=True, comment="핵심 유사 구절 (제목/초록/청구항)")
    
    # 비교 분석
    comparison_summary = Column(Text, nullable=True, comment="유사점/차이점 요약")
    risk_level = Column(String(20), nullable=True, comment="리스크 수준 (HIGH/MEDIUM/LOW)")
    
    # 사용자 평가
    user_rating = Column(Integer, nullable=True, comment="사용자 평가 (1-5)")
    user_notes = Column(Text, nullable=True, comment="사용자 메모")
    
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    session = relationship("TbPatentSearchSessions", back_populates="search_results")
    candidate_patent = relationship("TbPatentBibliographicInfo", back_populates="search_results")


Index('idx_search_result_session', TbPatentSearchResults.session_id)
Index('idx_search_result_candidate', TbPatentSearchResults.candidate_patent_id)
Index('idx_search_result_rank', TbPatentSearchResults.session_id, TbPatentSearchResults.rank_order)


# =============================================================================
# 10. 선행기술조사 보고서 테이블
# =============================================================================

class TbPatentPriorArtReports(Base):
    """
    선행기술조사 최종 보고서
    
    검색 결과를 바탕으로 생성된 구조화된 보고서
    """
    __tablename__ = "tb_patent_prior_art_reports"
    
    report_id = Column(String(50), primary_key=True, comment="보고서 UUID")
    session_id = Column(String(50), ForeignKey('tb_patent_search_sessions.session_id', ondelete='CASCADE'), nullable=False)
    
    # 보고서 메타데이터
    report_title = Column(String(500), nullable=False, comment="보고서 제목")
    report_type = Column(String(50), nullable=False, default='PRIOR_ART_SEARCH', comment="보고서 유형")
    
    # 보고서 내용 (구조화)
    executive_summary = Column(Text, nullable=True, comment="요약")
    target_patent_summary = Column(JSONB, nullable=True, comment="대상 특허 요약")
    search_strategy_summary = Column(Text, nullable=True, comment="검색 전략 요약")
    top_candidates_summary = Column(JSONB, nullable=True, comment="상위 후보 특허 요약")
    detailed_comparisons = Column(JSONB, nullable=True, comment="상세 비교 분석")
    conclusions = Column(Text, nullable=True, comment="결론")
    recommendations = Column(ARRAY(Text), nullable=True, comment="권장사항")
    
    # 보고서 파일
    report_file_path = Column(String(500), nullable=True, comment="생성된 보고서 파일 경로 (PDF/DOCX)")
    
    # 시스템 정보
    generated_by = Column(String(50), nullable=False, comment="생성자 사번")
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 관계
    session = relationship("TbPatentSearchSessions", back_populates="reports")


Index('idx_report_session', TbPatentPriorArtReports.session_id)
Index('idx_report_date', TbPatentPriorArtReports.created_date)
