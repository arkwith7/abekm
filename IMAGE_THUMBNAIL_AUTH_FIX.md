## 이미지 썸네일 인증 문제 및 해결 내역

### 1. 증상

- 검색 결과 썸네일 로딩 시 401/403 오류 발생
- 백엔드 로그에 `[IMAGE_CHUNK] 이미지 조회 실패 - error='PermissionService' object has no attribute 'check_container_access'`
- 프론트엔드 콘솔에 `이미지 로드 실패: Error: HTTP 401`

### 2. 원인

1. **프론트엔드**: `<img>` 태그로 직접 API를 호출하면서 Authorization 헤더가 포함되지 않아 인증 실패
2. **백엔드**: `PermissionService`에 `check_container_access` 메서드가 없어 AttributeError 발생

### 3. 조치 사항

#### 3.1 백엔드

- `PermissionService`에 `check_container_access()` 메서드 추가하여 컨테이너 권한 확인 가능하도록 수정
- 이미지 청크 조회 API 진입 로그 추가로 디버깅 용이

#### 3.2 프론트엔드

- 토큰 추출 유틸(`resolveAuthToken`) 추가: `ABEKM_token`, `access_token`, `token`을 LocalStorage/SessionStorage/쿠키에서 탐색
- 이미지 로딩 방식을 `fetch + Blob URL`로 변경하여 Authorization 헤더를 수동으로 추가
- fetch AbortController 및 Blob URL 해제 로직 추가
- 토큰 미존재 시에도 부드러운 실패 처리를 위해 에러 상태 초기화 로직 개선

### 4. 후속 작업 / 확인 사항

1. 프론트엔드 Dev 서버 재시작 또는 새로고침 (npm start)
2. 검색 페이지에서 "사진" 등 이미지가 있는 문서 검색 후 썸네일 표시 확인
3. 백엔드 로그에서 `[IMAGE_CHUNK] 이미지 반환 성공` 확인
4. 필요 시 이미지 캐싱 전략/사이즈 최적화 추가 검토

### 5. 관련 파일

- `backend/app/services/auth/permission_service.py`
- `backend/app/api/v1/documents.py`
- `frontend/src/pages/user/search/components/ResultList.tsx`

### 6. 참고 로그 예시

```
INFO app.api.v1.documents [IMAGE_CHUNK] ========== 엔드포인트 진입 ========== chunk_id=305
INFO app.api.v1.documents [IMAGE_CHUNK] 청크 이미지 조회 시작 - chunk_id=305, user=77107791
INFO app.api.v1.documents [IMAGE_CHUNK] 권한 확인 완료 - user=77107791, container_id=WJ_MS_SERVICE
INFO app.api.v1.documents [IMAGE_CHUNK] 이미지 반환 성공 - chunk_id=305, size=123456 bytes
```