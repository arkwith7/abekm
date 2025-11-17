# ABKMS(AI-Based Knowledge Management System) 시스템 정적 설계서

## 1. 시스템 개요

### 1.1 프로젝트 개요

이 문서는 ABKMS(AI-Based Knowledge Management System) 시스템에 대한 주요 설명으로 이 프로젝트의 전체 시스템 구조와 데이터베이스 설계를 정리한 시스템 설계서입니다. ABKMS는 Azure/AWS 클라우드 서비스를 기반으로 한 시스템으로, RAG(Retrieval-Augmented Generation) 기술을 활용하여 문서 등록, 검색, 채팅 기능을 제공합니다.

### 1.2 시스템 아키텍처

#### 1.2.1 인프라 구조 (Azure 기반)

```
┌─────────────────────────────────────────────────────┐
│                   Frontend                          │
│  ┌─────────────┐  ┌─────────────┐                  │
│  │ Streamlit   │  │ Web Portal  │                  │
│  │    App      │  │             │                  │
│  └─────────────┘  └─────────────┘                  │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────────┐
│              Azure Functions (API Layer)            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │Chat API │ │Search   │ │Preproc  │ │SAP/SP   │   │
│  │         │ │API      │ │APIs     │ │APIs     │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────┼───────────────────────────────────┐
│                 │      Core Services                 │
│  ┌─────────────┼─────────────┐                     │
│  │  Azure OpenAI Services   │                     │
│  │  ├─ GPT-4o (답변생성)    │                     │
│  │  ├─ GPT-4o-mini (요약)   │                     │
│  │  └─ text-embedding-ada-002│                     │
│  └─────────────┼─────────────┘                     │
│  ┌─────────────┼─────────────┐                     │
│  │  Azure AI Search         │                     │
│  │  ├─ file-index           │                     │
│  │  ├─ search-index         │                     │
│  │  ├─ chat-history-index   │                     │
│  │  └─ preprocessing-result │                     │
│  └─────────────┼─────────────┘                     │
│  ┌─────────────┼─────────────┐                     │
│  │  Azure Document Intel   │                     │
│  │  (OCR & 문서 분석)       │                     │
│  └─────────────┼─────────────┘                     │
└─────────────────┼───────────────────────────────────┘
                  │
┌─────────────────┼───────────────────────────────────┐
│                 │      Data Layer                   │
│  ┌─────────────┼─────────────┐                     │
│  │  Azure MySQL Database   │                     │
│  │  (메타데이터 & 파일정보) │                     │
│  └─────────────┼─────────────┘                     │
│  ┌─────────────┼─────────────┐                     │
│  │  Azure Blob Storage     │                     │
│  │  ├─ Raw Files          │                     │
│  │  ├─ Preprocessed Data  │                     │
│  │  └─ Logs               │                     │
│  └─────────────┼─────────────┘                     │
│  ┌─────────────┼─────────────┐                     │
│  │  External Systems      │                     │
│  │  ├─ SAP RFC (인사/조직) │                     │
│  │  └─ SharePoint         │                     │
│  └─────────────┘─────────────┘                     │
└─────────────────────────────────────────────────────┘
```

#### 1.2.2 RAG 아키텍처 상세

##### 문서 처리 파이프라인

```
[문서 업로드] → [Azure Blob Storage] → [Queue Trigger]
     ↓
[Azure Document Intelligence] → [텍스트 추출 & OCR]
     ↓
[청크 분할] → [Azure OpenAI Embedding] → [Azure AI Search 인덱싱]
     ↓                                        ↓
[MySQL 메타데이터 저장]              [검색 인덱스 & 파일 메타데이터 인덱스]
```

##### 질의응답 프로세스

