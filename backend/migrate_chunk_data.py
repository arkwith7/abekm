"""
데이터 마이그레이션: tb_document_chunks → vs_doc_contents_chunks
안전한 점진적 마이그레이션 스크립트
"""
import asyncio
from sqlalchemy import text
        result = await session.execute(text("""
            SELECT COUNT(*) as new_count 
            FROM vs_doc_contents_chunks 
            WHERE del_yn = 'N'
        """))app.core.database import get_sync_engine, get_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

async def migrate_chunk_data():
    """tb_document_chunks 데이터를 vs_doc_contents_chunks로 마이그레이션"""
    
    # 동기 엔진으로 기존 데이터 조회
    sync_engine = get_sync_engine()
    
    # 비동기 엔진으로 새 테이블에 삽입
    async_engine = get_async_engine()
    AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    
    print("🔄 데이터 마이그레이션 시작...")
    
    # 1. 기존 데이터 확인
    with sync_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) as total_count 
            FROM tb_document_chunks 
            WHERE "DEL_YN" = 'N'
        """))
        total_count = result.fetchone()[0]
        print(f"📊 마이그레이션 대상: {total_count}개 레코드")
        
        if total_count == 0:
            print("✅ 마이그레이션할 데이터가 없습니다.")
            return
    
    # 2. 배치별 마이그레이션 (1000개씩)
    batch_size = 1000
    migrated_count = 0
    
    with sync_engine.connect() as conn:
        # 기존 데이터 조회 (배치별)
        offset = 0
        while True:
            result = conn.execute(text(f"""
                SELECT 
                    "FILE_BSS_INFO_SNO",
                    "CHUNK_INDEX",
                    "CHUNK_TEXT",
                    "CHUNK_SIZE",
                    "CHUNK_EMBEDDING",
                    "PAGE_NUMBER",
                    "SECTION_TITLE",
                    "DEL_YN",
                    "CREATED_BY",
                    "CREATED_DATE",
                    "LAST_MODIFIED_BY",
                    "LAST_MODIFIED_DATE",
                    "KNOWLEDGE_CONTAINER_ID"
                FROM tb_document_chunks 
                WHERE "DEL_YN" = 'N'
                ORDER BY "CHUNK_SNO"
                LIMIT {batch_size} OFFSET {offset}
            """))
            
            batch_data = result.fetchall()
            if not batch_data:
                break
                
            # 비동기로 새 테이블에 삽입
            async with AsyncSessionLocal() as session:
                try:
                    for row in batch_data:
                        # 메타데이터 JSON 생성 (호환성)
                        metadata_json = {
                            "page_number": row[5] if row[5] else 1,
                            "section_title": row[6] if row[6] else "",
                            "keywords": [],  # 기존 데이터에는 키워드 없음
                            "named_entities": []  # 기존 데이터에는 개체명 없음
                        }
                        
                        insert_sql = text("""
                            INSERT INTO vs_doc_contents_chunks (
                                file_bss_info_sno, chunk_index, chunk_text, chunk_size,
                                chunk_embedding, page_number, section_title, 
                                knowledge_container_id, metadata_json,
                                del_yn, created_by, created_date, last_modified_by, last_modified_date
                            ) VALUES (
                                :file_bss_info_sno, :chunk_index, :chunk_text, :chunk_size,
                                :chunk_embedding, :page_number, :section_title, 
                                :knowledge_container_id, :metadata_json,
                                :del_yn, :created_by, :created_date, :last_modified_by, :last_modified_date
                            )
                        """)
                        
                        await session.execute(insert_sql, {
                            "file_bss_info_sno": row[0],
                            "chunk_index": row[1],
                            "chunk_text": row[2],
                            "chunk_size": row[3],
                            "chunk_embedding": row[4],
                            "page_number": row[5],
                            "section_title": row[6],
                            "knowledge_container_id": row[12],  # 마지막 컬럼
                            "metadata_json": str(metadata_json) if metadata_json else None,
                            "del_yn": row[7],
                            "created_by": row[8],
                            "created_date": row[9],
                            "last_modified_by": row[10],
                            "last_modified_date": row[11]
                        })
                    
                    await session.commit()
                    migrated_count += len(batch_data)
                    print(f"📦 배치 완료: {migrated_count}/{total_count} ({migrated_count/total_count*100:.1f}%)")
                    
                except Exception as e:
                    await session.rollback()
                    print(f"❌ 배치 실패: {e}")
                    raise
            
            offset += batch_size
    
    print(f"✅ 데이터 마이그레이션 완료: {migrated_count}개 레코드")
    
    # 3. 마이그레이션 검증
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT COUNT(*) as new_count 
            FROM vs_doc_contents_chunks 
            WHERE "DEL_YN" = 'N'
        """))
        new_count = result.fetchone()[0]
        
        if new_count == total_count:
            print(f"✅ 마이그레이션 검증 성공: {new_count} == {total_count}")
        else:
            print(f"❌ 마이그레이션 검증 실패: {new_count} != {total_count}")

async def verify_migration():
    """마이그레이션 결과 검증"""
    async_engine = get_async_engine()
    AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        # 샘플 데이터 비교
        result = await session.execute(text("""
            SELECT 
                file_bss_info_sno, chunk_index, 
                LEFT(chunk_text, 50) as chunk_preview,
                page_number, keywords
            FROM vs_doc_contents_chunks 
            WHERE "DEL_YN" = 'N'
            ORDER BY chunk_sno 
            LIMIT 5
        """))
        
        print("🔍 마이그레이션된 샘플 데이터:")
        for row in result:
            print(f"  파일: {row[0]}, 청크: {row[1]}, 페이지: {row[3]}")
            print(f"  내용: {row[2]}...")
            print(f"  키워드: {row[4]}")
            print()

if __name__ == "__main__":
    print("🚀 TB_DOCUMENT_CHUNKS → VS_DOC_CONTENTS_CHUNKS 마이그레이션")
    print("=" * 60)
    
    # 마이그레이션 실행
    asyncio.run(migrate_chunk_data())
    
    # 검증
    asyncio.run(verify_migration())
    
    print("=" * 60)
    print("✅ 마이그레이션 완료!")
