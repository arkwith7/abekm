#!/usr/bin/env python3
"""빠른 CLIP 검색 실패 원인 진단"""
import psycopg2

conn = psycopg2.connect(host="localhost", port=5432, database="wkms", user="wkms", password="wkms123")
cur = conn.cursor()

print("=" * 80)
print("🔍 CLIP 검색 실패 원인 진단")
print("=" * 80)

# 1. CLIP 벡터 존재 확인
cur.execute("""
    SELECT COUNT(*) 
    FROM doc_embedding 
    WHERE clip_vector IS NOT NULL
""")
total_clip = cur.fetchone()[0]
print(f"\n✅ 전체 CLIP 벡터: {total_clip}개")

# 2. IMAGE 모달리티 CLIP 벡터
cur.execute("""
    SELECT COUNT(*) 
    FROM doc_embedding de
    JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
    WHERE de.clip_vector IS NOT NULL 
    AND dc.modality = 'image'
""")
image_clip = cur.fetchone()[0]
print(f"✅ IMAGE CLIP 벡터: {image_clip}개")

# 3. 문서 69의 CLIP 벡터
cur.execute("""
    SELECT dc.chunk_id, dc.content_text
    FROM doc_chunk dc
    JOIN doc_embedding de ON dc.chunk_id = de.chunk_id
    WHERE dc.file_bss_info_sno = 69
    AND dc.modality = 'image'
    AND de.clip_vector IS NOT NULL
""")
doc69_clips = cur.fetchall()
print(f"✅ 문서 69 IMAGE CLIP: {len(doc69_clips)}개")
for chunk_id, content in doc69_clips:
    print(f"   - chunk_id={chunk_id}: {content[:60]}")

# 4. CLIP 벡터 차원 확인 (중요!)
print("\n" + "=" * 80)
print("🔬 CLIP 벡터 NULL 체크")
print("=" * 80)

cur.execute("""
    SELECT 
        de.embedding_id,
        dc.chunk_id,
        dc.modality,
        de.clip_vector::text IS NULL as clip_is_null,
        de.clip_vector::text = '[]' as clip_is_empty,
        CASE 
            WHEN de.clip_vector::text IS NOT NULL 
            THEN length(de.clip_vector::text) 
            ELSE 0 
        END as clip_vector_length
    FROM doc_embedding de
    JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
    WHERE dc.chunk_id IN (2924, 2925)
""")

for row in cur.fetchall():
    emb_id, chunk_id, modality, is_null, is_empty, vec_len = row
    print(f"\n  • chunk_id={chunk_id}, embedding_id={emb_id}")
    print(f"    - modality: {modality}")
    print(f"    - clip_is_null: {is_null}")
    print(f"    - clip_is_empty: {is_empty}")
    print(f"    - clip_vector_length: {vec_len}")
    
    if is_null:
        print(f"    ❌ CLIP 벡터가 NULL입니다!")
    elif is_empty:
        print(f"    ❌ CLIP 벡터가 빈 배열입니다!")
    elif vec_len < 100:
        print(f"    ❌ CLIP 벡터가 너무 짧습니다! (예상: 수천자, 실제: {vec_len}자)")
    else:
        print(f"    ✅ CLIP 벡터가 정상입니다")

print("\n" + "=" * 80)
print("📋 최종 진단")
print("=" * 80)

if image_clip == 0:
    print("❌ IMAGE 모달리티의 CLIP 벡터가 하나도 없습니다!")
    print("   → 원인: CLIP 임베딩이 생성되지 않았거나 INSERT 실패")
elif len(doc69_clips) == 0:
    print("❌ 문서 69의 IMAGE CLIP 벡터가 없습니다!")
    print("   → 원인: 문서 69 재처리 필요")
else:
    print("✅ 데이터는 정상입니다!")
    print("   → 검색 쿼리 로직 또는 벡터 차원 문제 가능성")
    print("\n다음 단계:")
    print("   1. 로그에서 'clip_vector <=> ...' 쿼리 확인")
    print("   2. similarity_threshold 값 확인 (현재: 0.3)")
    print("   3. 벡터 차원 불일치 가능성 체크")

cur.close()
conn.close()
