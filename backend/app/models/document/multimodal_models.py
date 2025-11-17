"""멀티모달 RAG 확장 모델 (초안)

주의: 실제 마이그레이션은 migrations/0001_multimodal_schema.sql 참고.
이 파일은 ORM 매핑 및 서비스 계층에서의 타입 안정성을 위해 추가.
"""
from __future__ import annotations
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, DateTime, JSON, JSON as JSON_, ForeignKey, Numeric, ARRAY
)
from sqlalchemy.dialects.postgresql import JSONB, INT4RANGE, TSVECTOR
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.core.config import settings

# ---------------------------------------------------------------------------
# Extraction Session
# ---------------------------------------------------------------------------
class DocExtractionSession(Base):
    __tablename__ = "doc_extraction_session"

    extraction_session_id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_bss_info_sno = Column(BigInteger, ForeignKey("tb_file_bss_info.file_bss_info_sno", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    model_profile = Column(String(50), nullable=True)
    pipeline_type = Column(String(20), default=settings.default_llm_provider)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="running")  # running|success|failed|partial
    page_count_detected = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    objects = relationship("DocExtractedObject", back_populates="extraction_session", cascade="all, delete-orphan")

# ---------------------------------------------------------------------------
# Extracted Object
# ---------------------------------------------------------------------------
class DocExtractedObject(Base):
    __tablename__ = "doc_extracted_object"

    object_id = Column(BigInteger, primary_key=True, autoincrement=True)
    extraction_session_id = Column(BigInteger, ForeignKey("doc_extraction_session.extraction_session_id", ondelete="CASCADE"), nullable=False)
    file_bss_info_sno = Column(BigInteger, nullable=False)
    page_no = Column(Integer, nullable=True)
    object_type = Column(String(20), nullable=False)  # TEXT_BLOCK|TABLE|IMAGE|FIGURE|HEADER|FOOTER
    sequence_in_page = Column(Integer, nullable=True)
    # DB 실제 컬럼 타입은 integer[] 인 것으로 확인되었으므로 ARRAY(Integer)로 매핑 (기존 JSONB -> 타입 불일치 오류 발생)
    bbox = Column(ARRAY(Integer), nullable=True)  # 저장 형식: [x1,y1,x2,y2]
    content_text = Column(Text, nullable=True)
    structure_json = Column(JSONB, nullable=True)
    lang_code = Column(String(10), nullable=True, default="ko")
    char_count = Column(Integer, nullable=True)
    token_estimate = Column(Integer, nullable=True)
    confidence = Column(Numeric(5,2), nullable=True)
    hash_sha256 = Column(String(64), nullable=True)
    # D. 이미지 특징 필드 추가 (IMAGE 타입에서만 사용)
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    phash = Column(String(32), nullable=True)  # perceptual hash (16 hex chars typically)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    extraction_session = relationship("DocExtractionSession", back_populates="objects")

# ---------------------------------------------------------------------------
# Chunk Session
# ---------------------------------------------------------------------------
class DocChunkSession(Base):
    __tablename__ = "doc_chunk_session"

    chunk_session_id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_bss_info_sno = Column(BigInteger, ForeignKey("tb_file_bss_info.file_bss_info_sno", ondelete="CASCADE"), nullable=False)
    extraction_session_id = Column(BigInteger, ForeignKey("doc_extraction_session.extraction_session_id", ondelete="CASCADE"), nullable=False)
    strategy_name = Column(String(50), nullable=False)
    params_json = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="running")
    chunk_count = Column(Integer, nullable=True)

    chunks = relationship("DocChunk", back_populates="chunk_session", cascade="all, delete-orphan")

# ---------------------------------------------------------------------------
# Chunk
# ---------------------------------------------------------------------------
class DocChunk(Base):
    __tablename__ = "doc_chunk"

    chunk_id = Column(BigInteger, primary_key=True, autoincrement=True)
    chunk_session_id = Column(BigInteger, ForeignKey("doc_chunk_session.chunk_session_id", ondelete="CASCADE"), nullable=False)
    file_bss_info_sno = Column(BigInteger, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    # 실제 DB 컬럼은 bigint[] 이므로 ARRAY(BigInteger) 로 매핑
    source_object_ids = Column(ARRAY(BigInteger), nullable=False)
    content_text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    modality = Column(String(20), nullable=True, default="text")
    section_heading = Column(Text, nullable=True)
    page_range = Column(INT4RANGE, nullable=True)
    blob_key = Column(String(500), nullable=True)  # Blob Storage 파일 경로 (이미지/테이블)
    quality_score = Column(Numeric(5,2), nullable=True)
    content_tsvector = Column(TSVECTOR, nullable=True, comment="전문검색 벡터 (Korean + English dual configuration)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chunk_session = relationship("DocChunkSession", back_populates="chunks")
    embeddings = relationship("DocEmbedding", back_populates="chunk", cascade="all, delete-orphan")

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
class DocEmbedding(Base):
    __tablename__ = "doc_embedding"

    embedding_id = Column(BigInteger, primary_key=True, autoincrement=True)
    chunk_id = Column(BigInteger, ForeignKey("doc_chunk.chunk_id", ondelete="CASCADE"), nullable=False)
    file_bss_info_sno = Column(BigInteger, nullable=False)
    
    # 벤더 구분 및 메타데이터
    provider = Column(String(20), nullable=True, index=True, comment="벤더 구분 (azure | aws)")
    model_name = Column(String(100), nullable=False)
    modality = Column(String(20), nullable=True, default="text")
    dimension = Column(Integer, nullable=False)
    
    # 🔷 Azure 전용 벡터 컬럼 (고정 차원)
    azure_vector_1536 = Column(Vector(1536), nullable=True, comment="Azure text-embedding-3-small (1536d)")
    azure_vector_3072 = Column(Vector(3072), nullable=True, comment="Azure text-embedding-3-large (3072d)")
    azure_clip_vector = Column(Vector(512), nullable=True, comment="Azure CLIP multimodal (512d)")
    
    # 🟧 AWS 전용 벡터 컬럼 (고정 차원)
    aws_vector_1024 = Column(Vector(1024), nullable=True, comment="AWS Titan v2 텍스트 임베딩 (1024d)")
    aws_vector_256 = Column(Vector(256), nullable=True, comment="AWS Titan v2 small (256d)")
    aws_multimodal_vector_1024 = Column(Vector(1024), nullable=True, comment="AWS Cohere Embed v4 멀티모달 (1024d)")
    
    # 🔄 레거시 호환 (기존 컬럼 유지)
    vector = Column(Vector(), nullable=True, comment="레거시: 동적 차원 지원")
    clip_vector = Column(Vector(512), nullable=True, comment="레거시: Azure CLIP (512d)")
    
    norm_l2 = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chunk = relationship("DocChunk", back_populates="embeddings")

# NOTE: 
# - vector 컬럼: 텍스트 임베딩 (1536d, 3072d 등) 동적 차원 지원
# - clip_vector 컬럼: Azure CLIP 멀티모달 임베딩 (512d) 고정
# - aws_multimodal_vector 컬럼: AWS 멀티모달 임베딩 (1024d)
#   → Claude 3 Vision으로 이미지 설명 생성 → Titan v2로 임베딩
# - dimension 컬럼: vector의 실제 차원 값 저장
# - 듀얼 벡터 전략: 텍스트 검색(vector) + 멀티모달 검색(clip_vector/aws_multimodal_vector)
