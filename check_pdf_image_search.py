"""
논문 PDF의 이미지 청크 DB 저장 상태 및 검색 가능 여부 확인
"""
import psycopg2
from psycopg2.extras import RealDictCursor

# DB 연결 정보
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'wkms',
    'user': 'wkms',
    'password': 'wkms123'
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. 논문 PDF 문서 목록 확인
    print("\n" + "="*80)
    print("📋 논문 PDF 문서 목록")
    print("="*80)
    
    cursor.execute("""
        SELECT 
            f.file_bss_info_sno,
            f.file_lgc_nm,
            f.knowledge_container_id,
            d.search_doc_id,
            f.created_date
        FROM tb_file_bss_info f
        LEFT JOIN tb_document_search_index d ON f.file_bss_info_sno = d.file_bss_info_sno
        WHERE f.file_lgc_nm LIKE '%Ambidextrous%'
        ORDER BY f.file_bss_info_sno;
    """)
    
    pdf_docs = cursor.fetchall()
    for doc in pdf_docs:
        print(f"\n  📄 문서 {doc['file_bss_info_sno']}:")
        print(f"     file_name: {doc['file_lgc_nm'][:60]}...")
        print(f"     container_id: {doc['knowledge_container_id']}")
        print(f"     search_doc_id: {doc['search_doc_id']}")
        print(f"     created_date: {doc['created_date']}")
    
    # 2. 각 문서의 doc_embedding 통계
    print("\n" + "="*80)
    print("📊 문서별 doc_embedding 통계 (검색 가능 여부)")
    print("="*80)
    
    for doc in pdf_docs:
        doc_id = doc['file_bss_info_sno']
        print(f"\n📄 문서 {doc_id}:")
        
        cursor.execute("""
            SELECT 
                modality,
                COUNT(*) as chunk_count,
                COUNT(CASE WHEN vector IS NOT NULL THEN 1 END) as has_text_vector,
                COUNT(CASE WHEN clip_vector IS NOT NULL THEN 1 END) as has_clip_vector
            FROM doc_embedding
            WHERE file_bss_info_sno = %s
            GROUP BY modality
            ORDER BY modality;
        """, (doc_id,))
        
        stats = cursor.fetchall()
        if stats:
            for row in stats:
                status = "✅ 검색 가능" if row['has_clip_vector'] > 0 or row['has_text_vector'] > 0 else "❌ 검색 불가"
                print(f"  {row['modality']:10s}: {row['chunk_count']:3d}개 - text_vec={row['has_text_vector']:3d}, clip_vec={row['has_clip_vector']:3d} {status}")
        else:
            print("  ❌ doc_embedding에 데이터 없음 - 검색 불가!")
    
    # 3. doc_chunk 테이블 확인 (청킹은 되었는지)
    print("\n" + "="*80)
    print("📦 doc_chunk 테이블 통계 (청킹 여부)")
    print("="*80)
    
    for doc in pdf_docs:
        doc_id = doc['file_bss_info_sno']
        print(f"\n📄 문서 {doc_id}:")
        
        cursor.execute("""
            SELECT 
                modality,
                COUNT(*) as chunk_count
            FROM doc_chunk
            WHERE file_bss_info_sno = %s
            GROUP BY modality
            ORDER BY modality;
        """, (doc_id,))
        
        chunk_stats = cursor.fetchall()
        if chunk_stats:
            for row in chunk_stats:
                print(f"  {row['modality']:10s}: {row['chunk_count']:3d}개 청크 생성됨")
        else:
            print("  ⚠️ doc_chunk에 데이터 없음")
    
    # 4. Azure DI 추출 객체 확인
    print("\n" + "="*80)
    print("🖼️ doc_extracted_object 통계 (Azure DI 추출)")
    print("="*80)
    
    for doc in pdf_docs:
        doc_id = doc['file_bss_info_sno']
        print(f"\n📄 문서 {doc_id}:")
        
        cursor.execute("""
            SELECT 
                object_type,
                COUNT(*) as obj_count
            FROM doc_extracted_object
            WHERE file_bss_info_sno = %s
            GROUP BY object_type
            ORDER BY object_type;
        """, (doc_id,))
        
        obj_stats = cursor.fetchall()
        if obj_stats:
            for row in obj_stats:
                print(f"  {row['object_type']:15s}: {row['obj_count']:3d}개")
        else:
            print("  ⚠️ doc_extracted_object에 데이터 없음")
    
    # 5. 상세 분석: IMAGE 청크와 임베딩 연결 상태
    print("\n" + "="*80)
    print("🔍 IMAGE 청크 상세 분석 (doc_chunk ↔ doc_embedding)")
    print("="*80)
    
    for doc in pdf_docs:
        doc_id = doc['file_bss_info_sno']
        print(f"\n📄 문서 {doc_id}:")
        
        cursor.execute("""
            SELECT 
                c.chunk_id,
                c.modality,
                c.chunk_index,
                LEFT(c.content_text, 50) as content_preview,
                e.embedding_id,
                e.vector IS NOT NULL as has_text_vec,
                e.clip_vector IS NOT NULL as has_clip_vec
            FROM doc_chunk c
            LEFT JOIN doc_embedding e ON c.chunk_id = e.chunk_id
            WHERE c.file_bss_info_sno = %s
            AND c.modality = 'image'
            ORDER BY c.chunk_index
            LIMIT 3;
        """, (doc_id,))
        
        image_chunks = cursor.fetchall()
        if image_chunks:
            print(f"  ✅ IMAGE 청크 발견: {len(image_chunks)}개")
            for chunk in image_chunks:
                print(f"\n    • chunk_id={chunk['chunk_id']}, index={chunk['chunk_index']}")
                print(f"      content: {chunk['content_preview']}")
                if chunk['embedding_id']:
                    print(f"      ✅ embedding_id={chunk['embedding_id']}")
                    print(f"         text_vec={chunk['has_text_vec']}, clip_vec={chunk['has_clip_vec']}")
                else:
                    print(f"      ❌ doc_embedding에 INSERT 안 됨! (검색 불가)")
        else:
            print("  ⚠️ IMAGE 청크 없음")
    
    # 6. 검색 가능 여부 최종 판정
    print("\n" + "="*80)
    print("🎯 검색 가능 여부 최종 판정")
    print("="*80)
    
    for doc in pdf_docs:
        doc_id = doc['file_bss_info_sno']
        
        # doc_embedding에서 image modality 확인
        cursor.execute("""
            SELECT COUNT(*) as image_embedding_count
            FROM doc_embedding
            WHERE file_bss_info_sno = %s
            AND modality = 'image'
            AND clip_vector IS NOT NULL;
        """, (doc_id,))
        
        result = cursor.fetchone()
        image_count = result['image_embedding_count']
        
        print(f"\n📄 문서 {doc_id}:")
        if image_count > 0:
            print(f"  ✅ 이미지 검색 가능! ({image_count}개 이미지 CLIP 임베딩 존재)")
            print(f"  → '사진', 'Figure', 'Research' 등으로 검색 시 결과에 포함될 수 있음")
        else:
            print(f"  ❌ 이미지 검색 불가! (CLIP 임베딩 없음)")
            print(f"  → 텍스트 검색만 가능, 이미지는 검색 결과에 나타나지 않음")
            print(f"  → 해결: 문서 재처리 필요 (수정된 코드로 다시 업로드)")
    
    # 7. DOCX 비교 (정상 작동 참고용)
    print("\n" + "="*80)
    print("✅ 참고: DOCX 문서 21 (정상 작동 중)")
    print("="*80)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as image_embedding_count
        FROM doc_embedding
        WHERE file_bss_info_sno = 21
        AND modality = 'image'
        AND clip_vector IS NOT NULL;
    """)
    
    result = cursor.fetchone()
    print(f"\n  DOCX 이미지 CLIP 임베딩: {result['image_embedding_count']}개")
    print(f"  → '사진' 검색 시 DOCX 이미지는 정상 검색됨 ✅")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    try:
        main()
        print("\n" + "="*80)
        print("✅ 분석 완료")
        print("="*80)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
