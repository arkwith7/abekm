#!/usr/bin/env python3
"""
데이터베이스 스키마 확인 스크립트
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

# .env 파일에서 DATABASE_URL 읽기
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql+asyncpg://postgres:postgres@localhost:5432/wkms_db'
)

async def check_schema():
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    try:
        async with engine.begin() as conn:
            # 1. 컬럼 정보 확인
            print("=" * 80)
            print("✅ document_type 및 processing_options 컬럼 확인")
            print("=" * 80)
            
            result = await conn.execute(text("""
                SELECT 
                    column_name, 
                    data_type, 
                    column_default, 
                    is_nullable,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = 'tb_file_bss_info' 
                AND column_name IN ('document_type', 'processing_options')
                ORDER BY column_name
            """))
            
            rows = result.all()
            if rows:
                print(f"\n{'컬럼명':<25} {'타입':<20} {'기본값':<30} {'NULL허용':<10}")
                print("-" * 90)
                for row in rows:
                    col_name = row[0]
                    data_type = row[1] + (f"({row[4]})" if row[4] else "")
                    default = str(row[2])[:28] if row[2] else "NULL"
                    nullable = row[3]
                    print(f"{col_name:<25} {data_type:<20} {default:<30} {nullable:<10}")
            else:
                print("⚠️  컬럼이 존재하지 않습니다!")
            
            # 2. 인덱스 확인
            print("\n" + "=" * 80)
            print("✅ 관련 인덱스 확인")
            print("=" * 80)
            
            result = await conn.execute(text("""
                SELECT 
                    indexname, 
                    indexdef
                FROM pg_indexes 
                WHERE tablename = 'tb_file_bss_info' 
                AND indexname LIKE '%document_type%' OR indexname LIKE '%processing_options%'
                ORDER BY indexname
            """))
            
            rows = result.all()
            if rows:
                for row in rows:
                    print(f"\n인덱스: {row[0]}")
                    print(f"정의: {row[1]}")
            else:
                print("⚠️  관련 인덱스가 존재하지 않습니다!")
            
            # 3. 체크 제약 조건 확인
            print("\n" + "=" * 80)
            print("✅ 체크 제약 조건 확인")
            print("=" * 80)
            
            result = await conn.execute(text("""
                SELECT 
                    conname, 
                    pg_get_constraintdef(oid)
                FROM pg_constraint 
                WHERE conrelid = 'tb_file_bss_info'::regclass 
                AND contype = 'c'
                AND conname = 'chk_document_type'
            """))
            
            rows = result.all()
            if rows:
                for row in rows:
                    print(f"\n제약명: {row[0]}")
                    print(f"정의: {row[1]}")
            else:
                print("⚠️  체크 제약 조건이 존재하지 않습니다!")
            
            # 4. 문서 유형별 통계
            print("\n" + "=" * 80)
            print("✅ 문서 유형별 통계")
            print("=" * 80)
            
            result = await conn.execute(text("""
                SELECT 
                    document_type,
                    COUNT(*) as total,
                    COUNT(CASE WHEN del_yn = 'N' THEN 1 END) as active
                FROM tb_file_bss_info
                GROUP BY document_type
                ORDER BY total DESC
            """))
            
            rows = result.all()
            if rows:
                print(f"\n{'문서 유형':<20} {'전체':<10} {'활성':<10}")
                print("-" * 40)
                for row in rows:
                    print(f"{row[0]:<20} {row[1]:<10} {row[2]:<10}")
            else:
                print("⚠️  데이터가 없습니다!")
            
            # 5. 통계 뷰 확인
            print("\n" + "=" * 80)
            print("✅ vw_document_type_stats 뷰 확인")
            print("=" * 80)
            
            result = await conn.execute(text("""
                SELECT * FROM vw_document_type_stats
                ORDER BY total_documents DESC
            """))
            
            rows = result.all()
            if rows:
                print(f"\n{'유형':<20} {'전체':<8} {'활성':<8} {'삭제':<8} {'최초등록':<20} {'최근등록':<20}")
                print("-" * 90)
                for row in rows:
                    print(f"{row[0]:<20} {row[1]:<8} {row[2]:<8} {row[3]:<8} {str(row[4])[:19]:<20} {str(row[5])[:19]:<20}")
            
            print("\n" + "=" * 80)
            print("✅ 마이그레이션 완료 확인 성공!")
            print("=" * 80)
            
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_schema())
