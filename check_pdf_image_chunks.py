"""
논문 PDF(문서 68)의 FIGURE 이미지 청크 DB 저장 상태 확인
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

def check_table_schema():
    """테이블 스키마 확인"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # vs_doc_contents_chunks 스키마
    print("\n" + "="*80)
    print("📋 vs_doc_contents_chunks 테이블 스키마")
    print("="*80)
    
    cursor.execute("""
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'vs_doc_contents_chunks'
        ORDER BY ordinal_position;
    """)
    
    for row in cursor.fetchall():
        print(f"  {row['column_name']:30s} {row['data_type']:20s} nullable={row['is_nullable']}")
    
    # doc_embedding 스키마
    print("\n" + "="*80)
    print("📋 doc_embedding 테이블 스키마")
    print("="*80)
    
    cursor.execute("""
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'doc_embedding'
        ORDER BY ordinal_position;
    """)
    
    for row in cursor.fetchall():
        print(f"  {row['column_name']:30s} {row['data_type']:20s} nullable={row['is_nullable']}")
    
    cursor.close()
    conn.close()

def check_document_68_chunks():
    """문서 68/69의 청크 데이터 확인"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. 논문 PDF 문서 목록 확인 (68, 69)
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
        print(f"\n  file_bss_info_sno: {doc['file_bss_info_sno']}")
        print(f"  file_name: {doc['file_lgc_nm']}")
        print(f"  container_id: {doc['knowledge_container_id']}")
        print(f"  search_doc_id: {doc['search_doc_id']}")
        print(f"  created_date: {doc['created_date']}")
    
    # 1. 문서 68의 기본 정보
    print("\n" + "="*80)
    print("📄 문서 68 기본 정보")
    print("="*80)
    
    cursor.execute("""
        SELECT 
            f.file_bss_info_sno,
            f.file_lgc_nm,
            f.knowledge_container_id,
            d.search_doc_id
        FROM tb_file_bss_info f
        LEFT JOIN tb_document_search_index d ON f.file_bss_info_sno = d.file_bss_info_sno
        WHERE f.file_bss_info_sno = 68;
    """)
    
    doc_info = cursor.fetchone()
    if doc_info:
        print(f"  file_bss_info_sno: {doc_info['file_bss_info_sno']}")
        print(f"  file_name: {doc_info['file_lgc_nm']}")
        print(f"  container_id: {doc_info['knowledge_container_id']}")
        print(f"  search_doc_id: {doc_info['search_doc_id']}")
    else:
        print("  ⚠️ 문서 68을 찾을 수 없습니다!")
        cursor.close()
        conn.close()
        return
    
    # 2. doc_embedding 테이블에서 통계
    print("\n" + "="*80)
    print("📊 doc_embedding 통계 (modality 별)")
    print("="*80)
    
    cursor.execute("""
        SELECT 
            modality,
            COUNT(*) as chunk_count,
            COUNT(CASE WHEN vector IS NOT NULL THEN 1 END) as has_text_vector,
            COUNT(CASE WHEN clip_vector IS NOT NULL THEN 1 END) as has_clip_vector
        FROM doc_embedding
        WHERE file_bss_info_sno = 68
        GROUP BY modality
        ORDER BY modality;
    """)
    
    stats = cursor.fetchall()
    if stats:
        for row in stats:
            print(f"  {row['modality']:10s}: {row['chunk_count']:3d}개")
            print(f"               text_vector={row['has_text_vector']:3d}, clip_vector={row['has_clip_vector']:3d}")
    else:
        print("  ⚠️ doc_embedding에 청크가 없습니다!")
    
    # 3. image 모달리티 상세 조회
    print("\n" + "="*80)
    print("🖼️ IMAGE 모달리티 상세 (최대 5개)")
    print("="*80)
    
    cursor.execute("""
        SELECT 
            embedding_id,
            file_bss_info_sno as document_id,
            chunk_id,
            modality,
            content_type,
            LEFT(content, 100) as content_preview,
            vector IS NOT NULL as has_text_vector,
            clip_vector IS NOT NULL as has_clip_vector,
            image_blob_key,
            thumbnail_blob_key,
            page_number,
            metadata::text as metadata
        FROM doc_embedding
        WHERE file_bss_info_sno = 68 
        AND modality = 'image'
        ORDER BY chunk_id
        LIMIT 5;
    """)
    
    image_chunks = cursor.fetchall()
    if image_chunks:
        for chunk in image_chunks:
            print(f"\n  embedding_id: {chunk['embedding_id']}")
            print(f"  chunk_id: {chunk['chunk_id']}")
            print(f"  modality: {chunk['modality']}")
            print(f"  content_type: {chunk['content_type']}")
            print(f"  content_preview: {chunk['content_preview']}")
            print(f"  page_number: {chunk['page_number']}")
            print(f"  has_text_vector: {chunk['has_text_vector']}")
            print(f"  has_clip_vector: {chunk['has_clip_vector']}")
            print(f"  image_blob_key: {chunk['image_blob_key']}")
            print(f"  thumbnail_blob_key: {chunk['thumbnail_blob_key']}")
            print(f"  metadata: {chunk['metadata'][:200] if chunk['metadata'] else 'None'}...")
    else:
        print("  ⚠️ IMAGE 모달리티가 없습니다!")
        print("  ❌ 논문 PDF의 FIGURE 이미지가 DB에 저장되지 않았습니다!")
    
    # 4. DOCX 문서(21번)의 이미지 비교
    print("\n" + "="*80)
    print("🔍 비교: DOCX 문서 21의 IMAGE (참고용)")
    print("="*80)
    
    cursor.execute("""
        SELECT 
            embedding_id,
            file_bss_info_sno as document_id,
            chunk_id,
            modality,
            content_type,
            LEFT(content, 50) as content_preview,
            vector IS NOT NULL as has_text_vector,
            clip_vector IS NOT NULL as has_clip_vector,
            image_blob_key,
            thumbnail_blob_key
        FROM doc_embedding
        WHERE file_bss_info_sno = 21 
        AND modality = 'image'
        ORDER BY chunk_id
        LIMIT 3;
    """)
    
    docx_chunks = cursor.fetchall()
    if docx_chunks:
        for chunk in docx_chunks:
            print(f"\n  embedding_id: {chunk['embedding_id']}")
            print(f"  document_id: {chunk['document_id']}")
            print(f"  chunk_id: {chunk['chunk_id']}")
            print(f"  modality: {chunk['modality']}")
            print(f"  content_type: {chunk['content_type']}")
            print(f"  content_preview: {chunk['content_preview']}")
            print(f"  has_text_vector: {chunk['has_text_vector']}")
            print(f"  has_clip_vector: {chunk['has_clip_vector']} ✅")
            print(f"  image_blob_key: {chunk['image_blob_key']}")
            print(f"  thumbnail_blob_key: {chunk['thumbnail_blob_key']}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    try:
        check_table_schema()
        check_document_68_chunks()
        
        print("\n" + "="*80)
        print("✅ 분석 완료")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