```
[사용자 질문] → [질문 전처리 & 키워드 추출] → [의도 분류]
     ↓
[검색 or Q&A 분기]
     ↓
[하이브리드 검색] ← → [RAG 검색]
     ↓                    ↓
[문서 검색 결과]    [관련 문서 조회]
     ↓                    ↓
[검색 결과 반환]    [컨텍스트 구성] → [Azure OpenAI GPT-4o]
                         ↓
                    [답변 생성] → [후처리 & 응답]
```

- **Frontend**: Streamlit 기반 웹 애플리케이션 (`app.py`)
- **Backend**: Azure Functions 기반 서버리스 API (`functions/`)
- **데이터베이스**: Azure MySQL, CosmosDB, Azure AI Search
- **스토리지**: Azure Blob Storage
- **배포**: Azure DevOps Pipeline (`azure-pipelines.yml`)
- **컨테이너화**: Docker (`Dockerfile`)

### 1.3 주요 기능

1. **문서 관리**: 업로드, 전처리, 인덱싱
2. **검색 기능**: 하이브리드 검색 (키워드 + 벡터)
3. **채팅 봇**: RAG 기반 질의응답
4. **SAP 연동**: RFC 통신을 통한 조직/인사 정보 연동
5. **SharePoint 연동**: 문서 배치 처리

### 1.4 핵심 컴포넌트 분석

#### 1.4.1 Chat API (`chat_api.py`)

- **기능**: RAG 기반 질의응답
- **프로세스**:
  1. **Refinement**: 질문 분석 및 키워드 추출
  2. **RAG**: 관련 문서 검색
  3. **Answer Generation**: GPT-4o로 답변 생성
  4. **Chat History**: 대화 이력 관리

#### 1.4.2 AI Search (`aisearch.py`)

- **인덱스 구조**:
  - `file-index`: 파일 메타데이터
  - `search-index`: 문서 내용 (벡터 + 텍스트)
  - `chat-history-index`: 대화 이력
- **검색 방식**: 하이브리드 (키워드 + 벡터)

#### 1.4.3 문서 전처리 시스템

- **Blob Trigger**: 자동 문서 처리
- **Queue Trigger**: 배치 처리
- **Timer Trigger**: 스케줄 처리 (5분 간격)

#### 1.4.4 외부 시스템 연동

- **SAP RFC**: 인사/조직 정보 연동
- **SharePoint**: 문서 배치 업로드
- **Azure Document Intelligence**: OCR 및 문서 분석

### 1.5 데이터 플로우

#### 1.5.1 검색 시나리오

1. **사용자 질문** → **키워드 추출** → **의도 분류**
2. **Azure AI Search** → **하이브리드 검색**
3. **문서 유사도 스코어링** → **결과 반환**

#### 1.5.2 Q&A 시나리오

1. **사용자 질문** → **임베딩 생성**
2. **벡터 검색** → **관련 문서 조회**
3. **컨텍스트 구성** → **GPT-4o 답변 생성**
4. **채팅 이력 저장** → **응답 반환**

### 1.6 주요 특징

#### 1.6.1 엔터프라이즈 기능

- **멀티 테넌트**: 부서별/프로젝트별 격리
- **권한 관리**: 사용자별 문서 접근 제어
- **감사 로그**: 모든 활동 추적

#### 1.6.2 고급 검색 기능

- **의미적 검색**: 벡터 임베딩 기반
- **키워드 검색**: 전통적 텍스트 매칭
- **하이브리드 검색**: 두 방식 결합
- **패싯 검색**: 카테고리별 필터링

#### 1.6.3 AI 기능

- **질의 정제**: 사용자 질문 개선
- **의도 분류**: Search/Q&A/Summary 구분
- **다단계 RAG**: 단계별 검색 및 답변 생성

#### 1.6.4 스케일링 & 성능

- **서버리스 아키텍처**: Azure Functions
- **비동기 처리**: Queue 기반 처리
- **캐싱**: Redis를 통한 응답 캐싱

---

## 2. Azure Functions API 목록

### 2.1 Chat API

