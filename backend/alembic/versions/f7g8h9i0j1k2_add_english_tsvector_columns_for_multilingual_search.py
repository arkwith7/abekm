"""add_english_tsvector_columns_for_multilingual_search

Revision ID: f7g8h9i0j1k2
Revises: c5aebed798ed
Create Date: 2025-10-24 05:00:00.000000

Purpose:
    영어 + 한국어 dual configuration 검색 지원
    - content_tsvector_en: 영어 전문검색 벡터 추가
    - keyword_tsvector_en: 영어 키워드 검색 벡터 추가
    
Benefits:
    - "Figure 1", "Research Model" 같은 영어 쿼리 검색 가능
    - 학술논문 IMAGE 캡션 검색 개선
    - 한국어 + 영어 혼합 문서 검색 품질 향상
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR


# revision identifiers, used by Alembic.
revision: str = 'f7g8h9i0j1k2'
down_revision: Union[str, Sequence[str], None] = 'b9e25ab62141'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    영어 tsvector 컬럼 추가 및 dual configuration 트리거 생성
    
    Steps:
    1. content_tsvector_en, keyword_tsvector_en 컬럼 추가
    2. GIN 인덱스 생성 (성능 최적화)
    3. 트리거 함수 업데이트 (한국어 + 영어)
    4. 기존 데이터 마이그레이션
    """
    
    # Step 1: 영어 tsvector 컬럼 추가
    op.add_column('tb_document_search_index',
        sa.Column('content_tsvector_en', TSVECTOR, nullable=True,
                 comment='영어 전문검색 벡터 (English configuration)')
    )
    op.add_column('tb_document_search_index',
        sa.Column('keyword_tsvector_en', TSVECTOR, nullable=True,
                 comment='영어 키워드 검색 벡터 (English configuration)')
    )
    
    # Step 2: GIN 인덱스 생성
    op.create_index(
        'idx_search_content_tsvector_en',
        'tb_document_search_index',
        ['content_tsvector_en'],
        postgresql_using='gin'
    )
    op.create_index(
        'idx_search_keyword_tsvector_en',
        'tb_document_search_index',
        ['keyword_tsvector_en'],
        postgresql_using='gin'
    )
    
    # Step 3: Content tsvector 트리거 함수 업데이트 (한국어 + 영어)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_content_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            -- 한국어 content_tsvector (기존 hybrid 로직 유지)
            -- setweight 사용: simple(B) + korean(A)
            NEW.content_tsvector := 
                setweight(to_tsvector('simple', COALESCE(NEW.full_content, '')), 'B') ||
                setweight(to_tsvector('korean', COALESCE(NEW.full_content, '')), 'A');
            
            -- 영어 content_tsvector (새로 추가)
            -- English configuration: stemming, stopword 제거 등 영어 최적화
            NEW.content_tsvector_en := to_tsvector('english',
                COALESCE(NEW.document_title, '') || ' ' ||
                COALESCE(NEW.content_summary, '') || ' ' ||
                COALESCE(substring(NEW.full_content, 1, 50000), '')
            );
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Step 4: Keyword tsvector 트리거 함수 업데이트 (한국어 + 영어)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_keyword_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            -- 한국어 keyword_tsvector (기존 hybrid 로직 유지)
            NEW.keyword_tsvector := 
                setweight(to_tsvector('simple', 
                    COALESCE(NEW.document_title, '') || ' ' || 
                    COALESCE(NEW.content_summary, '')
                ), 'B') ||
                setweight(to_tsvector('korean', 
                    COALESCE(NEW.document_title, '') || ' ' || 
                    COALESCE(NEW.content_summary, '')
                ), 'A');
            
            -- 영어 keyword_tsvector (새로 추가)
            NEW.keyword_tsvector_en := to_tsvector('english',
                COALESCE(NEW.document_title, '') || ' ' ||
                COALESCE(NEW.content_summary, '')
            );
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Step 5: 기존 데이터 마이그레이션
    # full_content를 자기 자신으로 업데이트하여 트리거 실행
    print("📝 기존 데이터 마이그레이션 시작...")
    op.execute("""
        UPDATE tb_document_search_index
        SET full_content = full_content
        WHERE indexing_status = 'indexed'
        AND (content_tsvector_en IS NULL OR keyword_tsvector_en IS NULL);
    """)
    print("✅ 영어 tsvector 마이그레이션 완료!")


def downgrade() -> None:
    """
    영어 tsvector 제거 및 이전 상태로 복원
    """
    
    # Step 1: 인덱스 제거
    op.drop_index('idx_search_keyword_tsvector_en', table_name='tb_document_search_index')
    op.drop_index('idx_search_content_tsvector_en', table_name='tb_document_search_index')
    
    # Step 2: 컬럼 제거
    op.drop_column('tb_document_search_index', 'keyword_tsvector_en')
    op.drop_column('tb_document_search_index', 'content_tsvector_en')
    
    # Step 3: 트리거 함수 복원 (이전 버전)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_content_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.content_tsvector := 
                setweight(to_tsvector('simple', COALESCE(NEW.full_content, '')), 'B') ||
                setweight(to_tsvector('korean', COALESCE(NEW.full_content, '')), 'A');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_index_keyword_tsvector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.keyword_tsvector := 
                setweight(to_tsvector('simple', 
                    COALESCE(NEW.document_title, '') || ' ' || 
                    COALESCE(NEW.content_summary, '')
                ), 'B') ||
                setweight(to_tsvector('korean', 
                    COALESCE(NEW.document_title, '') || ' ' || 
                    COALESCE(NEW.content_summary, '')
                ), 'A');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    print("⚠️ 영어 tsvector 제거 완료 - 한국어+simple hybrid로 복원")
