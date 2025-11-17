"""
문서 ID 6번의 임베딩 데이터를 검색 가능하게 만드는 스크립트

배경:
- doc_embedding 테이블에 48개 임베딩 저장됨 (3072차원)
- vs_doc_contents_chunks는 1024차원으로 호환 불가
- 검색 서비스가 doc_embedding을 직접 사용하도록 수정 필요

실행:
python backend/scripts/verify_search_data.py
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import get_async_session_local
from sqlalchemy import text


async def verify_doc_6():
    """문서 ID 6번의 검색 데이터 확인"""
    async_session_factory = get_async_session_local()
    async with async_session_factory() as session:
        print("=" * 80)
        print("문서 ID 6번 검색 데이터 검증")
        print("=" * 80)
        
        # 1. 기본 정보
        result = await session.execute(text("""
            SELECT file_bss_info_sno, file_lgc_nm, processing_status, chunk_count
            FROM tb_file_bss_info
            WHERE file_bss_info_sno = 6
        """))
        row = result.fetchone()
        if row:
            print(f"\n📄 문서 정보:")
            print(f"   ID: {row[0]}")
            print(f"   파일명: {row[1]}")
            print(f"   상태: {row[2]}")
            print(f"   청크 수: {row[3]}")
        
        # 2. 청크 확인
        result = await session.execute(text("""
            SELECT COUNT(*) as chunk_count,
                   MIN(chunk_id) as first_chunk,
                   MAX(chunk_id) as last_chunk,
                   AVG(LENGTH(content_text)) as avg_length
            FROM doc_chunk
            WHERE file_bss_info_sno = 6
        """))
        row = result.fetchone()
        if row:
            print(f"\n📦 청크 정보:")
            print(f"   개수: {row[0]}")
            print(f"   ID 범위: {row[1]} ~ {row[2]}")
            print(f"   평균 길이: {row[3]:.0f} chars")
        
        # 3. 임베딩 확인
        result = await session.execute(text("""
            SELECT COUNT(*) as embedding_count,
                   model_name,
                   dimension,
                   modality
            FROM doc_embedding
            WHERE file_bss_info_sno = 6
            GROUP BY model_name, dimension, modality
        """))
        print(f"\n🔢 임베딩 정보:")
        for row in result:
            print(f"   모델: {row[1]}")
            print(f"   개수: {row[0]}")
            print(f"   차원: {row[2]}")
            print(f"   타입: {row[3]}")
        
        # 4. 샘플 청크 + 임베딩 조인
        result = await session.execute(text("""
            SELECT 
                c.chunk_id,
                LEFT(c.content_text, 100) as content_preview,
                c.token_count,
                e.model_name,
                e.dimension,
                e.vector IS NOT NULL as has_vector
            FROM doc_chunk c
            LEFT JOIN doc_embedding e ON c.chunk_id = e.chunk_id
            WHERE c.file_bss_info_sno = 6
            ORDER BY c.chunk_id
            LIMIT 3
        """))
        print(f"\n📋 샘플 청크 (3개):")
        for row in result:
            print(f"\n   청크 ID: {row[0]}")
            print(f"   내용: {row[1]}...")
            print(f"   토큰: {row[2]}")
            print(f"   모델: {row[3]}")
            print(f"   차원: {row[4]}")
            print(f"   벡터: {'✅' if row[5] else '❌'}")
        
        # 5. vs_doc_contents_chunks 확인 (비어있을 것)
        result = await session.execute(text("""
            SELECT COUNT(*) FROM vs_doc_contents_chunks
            WHERE file_bss_info_sno = 6
        """))
        count = result.scalar()
        print(f"\n🗂️  vs_doc_contents_chunks: {count}개 (0이면 정상)")
        
        # 6. 검색 테스트 쿼리 (벡터 검색 시뮬레이션)
        result = await session.execute(text("""
            SELECT 
                c.chunk_id,
                LEFT(c.content_text, 80) as preview
            FROM doc_chunk c
            INNER JOIN doc_embedding e ON c.chunk_id = e.chunk_id
            WHERE c.file_bss_info_sno = 6
              AND e.vector IS NOT NULL
              AND c.content_text ILIKE '%leadership%'
            LIMIT 5
        """))
        print(f"\n🔍 키워드 검색 테스트 ('leadership'):")
        for i, row in enumerate(result, 1):
            print(f"   {i}. 청크 {row[0]}: {row[1]}...")
        
        print("\n" + "=" * 80)
        print("✅ 검증 완료")
        print("=" * 80)
        print("\n📋 다음 단계:")
        print("   1. search_service.py 수정: vs_doc_contents_chunks → doc_embedding")
        print("   2. 벡터 검색 쿼리 변경 (chunk 조인 필요)")
        print("   3. pgvector 0.7.0+ 업그레이드 또는 1536차원 모델 전환 고려")


if __name__ == "__main__":
    asyncio.run(verify_doc_6())
