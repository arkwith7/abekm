# PostgreSQL Korean Search Stack (Mecab + kor_search + pgvector)

이 가이드는 `postgres/Dockerfile`과 `init.sql`을 기반으로, **한국어 형태소 분석(Mecab)** 과 **동의어/다국어 보강(kor_search)** 을 동시에 활용하는 PostgreSQL 컨테이너를 빌드하고 운영하는 방법을 설명합니다. Docker Compose(`docker-compose.yml`) 환경을 기준으로 작성되었습니다.

- **textsearch_ko + Mecab** → 모든 한국어 텍스트에 대한 형태소 기반 색인/검색 (기본값)
- **kor_search** → 한국어/영어 혼합 용어 및 커스텀 동의어 확장
- **pgvector** → 임베딩 기반 벡터 검색 (Hybrid Search 용)

---

## 1️⃣ 빌드 & 기동

```bash
# PostgreSQL 이미지를 빌드하고 컨테이너를 기동합니다.
docker compose build postgres
docker compose up postgres -d

# 상태 확인
docker compose ps postgres
docker compose logs -f postgres
```

> `.env` 또는 쉘 환경에 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` 를 반드시 지정하세요. Compose 파일은 `POSTGRES_DB: ${POSTGRES_USER}` 형태로 사용자 이름과 동일한 DB를 생성합니다.

---

## 2️⃣ Dockerfile 주요 작업

`postgres/Dockerfile`은 다음 순서로 확장을 준비합니다.

1. **기본 패키지 설치**: `build-essential`, `postgresql-server-dev-15`, `libmecab-dev`, `automake`, `libtool` 등 컴파일 의존성
2. **pgvector 컴파일**: `v0.5.1` 소스 빌드 후 `make install`
3. **Mecab Core & 사전 설치**:
   - `mecab-0.996-ko-0.9.2`
   - `mecab-ko-dic-2.1.1-20180720`
   - 설치 후 `ldconfig` 로 라이브러리 등록
4. **textsearch_ko 설치**: PostgreSQL 확장으로 빌드 → `01_ts_mecab_ko.sql` 을 `/docker-entrypoint-initdb.d/` 에 복사하여 초기화 시 한국어 텍스트 검색 구성(`public.korean`)을 자동 생성
5. **kor_search 설치**: GitHub(`junhkang/kor_search`) 소스 빌드
6. **클린업**: 빌드 의존성 패키지 제거, `/tmp` 정리, APT 캐시 삭제
7. **초기화 스크립트 배치**: `init.sql` 은 `20_init.sql`로 복사되어 Mecab/TextSearch/KorSearch 확장을 생성하고 기본 설정을 수행합니다.

> 빌드 결과 이미지는 보안 패치를 위해 주기적으로 `FROM postgres:15` 베이스 이미지를 업데이트하는 것을 권장합니다.

---

## 3️⃣ 초기 구동 검증 (psql)

```bash
# 호스트에서 psql 접속 예시
psql "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"

-- 설치된 확장 확인
SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm', 'textsearch_ko', 'kor_search');

-- 기본 텍스트 검색 설정 확인
SHOW default_text_search_config;  -- 기대값: public.korean

-- Mecab 기반 형태소 분석 확인
SELECT to_tsvector('korean', '한국어 형태소 분석이 정상 동작하는지 확인합니다.');
SELECT * FROM mecabko_analyze('하이브리드 검색을 위한 형태소 분석 예시') LIMIT 5;

-- kor_search 동의어 매핑 확인
SELECT kor_search_like('삼성전자와 Samsung Electronics는 동일 회사입니다.', 'samsung');
```

예상 결과:
- `default_text_search_config` 가 `public.korean` 으로 설정되어 있으며 Mecab 파서를 사용
- `to_tsvector('korean', ...)` 호출 시 형태소 단위 토큰이 생성됨
- `kor_search_like` 로 한국어/영문 혼용 질의가 동일 문서를 매칭

---

## 4️⃣ 테이블/인덱스 적용 패턴

### 4.1 형태소 기반 TSVECTOR 컬럼

```sql
ALTER TABLE doc_chunk
  ADD COLUMN IF NOT EXISTS title_fts tsvector GENERATED ALWAYS AS (
    to_tsvector('korean', coalesce(title, ''))
  ) STORED,
  ADD COLUMN IF NOT EXISTS content_fts tsvector GENERATED ALWAYS AS (
    to_tsvector('korean', coalesce(content, ''))
  ) STORED;
