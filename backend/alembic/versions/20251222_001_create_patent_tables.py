"""create patent bibliographic tables

Revision ID: 20251222_001
Revises: 20251219_001
Create Date: 2025-12-22 00:00:00.000000

특허 서지정보 관리 시스템 구축:
1. tb_patent_bibliographic_info - 특허 서지정보 메인 테이블
2. tb_patent_inventors - 발명자 정보
3. tb_patent_applicants - 출원인 정보
4. tb_patent_ipc_classifications - IPC/CPC 분류
5. tb_patent_citations - 인용 관계
6. tb_patent_legal_status - 법적 상태 이력
7. tb_patent_family_members - 패밀리 특허
8. tb_patent_search_sessions - 선행기술조사 세션
9. tb_patent_search_results - 검색 결과
10. tb_patent_prior_art_reports - 선행기술조사 보고서
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '20251222_001'
down_revision = '20251219_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =============================================================================
    # 1. tb_patent_bibliographic_info - 특허 서지정보 메인 테이블
    # =============================================================================
    op.create_table(
        'tb_patent_bibliographic_info',
        sa.Column('patent_id', sa.BigInteger(), autoincrement=True, nullable=False, comment='특허 내부 ID'),
        sa.Column('application_number', sa.String(50), nullable=False, comment='출원번호'),
        sa.Column('publication_number', sa.String(50), nullable=True, comment='공개번호'),
        sa.Column('registration_number', sa.String(50), nullable=True, comment='등록번호'),
        sa.Column('jurisdiction', sa.String(10), nullable=False, server_default='KR', comment='관할권 코드'),
        sa.Column('title', sa.String(1000), nullable=False, comment='발명의 명칭'),
        sa.Column('title_en', sa.String(1000), nullable=True, comment='영문 발명의 명칭'),
        sa.Column('abstract', sa.Text(), nullable=True, comment='초록'),
        sa.Column('abstract_en', sa.Text(), nullable=True, comment='영문 초록'),
        sa.Column('application_date', sa.Date(), nullable=True, comment='출원일'),
        sa.Column('publication_date', sa.Date(), nullable=True, comment='공개일'),
        sa.Column('registration_date', sa.Date(), nullable=True, comment='등록일'),
        sa.Column('priority_date', sa.Date(), nullable=True, comment='우선일'),
        sa.Column('expiration_date', sa.Date(), nullable=True, comment='만료일'),
        sa.Column('legal_status', sa.String(50), nullable=False, server_default='APPLICATION', comment='법적 상태'),
        sa.Column('current_status_date', sa.Date(), nullable=True, comment='현재 상태 변경일'),
        sa.Column('claims_text', sa.Text(), nullable=True, comment='청구항 전문'),
        sa.Column('claims_count', sa.Integer(), nullable=True, server_default='0', comment='청구항 수'),
        sa.Column('independent_claims_count', sa.Integer(), nullable=True, server_default='0', comment='독립항 수'),
        sa.Column('description', sa.Text(), nullable=True, comment='발명의 상세한 설명'),
        sa.Column('background', sa.Text(), nullable=True, comment='발명의 배경'),
        sa.Column('technical_field', sa.String(500), nullable=True, comment='기술 분야'),
        sa.Column('family_id', sa.String(100), nullable=True, comment='패밀리 ID'),
        sa.Column('cited_by_count', sa.Integer(), nullable=False, server_default='0', comment='피인용 횟수'),
        sa.Column('cites_count', sa.Integer(), nullable=False, server_default='0', comment='인용 횟수'),
        sa.Column('data_source', sa.String(20), nullable=False, server_default='KIPRIS', comment='데이터 소스'),
        sa.Column('source_url', sa.String(500), nullable=True, comment='원본 URL'),
        sa.Column('additional_metadata', postgresql.JSONB(), nullable=True, comment='추가 메타데이터'),
        sa.Column('embedding_vector', Vector(1536), nullable=True, comment='특허 전체 내용 임베딩'),
        sa.Column('knowledge_container_id', sa.String(50), nullable=True, comment='지식 컨테이너 ID'),
        sa.Column('imported_by', sa.String(50), nullable=True, comment='수집한 사용자 ID'),
        sa.Column('imported_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), comment='수집일시'),
        sa.Column('last_synced_date', sa.DateTime(timezone=True), nullable=True, comment='마지막 동기화 일시'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_modified_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('del_yn', sa.String(1), nullable=False, server_default='N', comment='삭제 여부'),
        sa.PrimaryKeyConstraint('patent_id'),
        comment='특허 서지정보 메인 테이블'
    )
    
    # 인덱스
    op.create_index('idx_patent_application_number', 'tb_patent_bibliographic_info', ['application_number'], unique=True)
    op.create_index('idx_patent_jurisdiction', 'tb_patent_bibliographic_info', ['jurisdiction'])
    op.create_index('idx_patent_legal_status', 'tb_patent_bibliographic_info', ['legal_status'])
    op.create_index('idx_patent_application_date', 'tb_patent_bibliographic_info', ['application_date'])
    op.create_index('idx_patent_container', 'tb_patent_bibliographic_info', ['knowledge_container_id'])
    op.create_index('idx_patent_family', 'tb_patent_bibliographic_info', ['family_id'])
    op.create_index('idx_patent_del_yn', 'tb_patent_bibliographic_info', ['del_yn'])
    op.create_index(
        'idx_patent_embedding',
        'tb_patent_bibliographic_info',
        ['embedding_vector'],
        postgresql_using='ivfflat',
        postgresql_ops={'embedding_vector': 'vector_cosine_ops'}
    )
    
    # =============================================================================
    # 2. tb_patent_inventors - 발명자 정보
    # =============================================================================
    op.create_table(
        'tb_patent_inventors',
        sa.Column('inventor_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('patent_id', sa.BigInteger(), nullable=False),
        sa.Column('inventor_name', sa.String(300), nullable=False, comment='발명자 이름'),
        sa.Column('inventor_name_en', sa.String(300), nullable=True, comment='영문 이름'),
        sa.Column('inventor_order', sa.Integer(), nullable=False, comment='발명자 순서'),
        sa.Column('country', sa.String(100), nullable=True, comment='국가'),
        sa.Column('address', sa.String(500), nullable=True, comment='주소'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('inventor_id'),
        sa.ForeignKeyConstraint(['patent_id'], ['tb_patent_bibliographic_info.patent_id'], ondelete='CASCADE'),
        comment='특허 발명자 정보'
    )
    
    op.create_index('idx_patent_inventor_name', 'tb_patent_inventors', ['inventor_name'])
    op.create_index('idx_patent_inventor_patent', 'tb_patent_inventors', ['patent_id'])
    
    # =============================================================================
    # 3. tb_patent_applicants - 출원인 정보
    # =============================================================================
    op.create_table(
        'tb_patent_applicants',
        sa.Column('applicant_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('patent_id', sa.BigInteger(), nullable=False),
        sa.Column('applicant_name', sa.String(300), nullable=False, comment='출원인 명칭'),
        sa.Column('applicant_name_en', sa.String(300), nullable=True, comment='영문 명칭'),
        sa.Column('applicant_type', sa.String(50), nullable=True, comment='출원인 유형'),
        sa.Column('applicant_order', sa.Integer(), nullable=False, comment='출원인 순서'),
        sa.Column('customer_no', sa.String(50), nullable=True, comment='KIPRIS 출원인 코드'),
        sa.Column('country', sa.String(100), nullable=True, comment='국가'),
        sa.Column('address', sa.String(500), nullable=True, comment='주소'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('applicant_id'),
        sa.ForeignKeyConstraint(['patent_id'], ['tb_patent_bibliographic_info.patent_id'], ondelete='CASCADE'),
        comment='특허 출원인 정보'
    )
    
    op.create_index('idx_patent_applicant_name', 'tb_patent_applicants', ['applicant_name'])
    op.create_index('idx_patent_applicant_patent', 'tb_patent_applicants', ['patent_id'])
    op.create_index('idx_patent_applicant_customer_no', 'tb_patent_applicants', ['customer_no'])
    
    # =============================================================================
    # 4. tb_patent_ipc_classifications - IPC/CPC 분류
    # =============================================================================
    op.create_table(
        'tb_patent_ipc_classifications',
        sa.Column('classification_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('patent_id', sa.BigInteger(), nullable=False),
        sa.Column('classification_type', sa.String(10), nullable=False, server_default='IPC', comment='분류 타입'),
        sa.Column('classification_code', sa.String(50), nullable=False, comment='분류 코드'),
        sa.Column('section', sa.String(1), nullable=True, comment='섹션'),
        sa.Column('class_code', sa.String(3), nullable=True, comment='클래스'),
        sa.Column('subclass', sa.String(4), nullable=True, comment='서브클래스'),
        sa.Column('main_group', sa.String(10), nullable=True, comment='메인 그룹'),
        sa.Column('subgroup', sa.String(20), nullable=True, comment='서브 그룹'),
        sa.Column('classification_order', sa.Integer(), nullable=False, comment='분류 순서'),
        sa.Column('is_main_classification', sa.Boolean(), nullable=False, server_default='false', comment='주 분류 여부'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('classification_id'),
        sa.ForeignKeyConstraint(['patent_id'], ['tb_patent_bibliographic_info.patent_id'], ondelete='CASCADE'),
        comment='IPC/CPC 분류 코드'
    )
    
    op.create_index('idx_patent_ipc_code', 'tb_patent_ipc_classifications', ['classification_code'])
    op.create_index('idx_patent_ipc_patent', 'tb_patent_ipc_classifications', ['patent_id'])
    op.create_index('idx_patent_ipc_section', 'tb_patent_ipc_classifications', ['section'])
    
    # =============================================================================
    # 5. tb_patent_citations - 인용 관계
    # =============================================================================
    op.create_table(
        'tb_patent_citations',
        sa.Column('citation_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('citing_patent_id', sa.BigInteger(), nullable=False, comment='인용하는 특허'),
        sa.Column('cited_patent_id', sa.BigInteger(), nullable=False, comment='피인용 특허'),
        sa.Column('citation_type', sa.String(50), nullable=True, comment='인용 유형'),
        sa.Column('citation_category', sa.String(50), nullable=True, comment='인용 범주'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('citation_id'),
        sa.ForeignKeyConstraint(['citing_patent_id'], ['tb_patent_bibliographic_info.patent_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cited_patent_id'], ['tb_patent_bibliographic_info.patent_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('citing_patent_id', 'cited_patent_id', name='uq_citation_pair'),
        comment='특허 인용 관계'
    )
    
    op.create_index('idx_citation_citing', 'tb_patent_citations', ['citing_patent_id'])
    op.create_index('idx_citation_cited', 'tb_patent_citations', ['cited_patent_id'])
    
    # =============================================================================
    # 6. tb_patent_legal_status - 법적 상태 이력
    # =============================================================================
    op.create_table(
        'tb_patent_legal_status',
        sa.Column('status_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('patent_id', sa.BigInteger(), nullable=False),
        sa.Column('status_code', sa.String(50), nullable=False, comment='상태 코드'),
        sa.Column('status_date', sa.Date(), nullable=False, comment='상태 변경일'),
        sa.Column('status_description', sa.Text(), nullable=True, comment='상태 설명'),
        sa.Column('event_type', sa.String(100), nullable=True, comment='이벤트 유형'),
        sa.Column('event_code', sa.String(50), nullable=True, comment='이벤트 코드'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('status_id'),
        sa.ForeignKeyConstraint(['patent_id'], ['tb_patent_bibliographic_info.patent_id'], ondelete='CASCADE'),
        comment='특허 법적 상태 변경 이력'
    )
    
    op.create_index('idx_legal_status_patent', 'tb_patent_legal_status', ['patent_id'])
    op.create_index('idx_legal_status_date', 'tb_patent_legal_status', ['status_date'])
    
    # =============================================================================
    # 7. tb_patent_family_members - 패밀리 특허
    # =============================================================================
    op.create_table(
        'tb_patent_family_members',
        sa.Column('family_member_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('patent_id', sa.BigInteger(), nullable=False),
        sa.Column('family_id', sa.String(100), nullable=False, comment='패밀리 ID'),
        sa.Column('member_application_number', sa.String(50), nullable=False, comment='패밀리 구성원 출원번호'),
        sa.Column('member_jurisdiction', sa.String(10), nullable=False, comment='패밀리 구성원 관할권'),
        sa.Column('priority_claim', sa.Boolean(), nullable=False, server_default='false', comment='우선권 주장 여부'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('family_member_id'),
        sa.ForeignKeyConstraint(['patent_id'], ['tb_patent_bibliographic_info.patent_id'], ondelete='CASCADE'),
        comment='특허 패밀리 구성원'
    )
    
    op.create_index('idx_family_members_family', 'tb_patent_family_members', ['family_id'])
    op.create_index('idx_family_members_patent', 'tb_patent_family_members', ['patent_id'])
    
    # =============================================================================
    # 8. tb_patent_search_sessions - 선행기술조사 세션
    # =============================================================================
    op.create_table(
        'tb_patent_search_sessions',
        sa.Column('session_id', sa.String(50), nullable=False, comment='세션 UUID'),
        sa.Column('user_emp_no', sa.String(20), nullable=False, comment='사용자 사번'),
        sa.Column('knowledge_container_id', sa.String(50), nullable=True, comment='지식 컨테이너 ID'),
        sa.Column('target_type', sa.String(50), nullable=False, comment='대상 유형'),
        sa.Column('target_document_id', sa.String(100), nullable=True, comment='대상 문서 ID'),
        sa.Column('target_patent_id', sa.BigInteger(), nullable=True, comment='대상 특허 ID'),
        sa.Column('target_text', sa.Text(), nullable=True, comment='직접 입력한 아이디어 텍스트'),
        sa.Column('extracted_patent_info', postgresql.JSONB(), nullable=True, comment='추출된 특허 정보'),
        sa.Column('search_plan', postgresql.JSONB(), nullable=True, comment='검색 계획'),
        sa.Column('search_iterations', postgresql.JSONB(), nullable=True, comment='ReAct 반복 검색 이력'),
        sa.Column('session_status', sa.String(20), nullable=False, server_default='IN_PROGRESS', comment='세션 상태'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('completed_date', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('session_id'),
        sa.ForeignKeyConstraint(['target_patent_id'], ['tb_patent_bibliographic_info.patent_id']),
        comment='선행기술조사 세션'
    )
    
    op.create_index('idx_search_session_user', 'tb_patent_search_sessions', ['user_emp_no'])
    op.create_index('idx_search_session_container', 'tb_patent_search_sessions', ['knowledge_container_id'])
    op.create_index('idx_search_session_status', 'tb_patent_search_sessions', ['session_status'])
    op.create_index('idx_search_session_date', 'tb_patent_search_sessions', ['created_date'])
    
    # =============================================================================
    # 9. tb_patent_search_results - 검색 결과
    # =============================================================================
    op.create_table(
        'tb_patent_search_results',
        sa.Column('result_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(50), nullable=False),
        sa.Column('candidate_patent_id', sa.BigInteger(), nullable=False),
        sa.Column('rank_order', sa.Integer(), nullable=False, comment='순위'),
        sa.Column('similarity_score', sa.Float(), nullable=True, comment='유사도 점수'),
        sa.Column('matched_components', postgresql.ARRAY(sa.Text()), nullable=True, comment='매칭된 핵심 구성요소'),
        sa.Column('matched_ipc_codes', postgresql.ARRAY(sa.String()), nullable=True, comment='매칭된 IPC 코드'),
        sa.Column('key_snippets', postgresql.JSONB(), nullable=True, comment='핵심 유사 구절'),
        sa.Column('comparison_summary', sa.Text(), nullable=True, comment='유사점/차이점 요약'),
        sa.Column('risk_level', sa.String(20), nullable=True, comment='리스크 수준'),
        sa.Column('user_rating', sa.Integer(), nullable=True, comment='사용자 평가'),
        sa.Column('user_notes', sa.Text(), nullable=True, comment='사용자 메모'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('result_id'),
        sa.ForeignKeyConstraint(['session_id'], ['tb_patent_search_sessions.session_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['candidate_patent_id'], ['tb_patent_bibliographic_info.patent_id'], ondelete='CASCADE'),
        comment='선행기술조사 후보 특허'
    )
    
    op.create_index('idx_search_result_session', 'tb_patent_search_results', ['session_id'])
    op.create_index('idx_search_result_candidate', 'tb_patent_search_results', ['candidate_patent_id'])
    op.create_index('idx_search_result_rank', 'tb_patent_search_results', ['session_id', 'rank_order'])
    
    # =============================================================================
    # 10. tb_patent_prior_art_reports - 선행기술조사 보고서
    # =============================================================================
    op.create_table(
        'tb_patent_prior_art_reports',
        sa.Column('report_id', sa.String(50), nullable=False, comment='보고서 UUID'),
        sa.Column('session_id', sa.String(50), nullable=False),
        sa.Column('report_title', sa.String(500), nullable=False, comment='보고서 제목'),
        sa.Column('report_type', sa.String(50), nullable=False, server_default='PRIOR_ART_SEARCH', comment='보고서 유형'),
        sa.Column('executive_summary', sa.Text(), nullable=True, comment='요약'),
        sa.Column('target_patent_summary', postgresql.JSONB(), nullable=True, comment='대상 특허 요약'),
        sa.Column('search_strategy_summary', sa.Text(), nullable=True, comment='검색 전략 요약'),
        sa.Column('top_candidates_summary', postgresql.JSONB(), nullable=True, comment='상위 후보 특허 요약'),
        sa.Column('detailed_comparisons', postgresql.JSONB(), nullable=True, comment='상세 비교 분석'),
        sa.Column('conclusions', sa.Text(), nullable=True, comment='결론'),
        sa.Column('recommendations', postgresql.ARRAY(sa.Text()), nullable=True, comment='권장사항'),
        sa.Column('report_file_path', sa.String(500), nullable=True, comment='생성된 보고서 파일 경로'),
        sa.Column('generated_by', sa.String(50), nullable=False, comment='생성자 사번'),
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('last_modified_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('report_id'),
        sa.ForeignKeyConstraint(['session_id'], ['tb_patent_search_sessions.session_id'], ondelete='CASCADE'),
        comment='선행기술조사 최종 보고서'
    )
    
    op.create_index('idx_report_session', 'tb_patent_prior_art_reports', ['session_id'])
    op.create_index('idx_report_date', 'tb_patent_prior_art_reports', ['created_date'])


def downgrade() -> None:
    # 역순으로 테이블 삭제
    op.drop_table('tb_patent_prior_art_reports')
    op.drop_table('tb_patent_search_results')
    op.drop_table('tb_patent_search_sessions')
    op.drop_table('tb_patent_family_members')
    op.drop_table('tb_patent_legal_status')
    op.drop_table('tb_patent_citations')
    op.drop_table('tb_patent_ipc_classifications')
    op.drop_table('tb_patent_applicants')
    op.drop_table('tb_patent_inventors')
    op.drop_table('tb_patent_bibliographic_info')
