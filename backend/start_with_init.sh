#!/bin/bash
set -euo pipefail

echo "🚀 WKMS Backend Server Starting (schema + seed check)"

DB_HOST=${DB_HOST:-postgres}
DB_USER=${DB_USER:-wkms}
DB_PASSWORD=${DB_PASSWORD:-wkms123}
DB_NAME=${DB_NAME:-wkms}
DB_PORT=${DB_PORT:-5432}
FORCE_DB_SEED=${FORCE_DB_SEED:-false}

export DB_HOST DB_USER DB_PASSWORD DB_NAME DB_PORT FORCE_DB_SEED

echo "🔧 DB_HOST=$DB_HOST DB_NAME=$DB_NAME FORCE_DB_SEED=$FORCE_DB_SEED"

echo "⏳ Waiting for PostgreSQL to be ready..."
until python - <<PY
import asyncpg, asyncio, os, sys
async def main():
    try:
        conn = await asyncpg.connect(host=os.getenv('DB_HOST'), port=int(os.getenv('DB_PORT')), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'))
        await conn.close()
        print('✅ Database connection ok')
    except Exception as e:
        print(f'❌ DB not ready: {e}')
        sys.exit(1)
asyncio.run(main())
PY
do
  sleep 2
done

echo "✅ PostgreSQL is ready"

echo "🔍 Checking schema (tb_user exists?)"
USER_TABLE_EXISTS=$(python - <<PY
import asyncpg, asyncio, os
async def run():
    conn = await asyncpg.connect(host=os.getenv('DB_HOST'), port=int(os.getenv('DB_PORT')), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'))
    r = await conn.fetch("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tb_user'")
    await conn.close()
    print('True' if r else 'False')
asyncio.run(run())
PY
)

if [ "$USER_TABLE_EXISTS" != "True" ]; then
  echo "📋 tb_user not found → running Alembic migrations"
  alembic upgrade head
  echo "✅ Alembic migration complete"
else
  echo "✅ Schema already present"
fi

READ_COUNTS=$(python - <<PY
import asyncpg, asyncio, os, json
TARGETS={
  'users':'SELECT COUNT(*) FROM tb_user',
  'roles':'SELECT COUNT(*) FROM tb_user_roles',
  'permissions':'SELECT COUNT(*) FROM tb_user_permissions',
  'categories':'SELECT COUNT(*) FROM tb_knowledge_categories'
}
async def run():
    try:
        conn = await asyncpg.connect(host=os.getenv('DB_HOST'), port=int(os.getenv('DB_PORT')), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'))
        out={}
        for k,q in TARGETS.items():
            try:
                r=await conn.fetch(q)
                out[k]=r[0]['count'] if 'count' in r[0] else list(r[0].values())[0]
            except Exception:
                out[k]=-1
        await conn.close()
        print(json.dumps(out))
    except Exception:
        print(json.dumps({k:-1 for k in TARGETS}))
asyncio.run(run())
PY
)

export READ_COUNTS

USERS=$(python -c "import json,os;print(json.loads(os.getenv('READ_COUNTS'))['users'])" 2>/dev/null || python - <<PY
import os,json; print(json.loads(os.getenv('READ_COUNTS','{}')).get('users',-1))
PY)

echo "📊 Table counts: $READ_COUNTS"

NEED_SEED=false
if [ "$FORCE_DB_SEED" = "true" ]; then
  echo "⚠️  FORCE_DB_SEED=true → forcing full seed"
  NEED_SEED=true
else
  # Parse JSON to detect any zero tables
  ANY_EMPTY=$(python - <<PY
import json, os
rc=os.getenv('READ_COUNTS','{}')
try:
    d=json.loads(rc)
    # treat -1 (error) as empty as well
    print('true' if any(v in (0,-1) for v in d.values()) else 'false')
except Exception:
    print('true')
PY)
  if [ "$ANY_EMPTY" = "true" ]; then
    echo "ℹ️  One or more target tables empty → seeding will run"
    NEED_SEED=true
  fi
fi

if [ "$NEED_SEED" = true ]; then
  echo "📊 Running data initialization (init_simple_database.py)..."
  python init_simple_database.py || { echo "❌ Seeding failed"; exit 1; }
  echo "✅ Seeding completed"
else
  echo "✅ Skipping seeding (all target tables populated). Use FORCE_DB_SEED=true to override."
fi

echo "🚀 Starting FastAPI (Uvicorn)"  
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
