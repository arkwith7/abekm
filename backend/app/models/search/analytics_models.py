"""
WKMS 검색 및 분석 로그 모델
"""
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class TbKnowledgeAccessLog(Base):
    """지식 접근 로그 테이블"""
    __tablename__ = "tb_knowledge_access_log"
    
    # 기본 정보
    access_log_id = Column(Integer, primary_key=True, autoincrement=True, comment="접근 로그 ID")
    user_emp_no = Column(String(20), nullable=False, comment="사용자 사번")
    file_bss_info_sno = Column(Integer, nullable=True, comment="파일 기본 정보 일련번호")
    knowledge_container_id = Column(String(50), nullable=True, comment="지식 컨테이너 ID")
    
    # 접근 정보
    access_type = Column(String(20), nullable=False, comment="접근 유형 (view/download/search/chat)")
    access_method = Column(String(20), nullable=True, comment="접근 방법 (web/api/mobile)")
    
    # 검색 정보 (검색인 경우)
    search_query = Column(Text, nullable=True, comment="검색 쿼리")
    search_results_count = Column(Integer, nullable=True, comment="검색 결과 수")
    search_method = Column(String(20), nullable=True, comment="검색 방법 (semantic/keyword/hybrid)")
    
    # 세션 정보
    session_id = Column(String(100), nullable=True, comment="세션 ID")
    ip_address = Column(String(50), nullable=True, comment="IP 주소")
    user_agent = Column(Text, nullable=True, comment="사용자 에이전트")
    
    # 결과 정보
    response_time_ms = Column(Integer, nullable=True, comment="응답 시간 (밀리초)")
    is_successful = Column(Boolean, nullable=False, default=True, comment="성공 여부")
    error_message = Column(Text, nullable=True, comment="오류 메시지")
    
    # 시스템 필드
    access_date = Column(DateTime(timezone=True), server_default=func.now(), comment="접근 일시")


class TbKnowledgeSharingLog(Base):
    """지식 공유 로그 테이블"""
    __tablename__ = "tb_knowledge_sharing_log"
    
    # 기본 정보
    sharing_log_id = Column(Integer, primary_key=True, autoincrement=True, comment="공유 로그 ID")
    sharer_emp_no = Column(String(20), nullable=False, comment="공유자 사번")
    file_bss_info_sno = Column(Integer, nullable=False, comment="파일 기본 정보 일련번호")
    knowledge_container_id = Column(String(50), nullable=True, comment="지식 컨테이너 ID")
    
    # 공유 정보
    sharing_type = Column(String(20), nullable=False, comment="공유 유형 (link/download/email)")
    shared_with = Column(ARRAY(String(20)), nullable=True, comment="공유 대상자 목록")
    sharing_scope = Column(String(20), nullable=False, comment="공유 범위 (internal/external/public)")
    
    # 권한 정보
    access_permission = Column(String(20), nullable=False, comment="접근 권한")
    expires_date = Column(DateTime(timezone=True), nullable=True, comment="만료일")
    
    # 메타데이터
    sharing_note = Column(Text, nullable=True, comment="공유 메모")
    
    # 시스템 필드
    sharing_date = Column(DateTime(timezone=True), server_default=func.now(), comment="공유 일시")


class TbSearchAnalytics(Base):
    """검색 분석 통계 테이블"""
    __tablename__ = "tb_search_analytics"
    
    # 기본 정보
    analytics_id = Column(Integer, primary_key=True, autoincrement=True, comment="분석 ID")
    analytics_date = Column(String(8), nullable=False, comment="분석 일자 (YYYYMMDD)")
    analytics_type = Column(String(20), nullable=False, comment="분석 유형 (daily/weekly/monthly)")
    
    # 검색 통계
    total_searches = Column(Integer, nullable=False, default=0, comment="총 검색 수")
    unique_users = Column(Integer, nullable=False, default=0, comment="고유 사용자 수")
    avg_response_time = Column(Float, nullable=True, comment="평균 응답 시간")
    success_rate = Column(Float, nullable=True, comment="성공률")
    
    # 인기 검색어
    top_keywords = Column(JSONB, nullable=True, comment="인기 검색어 (JSON)")
    top_documents = Column(JSONB, nullable=True, comment="인기 문서 (JSON)")
    top_containers = Column(JSONB, nullable=True, comment="인기 컨테이너 (JSON)")
    
    # 사용자 패턴
    user_patterns = Column(JSONB, nullable=True, comment="사용자 패턴 분석 (JSON)")
    time_patterns = Column(JSONB, nullable=True, comment="시간대별 패턴 (JSON)")
    
    # 시스템 필드
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일")
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="마지막 업데이트")
