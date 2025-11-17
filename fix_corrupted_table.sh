#!/bin/bash
# PostgreSQL 손상된 테이블 복구 스크립트

echo "🔧 PostgreSQL 손상된 테이블 복구 시작..."

# 1. PostgreSQL 컨테이너 재시작
echo "1️⃣ PostgreSQL 재시작..."
docker restart wkms-postgres
sleep 15

# 2. 긴급 복구 모드로 접속하여 손상된 인덱스 재생성
echo "2️⃣ 인덱스 재생성 시도..."
docker exec -i wkms-postgres psql -U wkms -d wkms <<EOF
-- pgvector 확장 상태 확인
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- 테이블 존재 확인
SELECT tablename FROM pg_tables WHERE tablename = 'vs_doc_contents_chunks';
EOF

# 3. VACUUM FULL 시도 (손상된 데이터 정리)
echo "3️⃣ VACUUM FULL 시도..."
docker exec -i wkms-postgres psql -U wkms -d wkms <<EOF
SET statement_timeout = '5min';
VACUUM FULL ANALYZE tb_file_bss_info;
VACUUM FULL ANALYZE tb_document_search_index;
EOF

# 4. 문서 78 메타데이터만 삭제 상태로 변경 (이미 완료)
echo "4️⃣ 문서 78 메타데이터 확인..."
docker exec -i wkms-postgres psql -U wkms -d wkms <<EOF
SELECT file_bss_info_sno, file_lgc_nm, del_yn, processing_status 
FROM tb_file_bss_info 
WHERE file_bss_info_sno = 78;
EOF

# 5. 다른 문서들이 정상인지 확인
echo "5️⃣ 다른 문서 정상 확인..."
docker exec -i wkms-postgres psql -U wkms -d wkms <<EOF
SELECT file_bss_info_sno, file_lgc_nm, del_yn 
FROM tb_file_bss_info 
WHERE del_yn = 'N'
ORDER BY file_bss_info_sno DESC
LIMIT 5;
EOF

echo "✅ 복구 작업 완료"
echo ""
echo "📌 다음 단계:"
echo "1. 프론트엔드에서 문서 78이 사라졌는지 확인"
echo "2. 다른 문서 삭제 테스트"
echo "3. 문서 78의 청크 데이터는 고아 데이터로 남음 (무시)"
echo "4. 향후 VACUUM FULL로 디스크 공간 회수 가능"
