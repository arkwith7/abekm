"""
SQLAlchemy ORM models for academic bibliographic tables
Match Alembic migration b9e25ab62141
"""
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class TbAcademicDocumentMetadata(Base):
    __tablename__ = "tb_academic_document_metadata"

    file_bss_info_sno = Column(Integer, ForeignKey('tb_file_bss_info.file_bss_info_sno', ondelete='CASCADE'), primary_key=True)
    title = Column(String(1000), nullable=True)
    abstract = Column(Text, nullable=True)
    doi = Column(String(200), nullable=True)
    journal = Column(String(300), nullable=True)
    volume = Column(String(50), nullable=True)
    issue = Column(String(50), nullable=True)
    year = Column(String(4), nullable=True)
    pages = Column(String(50), nullable=True)
    publisher = Column(String(200), nullable=True)
    issn = Column(String(50), nullable=True)
    isbn = Column(String(50), nullable=True)
    language_code = Column(String(10), nullable=True)
    keywords = Column(ARRAY(Text), nullable=True)
    publication_date = Column(Date, nullable=True)
    accepted_date = Column(Date, nullable=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # relationships
    authors = relationship("TbAcademicDocumentAuthors", back_populates="document", cascade="all, delete-orphan")
    references = relationship("TbAcademicReferences", back_populates="document", cascade="all, delete-orphan")


Index('idx_acad_doc_doi', TbAcademicDocumentMetadata.doi, unique=True)
Index('idx_acad_doc_year_journal', TbAcademicDocumentMetadata.year, TbAcademicDocumentMetadata.journal)
Index('idx_acad_doc_keywords', TbAcademicDocumentMetadata.keywords, postgresql_using='gin')


class TbAcademicAuthors(Base):
    __tablename__ = "tb_academic_authors"

    author_id = Column(BigInteger, primary_key=True, autoincrement=True)
    full_name = Column(String(300), nullable=False)
    given_name = Column(String(150), nullable=True)
    family_name = Column(String(150), nullable=True)
    orcid = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # relationships
    documents = relationship("TbAcademicDocumentAuthors", back_populates="author", cascade="all, delete-orphan")


Index('idx_author_full_name', TbAcademicAuthors.full_name)
Index('idx_author_orcid', TbAcademicAuthors.orcid, unique=True)


class TbAcademicAffiliations(Base):
    __tablename__ = "tb_academic_affiliations"

    affiliation_id = Column(BigInteger, primary_key=True, autoincrement=True)
    institution = Column(String(300), nullable=True)
    department = Column(String(300), nullable=True)
    country = Column(String(100), nullable=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # relationships
    authors = relationship("TbAcademicDocumentAuthors", back_populates="affiliation")


Index('idx_affiliation_institution', TbAcademicAffiliations.institution)


class TbAcademicDocumentAuthors(Base):
    __tablename__ = "tb_academic_document_authors"

    file_bss_info_sno = Column(Integer, ForeignKey('tb_academic_document_metadata.file_bss_info_sno', ondelete='CASCADE'), primary_key=True)
    author_id = Column(BigInteger, ForeignKey('tb_academic_authors.author_id', ondelete='CASCADE'), primary_key=True)
    author_order = Column(Integer, nullable=False)
    affiliation_id = Column(BigInteger, ForeignKey('tb_academic_affiliations.affiliation_id'), nullable=True)
    corresponding_author = Column(Boolean, server_default='false', nullable=False)
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # relationships
    document = relationship("TbAcademicDocumentMetadata", back_populates="authors")
    author = relationship("TbAcademicAuthors", back_populates="documents")
    affiliation = relationship("TbAcademicAffiliations", back_populates="authors")


Index('idx_doc_authors_order', TbAcademicDocumentAuthors.file_bss_info_sno, TbAcademicDocumentAuthors.author_order)


class TbAcademicReferences(Base):
    __tablename__ = "tb_academic_references"

    reference_id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_bss_info_sno = Column(Integer, ForeignKey('tb_academic_document_metadata.file_bss_info_sno', ondelete='CASCADE'), nullable=False)
    ref_index = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=True)
    parsed = Column(JSONB, nullable=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # relationships
    document = relationship("TbAcademicDocumentMetadata", back_populates="references")


Index('idx_doc_ref_index', TbAcademicReferences.file_bss_info_sno, TbAcademicReferences.ref_index)
Index('idx_acad_refs_parsed', TbAcademicReferences.parsed, postgresql_using='gin')
