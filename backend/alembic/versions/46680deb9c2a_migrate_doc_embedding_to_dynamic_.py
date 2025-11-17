"""migrate_doc_embedding_to_dynamic_dimension

Revision ID: 46680deb9c2a
Revises: 72342a21e7bc
Create Date: 2025-10-15 06:20:16.856575

목적:
- doc_embedding.vector 컬럼을 동적 차원 지원으로 변경
- 기존 3072 고정 → Vector() 차원 미지정 타입으로 변경
- text-embedding-3-small (1536), text-embedding-3-large (3072) 모두 지원

변경 사항:
1. doc_embedding.vector: vector(3072) → vector (차원 미지정)
2. dimension 컬럼에 실제 차원 값 저장
3. 기존 데이터 보존 (3072차원 데이터 유지)

마이그레이션 전략:
- ALTER COLUMN으로 타입만 변경 (데이터 손실 없음)
- dimension 컬럼은 이미 존재하므로 별도 작업 불필요
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '46680deb9c2a'
down_revision: Union[str, Sequence[str], None] = '72342a21e7bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    doc_embedding.vector를 동적 차원 지원으로 변경
    """
    print("\n🔧 [doc_embedding 동적 차원 마이그레이션 시작]")
    
    connection = op.get_bind()
    
    # 1. 현재 상태 확인
    print("\n1️⃣ 현재 doc_embedding 테이블 상태 확인...")
    result = connection.execute(text("""
        SELECT COUNT(*), model_name, dimension 
        FROM doc_embedding 
        GROUP BY model_name, dimension
    """))
    for row in result:
        print(f"   - {row[1]}: {row[0]}개 (차원: {row[2]})")
    
    # 2. vector 컬럼 타입 변경 (3072 고정 → 차원 미지정)
    print("\n2️⃣ vector 컬럼 타입 변경 중...")
    print("   - 기존: vector(3072) 또는 고정 차원")
    print("   - 변경: vector (차원 미지정, dimension 컬럼 참조)")
    
    # PostgreSQL에서 vector 타입은 차원 변경이 자유로움
    # 단, 기존 데이터가 있으면 조심스럽게 처리 필요
    connection.execute(text("""
        ALTER TABLE doc_embedding 
        ALTER COLUMN vector TYPE vector 
        USING vector::text::vector
    """))
    print("   ✅ vector 컬럼 타입 변경 완료")
    
    # 3. 변경 후 확인
    print("\n3️⃣ 변경 후 확인...")
    result = connection.execute(text("""
        SELECT 
            a.attname,
            pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type
        FROM pg_attribute a
        WHERE a.attrelid = 'doc_embedding'::regclass
          AND a.attname = 'vector'
          AND NOT a.attisdropped
    """))
    for row in result:
        print(f"   - {row[0]}: {row[1]}")
    
    print("\n✅ [doc_embedding 동적 차원 마이그레이션 완료]")
    print("   이제 1536, 3072 등 다양한 차원의 임베딩을 저장할 수 있습니다.")
    print("   dimension 컬럼에 실제 차원 값이 저장됩니다.\n")


def downgrade() -> None:
    """
    doc_embedding.vector를 3072 고정 차원으로 복원
    """
    print("\n🔧 [doc_embedding 차원 복원 시작]")
    
    connection = op.get_bind()
    
    # 1. 3072 차원이 아닌 데이터 확인
    print("\n1️⃣ 3072 차원이 아닌 데이터 확인...")
    result = connection.execute(text("""
        SELECT COUNT(*), dimension 
        FROM doc_embedding 
        WHERE dimension != 3072
        GROUP BY dimension
    """))
    non_3072_count = 0
    for row in result:
        print(f"   ⚠️ 차원 {row[1]}: {row[0]}개")
        non_3072_count += row[0]
    
    if non_3072_count > 0:
        print(f"\n   ⚠️ 경고: {non_3072_count}개의 데이터가 3072 차원이 아닙니다.")
        print("   이 데이터는 downgrade 시 손실될 수 있습니다.")
    
    # 2. vector 컬럼을 3072 고정으로 변경
    print("\n2️⃣ vector 컬럼을 vector(3072)로 변경 중...")
    connection.execute(text("""
        ALTER TABLE doc_embedding 
        ALTER COLUMN vector TYPE vector(3072) 
        USING vector::text::vector(3072)
    """))
    print("   ✅ vector 컬럼 타입 복원 완료")
    
    print("\n✅ [doc_embedding 차원 복원 완료]\n")
