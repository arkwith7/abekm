# 채팅 세션 복원 오류 수정

## 🔴 발견된 문제

### 오류 로그
```
2025-11-07 14:05:06.310 | WARNING | app.api.v1.chat:get_chat_session:626 - 
참고자료 상세 정보 조회 실패: No module named 'app.models.document_models'
```

### 문제점
**Import 경로 오류**로 인해 세션 복원 시 참고자료 및 선택 문서 조회가 완전히 실패

## 📊 로그 분석 결과

### 1. 검색 기능 상태: ✅ 정상
```
- 쿼리 처리: "Roadmap" → keyword_search 의도 분류 (confidence: 0.90)
- 언어 감지: en (영어)
- 키워드 추출: ['roadmap']
- 벡터 검색: 23개 결과 (임계값: 0.4, 점수 범위: 0.406 ~ 0.603)
- 키워드 검색: 4개 결과 (문서 1개 + IMAGE chunk 3개)
- 전문검색: 1개 결과
- 최종 결과: 24개 → 품질 필터링 → 24개 → 파일 그룹화 → 1개 파일
```

**검색 품질**:
- ✅ 하이브리드 검색 정상 작동 (벡터 + 키워드 + 전문검색)
- ✅ 이미지 청크 캡션 검색 정상
- ✅ 컨테이너 권한 검증 정상 (6개 컨테이너 접근 가능)
- ✅ 결과 포맷팅 및 메타데이터 생성 정상

### 2. 세션 복원 기능 상태: ❌ 실패
```
GET /api/v1/chat/sessions/chat_1762491307850_6b0vzt66l HTTP/1.1 200 OK
WARNING - 참고자료 상세 정보 조회 실패: No module named 'app.models.document_models'
```

**영향 범위**:
- ❌ 참고자료 목록 (`referenced_documents`) 반환 불가
- ❌ 선택된 문서 목록 (`selected_documents`) 반환 불가
- ⚠️ 메시지 목록은 반환되지만 문서 컨텍스트 없음
- ⚠️ 프론트엔드에서 문서 복원 이벤트 발생하지 않음

### 3. 발생 빈도
```
14:05:06 - chat_1762491307850_6b0vzt66l
14:05:16 - chat_1762489901728_vo422kwt4
14:05:27 - chat_1762484043000_hpkvfjsl4
14:05:37 - chat_1762489901728_vo422kwt4
```
→ **모든 세션 로드 요청에서 100% 실패**

## 🔧 원인 분석

### 잘못된 Import 경로
```python
# ❌ 잘못된 경로 (존재하지 않는 모듈)
from app.models.document_models import TbFileBssInfo

# ✅ 올바른 경로
from app.models.document.file_models import TbFileBssInfo
```

### 위치
- **파일**: `/home/admin/wkms-aws/backend/app/api/v1/chat.py`
- **라인**: 598
- **함수**: `get_chat_session()`
- **블록**: 참고자료 상세 정보 조회 섹션

### 실제 모듈 구조
```
backend/app/models/
├── chat/          # 채팅 관련 모델
├── document/      # 문서 관련 모델
│   └── file_models.py  ← TbFileBssInfo 정의 위치
├── knowledge/     # 지식 컨테이너 모델
└── user/          # 사용자 모델
```

## ✅ 수정 내용

### Before (오류 코드)
```python
# 참고자료 상세 정보 조회 (DB에서)
referenced_docs_detail = []
if all_referenced_doc_ids:
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.database import get_db
        from app.models.document_models import TbFileBssInfo  # ❌ 잘못된 경로
        
        # DB 세션 생성
        db_gen = get_db()
        db: AsyncSession = await db_gen.__anext__()
        
        try:
            # 참고자료 문서 정보 조회
            query = select(TbFileBssInfo).where(
                TbFileBssInfo.file_bss_info_sno.in_(list(all_referenced_doc_ids))
            )
            # ...
```

### After (수정 코드)
```python
# 참고자료 상세 정보 조회 (DB에서)
referenced_docs_detail = []
if all_referenced_doc_ids:
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.database import get_db
        from app.models.document.file_models import TbFileBssInfo  # ✅ 올바른 경로
        
        # DB 세션 생성
        db_gen = get_db()
        db: AsyncSession = await db_gen.__anext__()
        
        try:
            # 참고자료 문서 정보 조회
            query = select(TbFileBssInfo).where(
                TbFileBssInfo.file_bss_info_sno.in_(list(all_referenced_doc_ids))
            )
            # ...
```

### 변경 사항
```diff
- from app.models.document_models import TbFileBssInfo
+ from app.models.document.file_models import TbFileBssInfo
```

## 🎯 예상 효과

### 수정 전
```json
{
  "success": true,
  "session_id": "chat_1762491307850_6b0vzt66l",
  "messages": [...],
  "referenced_documents": [],      // ❌ 빈 배열
  "selected_documents": []         // ❌ 빈 배열
}
```

### 수정 후
```json
{
  "success": true,
  "session_id": "chat_1762491307850_6b0vzt66l",
  "messages": [...],
  "referenced_documents": [        // ✅ 복원됨
    {
      "fileId": "5",
      "fileName": "Roadmapping integrates business and technology.pdf",
      "fileType": "pdf",
      "containerName": "USER_77107791_0627BBC2",
      "uploadDate": "2025-11-07T10:30:00"
    }
  ],
  "selected_documents": [          // ✅ 복원됨
    {
      "id": "5",
      "fileName": "Roadmapping integrates business and technology.pdf",
      "fileType": "pdf"
    }
  ]
}
```

