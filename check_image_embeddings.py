#!/usr/bin/env python3
"""
이미지 임베딩 데이터 확인 스크립트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy import text
from app.core.database import get_async_session_local


async def check_image_embeddings():
    """DB에 저장된 이미지 임베딩 정보 확인"""
    
    async_session_local = get_async_session_local()
    async with async_session_local() as db:
        # 1. 전체 CLIP 벡터 개수
        result = await db.execute(text("""
            SELECT COUNT(*) as total
            FROM doc_embedding
            WHERE clip_vector IS NOT NULL
        """))
        total = result.scalar()
        print(f"📊 총 CLIP 벡터 개수: {total}")
        
        if total == 0:
            print("\n❌ DB에 이미지 임베딩이 저장된 문서가 없습니다!")
            print("   → 이미지가 포함된 문서를 업로드해야 합니다.")
            return
        
        # 2. 컨테이너별 분포
        result = await db.execute(text("""
            SELECT 
                fbf.knowledge_container_id,
                COUNT(DISTINCT dc.file_bss_info_sno) as file_count,
                COUNT(de.embedding_id) as embedding_count
            FROM doc_embedding de
            JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
            JOIN tb_file_bss_info fbf ON dc.file_bss_info_sno = fbf.file_bss_info_sno
            WHERE de.clip_vector IS NOT NULL
              AND fbf.del_yn = 'N'
            GROUP BY fbf.knowledge_container_id
            ORDER BY embedding_count DESC
        """))
        
        print("\n📁 컨테이너별 이미지 임베딩 분포:")
        print("-" * 80)
        print(f"{'컨테이너 ID':<30} {'파일 수':>10} {'임베딩 수':>15}")
        print("-" * 80)
        
        rows = result.fetchall()
        for row in rows:
            print(f"{row.knowledge_container_id:<30} {row.file_count:>10} {row.embedding_count:>15}")
        
        # 3. 사용자 77107791이 접근 가능한 컨테이너의 이미지 임베딩
        result = await db.execute(text("""
            SELECT 
                fbf.knowledge_container_id,
                fbf.file_lgc_nm,
                COUNT(de.embedding_id) as clip_count
            FROM doc_embedding de
            JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
            JOIN tb_file_bss_info fbf ON dc.file_bss_info_sno = fbf.file_bss_info_sno
            WHERE de.clip_vector IS NOT NULL
              AND fbf.del_yn = 'N'
              AND fbf.knowledge_container_id IN (
                  'WJ_MS_SERVICE', 'WJ_CLOUD', 'USER_77107791_0627BBC2', 
                  'WJ_INFRA_CONSULT', 'WJ_CLOUD_SERVICE', 'CON_MHLGV17I'
              )
            GROUP BY fbf.knowledge_container_id, fbf.file_lgc_nm
            ORDER BY clip_count DESC
            LIMIT 20
        """))
        
        print("\n📷 사용자 77107791이 접근 가능한 이미지 임베딩:")
        print("-" * 80)
        print(f"{'컨테이너':<25} {'파일명':<35} {'CLIP 수':>10}")
        print("-" * 80)
        
        rows = result.fetchall()
        if not rows:
            print("❌ 접근 가능한 컨테이너에 이미지 임베딩이 없습니다!")
            print("   → 권한이 있는 컨테이너에 이미지가 포함된 문서를 업로드하세요.")
        else:
            for row in rows:
                file_name = row.file_lgc_nm[:35] if len(row.file_lgc_nm) > 35 else row.file_lgc_nm
                print(f"{row.knowledge_container_id:<25} {file_name:<35} {row.clip_count:>10}")
        
        # 4. 샘플 벡터 차원 확인
        result = await db.execute(text("""
            SELECT array_length(clip_vector, 1) as dimension
            FROM doc_embedding
            WHERE clip_vector IS NOT NULL
            LIMIT 1
        """))
        dimension = result.scalar()
        print(f"\n🔢 CLIP 벡터 차원: {dimension}d")


if __name__ == "__main__":
    asyncio.run(check_image_embeddings())
