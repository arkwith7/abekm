# WKMS 데이터베이스 스키마 명세서

## 📋 개요

본 문서는 WKMS(Woonjin Knowledge Management System)에서 사용하는 데이터 저장소의 상세 스키마 정보를 다룹니다. 시스템은 메타데이터 관리를 위한 **MySQL RDBMS**와 문서 검색을 위한 **Azure AI Search Vector Store**를 함께 사용합니다.

---

## 🗄️ MySQL RDBMS 스키마

### 1. 테이블 구조 개요

| 테이블명                | 용도                  | 관계                              |
| ------------------- | ------------------- | ------------------------------- |
| tb_file_bss_info    | 파일 기본 정보            | 부모 테이블 (1:1 → tb_file_dtl_info) |
| tb_file_dtl_info    | 파일 상세 정보            | 자식 테이블 (1:1 ← tb_file_bss_info) |
| tb_cmns_cd_grp_item | 공통 코드 그룹 아이템 (카테고리) | 참조 테이블 (계층 구조)                  |
| tb_sap_hr_info      | SAP 인사 정보           | 참조 테이블 (사용자 정보)                 |

### 2. 테이블 상세 스키마

#### 2.1 tb_file_bss_info (파일 기본 정보)

| 컬럼명                | 데이터 타입       | 제약조건       | 설명            |
| ------------------ | ------------ | ---------- | ------------- |
| FILE_BSS_INFO_SNO  | INT          | PK, AI     | 파일 기본 정보 일련번호 |
| DRCY_SNO           | INT          | NOT NULL   | 디렉토리 일련번호     |
| FILE_DTL_INFO_SNO  | INT          | FK, UNIQUE | 파일 상세 정보 일련번호 |
| FILE_LGC_NM        | VARCHAR(255) | NOT NULL   | 파일 논리명        |
| FILE_PSL_NM        | VARCHAR(255) | NOT NULL   | 파일 물리명        |
| FILE_EXTSN         | VARCHAR(10)  | NOT NULL   | 파일 확장자        |
| PATH               | VARCHAR(500) | NOT NULL   | 파일 저장 경로      |
| DEL_YN             | CHAR(1)      | NOT NULL   | 삭제 여부 (Y/N)   |
| CREATED_BY         | VARCHAR(50)  | NULL       | 생성자 ID        |
| CREATED_DATE       | TIMESTAMP    | DEFAULT    | 생성일시          |
| LAST_MODIFIED_BY   | VARCHAR(50)  | NULL       | 최종 수정자 ID     |
| LAST_MODIFIED_DATE | TIMESTAMP    | DEFAULT    | 최종 수정일시       |

**인덱스**:
- PK: FILE_BSS_INFO_SNO
- UNIQUE: FILE_DTL_INFO_SNO
- INDEX: FILE_PSL_NM, DEL_YN, LAST_MODIFIED_DATE

#### 2.2 tb_file_dtl_info (파일 상세 정보)

| 컬럼명                | 데이터 타입       | 제약조건    | 설명                               |
| ------------------ | ------------ | ------- | -------------------------------- |
| FILE_DTL_INFO_SNO  | INT          | PK, AI  | 파일 상세 정보 일련번호                    |
| SJ                 | VARCHAR(500) | NULL    | 파일 제목                            |
| CN                 | TEXT         | NULL    | 파일 내용 요약                         |
| KW                 | JSON         | NULL    | 키워드 목록 (JSON 배열)                 |
| CTG_LVL1           | INT          | FK      | 1차 카테고리 ID (tb_cmns_cd_grp_item) |
| CTG_LVL2           | INT          | FK      | 2차 카테고리 ID (tb_cmns_cd_grp_item) |
| CREATED_BY         | VARCHAR(50)  | NULL    | 생성자 ID                           |
| CREATED_DATE       | TIMESTAMP    | DEFAULT | 생성일시                             |
| LAST_MODIFIED_BY   | VARCHAR(50)  | NULL    | 최종 수정자 ID                        |
| LAST_MODIFIED_DATE | TIMESTAMP    | DEFAULT | 최종 수정일시                          |

