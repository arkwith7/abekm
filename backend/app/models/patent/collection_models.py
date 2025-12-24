"""
특허 수집 관련 모델
KIPRIS 자동 수집 설정 및 작업 상태 관리
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.core.database import Base


class TbPatentCollectionSettings(Base):
    """사용자별 특허 수집 설정 테이블"""
    __tablename__ = "tb_patent_collection_settings"
    
    # 기본 정보
    setting_id = Column(Integer, primary_key=True, autoincrement=True, comment="설정 ID")
    user_emp_no = Column(String(20), ForeignKey('tb_user.emp_no'), nullable=False, comment="사용자 사번")
    container_id = Column(String(50), ForeignKey('tb_knowledge_containers.container_id'), nullable=False, comment="대상 컨테이너 ID")
    
    # 검색 조건 (JSONB)
    # 예: {"ipc_codes": ["G06N", "G06F"], "keywords": ["AI", "딥러닝"], "applicants": ["삼성전자"]}
    search_config = Column(JSONB, nullable=False, comment="검색 조건 (IPC, 키워드, 출원인)")
    max_results = Column(Integer, nullable=False, default=100, comment="최대 수집 건수")
    
    # 수집 옵션
    auto_download_pdf = Column(Boolean, nullable=False, default=False, comment="PDF 자동 다운로드 여부")
    auto_generate_embeddings = Column(Boolean, nullable=False, default=True, comment="임베딩 자동 생성 여부")
    
    # 스케줄 설정
    schedule_type = Column(String(20), nullable=False, default='manual', comment="스케줄 타입 (manual/daily/weekly/monthly)")
    schedule_config = Column(JSONB, nullable=True, comment="스케줄 상세 설정")
    
    # 상태
    is_active = Column(Boolean, nullable=False, default=True, comment="활성화 여부")
    last_collection_date = Column(DateTime(timezone=True), nullable=True, comment="마지막 수집 일시")
    last_collection_result = Column(JSONB, nullable=True, comment="마지막 수집 결과 (collected, errors)")
    
    # 시스템 필드
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일")
    updated_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="수정일")
    
    def __repr__(self):
        return f"<PatentCollectionSetting(id={self.setting_id}, user={self.user_emp_no}, container={self.container_id})>"


class TbPatentCollectionTasks(Base):
    """특허 수집 작업 상태 추적 테이블"""
    __tablename__ = "tb_patent_collection_tasks"
    
    # 기본 정보
    task_id = Column(String(100), primary_key=True, comment="Celery Task ID")
    setting_id = Column(Integer, ForeignKey('tb_patent_collection_settings.setting_id'), nullable=True, comment="수집 설정 ID")
    user_emp_no = Column(String(20), nullable=False, comment="사용자 사번")
    
    # 작업 상태
    status = Column(String(20), nullable=False, default='pending', comment="작업 상태 (pending/running/completed/failed)")
    progress_current = Column(Integer, nullable=False, default=0, comment="현재 진행 건수")
    progress_total = Column(Integer, nullable=False, default=0, comment="전체 작업 건수")
    
    # 결과
    collected_count = Column(Integer, nullable=False, default=0, comment="수집 성공 건수")
    error_count = Column(Integer, nullable=False, default=0, comment="오류 건수")
    error_details = Column(JSONB, nullable=True, comment="오류 상세 정보")
    
    # 시간
    started_at = Column(DateTime(timezone=True), nullable=True, comment="시작 시간")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="완료 시간")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일")
    
    def __repr__(self):
        return f"<PatentCollectionTask(id={self.task_id}, status={self.status}, progress={self.progress_current}/{self.progress_total})>"