```

> 기존 코드에서 `to_tsvector('korean', ...)` 를 사용하고 있다면 변경 없이 Mecab 파서를 활용하게 됩니다. 추가로 kor_search 전용 함수(`kor_search_to_tsvector`, `kor_search_plainto_tsquery`)를 병행 사용하거나, TSVECTOR 컬럼을 두 개(기본 Mecab + 동의어 확장)로 운용하는 하이브리드 전략도 가능합니다.

### 4.2 GIN 인덱스

```sql
CREATE INDEX IF NOT EXISTS idx_doc_chunk_title_fts
  ON doc_chunk USING GIN (title_fts);

CREATE INDEX IF NOT EXISTS idx_doc_chunk_content_fts
  ON doc_chunk USING GIN (content_fts);
```

### 4.3 검색 질의 예시

```sql
-- 형태소 기반 검색
SELECT id, title
FROM doc_chunk
WHERE content_fts @@ plainto_tsquery('korean', '회의록 요약');

-- kor_search 동의어/다국어 검색
SELECT id, title
FROM doc_chunk
WHERE kor_search_like(content, '삼성');
```

---

## 5️⃣ 벡터 검색 (pgvector)

```sql
ALTER TABLE doc_embedding
  ADD COLUMN IF NOT EXISTS embedding vector(3072);

CREATE INDEX IF NOT EXISTS idx_doc_embedding_vector
  ON doc_embedding USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

VACUUM ANALYZE doc_embedding;
```

> `ivfflat` 는 통계가 존재해야 효율적으로 동작합니다. 대량 삽입 후 `VACUUM ANALYZE` 를 수행하세요.

---

## 6️⃣ 백엔드 연동 포인트

- `backend/app/services/document/storage/vector_storage_service.py` 등에서 `to_tsvector('korean', ...)` 호출 → Mecab 기반 토큰 생성
- `kor_search_like` 또는 `kor_search_to_tsvector` 를 병행하여 **동의어 확장** 과 **형태소 기반 색인** 을 동시에 활용할 수 있음
- `.env` 설정 예시:

```
KOR_SEARCH_ENABLED=1   # kor_search 플래그
KOR_SEARCH_LANGUAGE=korean
```

- 향후 RAG/검색 API에서 `plainto_tsquery('korean', :query)` → Mecab 토크나이저 사용
- 한국어가 포함된 문서 업로드 시 별도 전처리 없이 전체 파이프라인이 형상상 동작

---

## 7️⃣ 재색인 & 유지보수

| 상황              | 조치                                                                                           |
| --------------- | -------------------------------------------------------------------------------------------- |
| 동의어 추가/수정       | `kor_search_word_transform`, `kor_search_word_synonyms` 업데이트 후 `REINDEX` 또는 `VACUUM ANALYZE` |
| Mecab 사전 커스터마이징 | `/usr/local/lib/mecab/dic/mecab-ko-dic` 수정 후 `mecab-dict-index` 실행, 컨테이너 재빌드 필요              |
| TSVECTOR 재생성    | `backend/scripts/reindex_kor_search.py` 확장 (Stub) 또는 별도 SQL 배치 실행                            |
| 성능 튜닝           | `SET enable_seqscan = off` 로 인덱스 사용 여부 확인, ivfflat `lists` 값 조정                              |

---

## 8️⃣ 문제 해결 체크리스트

| 증상                                  | 점검 항목                                                                                                     |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 컨테이너 빌드 실패                          | 외부 다운로드 URL 접근 가능 여부(Bitbucket, GitHub), 빌드 도중 네트워크 타임아웃                                                  |
| `CREATE EXTENSION textsearch_ko` 실패 | `textsearch_ko` 빌드 로그 확인, `postgresql-server-dev-15` 설치 여부                                                |
| 형태소 분석 미동작                          | `SHOW default_text_search_config`, `SELECT * FROM mecabko_analyze('테스트')` 으로 확인                           |
| 동의어 매칭 실패                           | `kor_search_word_transform` / `kor_search_word_synonyms` 데이터 확인, `kor_search_refresh_synonym()` (제공 시) 호출 |
| 벡터 검색 느림                            | `ANALYZE` 실행 여부, `ivfflat` 파라미터 조정, 임베딩 차원 일치 확인                                                          |

---

## 9️⃣ 참고 자료

- [textsearch_ko GitHub (Mecab + PostgreSQL)](https://github.com/i0seph/textsearch_ko)
- [kor_search GitHub](https://github.com/junhkang/kor_search)
- [pgvector 공식 문서](https://github.com/pgvector/pgvector)
- [Hybrid Search 설계 참고](https://growth-coder.tistory.com/334)

필요한 항목을 자유롭게 확장하거나, 추가 스크립트를 `/docker-entrypoint-initdb.d/`에 배치하여 초기화를 자동화할 수 있습니다.