| Function Name | Route | Method | 설명            |
| ------------- | ----- | ------ | ------------- |
| Chat          | /Chat | POST   | RAG 기반 채팅 API |

### 2.2 Preprocessing APIs

| Function Name              | Route              | Method | 설명                    |
| -------------------------- | ------------------ | ------ | --------------------- |
| preprocessing_api          | /preprocessing_api | POST   | 문서 전처리 요청 API         |
| preprocessing_queuetrigger | Queue Trigger      | -      | 큐 기반 문서 전처리           |
| preprocessing_blob         | Blob Trigger       | -      | Blob 업로드 시 자동 전처리     |
| preprocessing_timer        | Timer Trigger      | -      | 스케줄 기반 배치 전처리 (5분 간격) |

### 2.3 SAP Integration APIs

| Function Name     | Route              | Method | 설명          |
| ----------------- | ------------------ | ------ | ----------- |
| sap-rfc-pers-info | /sap-rfc-pers-info | POST   | SAP 인사정보 조회 |
| sap-rfc-org-info  | /sap-rfc-org-info  | POST   | SAP 조직정보 조회 |

### 2.4 SharePoint APIs

| Function Name     | Route | Method | 설명                |
| ----------------- | ----- | ------ | ----------------- |
| sharepoint_batch  | -     | -      | SharePoint 배치 처리  |
| sharepoint_upload | -     | -      | SharePoint 업로드 처리 |

### 2.5 Search API

| Function Name | Route   | Method | 설명        |
| ------------- | ------- | ------ | --------- |
| search        | /search | POST   | 문서 검색 API |

---

## 3. 주요 클래스 및 엔티티

### 3.1 데이터베이스 연동 클래스

| 클래스명         | 파일          | 설명                    | 주요 메서드                                             |
| ------------ | ----------- | --------------------- | -------------------------------------------------- |
| AzureMySQL   | database.py | MySQL 데이터베이스 연동       | select_all_file_info(), select_file_info_bss_sno() |
| CosmosDB     | database.py | CosmosDB 문서 데이터베이스 연동 | get_item(), upload_item()                          |
| AzureStorage | database.py | Blob Storage 파일 관리    | upload_file(), download_file(), get_sas_url()      |
| SharePoint   | database.py | SharePoint 연동         | get_access_token(), get_file_item_id()             |

### 3.2 AI/ML 관련 클래스

| 클래스명      | 파일          | 설명                          | 주요 메서드                                               |
| --------- | ----------- | --------------------------- | ---------------------------------------------------- |
| AOAI      | model.py    | Azure OpenAI 연동             | generate_embeddings(), generate_answer()             |
| AzureDI   | model.py    | Azure Document Intelligence | analyze_document()                                   |
| AISearch  | aisearch.py | Azure AI Search 연동          | search(), hybrid_search(), vector_search()           |
| WJChatbot | chatbot.py  | RAG 기반 채팅봇 엔진               | step1_refinement(), step2_rag(), make_chat_history() |

#### 3.2.1 WJChatbot 클래스 상세

**주요 메서드**:
- `step1_refinement()`: 질문 분석, 키워드 추출, 의도 분류
- `step1_1_refinement()`: 채팅 이력 기반 질문 개선
- `step2_rag()`: 관련 문서 검색 및 컨텍스트 구성
- `make_chat_history_output()`: 채팅 이력 응답 생성

**RAG 프로세스**:
1. **Refinement**: 사용자 질문을 분석하여 키워드 추출 및 의도 분류
2. **Document Search**: 의도에 따라 적절한 검색 전략 선택
3. **Answer Generation**: 검색된 문서를 바탕으로 답변 생성

### 3.3 비즈니스 로직 클래스

| 클래스명          | 파일               | 설명        | 주요 메서드                          |
| ------------- | ---------------- | --------- | ------------------------------- |
| WJChatbot     | chatbot.py       | 채팅봇 핵심 로직 | step1_refinement(), step2_rag() |
| Preprocessing | preprocessing.py | 문서 전처리    | document_intelligence()         |

