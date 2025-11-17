#!/usr/bin/env python3
"""
간단한 데이터베이스 스키마 테스트 스크립트
WKMS 스키마 명세서에 따른 테이블 생성 및 검증
"""

import os
import sys
import asyncio
import asyncpg
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv('backend/.env')

# 데이터베이스 연결 정보
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'wkms',
    'password': 'wkms123',
    'database': 'wkms'
}

# 스키마 DDL (명세서 기준, 1024차원 벡터)
SCHEMA_DDL = """
-- pgvector 확장 기능 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 파일 상세 정보 테이블 (먼저 생성)
CREATE TABLE IF NOT EXISTS tb_file_dtl_info (
    FILE_DTL_INFO_SNO SERIAL PRIMARY KEY,
    SJ VARCHAR(500),
    CN TEXT,
    KWRD VARCHAR(1000),
    AUTHR VARCHAR(100),
    WRT_DE VARCHAR(8),
    UPDT_DE VARCHAR(8),
    CTGRY_CD VARCHAR(20),
    CTGRY_NM VARCHAR(100),
    FILE_SZ INTEGER,
    PAGE_CO INTEGER,
    LANG_CD VARCHAR(10),
    SECRTY_LVL VARCHAR(10),
    VRSN VARCHAR(20),
    TAG VARCHAR(500),
    SUMRY TEXT,
    DEL_YN CHAR(1) NOT NULL DEFAULT 'N',
    CREATED_BY VARCHAR(50),
    CREATED_DATE TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    LAST_MODIFIED_BY VARCHAR(50),
    LAST_MODIFIED_DATE TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 파일 기본 정보 테이블
CREATE TABLE IF NOT EXISTS tb_file_bss_info (
    FILE_BSS_INFO_SNO SERIAL PRIMARY KEY,
    DRCY_SNO INTEGER NOT NULL,
    FILE_DTL_INFO_SNO INTEGER UNIQUE REFERENCES tb_file_dtl_info(FILE_DTL_INFO_SNO),
    FILE_LGC_NM VARCHAR(255) NOT NULL,
    FILE_PSL_NM VARCHAR(255) NOT NULL,
    FILE_EXTSN VARCHAR(10) NOT NULL,
    PATH VARCHAR(500) NOT NULL,
    DEL_YN CHAR(1) NOT NULL DEFAULT 'N',
    CREATED_BY VARCHAR(50),
    CREATED_DATE TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    LAST_MODIFIED_BY VARCHAR(50),
    LAST_MODIFIED_DATE TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 공통 코드 그룹 아이템 테이블
CREATE TABLE IF NOT EXISTS tb_cmns_cd_grp_item (
    GRP_CD VARCHAR(20),
    ITEM_CD VARCHAR(20),
    ITEM_NM VARCHAR(100) NOT NULL,
    ITEM_DESC VARCHAR(500),
    SORT_ORDR INTEGER,
    USE_YN CHAR(1) NOT NULL DEFAULT 'Y',
    UPPR_GRP_CD VARCHAR(20),
    UPPR_ITEM_CD VARCHAR(20),
    LVL INTEGER,
    DEL_YN CHAR(1) NOT NULL DEFAULT 'N',
    CREATED_BY VARCHAR(50),
    CREATED_DATE TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    LAST_MODIFIED_BY VARCHAR(50),
    LAST_MODIFIED_DATE TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (GRP_CD, ITEM_CD)
);

-- SAP 인사 정보 테이블
CREATE TABLE IF NOT EXISTS tb_sap_hr_info (
    EMP_NO VARCHAR(20) PRIMARY KEY,
    EMP_NM VARCHAR(100) NOT NULL,
    DEPT_CD VARCHAR(20),
    DEPT_NM VARCHAR(100),
    POSTN_CD VARCHAR(20),
    POSTN_NM VARCHAR(100),
    EMAIL VARCHAR(200),
    TELNO VARCHAR(20),
    MBTLNO VARCHAR(20),
    ENTRPS_DE VARCHAR(8),
    RSGNTN_DE VARCHAR(8),
    EMP_STATS_CD VARCHAR(10),
    DEL_YN CHAR(1) NOT NULL DEFAULT 'N',
    CREATED_BY VARCHAR(50),
    CREATED_DATE TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    LAST_MODIFIED_BY VARCHAR(50),
    LAST_MODIFIED_DATE TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 문서 내용 임베딩 인덱스 (1024차원 - Amazon Titan Embeddings V2)
CREATE TABLE IF NOT EXISTS wkms_dev_con_ada_index (
    id VARCHAR(50) PRIMARY KEY,
    FILE_BSS_INFO_SNO INTEGER REFERENCES tb_file_bss_info(FILE_BSS_INFO_SNO),
    chunk_text TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    chunk_index INTEGER,
    chunk_size INTEGER,
    metadata_json TEXT,
    created_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 파일 메타데이터 임베딩 인덱스 (1024차원)
CREATE TABLE IF NOT EXISTS wkms_dev_file_index (
    id VARCHAR(50) PRIMARY KEY,
    FILE_DTL_INFO_SNO INTEGER REFERENCES tb_file_dtl_info(FILE_DTL_INFO_SNO),
    title VARCHAR(500),
    summary TEXT,
    keywords VARCHAR(1000),
    embedding vector(1024) NOT NULL,
    metadata_json TEXT,
    created_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 채팅 기록 임베딩 인덱스 (1024차원)
CREATE TABLE IF NOT EXISTS dev_chat_history_index (
    id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    user_message TEXT,
    ai_response TEXT,
    embedding vector(1024) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata_json TEXT
);

-- 전처리 결과 임베딩 인덱스 (1024차원)
CREATE TABLE IF NOT EXISTS dev_preprocessing_result_index (
    id VARCHAR(50) PRIMARY KEY,
    FILE_BSS_INFO_SNO INTEGER REFERENCES tb_file_bss_info(FILE_BSS_INFO_SNO),
    preprocessing_type VARCHAR(50) NOT NULL,
    processed_text TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    processing_params TEXT,
    created_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 인덱스 생성 (명세서 기준)
CREATE INDEX IF NOT EXISTS idx_tb_file_bss_info_file_psl_nm ON tb_file_bss_info(FILE_PSL_NM);
CREATE INDEX IF NOT EXISTS idx_tb_file_bss_info_del_yn ON tb_file_bss_info(DEL_YN);
CREATE INDEX IF NOT EXISTS idx_tb_file_bss_info_last_modified_date ON tb_file_bss_info(LAST_MODIFIED_DATE);

CREATE INDEX IF NOT EXISTS idx_tb_file_dtl_info_sj ON tb_file_dtl_info(SJ);
CREATE INDEX IF NOT EXISTS idx_tb_file_dtl_info_authr ON tb_file_dtl_info(AUTHR);
CREATE INDEX IF NOT EXISTS idx_tb_file_dtl_info_ctgry_cd ON tb_file_dtl_info(CTGRY_CD);
CREATE INDEX IF NOT EXISTS idx_tb_file_dtl_info_del_yn ON tb_file_dtl_info(DEL_YN);

CREATE INDEX IF NOT EXISTS idx_tb_cmns_cd_grp_item_use_yn ON tb_cmns_cd_grp_item(USE_YN);
CREATE INDEX IF NOT EXISTS idx_tb_cmns_cd_grp_item_uppr ON tb_cmns_cd_grp_item(UPPR_GRP_CD, UPPR_ITEM_CD);

CREATE INDEX IF NOT EXISTS idx_tb_sap_hr_info_emp_nm ON tb_sap_hr_info(EMP_NM);
CREATE INDEX IF NOT EXISTS idx_tb_sap_hr_info_dept_cd ON tb_sap_hr_info(DEPT_CD);
CREATE INDEX IF NOT EXISTS idx_tb_sap_hr_info_email ON tb_sap_hr_info(EMAIL);
CREATE INDEX IF NOT EXISTS idx_tb_sap_hr_info_emp_stats ON tb_sap_hr_info(EMP_STATS_CD);

-- pgvector 인덱스 (벡터 검색 성능 향상)
CREATE INDEX IF NOT EXISTS idx_wkms_con_ada_embedding ON wkms_dev_con_ada_index USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_wkms_file_embedding ON wkms_dev_file_index USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_chat_history_embedding ON dev_chat_history_index USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_preprocessing_embedding ON dev_preprocessing_result_index USING ivfflat (embedding vector_cosine_ops);
"""