## 🧪 테스트 시나리오

### 1. 기본 세션 복원 테스트
```bash
# 1. 문서 선택 후 새 대화 생성
curl -X POST http://localhost:8000/api/v1/chat/generate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "message": "Roadmap에 대해 설명해줘",
    "selected_documents": [{"id": "5", "fileName": "..."}],
    "mode": "text"
  }'

# 2. 세션 ID 확인 (예: chat_xxx)

# 3. 세션 복원
curl -X GET http://localhost:8000/api/v1/chat/sessions/chat_xxx \
  -H "Authorization: Bearer $TOKEN"

# 4. 응답 검증
# - referenced_documents 배열에 데이터 있는지 확인
# - selected_documents 배열에 데이터 있는지 확인
```

### 2. 프론트엔드 통합 테스트
```typescript
// 1. 대시보드에서 "최근 AI 대화" 클릭

// 2. 브라우저 콘솔 확인
// 예상 로그:
📦 세션 데이터 수신: { 
  success: true, 
  referencedDocumentsCount: 3,
  selectedDocumentsCount: 2 
}
📄 선택된 문서 복원: 2 개
📚 참고자료 복원: 3 개
📄 세션 복원: 선택된 문서 복원 2 개

// 3. UI 검증
// - 우측 사이드바 "선택된 문서" 패널에 2개 문서 표시
// - 각 AI 응답 메시지 하단에 참고자료 표시
```

### 3. 백엔드 로그 확인
```bash
# 수정 전 (오류 발생)
tail -f logs/app.log | grep "참고자료 상세 정보 조회"
# WARNING - 참고자료 상세 정보 조회 실패: No module named 'app.models.document_models'

# 수정 후 (정상 동작)
tail -f logs/app.log | grep "참고자료"
# INFO - 참고자료 3개 발견
# INFO - 참고자료 DB 조회 성공: 3개
```

## 📝 추가 로그 분석

### 검색 성능 지표
```
QueryPipeline 처리 시간:
- 1차: 1498.5ms
- 2차: 4136.9ms (권한 조회 포함)
- 3차: 1111.0ms

처리 단계별 시간:
- 언어 감지 및 키워드 추출: ~100ms
- 벡터 임베딩 생성: ~500ms (Azure OpenAI API 호출)
- 벡터 검색: ~300ms
- 키워드/전문검색: ~200ms
- 결과 포맷팅: ~100ms
```

### 권한 검증
```
사용자 77107791의 접근 가능한 컨테이너:
1. WJ_MS_SERVICE (MS서비스팀) - MEMBER_DEPT
2. WJ_CLOUD (클라우드사업본부) - MEMBER_DIVISION
3. USER_77107791_0627BBC2 (myMS서비스) - OWNER
4. WJ_INFRA_CONSULT (인프라컨설팅팀) - VIEWER
5. CON_MHLGV17I (AOAI프로젝트) - 상속 (VIEWER)
6. WJ_CLOUD_SERVICE (클라우드서비스팀) - 상속 (VIEWER)

권한 상속 체인:
WJ_CLOUD (MEMBER_DIVISION)
  └─ WJ_MS_SERVICE (상속: VIEWER)
       ├─ USER_77107791_0627BBC2 (OWNER - 직접)
       └─ CON_MHLGV17I (상속: VIEWER)
  └─ WJ_CLOUD_SERVICE (상속: VIEWER)
```

### 검색 결과 품질
```
문서 ID: 5
제목: (논문 2) Roadmapping integrates business and technology...
컨테이너: USER_77107791_0627BBC2 (myMS서비스)
매칭: hybrid (벡터 + 키워드)
점수: 1.0
청크: 20개 관련 섹션
모달리티: image (이미지 기반 청크)
- thumbnail: multimodal/5/objects/image_30_1.png
- full image: multimodal/5/objects/image_166_1.png
```

## 🎉 결과

### 수정 완료 사항
- ✅ Import 경로 수정: `app.models.document_models` → `app.models.document.file_models`
- ✅ 파일: `/home/admin/wkms-aws/backend/app/api/v1/chat.py`
- ✅ 라인: 598

### 복원되는 기능
- ✅ 참고자료 목록 조회 및 반환
- ✅ 선택된 문서 목록 조회 및 반환
- ✅ 프론트엔드 문서 복원 이벤트 발생
- ✅ 우측 사이드바 문서 패널 복원
- ✅ AI 응답 메시지 참고자료 표시

### 다음 단계
1. **서버 재시작** (hot reload로 자동 적용되지만 확인 권장)
2. **테스트 수행**:
   - 기존 세션 복원 테스트
   - 새 대화 생성 후 복원 테스트
   - 문서 선택/참고자료 표시 확인
3. **로그 모니터링**:
   - WARNING 메시지 사라졌는지 확인
   - 참고자료 조회 성공 로그 확인

---
**수정일시**: 2025-11-07 14:10
**심각도**: 🔴 Critical (핵심 기능 완전 실패)
**상태**: ✅ 수정 완료
**영향**: 세션 복원 시 문서 정보 누락 → 정상 복원