### 3.4 유틸리티 클래스

| 클래스명           | 파일     | 설명       | 주요 메서드   |
| -------------- | ------ | -------- | -------- |
| ListLogHandler | log.py | 로그 핸들러   | emit()   |
| KSTFormatter   | log.py | 한국시간 포맷터 | format() |

---

## 3. 테이블 정의(실제 구현)

### 3.1 tb_file_bss_info (파일 기본 정보)

| 컬럼                 | 타입           | 제약                                                    | 설명           |
| ------------------ | ------------ | ----------------------------------------------------- | ------------ |
| FILE_BSS_INFO_SNO  | INTEGER      | PK, AUTO_INCREMENT                                    | 파일 기본 정보 식별자 |
| DRCY_SNO           | INTEGER      | NOT NULL                                              | 디렉토리 식별자     |
| FILE_DTL_INFO_SNO  | INTEGER      | FK                                                    | 파일 상세 정보 식별자 |
| FILE_LGC_NM        | VARCHAR(255) | NOT NULL                                              | 논리 파일 이름     |
| FILE_PSL_NM        | VARCHAR(255) | NOT NULL                                              | 물리 파일 이름     |
| FILE_EXTSN         | VARCHAR(10)  |                                                       | 파일 확장자       |
| PATH               | VARCHAR(500) |                                                       | 파일 경로        |
| DEL_YN             | CHAR(1)      | DEFAULT 'N'                                           | 삭제 여부 (Y/N)  |
| CREATED_BY         | VARCHAR(20)  |                                                       | 생성자 ID       |
| CREATED_DATE       | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP                             | 생성 일시        |
| LAST_MODIFIED_BY   | VARCHAR(20)  |                                                       | 최종 수정자 ID    |
| LAST_MODIFIED_DATE | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 최종 수정 일시     |

### 3.2 tb_file_dtl_info (파일 상세 정보)

| 컬럼                 | 타입           | 제약                                                    | 설명           |
| ------------------ | ------------ | ----------------------------------------------------- | ------------ |
| FILE_DTL_INFO_SNO  | INTEGER      | PK, AUTO_INCREMENT                                    | 파일 상세 정보 식별자 |
| SJ                 | VARCHAR(500) |                                                       | 파일 제목        |
| CN                 | TEXT         |                                                       | 파일 내용        |
| KW                 | JSON         |                                                       | 키워드 정보       |
| CTG_LVL1           | INTEGER      |                                                       | 1차 카테고리 ID   |
| CTG_LVL2           | INTEGER      |                                                       | 2차 카테고리 ID   |
| CREATED_BY         | VARCHAR(20)  |                                                       | 생성자 ID       |
| CREATED_DATE       | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP                             | 생성 일시        |
| LAST_MODIFIED_BY   | VARCHAR(20)  |                                                       | 최종 수정자 ID    |
| LAST_MODIFIED_DATE | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 최종 수정 일시     |

### 3.3 tb_cmns_cd_grp_item (공통 코드 그룹 아이템)

| 컬럼           | 타입           | 제약                        | 설명               |
| ------------ | ------------ | ------------------------- | ---------------- |
| ITEM_ID      | INTEGER      | PK, AUTO_INCREMENT        | 아이템 식별자          |
| ITEM_NM      | VARCHAR(255) | NOT NULL                  | 아이템 이름           |
| REF_ITEM_ID  | INTEGER      | FK                        | 참조 아이템 ID (계층구조) |
| ITEM_ORDER   | INTEGER      |                           | 아이템 순서           |
| USE_YN       | CHAR(1)      | DEFAULT 'Y'               | 사용 여부 (Y/N)      |
| CREATED_BY   | VARCHAR(20)  |                           | 생성자 ID           |
| CREATED_DATE | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP | 생성 일시            |