# 테스트 데이터 삽입
TEST_DATA = """
-- 테스트 데이터 삽입
INSERT INTO tb_file_dtl_info (SJ, CN, AUTHR, CTGRY_CD, CTGRY_NM) 
VALUES ('테스트 문서', '이것은 테스트 문서입니다.', '관리자', 'DOC001', '일반문서')
ON CONFLICT DO NOTHING;

INSERT INTO tb_file_bss_info (DRCY_SNO, FILE_DTL_INFO_SNO, FILE_LGC_NM, FILE_PSL_NM, FILE_EXTSN, PATH) 
VALUES (1, 1, '테스트문서.pdf', 'test_doc_001.pdf', 'pdf', '/uploads/test_doc_001.pdf')
ON CONFLICT DO NOTHING;

INSERT INTO tb_cmns_cd_grp_item (GRP_CD, ITEM_CD, ITEM_NM, ITEM_DESC, SORT_ORDR) 
VALUES ('CATEGORY', 'DOC001', '일반문서', '일반적인 문서 카테고리', 1)
ON CONFLICT DO NOTHING;

INSERT INTO tb_sap_hr_info (EMP_NO, EMP_NM, DEPT_CD, DEPT_NM, EMAIL) 
VALUES ('EMP001', '홍길동', 'IT001', 'IT개발팀', 'hong@company.com')
ON CONFLICT DO NOTHING;
"""