**KW 컬럼 JSON 구조**:
```json
[
  {"keyword": "AI"},
  {"keyword": "머신러닝"},
  {"keyword": "데이터사이언스"}
]
```

**인덱스**:
- PK: FILE_DTL_INFO_SNO
- INDEX: CTG_LVL1, CTG_LVL2

#### 2.3 tb_cmns_cd_grp_item (공통 코드 그룹 아이템)

| 컬럼명          | 데이터 타입       | 제약조건     | 설명               |
| ------------ | ------------ | -------- | ---------------- |
| ITEM_ID      | INT          | PK, AI   | 아이템 ID           |
| ITEM_NM      | VARCHAR(100) | NOT NULL | 아이템명             |
| REF_ITEM_ID  | INT          | FK       | 상위 아이템 ID (계층구조) |
| SORT_ORDER   | INT          | NULL     | 정렬 순서            |
| USE_YN       | CHAR(1)      | DEFAULT  | 사용 여부 (Y/N)      |
| CREATED_DATE | TIMESTAMP    | DEFAULT  | 생성일시             |

**계층 구조**:
- REF_ITEM_ID가 NULL: 1차 카테고리 (루트)
- REF_ITEM_ID가 존재: 2차 카테고리 (하위)

**인덱스**:
- PK: ITEM_ID
- INDEX: REF_ITEM_ID, USE_YN

#### 2.4 tb_sap_hr_info (SAP 인사 정보)

| 컬럼명      | 데이터 타입       | 제약조건     | 설명      |
| -------- | ------------ | -------- | ------- |
| USER_ID  | VARCHAR(50)  | PK       | 사용자 ID  |
| USER_FNM | VARCHAR(100) | NOT NULL | 사용자 전체명 |
| DEPT_NM  | VARCHAR(100) | NULL     | 부서명     |
| POSITION | VARCHAR(50)  | NULL     | 직급      |
| EMAIL    | VARCHAR(100) | NULL     | 이메일     |
| PHONE    | VARCHAR(20)  | NULL     | 전화번호    |

**인덱스**:
- PK: USER_ID
- INDEX: DEPT_NM

### 3. 주요 쿼리 패턴

#### 3.1 파일 정보 조회 (계층적 카테고리 포함)

```sql
WITH RECURSIVE category_hierarchy AS (
    SELECT 
        ITEM_ID, ITEM_NM, REF_ITEM_ID, 1 as LEVEL
    FROM tb_cmns_cd_grp_item
    WHERE REF_ITEM_ID IS NULL
    
    UNION ALL
    
    SELECT 
        i.ITEM_ID, i.ITEM_NM, i.REF_ITEM_ID, h.LEVEL + 1
    FROM tb_cmns_cd_grp_item i
    INNER JOIN category_hierarchy h ON i.REF_ITEM_ID = h.ITEM_ID
)
SELECT 
    bss.FILE_BSS_INFO_SNO,
    bss.FILE_LGC_NM,
    bss.FILE_PSL_NM,
    dtl.SJ,
    dtl.CN,
    dtl.KW,
    cat1.ITEM_NM AS CTG_LVL1_NM,
    cat2.ITEM_NM AS CTG_LVL2_NM
FROM tb_file_bss_info bss
INNER JOIN tb_file_dtl_info dtl ON bss.FILE_DTL_INFO_SNO = dtl.FILE_DTL_INFO_SNO
LEFT JOIN category_hierarchy cat1 ON dtl.CTG_LVL1 = cat1.ITEM_ID
LEFT JOIN category_hierarchy cat2 ON dtl.CTG_LVL2 = cat2.ITEM_ID
WHERE bss.FILE_PSL_NM = ? AND bss.DEL_YN = 'N';
```

#### 3.2 최근 수정된 파일 조회 (배치 처리용)

```sql
SELECT * FROM tb_file_bss_info bss
INNER JOIN tb_file_dtl_info dtl ON bss.FILE_DTL_INFO_SNO = dtl.FILE_DTL_INFO_SNO
WHERE bss.LAST_MODIFIED_DATE >= NOW() - INTERVAL ? MINUTE;
```

---

## 🔍 Azure AI Search Vector Store 스키마

### 1. 인덱스 구조 개요

