"""
멀티모달 통합검색 인덱스 모델 - tb_document_search_index 테이블
텍스트 + 이미지 멀티모달 검색 지원 (textsearch_ko + 벡터 + FTS 하이브리드)

변경 사항 (2025-10-16):
- kiwipiepy 관련 필드 제거 (keywords, proper_nouns, corp_names)
- textsearch_ko 중심 검색으로 전환
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, Index, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.config import settings

class TbDocumentSearchIndex(Base):
    """멀티모달 통합검색 메인 테이블 - 텍스트 + 이미지 검색 지원"""
    __tablename__ = "tb_document_search_index"
    
    # 기본 식별자
    search_doc_id = Column(Integer, primary_key=True, autoincrement=True, comment="검색 문서 ID")
    file_bss_info_sno = Column(Integer, ForeignKey('tb_file_bss_info.file_bss_info_sno'), nullable=False, comment="파일 기본 정보 일련번호")
    knowledge_container_id = Column(String(50), ForeignKey('tb_knowledge_containers.container_id'), nullable=False, comment="지식 컨테이너 ID")
    
    # 문서 전문 내용 (기존 chunk_text 대체)
    document_title = Column(String(500), nullable=True, comment="문서 제목")
    full_content = Column(Text, nullable=False, comment="문서 전체 내용 또는 주요 섹션")
    content_summary = Column(Text, nullable=True, comment="내용 요약 (최대 1000자)")
    
    # ❌ 제거됨 (2025-10-16): kiwipiepy 관련 필드
    # keywords = Column(ARRAY(Text), nullable=True, comment="추출된 키워드 배열")
    # proper_nouns = Column(ARRAY(Text), nullable=True, comment="고유명사 배열")
    # corp_names = Column(ARRAY(Text), nullable=True, comment="회사명/기관명 배열")
    
    # ✅ 유지: 주제/카테고리 (검색 최적화)
    main_topics = Column(ARRAY(Text), nullable=True, comment="주요 주제/카테고리 배열")
    
    # 멀티모달 메타데이터 (이미지 + 테이블)
    has_images = Column(Boolean, nullable=False, default=False, comment="이미지 포함 여부 (멀티모달)")
    has_tables = Column(Boolean, nullable=False, default=False, comment="테이블 포함 여부")
    image_count = Column(Integer, nullable=False, default=0, comment="이미지 개수 (멀티모달)")
    table_count = Column(Integer, nullable=False, default=0, comment="테이블 개수")
    images_metadata = Column(JSONB, nullable=True, comment="이미지 메타데이터 (JSON, 멀티모달 검색용)")
    
    # 문서 메타데이터 (기존 chunk_index, chunk_size 대체)
    document_type = Column(String(50), nullable=True, comment="문서 유형 (PDF, DOCX, etc)")
    page_count = Column(Integer, nullable=True, comment="페이지 수")
    content_length = Column(Integer, nullable=True, comment="전체 내용 길이")
    language_code = Column(String(10), nullable=False, default='ko', comment="언어 코드")
    
    # 검색 성능 최적화 필드 (embedding 제거)
    keyword_tsvector = Column(TSVECTOR, nullable=True, comment="키워드 전문검색 벡터 (한국어+simple)")
    content_tsvector = Column(TSVECTOR, nullable=True, comment="내용 전문검색 벡터 (한국어+simple)")
    keyword_tsvector_en = Column(TSVECTOR, nullable=True, comment="영어 키워드 검색 벡터 (English configuration)")
    content_tsvector_en = Column(TSVECTOR, nullable=True, comment="영어 전문검색 벡터 (English configuration)")
    search_weight = Column(Integer, nullable=False, default=1, comment="검색 가중치")
    
    # 권한 및 접근성
    access_level = Column(String(20), nullable=False, default='normal', comment="접근 권한 레벨")
    is_public = Column(Boolean, nullable=False, default=False, comment="공개 문서 여부")
    
    # 시스템 관리
    indexing_status = Column(String(20), nullable=False, default='indexed', comment="색인 상태")
    last_searched_at = Column(DateTime(timezone=True), nullable=True, comment="마지막 검색 일시")
    search_count = Column(Integer, nullable=False, default=0, comment="검색 횟수")
    
    # 공통 필드
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일")
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="마지막 업데이트")
    
    # 관계 정의
    file_info = relationship("TbFileBssInfo", back_populates="search_indexes")
    container = relationship("TbKnowledgeContainers", back_populates="search_documents")

# 검색 최적화 인덱스 정의 (한국어 + 영어 dual configuration)
Index('idx_search_content_tsvector', TbDocumentSearchIndex.content_tsvector, postgresql_using='gin')
Index('idx_search_keyword_tsvector', TbDocumentSearchIndex.keyword_tsvector, postgresql_using='gin')
Index('idx_search_content_tsvector_en', TbDocumentSearchIndex.content_tsvector_en, postgresql_using='gin')
Index('idx_search_keyword_tsvector_en', TbDocumentSearchIndex.keyword_tsvector_en, postgresql_using='gin')

# ❌ 제거됨 (2025-10-16): kiwipiepy 관련 인덱스
# Index('idx_search_keywords', TbDocumentSearchIndex.keywords, postgresql_using='gin')
# Index('idx_search_proper_nouns', TbDocumentSearchIndex.proper_nouns, postgresql_using='gin')

# ✅ 유지: 주제/카테고리 인덱스
Index('idx_search_topics', TbDocumentSearchIndex.main_topics, postgresql_using='gin')
Index('idx_search_container_type', TbDocumentSearchIndex.knowledge_container_id, TbDocumentSearchIndex.document_type)
Index('idx_search_file_access', TbDocumentSearchIndex.file_bss_info_sno, TbDocumentSearchIndex.access_level)
Index('idx_search_updated', TbDocumentSearchIndex.last_updated)
Index('idx_search_status', TbDocumentSearchIndex.indexing_status)

# 멀티모달 검색 인덱스 (이미지 + 테이블)
Index('idx_search_has_images', TbDocumentSearchIndex.has_images)
Index('idx_search_multimodal', TbDocumentSearchIndex.has_images, TbDocumentSearchIndex.image_count)
Index('idx_search_images_metadata', TbDocumentSearchIndex.images_metadata, postgresql_using='gin')