### 3.4 tb_sap_hr_info (SAP 인사 정보)

| 컬럼           | 타입           | 제약                                                    | 설명        |
| ------------ | ------------ | ----------------------------------------------------- | --------- |
| USER_ID      | VARCHAR(20)  | PK                                                    | 사용자 ID    |
| USER_FNM     | VARCHAR(100) | NOT NULL                                              | 사용자 전체 이름 |
| DEPT_NM      | VARCHAR(100) |                                                       | 부서명       |
| POSITION_NM  | VARCHAR(50)  |                                                       | 직급명       |
| EMAIL        | VARCHAR(100) |                                                       | 이메일 주소    |
| PHONE        | VARCHAR(20)  |                                                       | 전화번호      |
| CREATED_DATE | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP                             | 생성 일시     |
| UPDATED_DATE | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 수정 일시     |

### 3.5 CosmosDB Container (문서 벡터 데이터)

| 필드                 | 타입     | 제약       | 설명               |
| ------------------ | ------ | -------- | ---------------- |
| id                 | STRING | PK       | 문서 고유 식별자        |
| file_name          | STRING | NOT NULL | 파일 이름            |
| chunk_name         | STRING |          | 청크 이름            |
| main_text          | STRING |          | 주요 텍스트 내용        |
| main_text_vector   | ARRAY  |          | 텍스트 벡터 (임베딩)     |
| file_logic_name    | STRING |          | 논리 파일 이름         |
| file_physical_name | STRING |          | 물리 파일 이름         |
| file_path          | STRING |          | 파일 경로            |
| sharepoint_item_id | STRING |          | SharePoint 항목 ID |
| file_view_link     | STRING |          | 파일 보기 링크         |
| graph_api_id       | STRING |          | Graph API ID     |

### 3.6 Azure AI Search Index (검색 인덱스)

| 필드               | 타입                     | 제약                     | 설명           |
| ---------------- | ---------------------- | ---------------------- | ------------ |
| id               | Edm.String             | KEY                    | 문서 고유 식별자    |
| file_lgc_nm      | Edm.String             | SEARCHABLE, FILTERABLE | 논리 파일 이름     |
| file_psl_nm      | Edm.String             | SEARCHABLE, FILTERABLE | 물리 파일 이름     |
| title            | Edm.String             | SEARCHABLE             | 문서 제목        |
| main_text        | Edm.String             | SEARCHABLE             | 주요 텍스트 내용    |
| chunk_text       | Edm.String             | SEARCHABLE             | 청크 텍스트 내용    |
| main_text_vector | Collection(Edm.Single) | VECTOR_SEARCH          | 텍스트 벡터 (임베딩) |
| del_yn           | Edm.Boolean            | FILTERABLE             | 삭제 여부        |
| ctg_lvl1_nm      | Edm.String             | FILTERABLE             | 1차 카테고리 이름   |
| ctg_lvl2_nm      | Edm.String             | FILTERABLE             | 2차 카테고리 이름   |

---

## 4. 시스템 설정 및 환경

### 4.1 Azure Functions 설정 (host.json)

```json
{
  "version": "2.0",
  "functionTimeout": "00:30:00",
  "extensions": {
    "blobs": {
      "maxDegreeOfParallelism": 4,
      "poisonBlobThreshold": 1
    },
    "queues": {
      "maxPollingInterval": "00:00:02",
      "visibilityTimeout": "00:00:10",
      "batchSize": 16,
      "maxDequeueCount": 5
    }
  }
}
```

### 4.2 환경별 설정

- **개발환경**: `config.yaml` (wkmsdev)
- **운영환경**: `config_prod.yaml` (wkmsprd)
- **로컬환경**: `config_local.yaml`

### 4.3 주요 설정 항목

