"""
통합 벡터 청킹 모델 - VS 접두사 명명 규칙 적용
기존 VsDocContentsChunks만 유지 (VsDocContentsIndex는 TbDocumentSearchIndex로 대체)
"""
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, Float, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid
from app.core.database import Base
from app.core.config import settings


class VsDocContentsChunks(Base):
    """문서 청킹 결과 + 벡터 저장 (통합 테이블)"""
    __tablename__ = "vs_doc_contents_chunks"
    
    # 기본 정보
    chunk_sno = Column('chunk_sno', Integer, primary_key=True, autoincrement=True)
    file_bss_info_sno = Column('file_bss_info_sno', Integer, nullable=False, index=True)
    chunk_index = Column('chunk_index', Integer, nullable=False)
    
    # 청크 내용
    chunk_text = Column('chunk_text', Text, nullable=False)
    chunk_size = Column('chunk_size', Integer, nullable=False)
    
    # 벤더 구분
    embedding_provider = Column('embedding_provider', String(20), nullable=True, comment="임베딩 벤더 (azure | aws)")
    
    # 🔷 Azure 전용 임베딩 (1536d)
    azure_embedding_1536 = Column('azure_embedding_1536', Vector(1536), nullable=True, comment="Azure text-embedding-3-small")
    
    # 🟧 AWS 전용 임베딩 (1024d)
    aws_embedding_1024 = Column('aws_embedding_1024', Vector(1024), nullable=True, comment="AWS Titan v2")
    
    # 🔄 레거시 호환 (기존 컬럼 유지)
    chunk_embedding = Column('chunk_embedding', Vector(settings.vector_dimension), nullable=True, comment="레거시: 동적 차원")
    
    # 문서 구조 정보
    page_number = Column('page_number', Integer, nullable=True)
    section_title = Column('section_title', String(200), nullable=True)
    
    # NLP 처리 결과 (키워드 정보)
    keywords = Column('keywords', Text, nullable=True, comment="추출된 키워드 (콤마 구분)")
    named_entities = Column('named_entities', Text, nullable=True, comment="고유명사 (콤마 구분)")
    
    # 지식 컨테이너 정보 
    knowledge_container_id = Column('knowledge_container_id', String(50), nullable=True, comment="지식 컨테이너 ID")
    
    # 메타데이터 (vs_doc_contents_index 호환)
    metadata_json = Column('metadata_json', Text, nullable=True, comment="메타데이터 JSON")
    
    # 공통 필드
    del_yn = Column('del_yn', String(1), nullable=False, default='N')
    created_by = Column('created_by', String(50), nullable=True)
    created_date = Column('created_date', DateTime(timezone=True), server_default=func.now())
    last_modified_by = Column('last_modified_by', String(50), nullable=True)
    last_modified_date = Column('last_modified_date', DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 인덱스 정의 (벡터 검색 최적화)
Index('idx_vs_doc_chunks_embedding', VsDocContentsChunks.chunk_embedding, postgresql_using='ivfflat')
Index('idx_vs_doc_chunks_file_sno', VsDocContentsChunks.file_bss_info_sno)
Index('idx_vs_doc_chunks_container_id', VsDocContentsChunks.knowledge_container_id)
Index('idx_vs_doc_chunks_del_yn', VsDocContentsChunks.del_yn)
Index('idx_vs_doc_chunks_page_number', VsDocContentsChunks.page_number)

