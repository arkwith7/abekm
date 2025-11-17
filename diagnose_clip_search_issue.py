#!/usr/bin/env python3
"""
CLIP 검색 실패 원인 진단 스크립트
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# 데이터베이스 연결 정보
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "wkms",
    "user": "wkms",
    "password": "wkms123"
}

def main():
    print("=" * 80)
    print("🔍 CLIP 검색 실패 원인 진단")
    print("=" * 80)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. 문서 69의 이미지 청크 정보 확인
    print("\n📄 [1단계] 문서 69 이미지 청크 상세 정보")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            dc.chunk_id,
            dc.file_bss_info_sno,
            dc.chunk_index,
            dc.modality,
            dc.content_text,
            LENGTH(dc.content_text) as content_length
        FROM doc_chunk dc
        JOIN doc_base db ON dc.file_bss_info_sno = db.file_bss_info_sno
        WHERE db.document_id = 69
        AND dc.modality = 'image'
        ORDER BY dc.chunk_index;
    """)
    
    image_chunks = cur.fetchall()
    print(f"✅ IMAGE 청크 개수: {len(image_chunks)}개\n")
    
    for chunk in image_chunks:
        print(f"  • chunk_id: {chunk['chunk_id']}")
        print(f"    - file_bss_info_sno: {chunk['file_bss_info_sno']}")
        print(f"    - chunk_index: {chunk['chunk_index']}")
        print(f"    - modality: {chunk['modality']}")
        print(f"    - content: {chunk['content_text'][:100]}...")
        print(f"    - content_length: {chunk['content_length']}")
        print()
    
    # 2. doc_embedding 테이블에서 CLIP 벡터 확인
    print("\n📊 [2단계] doc_embedding 테이블의 CLIP 벡터 확인")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            de.embedding_id,
            de.chunk_id,
            de.modality,
            de.model_name,
            de.dimension,
            (de.vector IS NOT NULL) as has_text_vec,
            (de.clip_vector IS NOT NULL) as has_clip_vec,
            CASE 
                WHEN de.vector IS NOT NULL THEN array_length(de.vector, 1)
                ELSE NULL 
            END as text_vec_dim,
            CASE 
                WHEN de.clip_vector IS NOT NULL THEN array_length(de.clip_vector, 1)
                ELSE NULL 
            END as clip_vec_dim,
            dc.content_text
        FROM doc_embedding de
        JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
        JOIN doc_base db ON dc.file_bss_info_sno = db.file_bss_info_sno
        WHERE db.document_id = 69
        AND dc.modality = 'image'
        ORDER BY de.chunk_id;
    """)
    
    embeddings = cur.fetchall()
    print(f"✅ doc_embedding 레코드: {len(embeddings)}개\n")
    
    for emb in embeddings:
        print(f"  • embedding_id: {emb['embedding_id']}")
        print(f"    - chunk_id: {emb['chunk_id']}")
        print(f"    - modality: {emb['modality']}")
        print(f"    - model_name: {emb['model_name']}")
        print(f"    - dimension: {emb['dimension']}")
        print(f"    - has_text_vec: {emb['has_text_vec']}")
        print(f"    - has_clip_vec: {emb['has_clip_vec']}")
        print(f"    - text_vec_dim: {emb['text_vec_dim']}")
        print(f"    - clip_vec_dim: {emb['clip_vec_dim']}")
        print(f"    - content: {emb['content_text'][:80]}")
        print()
    
    # 3. 실제 CLIP 검색 쿼리 시뮬레이션 (권한 포함)
    print("\n🔍 [3단계] CLIP 검색 쿼리 시뮬레이션")
    print("-" * 80)
    print("검색 조건:")
    print("  - user_emp_no: 77107791")
    print("  - 접근 가능 컨테이너: WJ_CLOUD, WJ_MS_SERVICE, WJ_CLOUD_SERVICE")
    print("  - modality: 'image'")
    print()
    
    # 사용자 권한 확인
    cur.execute("""
        SELECT DISTINCT db.container_id
        FROM doc_base db
        WHERE db.document_id = 69;
    """)
    
    doc_container = cur.fetchone()
    print(f"문서 69의 컨테이너: {doc_container['container_id'] if doc_container else 'None'}")
    
    # 실제 CLIP 검색 쿼리 (간단 버전)
    cur.execute("""
        SELECT 
            dc.chunk_id,
            db.document_id,
            dc.modality,
            dc.content_text,
            db.container_id,
            de.embedding_id,
            (de.clip_vector IS NOT NULL) as has_clip_vec
        FROM doc_chunk dc
        JOIN doc_embedding de ON dc.chunk_id = de.chunk_id
        JOIN doc_base db ON dc.file_bss_info_sno = db.file_bss_info_sno
        WHERE dc.modality = 'image'
        AND de.clip_vector IS NOT NULL
        AND db.container_id IN ('WJ_CLOUD', 'WJ_MS_SERVICE', 'WJ_CLOUD_SERVICE')
        ORDER BY db.document_id DESC
        LIMIT 10;
    """)
    
    search_results = cur.fetchall()
    print(f"\n✅ CLIP 검색 가능한 이미지 청크: {len(search_results)}개\n")
    
    if len(search_results) == 0:
        print("❌ 검색 가능한 이미지 청크가 없습니다!")
        print("\n가능한 원인:")
        print("  1. doc_embedding.clip_vector가 NULL")
        print("  2. container_id 권한 문제")
        print("  3. modality 값이 'image'가 아님")
    else:
        for result in search_results:
            print(f"  • chunk_id: {result['chunk_id']}")
            print(f"    - document_id: {result['document_id']}")
            print(f"    - modality: {result['modality']}")
            print(f"    - container_id: {result['container_id']}")
            print(f"    - has_clip_vec: {result['has_clip_vec']}")
            print(f"    - content: {result['content_text'][:80]}")
            print()
    
    # 4. CLIP 벡터 NULL 체크
    print("\n🔬 [4단계] CLIP 벡터 NULL 원인 분석")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            dc.chunk_id,
            db.document_id,
            dc.modality,
            de.embedding_id,
            (de.vector IS NULL) as vector_is_null,
            (de.clip_vector IS NULL) as clip_vector_is_null
        FROM doc_chunk dc
        LEFT JOIN doc_embedding de ON dc.chunk_id = de.chunk_id
        JOIN doc_base db ON dc.file_bss_info_sno = db.file_bss_info_sno
        WHERE db.document_id = 69
        AND dc.modality = 'image'
        ORDER BY dc.chunk_id;
    """)
    
    null_check = cur.fetchall()
    
    for check in null_check:
        print(f"  • chunk_id: {check['chunk_id']}")
        print(f"    - embedding_id: {check['embedding_id']}")
        print(f"    - vector_is_null: {check['vector_is_null']}")
        print(f"    - clip_vector_is_null: {check['clip_vector_is_null']}")
        
        if check['clip_vector_is_null']:
            print(f"    ⚠️  CLIP 벡터가 NULL입니다!")
        else:
            print(f"    ✅ CLIP 벡터가 존재합니다")
        print()
    
    # 5. 최종 진단
    print("\n" + "=" * 80)
    print("📋 최종 진단 결과")
    print("=" * 80)
    
    if len(embeddings) == 0:
        print("❌ 문제: doc_embedding 테이블에 IMAGE 청크 레코드가 없습니다")
        print("   → 원인: INSERT 조건문 버그 (if vec or clip_vec 수정 필요)")
    elif any(emb['clip_vector_is_null'] for emb in null_check):
        print("❌ 문제: doc_embedding.clip_vector가 NULL입니다")
        print("   → 원인: CLIP 임베딩 생성 실패 또는 INSERT 시 NULL 저장")
    elif len(search_results) == 0:
        print("❌ 문제: 권한 또는 조건 필터링 문제")
        print("   → 원인: container_id 권한 불일치 또는 modality 값 오류")
    else:
        print("✅ 데이터는 정상입니다!")
        print("   → 검색 로직 또는 임베딩 생성 로직 확인 필요")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
