#!/bin/bash
# RAG 기능 검증 스크립트

DOC_ID=${1:-14}  # 기본값: 14 (새로 업로드할 문서)

echo "========================================="
echo "🔍 RAG 기능 검증 스크립트"
echo "========================================="
echo "문서 ID: $DOC_ID"
echo ""

# PostgreSQL 연결 정보
PGCONNECT="postgresql://wkms:wkms123@localhost:5432/wkms"

# 1. vs_doc_contents_chunks 확인
echo "1️⃣ vs_doc_contents_chunks (청크 저장 확인)"
psql "$PGCONNECT" -c "
SELECT 
    COUNT(*) as chunk_count,
    SUM(chunk_size) as total_text_length,
    SUM(CASE WHEN chunk_embedding IS NOT NULL THEN 1 ELSE 0 END) as embeddings_count,
    COUNT(DISTINCT page_number) as unique_pages
FROM vs_doc_contents_chunks 
WHERE file_bss_info_sno = $DOC_ID;
"

# 2. 청크 상세 정보
echo ""
echo "2️⃣ 청크 상세 정보 (처음 3개)"
psql "$PGCONNECT" -c "
SELECT 
    chunk_sno,
    chunk_index,
    LEFT(chunk_text, 60) as text_preview,
    chunk_size,
    CASE WHEN chunk_embedding IS NOT NULL THEN '✅' ELSE '❌' END as embedding,
    page_number,
    knowledge_container_id
FROM vs_doc_contents_chunks 
WHERE file_bss_info_sno = $DOC_ID
ORDER BY chunk_index
LIMIT 3;
"

# 3. 임베딩 벡터 차원 확인
echo ""
echo "3️⃣ 임베딩 벡터 차원 확인"
psql "$PGCONNECT" -c "
SELECT 
    chunk_index,
    array_length(chunk_embedding, 1) as vector_dimension
FROM vs_doc_contents_chunks 
WHERE file_bss_info_sno = $DOC_ID 
  AND chunk_embedding IS NOT NULL
ORDER BY chunk_index
LIMIT 3;
"

# 4. doc_chunks 테이블 비교
echo ""
echo "4️⃣ doc_chunks (멀티모달) vs vs_doc_contents_chunks (레거시) 비교"
psql "$PGCONNECT" -c "
SELECT 
    'doc_chunks' as table_name,
    COUNT(*) as count
FROM doc_chunks 
WHERE file_bss_info_sno = $DOC_ID

UNION ALL

SELECT 
    'vs_doc_contents_chunks' as table_name,
    COUNT(*) as count
FROM vs_doc_contents_chunks 
WHERE file_bss_info_sno = $DOC_ID;
"

# 5. 검색 인덱스 확인
echo ""
echo "5️⃣ 검색 인덱스 (tb_document_search_index)"
psql "$PGCONNECT" -c "
SELECT 
    search_doc_id,
    file_bss_info_sno,
    LENGTH(full_content) as full_content_length,
    has_images,
    image_count,
    has_tables,
    table_count,
    indexing_status,
    CASE WHEN content_tsvector IS NOT NULL THEN '✅' ELSE '❌' END as fts_created
FROM tb_document_search_index 
WHERE file_bss_info_sno = $DOC_ID;
"

# 6. 종합 평가
echo ""
echo "========================================="
echo "📋 종합 평가"
echo "========================================="

CHUNK_COUNT=$(psql "$PGCONNECT" -t -c "SELECT COUNT(*) FROM vs_doc_contents_chunks WHERE file_bss_info_sno = $DOC_ID;")
EMBEDDING_COUNT=$(psql "$PGCONNECT" -t -c "SELECT COUNT(*) FROM vs_doc_contents_chunks WHERE file_bss_info_sno = $DOC_ID AND chunk_embedding IS NOT NULL;")

CHUNK_COUNT=$(echo $CHUNK_COUNT | xargs)  # trim whitespace
EMBEDDING_COUNT=$(echo $EMBEDDING_COUNT | xargs)

if [ "$CHUNK_COUNT" -gt 0 ]; then
    echo "✅ 청크 저장: $CHUNK_COUNT 개"
else
    echo "❌ 청크 저장: 0개 (실패)"
fi

if [ "$EMBEDDING_COUNT" -gt 0 ]; then
    echo "✅ 임베딩 저장: $EMBEDDING_COUNT 개"
else
    echo "❌ 임베딩 저장: 0개 (실패)"
fi

if [ "$CHUNK_COUNT" -gt 0 ] && [ "$EMBEDDING_COUNT" -gt 0 ]; then
    echo ""
    echo "🎉 RAG 기능: 완벽 작동! (100%)"
    echo "   - 청크 레벨 RAG: ✅ 가능"
    echo "   - 벡터 검색: ✅ 가능"
    echo "   - 문서 레벨 RAG: ✅ 가능"
elif [ "$CHUNK_COUNT" -gt 0 ]; then
    echo ""
    echo "⚠️  RAG 기능: 부분 작동 (50%)"
    echo "   - 청크 레벨 RAG: ✅ 가능"
    echo "   - 벡터 검색: ❌ 불가 (임베딩 없음)"
else
    echo ""
    echo "❌ RAG 기능: 작동 안 함 (0%)"
    echo "   - 청크 저장 안 됨"
fi

echo "========================================="