| 인덱스명                           | 용도          | 벡터 필드 수 | 문서 수 (예상) |
| ------------------------------ | ----------- | ------- | --------- |
| wkms-dev-file-index            | 파일 메타데이터 관리 | 0       | ~10,000   |
| wkms-dev-con-ada-index         | 문서 내용 검색    | 2       | ~100,000  |
| dev-chat-history-index         | 채팅 기록 관리    | 1       | ~50,000   |
| dev-preprocessing-result-index | 전처리 결과 추적   | 0       | ~10,000   |

### 2. 인덱스 상세 스키마

#### 2.1 wkms-dev-file-index (파일 메타데이터 인덱스)

**목적**: 파일의 메타데이터 정보 저장 및 검색

| 필드명               | 데이터 타입      | 속성                     | 설명            |
| ----------------- | ----------- | ---------------------- | ------------- |
| id                | Edm.String  | KEY, FILTERABLE        | 인코딩된 고유 ID    |
| file_bss_info_sno | Edm.Int32   | FILTERABLE, SORTABLE   | 파일 기본 정보 일련번호 |
| drcy_sno          | Edm.Int32   | FILTERABLE             | 디렉토리 일련번호     |
| file_dtl_info_sno | Edm.Int32   | FILTERABLE             | 파일 상세 정보 일련번호 |
| file_lgc_nm       | Edm.String  | SEARCHABLE, FILTERABLE | 파일 논리명        |
| file_psl_nm       | Edm.String  | SEARCHABLE, FILTERABLE | 파일 물리명        |
| path              | Edm.String  | FILTERABLE             | 파일 저장 경로      |
| del_yn            | Edm.Boolean | FILTERABLE             | 삭제 여부         |

**ID 생성 규칙**:
```python
original_key = f"{file_bss_info_sno}_{drcy_sno}_{file_dtl_info_sno}_{file_psl_nm}"
encoded_id = base64.urlsafe_b64encode(original_key.encode('utf-8')).decode('utf-8')
```

**검색 패턴**:
```python
# 파일명으로 검색
results = search_client.search(
    search_text="*",
    filter="file_lgc_nm eq 'document.pdf' and del_yn eq false",
    select=["file_bss_info_sno", "file_lgc_nm", "file_psl_nm", "path"]
)
```

#### 2.2 wkms-dev-con-ada-index (문서 내용 검색 인덱스)

**목적**: 문서 내용의 청킹된 텍스트와 벡터 임베딩을 저장하여 하이브리드 검색 지원

| 필드명                | 데이터 타입                 | 속성                                | 설명                      |
| ------------------ | ---------------------- | --------------------------------- | ----------------------- |
| id                 | Edm.String             | KEY, FILTERABLE                   | 인코딩된 고유 ID (청킹 단위)      |
| file_index_id      | Edm.String             | FILTERABLE                        | 원본 파일 인덱스 ID            |
| file_lgc_nm        | Edm.String             | SEARCHABLE, FILTERABLE, FACETABLE | 파일 논리명                  |
| file_psl_nm        | Edm.String             | SEARCHABLE, FILTERABLE            | 파일 물리명                  |
| title              | Edm.String             | SEARCHABLE, FILTERABLE            | 문서 제목                   |
| page_num           | Edm.Int32              | FILTERABLE, SORTABLE              | 페이지 번호                  |
| chunk_num          | Edm.Int32              | FILTERABLE, SORTABLE              | 청크 번호                   |
| chunk_text         | Edm.String             | SEARCHABLE                        | 청킹된 텍스트 내용              |
| main_text          | Edm.String             | SEARCHABLE                        | 구조화된 전체 텍스트             |
| chunk_text_vector  | Collection(Edm.Single) | VECTOR_SEARCH                     | 청크 텍스트의 벡터 임베딩 (1536차원) |
| main_text_vector   | Collection(Edm.Single) | VECTOR_SEARCH                     | 전체 텍스트의 벡터 임베딩 (1536차원) |
| preprocessing_time | Edm.DateTimeOffset     | FILTERABLE, SORTABLE              | 전처리 시간                  |
| del_yn             | Edm.Boolean            | FILTERABLE                        | 삭제 여부                   |
| ctg_lvl1_nm        | Edm.String             | FILTERABLE, FACETABLE             | 1차 카테고리명                |
| ctg_lvl2_nm        | Edm.String             | FILTERABLE, FACETABLE             | 2차 카테고리명                |