| 항목              | 설명                        |
| --------------- | ------------------------- |
| Azure OpenAI    | 임베딩 및 답변 생성 모델 설정         |
| Azure AI Search | 검색 엔드포인트 및 인덱스 설정         |
| Azure Storage   | Blob Storage 계정 및 컨테이너 설정 |
| MySQL           | 데이터베이스 연결 정보              |
| SAP RFC         | SAP 시스템 연결 정보             |

### 4.4 배포 환경

- **Dev**: wkms-eastasia-dev-api
- **Prod**: wkms-eastasia-prd-api
- **Pipeline**: Azure DevOps (azure-pipelines.yml)

---

## 5. 데이터 흐름 및 처리 프로세스

### 5.1 문서 등록 프로세스

1. **업로드**: Azure Blob Storage에 파일 업로드
2. **전처리 트리거**: Blob Trigger 또는 API 호출
3. **문서 분석**: Azure Document Intelligence로 텍스트 추출
4. **임베딩 생성**: Azure OpenAI로 벡터 생성
5. **인덱싱**: Azure AI Search에 저장
6. **메타데이터 저장**: MySQL에 파일 정보 저장

### 5.2 검색 프로세스

1. **쿼리 입력**: 사용자 질문 접수
2. **쿼리 정제**: 키워드 추출 및 의도 분석
3. **하이브리드 검색**: 키워드 + 벡터 검색
4. **문서 필터링**: 권한 및 상태 확인
5. **결과 반환**: 관련 문서 목록 제공

### 5.3 채팅 프로세스

1. **질의 분석**: 의도 및 엔티티 추출
2. **채팅 히스토리 확인**: 이전 대화 맥락 검토
3. **문서 검색**: RAG를 위한 관련 문서 검색
4. **답변 생성**: OpenAI로 최종 답변 생성
5. **채팅 히스토리 저장**: 대화 내용 저장

---

## 6. 보안 및 인증

### 6.1 Azure 서비스 인증

- **Azure Functions**: Managed Identity
- **Azure OpenAI**: API Key 기반 인증
- **Azure Storage**: Connection String
- **SAP RFC**: 사용자 ID/비밀번호

### 6.2 데이터 보안

- **파일 암호화**: Azure Storage 기본 암호화
- **네트워크 보안**: HTTPS 통신
- **접근 제어**: SAS Token을 통한 임시 접근

### 6.3 로깅 및 모니터링

- **Application Insights**: 성능 모니터링
- **Azure Storage**: 로그 파일 저장
- **Custom Logging**: 한국시간 기반 로그 포맷터

---

## 7. 성능 최적화

### 7.1 Azure Functions 최적화

- **타임아웃**: 30분으로 설정
- **동시 처리**: Blob 처리 시 최대 4개 병렬
- **큐 처리**: 배치 크기 16, 폴링 간격 2초

### 7.2 검색 성능

- **인덱스 설계**: 필터링 가능한 필드 최적화
- **벡터 검색**: 하이브리드 검색으로 정확도 향상
- **캐싱**: 자주 사용되는 검색 결과 캐시

### 7.3 스토리지 최적화

- **Blob Storage**: Hot/Cool tier 분리
- **문서 압축**: 대용량 파일 압축 저장
- **SAS Token**: 임시 접근으로 보안 강화

---

## 8. 연동 서비스 상세

### 8.1 Azure OpenAI 서비스

| 모델                     | 용도     | 설명             |
| ---------------------- | ------ | -------------- |
| text-embedding-3-small | 임베딩 생성 | 문서 벡터화 및 의미 검색 |
| gpt-4o                 | 답변 생성  | RAG 기반 질의응답    |
| gpt-4o-mini            | 이미지 분석 | 문서 내 이미지 전처리   |

### 8.2 Azure AI Search 인덱스

| 인덱스명                       | 용도       | 주요 필드                          |
| -------------------------- | -------- | ------------------------------ |
| file-index                 | 파일 메타데이터 | file_lgc_nm, file_psl_nm, path |
| search-index               | 문서 내용 검색 | chunk_text, main_text_vector   |
| chat-history-index         | 채팅 기록    | query, response, session_id    |
| preprocessing-result-index | 전처리 결과   | file_name, status, timestamp   |

