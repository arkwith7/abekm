"""
WKMS 채팅 및 대화 관리 모델
"""
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from app.core.database import Base
from app.core.config import settings


class TbChatHistory(Base):
    """채팅 기록 테이블 - 권한 기반 대화 관리"""
    __tablename__ = "tb_chat_history"
    
    # 기본 정보
    chat_id = Column(Integer, primary_key=True, autoincrement=True, comment="채팅 ID")
    session_id = Column(String(100), nullable=False, comment="세션 ID")
    user_emp_no = Column(String(20), nullable=False, comment="사용자 사번")
    
    # 권한 컨텍스트
    knowledge_container_id = Column(String(50), nullable=True, comment="대화 컨텍스트 컨테이너")
    user_permission_level = Column(String(20), nullable=True, comment="사용자 권한 레벨")
    accessible_containers = Column(ARRAY(String(50)), nullable=True, comment="접근 가능한 컨테이너 목록")
    
    # 대화 내용
    user_message = Column(Text, nullable=False, comment="사용자 질문")
    assistant_response = Column(Text, nullable=False, comment="AI 응답")
    
    # 검색 컨텍스트
    search_query = Column(Text, nullable=True, comment="검색 쿼리")
    search_results = Column(JSONB, nullable=True, comment="검색 결과 (JSON)")
    referenced_documents = Column(ARRAY(Integer), nullable=True, comment="참조된 문서 ID 목록")
    search_score = Column(String(10), nullable=True, comment="검색 점수")
    
    # 모델 정보
    model_used = Column(String(50), nullable=True, comment="사용된 AI 모델")
    model_parameters = Column(JSONB, nullable=True, comment="모델 파라미터 (JSON)")
    response_time_ms = Column(Integer, nullable=True, comment="응답 시간 (밀리초)")
    
    # 대화 메타데이터
    conversation_context = Column(JSONB, nullable=True, comment="대화 컨텍스트 (JSON)")
    feedback_score = Column(Integer, nullable=True, comment="사용자 피드백 점수 (1-5)")
    feedback_comment = Column(Text, nullable=True, comment="사용자 피드백 코멘트")
    
    # 시스템 필드
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일")


class TbChatSessions(Base):
    """채팅 세션 관리 테이블"""
    __tablename__ = "tb_chat_sessions"
    
    # 기본 정보
    session_id = Column(String(100), primary_key=True, comment="세션 ID")
    user_emp_no = Column(String(20), nullable=False, comment="사용자 사번")
    
    # 세션 정보
    session_name = Column(String(200), nullable=True, comment="세션명")
    session_description = Column(Text, nullable=True, comment="세션 설명")
    
    # 권한 컨텍스트
    default_container_id = Column(String(50), nullable=True, comment="기본 컨테이너 ID")
    allowed_containers = Column(ARRAY(String(50)), nullable=True, comment="허용된 컨테이너 목록")
    
    # 세션 설정
    max_messages = Column(Integer, nullable=False, default=100, comment="최대 메시지 수")
    session_timeout_minutes = Column(Integer, nullable=False, default=60, comment="세션 타임아웃 (분)")
    
    # 상태 정보
    is_active = Column(Boolean, nullable=False, default=True, comment="활성화 여부")
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), comment="마지막 활동 시간")
    message_count = Column(Integer, nullable=False, default=0, comment="메시지 수")
    
    # 시스템 필드
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일")
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="최종 수정일")


class TbChatFeedback(Base):
    """채팅 피드백 테이블"""
    __tablename__ = "tb_chat_feedback"
    
    # 기본 정보
    feedback_id = Column(Integer, primary_key=True, autoincrement=True, comment="피드백 ID")
    chat_id = Column(Integer, nullable=False, comment="채팅 ID")
    user_emp_no = Column(String(20), nullable=False, comment="사용자 사번")
    
    # 피드백 정보
    feedback_type = Column(String(20), nullable=False, comment="피드백 유형 (rating/thumbs/comment)")
    rating_score = Column(Integer, nullable=True, comment="평점 (1-5)")
    is_helpful = Column(Boolean, nullable=True, comment="도움이 되었는지 여부")
    
    # 상세 피드백
    feedback_comment = Column(Text, nullable=True, comment="피드백 코멘트")
    improvement_suggestion = Column(Text, nullable=True, comment="개선 제안")
    
    # 분류 정보
    feedback_category = Column(String(50), nullable=True, comment="피드백 카테고리")
    issue_type = Column(String(50), nullable=True, comment="이슈 유형")
    
    # 시스템 필드
    created_date = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일")