**ID 생성 규칙**:
```python
original_key = f"{file_psl_nm}_{page_num}_{chunk_num}"
encoded_id = base64.urlsafe_b64encode(original_key.encode('utf-8')).decode('utf-8')
```

**main_text 구조**:
```text
(file_name) 제안서_AI프로젝트.pdf

(title) AI 기반 지식 관리 시스템 제안서

(content)
1. 프로젝트 개요
본 프로젝트는 AI 기술을 활용하여...
```

**하이브리드 검색 예시**:
```python
# 벡터 + 키워드 하이브리드 검색
vector_query = VectorizedQuery(
    vector=question_embedding, 
    k_nearest_neighbors=50, 
    fields="main_text_vector"
)

results = search_client.search(
    search_text="AI 기술 적용",
    search_fields=["chunk_text", "main_text"],
    vector_queries=[vector_query],
    filter="del_yn eq false",
    select=["id", "file_lgc_nm", "title", "chunk_text"],
    top=10
)
```

#### 2.3 dev-chat-history-index (채팅 기록 인덱스)

**목적**: 사용자 채팅 기록 저장 및 대화 컨텍스트 관리

| 필드명             | 데이터 타입                      | 속성                    | 설명                         |
| --------------- | --------------------------- | --------------------- | -------------------------- |
| id              | Edm.String                  | KEY, FILTERABLE       | 채팅 세션 고유 ID                |
| loginEmpNo      | Edm.String                  | FILTERABLE            | 로그인 사원번호                   |
| sessionId       | Edm.String                  | FILTERABLE            | 세션 ID                      |
| question        | Edm.String                  | SEARCHABLE            | 사용자 질문                     |
| answer          | Edm.String                  | SEARCHABLE            | 시스템 답변                     |
| intent          | Edm.String                  | FILTERABLE, FACETABLE | 질문 의도 (Search/Q&A/Summary) |
| file_info       | Collection(Edm.ComplexType) | -                     | 참조된 파일 정보 배열               |
| check           | Edm.String                  | FILTERABLE            | 답변 검증 상태 (Yes/No)          |
| question_vector | Collection(Edm.Single)      | VECTOR_SEARCH         | 질문의 벡터 임베딩 (1536차원)        |
| is_chat_history | Edm.String                  | FILTERABLE            | 채팅 기록 기반 여부 (y/n)          |
| chat_time       | Edm.DateTimeOffset          | FILTERABLE, SORTABLE  | 채팅 시간                      |

**file_info ComplexType 구조**:
```json
{
  "file_bss_info_sno": 123,
  "drcy_sno": 456,
  "file_dtl_info_sno": 789,
  "file_lgc_nm": "document.pdf",
  "file_psl_nm": "doc_20240101_001.pdf",
  "path": "/uploads/2024/01/01"
}
```

**Chat ID 생성 규칙**:
```python
chat_id = f"{loginEmpNo}-{sessionId}-{YYYYMMDD}"
```

**채팅 기록 조회 예시**:
```python
# 특정 사용자의 당일 채팅 기록 조회
results = search_client.search(
    search_text="*",
    filter=f"chat_time ge {start_time} and chat_time lt {end_time} and loginEmpNo eq '{emp_no}' and sessionId eq '{session_id}' and check eq 'Yes'",
    order_by=["chat_time desc"],
    select=["question", "answer", "file_info"],
    top=10
)
```

#### 2.4 dev-preprocessing-result-index (전처리 결과 인덱스)

**목적**: 파일 전처리 작업의 상태 및 결과 추적