### 8.3 Azure Storage 컨테이너

| 컨테이너명        | 용도       | 설명                     |
| ------------ | -------- | ---------------------- |
| upload       | 원본 파일 저장 | 사용자가 업로드한 원본 문서        |
| preprocessed | 전처리 결과   | DI 분석 결과 JSON, 추출된 텍스트 |
| logs         | 로그 저장    | 시스템 로그 및 오류 로그         |

### 8.4 SAP RFC 연동

| Function Module  | 용도      | 반환 데이터       |
| ---------------- | ------- | ------------ |
| SAP_HR_PERS_INFO | 인사정보 조회 | 사용자명, 부서, 직급 |
| SAP_HR_ORG_INFO  | 조직정보 조회 | 조직도, 부서 구조   |

---

## 9. 에러 처리 및 복구

### 9.1 에러 분류

| 에러 코드 | 설명         | 처리 방법         |
| ----- | ---------- | ------------- |
| E001  | PDF 변환 실패  | 원본 파일로 재처리    |
| E002  | 일반적인 처리 실패 | 로그 분석 후 수동 처리 |
| F_001 | 잘못된 JSON   | 요청 데이터 검증     |
| F_002 | 필수 파라미터 누락 | 파라미터 확인       |
| F_003 | 상태 코드 누락   | 상태 값 확인       |
| F_004 | 잘못된 상태 코드  | c/d만 허용       |

### 9.2 복구 메커니즘

- **재시도 로직**: tenacity 라이브러리 활용
- **데드레터 큐**: 실패한 메시지 별도 처리
- **수동 재처리**: 관리자 도구를 통한 재처리

### 9.3 모니터링 대상

- **Function 실행 시간**: 30분 타임아웃 모니터링
- **큐 메시지 수**: 대기 중인 작업량 확인
- **AI Search 인덱스 크기**: 저장 용량 모니터링
- **OpenAI 토큰 사용량**: 비용 관리

---

## 10. 확장성 및 유지보수

### 10.1 수평 확장

- **Function Apps**: Auto-scaling 지원
- **Azure AI Search**: 검색 단위 확장 가능
- **Blob Storage**: 무제한 확장
- **MySQL**: Read Replica 추가 가능

### 10.2 버전 관리

- **Git**: 소스 코드 버전 관리
- **Azure DevOps**: CI/CD 파이프라인
- **환경 분리**: dev/prod 환경 별도 관리

### 10.3 백업 전략

- **데이터베이스**: 자동 백업 (7일 보관)
- **Blob Storage**: Geo-redundant 복제
- **설정 파일**: Git을 통한 형상 관리

---

## 11. 시스템 종합 분석

### 11.1 ABKMS 프로젝트 개요

**ABKMS(AI-Based Knowledge Management System)**는 내부 문서 및 지식을 체계적으로 관리하고 AI 기반 검색/질의응답을 제공하는 엔터프라이즈급 시스템입니다. Azure/AWS 클라우드의 PaaS 서비스들을 최대한 활용하여 구축된 현대적인 RAG 기반 지식 관리 시스템으로, 특히 **엔터프라이즈 환경에서의 대용량 문서 처리와 정확한 질의응답**에 최적화되어 있습니다.

### 11.2 시스템 특징

#### 11.2.1 Azure 클라우드 네이티브 아키텍처

- **서버리스 컴퓨팅**: Azure Functions 기반으로 자동 스케일링과 비용 효율성 확보
- **관리형 서비스**: Azure OpenAI, AI Search, Document Intelligence 등을 활용한 운영 부담 최소화
- **고가용성**: 다중 AZ 배포와 자동 페일오버 지원

#### 11.2.2 고급 RAG 구현

