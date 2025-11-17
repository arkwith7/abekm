#!/bin/bash
# 멀티모달 검색 시스템 검증 스크립트

echo "🔍 멀티모달 검색 시스템 검증 시작"
echo "======================================"

# 최신 파일 ID 가져오기
LATEST_FILE_ID=$(docker exec wkms-postgres psql -U wkms -d wkms -t -c "
SELECT file_bss_info_sno 
FROM tb_file_bss_info 
ORDER BY created_date DESC 
LIMIT 1;
" | tr -d ' ')

echo "📄 최신 파일 ID: $LATEST_FILE_ID"
echo ""

# 1. 청크 데이터 확인
echo "1️⃣ 텍스트 청크 확인 (vs_doc_contents_chunks):"
docker exec wkms-postgres psql -U wkms -d wkms -c "
SELECT 
    COUNT(*) as 청크수,
    SUM(LENGTH(chunk_text)) as 총_텍스트_길이,
    AVG(LENGTH(chunk_text))::int as 평균_청크_길이
FROM vs_doc_contents_chunks
WHERE file_bss_info_sno = $LATEST_FILE_ID;
"
echo ""

# 2. 임베딩 확인
echo "2️⃣ 임베딩 데이터 확인 (doc_embedding):"
docker exec wkms-postgres psql -U wkms -d wkms -c "
SELECT 
    COUNT(*) as 임베딩수,
    MAX(dimension) as 차원,
    COUNT(CASE WHEN modality = 'TEXT' THEN 1 END) as TEXT_청크
FROM doc_embedding
WHERE file_bss_info_sno = $LATEST_FILE_ID;
"
echo ""

# 3. 검색 인덱스 확인 (핵심!)
echo "3️⃣ 검색 인덱스 확인 (tb_document_search_index):"
docker exec wkms-postgres psql -U wkms -d wkms -c "
SELECT 
    search_doc_id,
    LEFT(document_title, 50) as 제목,
    LENGTH(full_content) as 텍스트_길이,
    array_length(keywords, 1) as 키워드수,
    has_images,
    image_count,
    indexing_status
FROM tb_document_search_index
WHERE file_bss_info_sno = $LATEST_FILE_ID;
"
echo ""

# 4. 이미지 메타데이터 확인
echo "4️⃣ 이미지 메타데이터 확인:"
docker exec wkms-postgres psql -U wkms -d wkms -c "
SELECT 
    has_images,
    image_count,
    jsonb_array_length(images_metadata) as 메타데이터수,
    LEFT(images_metadata::text, 100) as 메타데이터_미리보기
FROM tb_document_search_index
WHERE file_bss_info_sno = $LATEST_FILE_ID;
"
echo ""

# 5. FTS 벡터 확인
echo "5️⃣ Korean FTS 벡터 확인:"
docker exec wkms-postgres psql -U wkms -d wkms -c "
SELECT 
    content_tsvector IS NOT NULL as FTS_생성됨,
    ts_stat('SELECT content_tsvector FROM tb_document_search_index WHERE file_bss_info_sno = $LATEST_FILE_ID')::text as 토큰_샘플
FROM tb_document_search_index
WHERE file_bss_info_sno = $LATEST_FILE_ID
LIMIT 1;
" 2>&1 | head -10
echo ""

echo "======================================"
echo "✅ 검증 완료!"
echo ""
echo "📝 다음 단계:"
echo "   1. 위 결과에서 '텍스트_길이'가 0보다 큰지 확인"
echo "   2. '키워드수'가 1개 이상인지 확인"
echo "   3. 'has_images'가 true인지 확인"
echo "   4. 프론트엔드에서 '양손잡이' 검색 테스트"
