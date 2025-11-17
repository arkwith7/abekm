# 권한 관리 (Permission Management)

## 📁 디렉토리 구조

```
permission-management/
├── index.tsx                      # 메인 컨테이너 컴포넌트
└── components/
    ├── index.ts                   # 컴포넌트 export
    ├── AddPermissionModal.tsx     # 사용자 권한 추가 모달
    ├── PermissionFilters.tsx      # 필터 (검색, 부서, 컨테이너)
    ├── PermissionInfoPanel.tsx    # 권한 설명 패널
    ├── PermissionStats.tsx        # 통계 카드
    └── PermissionTable.tsx        # 권한 목록 테이블
```

## 🎯 주요 기능

### 1. 사용자 권한 현황 관리
- ✅ 시스템 관리자 제외 필터링
- ✅ 지식컨테이너, 부서, 사용자, 권한, 작업 순서로 표시
- ✅ 관리 범위 필터링 (MS서비스팀 및 하위)
- ✅ 검색 및 필터 기능
- ✅ 인라인 권한 수정

### 2. 사용자 검색 및 권한 추가
- ✅ 지식컨테이너 선택
- ✅ 사용자 검색 (이름, 사번, 부서)
- ✅ 권한 레벨 선택 (읽기/쓰기/관리자)
- ✅ 선택 정보 미리보기
- ✅ 실시간 사용자 검색 API 연동

### 3. 권한 요청 관리
- 내 권한 요청 조회
- 새 권한 요청 생성

## 🔧 컴포넌트 설명

### PermissionManagement (index.tsx)
메인 컨테이너 컴포넌트로 상태 관리 및 API 호출을 담당합니다.

**주요 상태:**
- `userPermissions`: 사용자 권한 목록
- `teamMembers`: 팀원 목록
- `containers`: 지식컨테이너 목록
- `allowedContainerIds`: 관리 범위 컨테이너 ID 목록

**주요 기능:**
- 데이터 로딩 및 새로고침
- 권한 업데이트
- 권한 추가
- 필터링 로직

### AddPermissionModal
사용자 검색 및 권한 추가 기능을 제공하는 모달입니다.

**기능:**
1. 지식컨테이너 선택
2. 사용자 검색 (실시간 API 호출)
3. 검색 결과 목록 표시
4. 사용자 선택
5. 권한 레벨 선택
6. 권한 추가 실행

**Props:**
```typescript
interface AddPermissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  containers: Array<{ id: string; name: string }>;
  onAddPermission: (userId: string, containerId: string, permission: string) => Promise<void>;
}
```

### PermissionTable
권한 목록을 테이블 형태로 표시하고 편집 기능을 제공합니다.

**특징:**
- 컬럼 순서: 지식컨테이너 → 부서 → 사용자 → 권한 → 작업
- 인라인 편집 모드
- 권한 레벨 색상 구분
- 시스템 관리자 자동 제외

### PermissionFilters
검색 및 필터 UI를 제공합니다.

**필터 옵션:**
- 사용자 검색 (이름/사번)
- 지식컨테이너 선택
- 부서 선택

### PermissionStats
권한 관리 통계를 카드 형태로 표시합니다.

**통계 항목:**
- 팀원 수
- 관리 컨테이너 수
- 설정된 권한 수

### PermissionInfoPanel
권한 레벨에 대한 설명을 표시합니다.

**권한 설명:**
- 읽기: 문서 조회, 검색, 다운로드
- 읽기/쓰기: 읽기 + 문서 업로드, 수정
- 관리자: 모든 권한 + 지식컨테이너 관리

## 🔌 API 연동

### getUserPermissions()
모든 사용자 권한 목록을 조회합니다.
```typescript
GET /api/v1/permissions/all-user-permissions
```

### searchUsersForPermissions(query)
사용자를 검색합니다.
```typescript
GET /api/v1/users/search?q={query}
```

### updateUserPermissions(userId, containerId, permission)
사용자 권한을 추가 또는 수정합니다.
```typescript
// TODO: 실제 API 엔드포인트 구현 필요
POST /api/v1/permissions/grant
```

## 📝 사용 예시

```tsx
import PermissionManagement from './permission-management';

function App() {
  return <PermissionManagement />;
}
```

## 🚀 향후 개선사항

- [ ] 권한 삭제 기능
- [ ] 일괄 권한 부여 기능
- [ ] 권한 만료일 설정
- [ ] 권한 변경 이력 조회
- [ ] 엑셀 다운로드 기능
- [ ] 권한 템플릿 기능

## 🔒 보안 고려사항

1. **시스템 관리자 제외**: `ADMIN001`, `admin`, `SYSTEM` 등의 시스템 계정은 목록에서 자동 제외
2. **관리 범위 제한**: 지식관리자는 자신의 관리 범위 내 권한만 조회/수정 가능
3. **백엔드 검증**: 모든 권한 변경은 백엔드에서 재검증 필요

## 📚 관련 파일

- **타입 정의**: `/src/types/manager.types.ts`
- **API 서비스**: `/src/services/managerService.ts`
- **라우팅**: `/src/App.tsx`, `/src/layouts/ManagerLayout.tsx`
- **하위 컴포넌트**: `/src/components/manager/`
