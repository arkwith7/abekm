"""add_ai_usage_tables

Revision ID: 20251225_001
Revises: 20251224_add_last_collection_result
Create Date: 2025-12-25 14:00:00.000000

AI 사용량 추적을 위한 테이블 추가:
- tb_ai_usage_log: LLM API 호출 로그
- tb_ai_model_config: 모델별 비용 단가 설정
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251225_001'
down_revision: Union[str, Sequence[str], None] = '20251224_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """AI 사용량 추적 테이블 생성"""
    
    # 테이블 존재 여부 확인
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # 1. AI 사용량 로그 테이블
    if 'tb_ai_usage_log' not in existing_tables:
        op.create_table(
            'tb_ai_usage_log',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, comment='로그 ID'),
            
            # 사용자 정보
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('tb_user.id', ondelete='SET NULL'), nullable=True, comment='사용자 ID'),
            sa.Column('user_emp_no', sa.String(length=20), nullable=True, comment='사용자 사번'),
            sa.Column('session_id', sa.String(length=100), nullable=True, comment='세션 ID'),
            
            # AI 제공자 정보
            sa.Column('provider', sa.String(length=50), nullable=False, comment='AI 제공자 (bedrock, azure_openai, openai)'),
            sa.Column('model', sa.String(length=100), nullable=False, comment='모델명'),
            
            # 작업 정보
            sa.Column('operation', sa.String(length=50), nullable=False, comment='작업 유형 (chat, embedding, summarize, search)'),
            sa.Column('endpoint', sa.String(length=200), nullable=True, comment='API 엔드포인트'),
            
            # 토큰 사용량
            sa.Column('input_tokens', sa.Integer(), nullable=True, comment='입력 토큰 수'),
            sa.Column('output_tokens', sa.Integer(), nullable=True, comment='출력 토큰 수'),
            sa.Column('total_tokens', sa.Integer(), nullable=True, comment='총 토큰 수'),
            
            # 비용 정보
            sa.Column('estimated_cost_usd', sa.Numeric(precision=10, scale=6), nullable=True, comment='예상 비용 (USD)'),
            
            # 성능 정보
            sa.Column('latency_ms', sa.Integer(), nullable=True, comment='응답 시간 (밀리초)'),
            
            # 결과 정보
            sa.Column('success', sa.Boolean(), nullable=False, server_default='true', comment='성공 여부'),
            sa.Column('error_code', sa.String(length=50), nullable=True, comment='에러 코드'),
            sa.Column('error_message', sa.Text(), nullable=True, comment='에러 메시지'),
            
            # 추가 메타데이터
            sa.Column('request_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='요청 메타데이터'),
            
            # 시스템 필드
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment='로그 생성일'),
        )
        
        # 인덱스 생성
        op.create_index('idx_ai_usage_user_id', 'tb_ai_usage_log', ['user_id'])
        op.create_index('idx_ai_usage_user_emp_no', 'tb_ai_usage_log', ['user_emp_no'])
        op.create_index('idx_ai_usage_created_at', 'tb_ai_usage_log', ['created_at'])
        op.create_index('idx_ai_usage_provider', 'tb_ai_usage_log', ['provider'])
        op.create_index('idx_ai_usage_operation', 'tb_ai_usage_log', ['operation'])
        op.create_index('idx_ai_usage_model', 'tb_ai_usage_log', ['model'])
        
        print("✅ tb_ai_usage_log 테이블 생성 완료")
    else:
        print("⏭️ tb_ai_usage_log 테이블 이미 존재")
    
    # 2. AI 모델 설정 테이블
    if 'tb_ai_model_config' not in existing_tables:
        op.create_table(
            'tb_ai_model_config',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, comment='설정 ID'),
            
            # 모델 정보
            sa.Column('provider', sa.String(length=50), nullable=False, comment='AI 제공자'),
            sa.Column('model', sa.String(length=100), nullable=False, comment='모델명'),
            sa.Column('display_name', sa.String(length=200), nullable=True, comment='표시 이름'),
            
            # 비용 단가 (USD per 1K tokens)
            sa.Column('input_cost_per_1k', sa.Numeric(precision=10, scale=6), nullable=True, comment='입력 토큰 1K당 비용 (USD)'),
            sa.Column('output_cost_per_1k', sa.Numeric(precision=10, scale=6), nullable=True, comment='출력 토큰 1K당 비용 (USD)'),
            
            # 제한 설정
            sa.Column('max_tokens_per_request', sa.Integer(), nullable=True, comment='요청당 최대 토큰 수'),
            sa.Column('max_requests_per_minute', sa.Integer(), nullable=True, comment='분당 최대 요청 수'),
            sa.Column('max_tokens_per_day', sa.Integer(), nullable=True, comment='일간 최대 토큰 수'),
            
            # 상태
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='활성화 여부'),
            
            # 시스템 필드
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        
        # 복합 유니크 인덱스
        op.create_index('idx_ai_model_config_provider_model', 'tb_ai_model_config', ['provider', 'model'], unique=True)
        
        # 기본 모델 비용 설정 데이터 삽입
        op.execute("""
            INSERT INTO tb_ai_model_config (provider, model, display_name, input_cost_per_1k, output_cost_per_1k, is_active)
            VALUES 
            -- AWS Bedrock Claude 3.5 Sonnet
            ('bedrock', 'anthropic.claude-3-5-sonnet-20241022-v2:0', 'Claude 3.5 Sonnet (Bedrock)', 0.003, 0.015, true),
            ('bedrock', 'apac.anthropic.claude-3-5-sonnet-20241022-v2:0', 'Claude 3.5 Sonnet APAC (Bedrock)', 0.003, 0.015, true),
            -- AWS Bedrock Titan Embedding
            ('bedrock', 'amazon.titan-embed-text-v2:0', 'Titan Embed V2 (Bedrock)', 0.00002, 0.0, true),
            -- Azure OpenAI
            ('azure_openai', 'gpt-4o', 'GPT-4o (Azure)', 0.005, 0.015, true),
            ('azure_openai', 'gpt-4o-mini', 'GPT-4o Mini (Azure)', 0.00015, 0.0006, true),
            -- OpenAI
            ('openai', 'gpt-4o', 'GPT-4o (OpenAI)', 0.005, 0.015, true),
            ('openai', 'gpt-4o-mini', 'GPT-4o Mini (OpenAI)', 0.00015, 0.0006, true),
            ('openai', 'text-embedding-3-small', 'Text Embedding 3 Small', 0.00002, 0.0, true),
            ('openai', 'text-embedding-3-large', 'Text Embedding 3 Large', 0.00013, 0.0, true)
            ON CONFLICT (provider, model) DO NOTHING;
        """)
        
        print("✅ tb_ai_model_config 테이블 생성 및 기본 데이터 삽입 완료")
    else:
        print("⏭️ tb_ai_model_config 테이블 이미 존재")


def downgrade() -> None:
    """AI 사용량 추적 테이블 삭제"""
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'tb_ai_usage_log' in existing_tables:
        op.drop_table('tb_ai_usage_log')
        print("✅ tb_ai_usage_log 테이블 삭제 완료")
    
    if 'tb_ai_model_config' in existing_tables:
        op.drop_table('tb_ai_model_config')
        print("✅ tb_ai_model_config 테이블 삭제 완료")

