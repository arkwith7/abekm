"""
AI 사용량 추적 모델
LLM API 호출 및 토큰 사용량을 기록하여 비용 관리 지원
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Numeric, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class TbAiUsageLog(Base):
    """AI 사용량 로그 테이블 - LLM API 호출 추적"""
    __tablename__ = "tb_ai_usage_log"
    
    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True, comment="로그 ID")
    
    # 사용자 정보
    user_id = Column(Integer, ForeignKey('tb_user.id', ondelete='SET NULL'), nullable=True, comment="사용자 ID")
    user_emp_no = Column(String(20), nullable=True, comment="사용자 사번")
    session_id = Column(String(100), nullable=True, comment="세션 ID")
    
    # AI 제공자 정보
    provider = Column(String(50), nullable=False, comment="AI 제공자 (bedrock, azure_openai, openai)")
    model = Column(String(100), nullable=False, comment="모델명 (claude-3-sonnet, gpt-4, etc.)")
    
    # 작업 정보
    operation = Column(String(50), nullable=False, comment="작업 유형 (chat, embedding, summarize, search)")
    endpoint = Column(String(200), nullable=True, comment="API 엔드포인트")
    
    # 토큰 사용량
    input_tokens = Column(Integer, nullable=True, comment="입력 토큰 수")
    output_tokens = Column(Integer, nullable=True, comment="출력 토큰 수")
    total_tokens = Column(Integer, nullable=True, comment="총 토큰 수")
    
    # 비용 정보
    estimated_cost_usd = Column(Numeric(10, 6), nullable=True, comment="예상 비용 (USD)")
    
    # 성능 정보
    latency_ms = Column(Integer, nullable=True, comment="응답 시간 (밀리초)")
    
    # 결과 정보
    success = Column(Boolean, nullable=False, default=True, comment="성공 여부")
    error_code = Column(String(50), nullable=True, comment="에러 코드")
    error_message = Column(Text, nullable=True, comment="에러 메시지")
    
    # 추가 메타데이터
    request_metadata = Column(JSONB, nullable=True, comment="요청 메타데이터 (JSON)")
    
    # 시스템 필드
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="로그 생성일")
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_ai_usage_user_id', 'user_id'),
        Index('idx_ai_usage_user_emp_no', 'user_emp_no'),
        Index('idx_ai_usage_created_at', 'created_at'),
        Index('idx_ai_usage_provider', 'provider'),
        Index('idx_ai_usage_operation', 'operation'),
        Index('idx_ai_usage_model', 'model'),
    )


class TbAiModelConfig(Base):
    """AI 모델 설정 테이블 - 비용 단가 및 제한 설정"""
    __tablename__ = "tb_ai_model_config"
    
    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True, comment="설정 ID")
    
    # 모델 정보
    provider = Column(String(50), nullable=False, comment="AI 제공자")
    model = Column(String(100), nullable=False, comment="모델명")
    display_name = Column(String(200), nullable=True, comment="표시 이름")
    
    # 비용 단가 (USD per 1K tokens)
    input_cost_per_1k = Column(Numeric(10, 6), nullable=True, comment="입력 토큰 1K당 비용 (USD)")
    output_cost_per_1k = Column(Numeric(10, 6), nullable=True, comment="출력 토큰 1K당 비용 (USD)")
    
    # 제한 설정
    max_tokens_per_request = Column(Integer, nullable=True, comment="요청당 최대 토큰 수")
    max_requests_per_minute = Column(Integer, nullable=True, comment="분당 최대 요청 수")
    max_tokens_per_day = Column(Integer, nullable=True, comment="일간 최대 토큰 수")
    
    # 상태
    is_active = Column(Boolean, nullable=False, default=True, comment="활성화 여부")
    
    # 시스템 필드
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_ai_model_config_provider_model', 'provider', 'model', unique=True),
    )