async def test_database_schema():
    """데이터베이스 스키마 테스트"""
    print("🔗 데이터베이스 연결 테스트...")
    
    try:
        # 데이터베이스 연결
        conn = await asyncpg.connect(**DB_CONFIG)
        print("✅ 데이터베이스 연결 성공")
        
        # 스키마 생성
        print("\n🏗️  스키마 생성 중...")
        await conn.execute(SCHEMA_DDL)
        print("✅ 스키마 생성 완료")
        
        # 테스트 데이터 삽입
        print("\n📊 테스트 데이터 삽입 중...")
        await conn.execute(TEST_DATA)
        print("✅ 테스트 데이터 삽입 완료")
        
        # 테이블 목록 확인
        print("\n📋 생성된 테이블 목록:")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        for table in tables:
            print(f"  📄 {table['table_name']}")
        
        # pgvector 확장 확인
        print("\n🔍 pgvector 확장 확인:")
        extensions = await conn.fetch("""
            SELECT extname, extversion 
            FROM pg_extension 
            WHERE extname = 'vector';
        """)
        
        if extensions:
            print(f"  ✅ pgvector 설치됨 (버전: {extensions[0]['extversion']})")
        else:
            print("  ❌ pgvector 확장이 설치되지 않음")
        
        # 벡터 컬럼 확인
        print("\n🧮 벡터 컬럼 확인:")
        vector_columns = await conn.fetch("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE data_type = 'USER-DEFINED' 
            AND udt_name = 'vector'
            ORDER BY table_name, column_name;
        """)
        
        for col in vector_columns:
            print(f"  📐 {col['table_name']}.{col['column_name']} (vector)")
        
        # 인덱스 확인
        print("\n🔖 생성된 인덱스 확인:")
        indexes = await conn.fetch("""
            SELECT schemaname, tablename, indexname, indexdef
            FROM pg_indexes 
            WHERE schemaname = 'public'
            AND indexname LIKE 'idx_%'
            ORDER BY tablename, indexname;
        """)
        
        for idx in indexes:
            print(f"  🔗 {idx['tablename']}.{idx['indexname']}")
        
        # 1024차원 벡터 테스트
        print("\n🧪 1024차원 벡터 테스트:")
        test_vector = "[" + ",".join(["0.1"] * 1024) + "]"
        
        await conn.execute("""
            INSERT INTO wkms_dev_con_ada_index (id, chunk_text, embedding)
            VALUES ('test_vector_001', '테스트 청크 텍스트', $1)
            ON CONFLICT (id) DO UPDATE SET 
                chunk_text = EXCLUDED.chunk_text,
                embedding = EXCLUDED.embedding;
        """, test_vector)
        
        # 벡터 검색 테스트
        result = await conn.fetchrow("""
            SELECT id, chunk_text, 
                   array_length(string_to_array(embedding::text, ','), 1) as vector_dim
            FROM wkms_dev_con_ada_index 
            WHERE id = 'test_vector_001';
        """)
        
        if result:
            print(f"  ✅ 벡터 저장/조회 성공 (차원: {result['vector_dim']})")
        else:
            print("  ❌ 벡터 저장/조회 실패")
        
        print("\n🎉 데이터베이스 스키마 테스트 완료!")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

if __name__ == "__main__":
    print("🚀 WKMS 데이터베이스 스키마 테스트 시작")
    print("=" * 50)
    
    success = asyncio.run(test_database_schema())
    
    if success:
        print("\n✅ 모든 테스트 통과!")
        sys.exit(0)
    else:
        print("\n❌ 테스트 실패!")
        sys.exit(1)