| 필드명                  | 데이터 타입             | 속성                     | 설명                    |
| -------------------- | ------------------ | ---------------------- | --------------------- |
| id                   | Edm.String         | KEY, FILTERABLE        | 파일 고유 ID              |
| file_bss_info_sno    | Edm.Int32          | FILTERABLE             | 파일 기본 정보 일련번호         |
| drcy_sno             | Edm.Int32          | FILTERABLE             | 디렉토리 일련번호             |
| file_dtl_info_sno    | Edm.Int32          | FILTERABLE             | 파일 상세 정보 일련번호         |
| path                 | Edm.String         | FILTERABLE             | 파일 저장 경로              |
| file_lgc_nm          | Edm.String         | SEARCHABLE, FILTERABLE | 파일 논리명                |
| file_psl_nm          | Edm.String         | SEARCHABLE, FILTERABLE | 파일 물리명                |
| preprocessing_time   | Edm.DateTimeOffset | FILTERABLE, SORTABLE   | 전처리 시간                |
| preprocessing_result | Edm.String         | FILTERABLE, FACETABLE  | 전처리 결과 (success/fail) |

**전처리 상태 조회 예시**:
```python
# 전처리 실패한 파일 목록 조회
results = search_client.search(
    search_text="*",
    filter="preprocessing_result eq 'fail'",
    order_by=["preprocessing_time desc"],
    select=["file_psl_nm", "preprocessing_time", "preprocessing_result"],
    top=50
)
```

### 3. 벡터 검색 설정

#### 3.1 벡터 구성

- **모델**: text-embedding-ada-002 (Azure OpenAI)
- **차원**: 1536
- **거리 메트릭**: 코사인 유사도

#### 3.2 하이브리드 검색 전략

1. **키워드 검색**: BM25 알고리즘 기반
2. **벡터 검색**: 의미적 유사도 기반
3. **결합 방식**: RRF (Reciprocal Rank Fusion)

---

## 🔗 RDBMS와 Vector Store 연동

### 1. 데이터 플로우

```
파일 업로드 → MySQL 메타데이터 저장 → Azure AI Search 파일 인덱스 저장
     ↓
문서 전처리 및 청킹 → 벡터 임베딩 생성 → Azure AI Search 콘텐츠 인덱스 저장
     ↓
전처리 결과 기록 → 상태 추적
```

### 2. 일관성 보장

- **트랜잭션**: MySQL 트랜잭션으로 메타데이터 일관성 보장
- **동기화**: AI Search 업로드 실패 시 MySQL 롤백
- **상태 추적**: preprocessing_result_index로 동기화 상태 모니터링

### 3. 검색 프로세스

1. **메타데이터 검색**: MySQL에서 권한 및 카테고리 필터링
2. **콘텐츠 검색**: AI Search에서 하이브리드 검색 수행
3. **결과 조합**: 메타데이터와 콘텐츠 결과 병합

---

## 📊 성능 최적화

### 1. MySQL 최적화

- **인덱스**: 자주 사용되는 검색 조건에 복합 인덱스 생성
- **파티셔닝**: 대용량 데이터의 경우 날짜 기반 파티셔닝 고려
- **커넥션 풀**: 연결 관리 최적화

### 2. AI Search 최적화

- **검색 단위**: 적절한 검색 단위 설정으로 성능과 비용 균형
- **캐싱**: 자주 검색되는 쿼리 결과 캐싱
- **배치 업로드**: 대량 문서 처리 시 배치 방식 활용

---

## 🔒 보안 및 권한

### 1. 데이터 보안

- **암호화**: 민감한 데이터 컬럼 암호화
- **접근 제어**: 사용자별/부서별 데이터 접근 권한 관리
- **감사 로그**: 모든 데이터 접근 및 수정 이력 기록

### 2. API 보안

- **인증**: Azure AD 기반 인증
- **권한 부여**: RBAC 기반 세분화된 권한 관리
- **네트워크**: VNet 및 Private Endpoint 활용

---

## 📈 확장성 고려사항

### 1. 데이터 증가 대응

- **샤딩**: 대용량 데이터 처리를 위한 수평 분할
- **아카이빙**: 오래된 데이터의 별도 저장소 이관
- **압축**: 벡터 데이터 압축 기술 활용

### 2. 성능 모니터링

- **쿼리 성능**: 슬로우 쿼리 로그 분석
- **인덱스 효율성**: 인덱스 사용률 모니터링
- **벡터 검색 성능**: 응답 시간 및 정확도 측정

이 스키마 명세서는 WKMS 시스템의 데이터 구조를 완전히 이해하고 운영하기 위한 핵심 문서입니다.
