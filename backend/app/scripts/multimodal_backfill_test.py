"""Temporary multimodal backfill & test script

Steps implemented:
1. Snapshot current row counts for latest uploaded file (multimodal tables)
2. Insert extracted objects (paragraphs, tables) if missing
3. Create simple chunks from paragraph objects (size ~ CHUNK_SIZE from settings, fallback 1000)
4. Generate embeddings for each chunk (Azure OpenAI or configured provider)
5. Re-snapshot counts
6. Run a simple similarity search test for a probe query

Safe to remove after full pipeline implementation.
"""
from __future__ import annotations
import asyncio
import os
import logging
from collections import defaultdict
from typing import List

os.environ.setdefault("PYTHONPATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text

from app.core.config import settings
from app.models.document.file_models import TbFileBssInfo
from app.models.document.multimodal_models import (
    DocExtractionSession,
    DocExtractedObject,
    DocChunkSession,
    DocChunk,
    DocEmbedding,
)
from app.services.document.extraction.text_extractor_service import text_extractor_service
from app.services.core.embedding_service import EmbeddingService

logger = logging.getLogger("multimodal_backfill")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

DB_URL = settings.database_url

async def get_latest_file(session: AsyncSession) -> TbFileBssInfo | None:
    q = select(TbFileBssInfo).order_by(TbFileBssInfo.file_bss_info_sno.desc()).limit(1)
    res = await session.execute(q)
    return res.scalar_one_or_none()

async def snapshot_counts(session: AsyncSession, file_id: int) -> dict:
    counts = {}
    tables = {
        "extraction_sessions": select(func.count()).select_from(DocExtractionSession).where(DocExtractionSession.file_bss_info_sno == file_id),
        "extracted_objects": select(func.count()).select_from(DocExtractedObject).where(DocExtractedObject.file_bss_info_sno == file_id),
        "chunk_sessions": select(func.count()).select_from(DocChunkSession).where(DocChunkSession.file_bss_info_sno == file_id),
        "chunks": select(func.count()).select_from(DocChunk).where(DocChunk.file_bss_info_sno == file_id),
        "embeddings": select(func.count()).select_from(DocEmbedding).where(DocEmbedding.file_bss_info_sno == file_id),
    }
    for name, query in tables.items():
        res = await session.execute(query)
        counts[name] = res.scalar_one()
    return counts

async def ensure_extraction_session(session: AsyncSession, file_id: int) -> DocExtractionSession:
    q = select(DocExtractionSession).where(DocExtractionSession.file_bss_info_sno == file_id).order_by(DocExtractionSession.extraction_session_id.asc()).limit(1)
    res = await session.execute(q)
    existing = res.scalar_one_or_none()
    if existing:
        return existing
    new = DocExtractionSession(
        file_bss_info_sno=file_id,
        provider="azure",
        model_profile=settings.azure_openai_multimodal_deployment or "gpt-4o-vision",
        pipeline_type="azure",
        status="success",
    )
    session.add(new)
    await session.flush()
    return new

async def backfill_extracted_objects(session: AsyncSession, file_row: TbFileBssInfo) -> int:
    file_id = file_row.file_bss_info_sno
    # Check existing
    existing_count = await session.execute(
        select(func.count()).select_from(DocExtractedObject).where(DocExtractedObject.file_bss_info_sno == file_id)
    )
    if existing_count.scalar_one() > 0:
        return 0  # already present

    # Need the actual file for extraction - try local uploads first or temp download directory
    candidate_paths = [file_row.path]
    # If relative path, attempt to anchor under backend root
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if not os.path.isabs(file_row.path):
        candidate_paths.append(os.path.join(backend_root, file_row.path))
    # Also any temp _source variant
    candidate_paths.extend([p for p in ("/tmp",) if os.path.isdir(p)])

    chosen_path = None
    for c in candidate_paths:
        if isinstance(c, str) and os.path.isfile(c):
            chosen_path = c
            break
        # If directory (like /tmp) try pattern
        if os.path.isdir(c):
            for fname in os.listdir(c):
                if str(file_id) in fname and fname.endswith(('.docx', '.pdf', '.pptx')):
                    chosen_path = os.path.join(c, fname)
                    break
        if chosen_path:
            break

    if not chosen_path:
        logger.warning(f"Could not locate physical file for extraction backfill: {file_row.path}")
        return 0

    ext = os.path.splitext(chosen_path)[1].lower()
    extraction = await text_extractor_service.extract_text(chosen_path, ext)
    if not extraction.get("success"):
        logger.error("Extraction failed during backfill")
        return 0

    paragraphs = extraction.get("metadata", {}).get("paragraphs", [])
    tables = extraction.get("metadata", {}).get("tables", [])

    session_row = await ensure_extraction_session(session, file_id)

    inserted = 0
    for p in paragraphs:
        session.add(DocExtractedObject(
            extraction_session_id=session_row.extraction_session_id,
            file_bss_info_sno=file_id,
            object_type="TEXT_BLOCK",
            sequence_in_page=p.get("paragraph_no"),
            content_text=p.get("text"),
            char_count=p.get("char_count"),
            lang_code="ko"
        ))
        inserted += 1
    for t in tables:
        # Flatten table content to newline text
        session.add(DocExtractedObject(
            extraction_session_id=session_row.extraction_session_id,
            file_bss_info_sno=file_id,
            object_type="TABLE",
            content_text='\n'.join(t.get("content", [])),
            structure_json=t,
            lang_code="ko"
        ))
        inserted += 1

    # Update session stats
    session_row.page_count_detected = extraction.get("metadata", {}).get("page_count")
    session_row.status = "success"

    logger.info(f"Inserted {inserted} extracted objects")
    return inserted

async def backfill_chunks(session: AsyncSession, file_id: int) -> int:
    # If chunks already exist skip
    existing = await session.execute(select(func.count()).select_from(DocChunk).where(DocChunk.file_bss_info_sno == file_id))
    if existing.scalar_one() > 0:
        return 0
    # Need extraction session & objects
    ex_q = select(DocExtractionSession).where(DocExtractionSession.file_bss_info_sno == file_id).limit(1)
    ex_res = await session.execute(ex_q)
    ex_row = ex_res.scalar_one_or_none()
    if not ex_row:
        logger.warning("No extraction session present; skipping chunk backfill")
        return 0
    obj_q = select(DocExtractedObject).where(DocExtractedObject.file_bss_info_sno == file_id).order_by(DocExtractedObject.object_id.asc())
    obj_res = await session.execute(obj_q)
    objects = obj_res.scalars().all()
    if not objects:
        logger.warning("No extracted objects to chunk")
        return 0

    chunk_size = getattr(settings, 'chunk_size', 1000) or 1000

    chunk_session = DocChunkSession(
        file_bss_info_sno=file_id,
        extraction_session_id=ex_row.extraction_session_id,
        strategy_name="paragraph_aware",
        status="running"
    )
    session.add(chunk_session)
    await session.flush()

    buffer: List[DocExtractedObject] = []
    acc_len = 0
    created = 0

    def flush():
        nonlocal buffer, acc_len, created
        if not buffer:
            return
        content = '\n\n'.join([o.content_text or '' for o in buffer]).strip()
        if not content:
            buffer = []
            acc_len = 0
            return
        chunk = DocChunk(
            chunk_session_id=chunk_session.chunk_session_id,
            file_bss_info_sno=file_id,
            chunk_index=created,
            source_object_ids=[o.object_id for o in buffer],
            content_text=content,
            modality='text'
        )
        session.add(chunk)
        created += 1
        buffer = []
        acc_len = 0

    for obj in objects:
        # Only chunk TEXT_BLOCK and TABLE for now
        if obj.object_type not in ("TEXT_BLOCK", "TABLE"):
            continue
        text_part = obj.content_text or ''
        if not text_part.strip():
            continue
        if acc_len + len(text_part) > chunk_size and buffer:
            flush()
        buffer.append(obj)
        acc_len += len(text_part)
    flush()

    chunk_session.chunk_count = created
    chunk_session.status = "success"
    logger.info(f"Created {created} chunks")
    return created

async def backfill_embeddings(session: AsyncSession, file_id: int) -> int:
    # Skip if embeddings exist
    existing = await session.execute(select(func.count()).select_from(DocEmbedding).where(DocEmbedding.file_bss_info_sno == file_id))
    if existing.scalar_one() > 0:
        return 0
    chunk_q = select(DocChunk).where(DocChunk.file_bss_info_sno == file_id).order_by(DocChunk.chunk_id.asc())
    chunk_res = await session.execute(chunk_q)
    chunks = chunk_res.scalars().all()
    if not chunks:
        logger.warning("No chunks for embedding")
        return 0

    embedder = EmbeddingService()
    created = 0
    for ch in chunks:
        emb = await embedder.get_embedding(ch.content_text[:8000])  # safety truncation
        dim = len(emb)
        session.add(DocEmbedding(
            chunk_id=ch.chunk_id,
            file_bss_info_sno=file_id,
            model_name=getattr(settings, 'azure_openai_embedding_deployment', 'text-embedding-3-large'),
            modality='text',
            dimension=dim,
            vector=emb
        ))
        created += 1
    logger.info(f"Created {created} embeddings")
    return created

async def similarity_search(session: AsyncSession, query: str, top_k: int = 3):
    embedder = EmbeddingService()
    q_emb = await embedder.get_embedding(query)
    # Build pgvector literal using bracket syntax: '[v1,v2,...]'
    # Keep precision modest to reduce query size
    vector_literal = "'[" + ','.join(f"{x:.6f}" for x in q_emb) + "]'"
    query_sql = f"""
        SELECT c.chunk_id, c.file_bss_info_sno, e.model_name, e.dimension,
               (e.vector <=> {vector_literal}) AS distance,
               substring(c.content_text for 120) AS preview
        FROM doc_embedding e
        JOIN doc_chunk c ON c.chunk_id = e.chunk_id
        ORDER BY e.vector <=> {vector_literal}
        LIMIT {int(top_k)}
    """
    result = await session.execute(text(query_sql))
    return result.fetchall()

async def main():
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        file_row = await get_latest_file(session)
        if not file_row:
            logger.error("No uploaded file found.")
            return
        file_id = file_row.file_bss_info_sno
        print(f"📁 Target file: {file_id} - {file_row.file_lgc_nm}")

        before = await snapshot_counts(session, file_id)
        print("\n=== BEFORE ===")
        for k,v in before.items():
            print(f"{k:18s}: {v}")

        inserted_objs = await backfill_extracted_objects(session, file_row)
        created_chunks = await backfill_chunks(session, file_id)
        created_embs = await backfill_embeddings(session, file_id)
        await session.commit()

        after = await snapshot_counts(session, file_id)
        print("\n=== AFTER ===")
        for k,v in after.items():
            print(f"{k:18s}: {v}")
        print(f"\nInserted objects: {inserted_objs}, chunks: {created_chunks}, embeddings: {created_embs}")

        if created_embs > 0 or after['embeddings'] > 0:
            print("\n=== SIMILARITY SEARCH TEST ===")
            probe = "인슐린 펌프 사용 사례 ROI"
            rows = await similarity_search(session, probe, top_k=3)
            for r in rows:
                print(f"chunk_id={r.chunk_id} distance={r.distance:.4f}")
        else:
            print("\n(No embeddings available for similarity search)")

if __name__ == "__main__":
    asyncio.run(main())