- **다단계 검색**: 키워드 추출 → 의도 분류 → 문서 검색 → 답변 생성의 체계적 프로세스
- **하이브리드 검색**: 키워드 검색과 벡터 검색의 결합으로 정확도 향상
- **컨텍스트 인식**: 채팅 이력을 활용한 연속적 대화 처리

#### 11.2.3 엔터프라이즈 통합

- **SAP RFC 연동**: 기업 핵심 시스템과의 실시간 데이터 연동
- **SharePoint 통합**: 기존 문서 관리 시스템과의 원활한 연계
- **권한 관리**: 사용자별/부서별 문서 접근 제어

### 11.3 기술적 우수성

#### 11.3.1 성능 최적화

- **비동기 처리**: Queue 기반 문서 전처리로 사용자 대기 시간 최소화
- **캐싱 전략**: 검색 결과와 임베딩 캐싱으로 응답 속도 향상
- **배치 처리**: Timer Trigger를 통한 대용량 문서 일괄 처리

#### 11.3.2 확장성 및 안정성

- **Auto Scaling**: Function Apps의 자동 확장으로 부하 대응
- **오류 처리**: 포괄적인 예외 처리와 재시도 메커니즘
- **모니터링**: 실시간 로그 분석과 성능 지표 추적

### 11.4 비즈니스 가치

#### 11.4.1 업무 효율성 향상

- **즉시 검색**: 자연어 질문으로 관련 문서 즉시 검색
- **지능형 답변**: RAG 기반으로 정확하고 맥락적인 답변 제공
- **통합 인터페이스**: 여러 시스템의 정보를 하나의 인터페이스로 통합

#### 11.4.2 지식 관리 혁신

- **자동 분류**: AI 기반 문서 자동 분류 및 태깅
- **의미적 검색**: 키워드 중심에서 의미 중심 검색으로 패러다임 전환
- **학습 효과**: 사용 패턴 분석을 통한 지속적 성능 개선

### 11.5 향후 발전 방향

#### 11.5.1 기능 확장

- **멀티모달 AI**: 이미지, 동영상 등 다양한 형태의 콘텐츠 처리
- **협업 기능**: 실시간 공동 편집 및 코멘트 시스템
- **개인화**: 사용자 선호도 학습 및 맞춤형 추천

#### 11.5.2 기술 진화

- **최신 AI 모델**: GPT-4o 등 최신 언어 모델 적용
- **Edge Computing**: 로컬 처리를 통한 응답 속도 개선
- **Federated Learning**: 분산 학습을 통한 프라이버시 보호

---

## 12. 결론

이 WKMS 시스템은 Azure 클라우드 네이티브 아키텍처를 기반으로 하여 높은 확장성과 안정성을 제공합니다. RAG 기술을 활용한 지능형 검색과 채팅 기능으로 사용자 경험을 향상시키며, SAP 연동을 통해 기업 업무와의 통합성을 확보했습니다.

특히 **서버리스 아키텍처**, **하이브리드 검색**, **다단계 RAG 프로세스**를 통해 현대적인 AI 기반 지식 관리 시스템의 모범 사례를 제시하고 있으며, 엔터프라이즈 환경에서 요구되는 보안성, 확장성, 안정성을 모두 충족하는 솔루션입니다.

### 11.2 주요 성과

- **서버리스 아키텍처**: 비용 효율적인 운영
- **AI 기반 검색**: 높은 정확도의 문서 검색
- **자동화된 전처리**: 문서 등록 프로세스 자동화
- **기업 시스템 연동**: SAP, SharePoint 통합

### 11.3 향후 개선 방향

- **멀티 클라우드 지원**: AWS, GCP 환경 확장
- **실시간 협업**: WebSocket 기반 실시간 채팅
- **고급 분석**: 사용자 행동 분석 및 추천 시스템
- **모바일 지원**: 반응형 웹 또는 네이티브 앱