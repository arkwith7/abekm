# 🎨 WKMS 역할별 UI/UX 분리 설계 및 최신 표준 통합

## 📋 1. 개요 및 목표

### 1.1 현재 상황
- 일반 사용자와 관리자가 동일한 인터페이스 사용
- 복잡한 관리 기능이 일반 사용자에게 노출
- 역할별 최적화된 워크플로우 부재

### 1.2 목표
- **역할별 특화된 UI/UX** 제공
- **직관적이고 효율적인** 사용자 경험
- **최신 반응형 웹 표준** 적용으로 모든 디바이스 지원

## 🎨 2. 프론트엔드 구조 재설계 방안

### 2.1 현재 구조 → 새로운 구조

#### 현재 구조의 문제점
```
frontend/
├── src/
│   ├── components/     # 모든 사용자가 공통 컴포넌트 사용
│   ├── pages/         # 역할 구분 없는 페이지 구조
│   ├── services/      # 통합된 API 서비스
│   └── utils/         # 공통 유틸리티
```

#### 새로운 역할별 구조
```
frontend/src/
├── App.tsx                         # 라우팅 및 인증
├── types/                          # TypeScript 타입 정의
│   ├── user.types.ts              # 일반 사용자 타입
│   ├── manager.types.ts           # 지식관리자 타입
│   └── admin.types.ts             # 시스템관리자 타입
├── layouts/                        # 레이아웃 컴포넌트
│   ├── UserLayout.tsx             # 일반 사용자 레이아웃
│   ├── ManagerLayout.tsx          # 지식관리자 레이아웃
│   └── AdminLayout.tsx            # 시스템관리자 레이아웃
├── pages/                          # 페이지 컴포넌트
│   ├── common/                    # 공통 페이지
│   │   ├── LoginPage.tsx
│   │   └── UnauthorizedPage.tsx
│   ├── user/                      # 일반 사용자 페이지
│   │   ├── Dashboard.tsx          # 사용자 대시보드
│   │   ├── SearchPage.tsx         # 지식 검색
│   │   ├── UploadPage.tsx         # 문서 업로드
│   │   ├── MyDocuments.tsx        # 내 문서
│   │   └── ChatPage.tsx           # AI 질의응답
│   ├── manager/                   # 지식관리자 페이지
│   │   ├── ManagerDashboard.tsx   # 관리 대시보드
│   │   ├── ContainerManagement.tsx # 컨테이너 관리
│   │   ├── PermissionApproval.tsx # 권한 승인
│   │   ├── QualityManagement.tsx  # 품질 관리
│   │   └── UserSupport.tsx        # 사용자 지원
│   └── admin/                     # 시스템관리자 페이지
│       ├── AdminDashboard.tsx     # 시스템 대시보드
│       ├── SystemMonitoring.tsx   # 시스템 모니터링
│       ├── UserManagement.tsx     # 사용자 관리
│       ├── SecurityPolicies.tsx   # 보안 정책
│       └── AuditLogs.tsx          # 감사 로그
├── components/                     # 재사용 컴포넌트
│   ├── common/                    # 공통 컴포넌트
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   ├── LoadingSpinner.tsx
│   │   └── Modal.tsx
│   ├── user/                      # 사용자 전용 컴포넌트
│   │   ├── SearchInterface.tsx
│   │   ├── DocumentCard.tsx
│   │   └── UploadForm.tsx
│   ├── manager/                   # 관리자 전용 컴포넌트
│   │   ├── ContainerTree.tsx
│   │   ├── PermissionTable.tsx
│   │   └── QualityMetrics.tsx
│   └── admin/                     # 시스템관리자 전용 컴포넌트
│       ├── SystemStats.tsx
│       ├── UserTable.tsx
│       └── AuditTable.tsx
├── services/                       # API 서비스
│   ├── authService.ts             # 인증 서비스
│   ├── userService.ts             # 사용자 기능 API
│   ├── managerService.ts          # 관리자 기능 API
│   └── adminService.ts            # 시스템관리자 API
├── hooks/                          # 커스텀 훅
│   ├── useAuth.ts                 # 인증 상태 관리
│   ├── usePermissions.ts          # 권한 확인
│   └── useRole.ts                 # 역할 기반 로직
└── utils/                          # 유틸리티 함수
    ├── permissions.ts             # 권한 체크 함수
    └── roleChecker.ts             # 역할 검증 유틸
```

### 2.2 역할별 화면 구성

#### 🏠 일반 사용자 (User)
- **대시보드**: 빠른 검색, 최근 문서, AI 추천
- **지식 검색**: 통합 검색 인터페이스
- **문서 업로드**: 간편한 업로드 프로세스  
- **내 문서**: 개인 문서 관리
- **AI 질의응답**: 실시간 채팅 인터페이스

#### 🏢 지식관리자 (Manager) 
- **관리 대시보드**: 관리 현황 + 일반 사용자 기능
- **컨테이너 관리**: 지식 체계 구성 및 관리
- **권한 승인**: 사용자 권한 요청 처리
- **품질 관리**: 문서 품질 검토 및 개선
- **사용자 지원**: 사용자 문의 및 도움 제공

#### 🔧 시스템관리자 (Admin)
- **시스템 대시보드**: 전체 시스템 상태 모니터링
- **사용자 관리**: 계정 생성, 권한 변경, 비활성화
- **보안 정책**: 시스템 보안 설정 및 정책 관리
- **감사 로그**: 시스템 활동 추적 및 분석
- **시스템 모니터링**: 성능, 리소스 사용량 모니터링

## 🛣️ 3. 역할별 라우팅 구조

### 3.1 라우팅 설계 원칙
- `/user/*` - 일반 사용자 전용
- `/manager/*` - 지식관리자 (사용자 기능 포함)
- `/admin/*` - 시스템관리자 (모든 기능 포함)

### 3.2 디바이스별 네비게이션 패턴

#### 📱 모바일 (320px ~ 767px)
```
┌─────────────────────────────────┐
│ [☰] WKMS              [👤]     │ ← 햄버거 메뉴 + 프로필
├─────────────────────────────────┤
│                                 │
│        메인 콘텐츠 영역          │ ← 전체 화면 활용
│                                 │
├─────────────────────────────────┤
│ [🏠] [🔍] [📤] [💬] [👤]       │ ← 하단 탭바 네비게이션
└─────────────────────────────────┘
```

#### 📟 태블릿 (768px ~ 1023px)
```
┌─────────────────────────────────────────────┐
│ WKMS    [대시보드] [검색] [업로드] [💬] [👤] │ ← 상단 탭 네비게이션
├─────────────────────────────────────────────┤
│ ┌─────────┐ ┌───────────────────────────────┐│
│ │         │ │                               ││
│ │ 사이드  │ │        메인 콘텐츠             ││ ← 사이드 패널 + 메인
│ │ 패널    │ │                               ││
│ │         │ │                               ││
│ └─────────┘ └───────────────────────────────┘│
└─────────────────────────────────────────────┘
```

#### 💻 데스크톱 (1024px+)
```
┌────────┬──────────────────────────────────────────────┐
│🏠 대시보드│ Home > 대시보드               [🔍] [🔔] [👤] │
│📊 분석    ├──────────────────────────────────────────────┤
│🔍 검색    │                                              │
│📤 업로드  │                                              │ ← 사이드바 +
│📁 문서    │            메인 콘텐츠 영역                   │   상단바 +
│💬 질의응답│                                              │   메인 영역
│⚙️ 설정    │                                              │
│          │                                              │
└────────┴──────────────────────────────────────────────┘
```

## 📱 멀티 디바이스 대응 역할별 화면 설계서

## 📱 4. 디바이스별 기본 정의

### 4.1 설계 목적
웅진 WKMS를 **PC, 태블릿, 스마트폰** 모든 디바이스에서 최적의 사용자 경험을 제공하는 **역할별 특화 인터페이스**로 구현하기 위한 핵심 화면 레이아웃을 정의합니다.

### 4.2 설계 원칙
- **Mobile First**: 모바일 우선 설계로 점진적 향상
- **Role-Based UX**: 역할별 맞춤형 사용자 경험
- **Responsive Layout**: 디바이스별 최적화된 레이아웃
- **Accessibility First**: 모든 사용자 접근 가능

### 4.3 디바이스별 Breakpoint
```
📱 모바일: 320px ~ 767px
📟 태블릿: 768px ~ 1023px  
💻 데스크톱: 1024px ~ 1440px
🖥️ 대형 모니터: 1441px 이상
```

### 4.4 역할별 기능 및 화면 정의

#### 4.4.1 일반 사용자 (User Role)
- **핵심 기능**: 지식 검색, 문서 업로드, AI 질의응답, 개인 문서 관리
- **접근 권한**: 본인 소속 조직 + 권한 부여된 지식 컨테이너
- **UI 철학**: **"찾기 쉽고, 올리기 쉽고, 물어보기 쉬운"** 직관적 인터페이스
- **주요 화면**: 검색 대시보드, 업로드 센터, AI 질의응답, 내 문서함

#### 4.4.2 지식관리자 (Knowledge Manager)
- **핵심 기능**: 컨테이너 관리, 권한 승인, 품질 관리, 사용자 지원 + 일반 사용자 모든 기능
- **접근 권한**: 담당 지식 컨테이너 + 해당 사용자 관리 + 일반 사용자 권한
- **UI 철학**: **"관리하기 쉽고, 승인하기 쉽고, 지원하기 쉬운"** 효율적 관리 인터페이스
- **주요 화면**: 관리 대시보드, 컨테이너 관리, 권한 승인, 품질 관리, 사용자 지원

#### 4.4.3 시스템관리자 (System Administrator)
- **핵심 기능**: 시스템 모니터링, 사용자 관리, 보안 정책, 감사 로그 + 모든 하위 권한
- **접근 권한**: 시스템 전체 + 모든 사용자 데이터 + 시스템 설정
- **UI 철학**: **"모니터링하기 쉽고, 관리하기 쉽고, 제어하기 쉬운"** 시스템 중심 인터페이스
- **주요 화면**: 시스템 대시보드, 사용자 관리, 보안 정책, 감사 로그, 시스템 모니터링

## 📱 3. 디바이스별 레이아웃 시스템

### 3.1 네비게이션 패턴

#### 📱 모바일 (320px ~ 767px)
```
┌─────────────────────────────────┐
│ [☰] WKMS Logo        [👤]       │ ← 상단 헤더 (고정)
├─────────────────────────────────┤
│                                 │
│       메인 콘텐츠 영역            │
│                                 │
├─────────────────────────────────┤
│ [🏠] [🔍] [📤] [💬] [👤]       │ ← 하단 탭 네비게이션
└─────────────────────────────────┘

특징:
- 햄버거 메뉴: 전체 기능 접근
- 하단 탭바: 핵심 5개 기능 직접 접근
- 풀스크린 모달: 모든 상세 기능
- 제스처: 스와이프, Pull-to-refresh
```

#### 📟 태블릿 (768px ~ 1023px)
```
┌─────────────────────────────────────────────┐
│ WKMS [탭1] [탭2] [탭3] [탭4]        [👤]   │ ← 상단 탭 네비게이션
├─────────────────────────────────────────────┤
│ [서브탭1] [서브탭2] [서브탭3]               │ ← 하위 네비게이션
├─────────────────────────────────────────────┤
│                                             │
│            메인 콘텐츠 영역                  │
│                                             │
└─────────────────────────────────────────────┘

특징:
- 상단 탭: 주요 기능 그룹화
- 서브 탭: 세부 기능 접근
- 2단 레이아웃: 좌우 분할 활용
- 터치 + 마우스: 하이브리드 인터랙션
```

#### 💻 데스크톱 (1024px 이상)
```
┌──────┬──────────────────────────────────────┐
│      │ Breadcrumb    [검색]  [알림] [👤]   │ ← 상단바
│ 사이 ├──────────────────────────────────────┤
│ 드바 │                                      │
│      │          메인 콘텐츠 영역              │
│ 네비 │                                      │
│ 게이 │                                      │
│ 션   │                                      │
└──────┴──────────────────────────────────────┘

특징:
- 고정 사이드바: 계층적 네비게이션
- 상단 브레드크럼: 현재 위치 표시
- 다단 레이아웃: 효율적 공간 활용
- 키보드 단축키: 파워 유저 지원
```

### 3.2 컴포넌트 반응형 설계

#### 카드 컴포넌트
```
모바일: 세로 스택 (1열)
┌─────────────────┐
│     제목        │
│   ──────────    │
│     내용        │
└─────────────────┘

태블릿: 2열 그리드
┌─────────┬─────────┐
│  제목   │  제목   │
│ ─────── │ ─────── │
│  내용   │  내용   │
└─────────┴─────────┘

데스크톱: 3-4열 그리드 + 호버 효과
┌─────┬─────┬─────┬─────┐
│제목 │제목 │제목 │제목 │
│──── │──── │──── │──── │
│내용 │내용 │내용 │내용 │
└─────┴─────┴─────┴─────┘
```

#### 테이블 컴포넌트
```
모바일: 카드형 변환
┌─────────────────┐
│ 제목: 값        │
│ 작성자: 값      │
│ 날짜: 값        │
│ [상세보기]      │
└─────────────────┘

데스크톱: 전통적 테이블
┌─────┬─────┬─────┬─────┐
│제목 │작성자│날짜 │액션 │
├─────┼─────┼─────┼─────┤
│값   │값   │값   │[버튼]│
└─────┴─────┴─────┴─────┘
```
```
## 🏠 4. 일반 사용자 핵심 화면 레이아웃

### 4.1 메인 대시보드 - "지식 검색 중심"

#### 📱 모바일 레이아웃
```
┌─────────────────────────────────┐
│ [☰] WKMS              [👤]     │
├─────────────────────────────────┤
│ ┌─────────────────────────────┐ │
│ │  🔍 "궁금한 것을 물어보세요"  │ │ ← 메인 검색바
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 🎯 빠른 질문                    │
│ ┌─────┐ ┌─────┐ ┌─────┐         │
│ │채용  │ │교육 │ │평가 │ ...     │ ← 카테고리 태그
│ └─────┘ └─────┘ └─────┘         │
├─────────────────────────────────┤
│ 📋 최근 문서                    │
│ ┌─────────────────────────────┐ │
│ │ 📄 2025 채용가이드         │ │
│ │ 👤 김인사 · 📅 2시간 전    │ │ ← 카드형 리스트
│ └─────────────────────────────┘ │
│ ┌─────────────────────────────┐ │
│ │ 📄 신입사원 교육자료       │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 💡 AI 추천                     │
│ "최근 채용 관련 질문이 많아요"   │
└─────────────────────────────────┘
```

#### 💻 데스크톱 레이아웃
```
┌────────┬──────────────────────────────────────────────┐
│🏠 대시보드│ Home > 대시보드               [🔍] [🔔] [👤] │
│📊 분석    ├──────────────────────────────────────────────┤
│🔍 검색    │ ┌──────────────────────────────────────────┐ │
│📤 업로드  │ │ 🔍 "문서, 질문, 키워드로 검색하세요"     │ │
│📁 문서    │ │ [필터] [카테고리] [날짜] [작성자]       │ │
│💬 질의응답│ └──────────────────────────────────────────┘ │
│⚙️ 설정    ├──────────────────────────────────────────────┤
│          │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│          │ │🎯 빠른 시작  │ │📋 최근 문서  │ │💡 AI 추천   ││
│          │ │             │ │             │ │            ││
│          │ │[새 문서업로드]│ │📄 채용가이드 │ │"채용 관련   ││
│          │ │[AI에게 질문] │ │📄 교육자료   │ │문서가       ││
│          │ │[검색하기]   │ │📄 평가양식   │ │업데이트됨"  ││
│          │ └─────────────┘ └─────────────┘ └─────────────┘│
│          ├──────────────────────────────────────────────┤
│          │ 📊 나의 활동 통계                            │
│          │ 🔍 검색: 23회 📤 업로드: 5건 💬 질문: 12회    │
└────────┴──────────────────────────────────────────────┘
```

### 4.2 검색 결과 화면 - "찾은 지식 소비"

#### 📱 모바일 검색 결과
```
┌─────────────────────────────────┐
│ [←] "채용 가이드" 검색결과      │
├─────────────────────────────────┤
│ 🎯 AI 답변                      │
│ ┌─────────────────────────────┐ │
│ │ 2025년 채용 가이드에 따르면... │ │
│ │                             │ │ ← AI 답변 카드
│ │ [자세히 보기] [관련 문서]     │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 📄 관련 문서 (12건)             │
│ ┌─────────────────────────────┐ │
│ │ 📄 2025 채용 가이드라인     │ │
│ │ 💯 95% 일치 · 👤 김인사     │ │ ← 일치도 + 작성자
│ │ "신입사원 채용 절차와..."    │ │
│ └─────────────────────────────┘ │
│ ┌─────────────────────────────┐ │
│ │ 📄 면접 평가표 양식         │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ [더 보기] [필터] [정렬]          │
└─────────────────────────────────┘
```

### 4.3 문서 업로드 화면 - "지식 기여"

#### 📱 모바일 업로드 (단계별)
```
┌─────────────────────────────────┐
│ [←] 문서 업로드 (1/3)           │
├─────────────────────────────────┤
│ 📁 파일 선택                    │
│ ┌─────────────────────────────┐ │
│ │                             │ │
│ │      📁 클릭하여 파일 선택     │ │
│ │         또는                 │ │ ← 드래그 앤 드롭 영역
│ │      드래그해서 놓기          │ │
│ │                             │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 📷 [카메라로 촬영]              │
│ 🖼️ [갤러리에서 선택]            │ ← 모바일 전용 옵션
│ 📎 [파일 앱에서 선택]           │
├─────────────────────────────────┤
│         [다음 단계]              │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ [←] 문서 정보 입력 (2/3)        │
├─────────────────────────────────┤
│ 📝 제목                         │
│ ┌─────────────────────────────┐ │
│ │ "2025 채용 가이드라인"       │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 🏷️ 카테고리                     │
│ ┌─────────────────────────────┐ │
│ │ "인사 > 채용" [v]           │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 📝 설명 (선택사항)              │
│ ┌─────────────────────────────┐ │
│ │ "신입사원 채용 절차..."      │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│    [이전] [다음 단계]            │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ [←] 권한 설정 (3/3)             │
├─────────────────────────────────┤
│ 🔒 누가 볼 수 있나요?           │
│ ◉ 팀 공유 (채용팀 5명)          │
│ ○ 부서 공유 (인사팀 23명)       │ ← 라디오 버튼 선택
│ ○ 본부 공유 (경영지원 89명)     │
│ ○ 전사 공유 (전체 1,247명)      │
├─────────────────────────────────┤
│ 🎯 세부 권한                    │
│ ✅ 읽기 ✅ 다운로드            │
│ ❌ 댓글 ❌ 외부공유            │ ← 체크박스
├─────────────────────────────────┤
│    [이전] [업로드 완료]          │
└─────────────────────────────────┘
```

#### 💻 데스크톱 업로드 (통합 레이아웃)
```
┌────────┬──────────────────────────────────────────────┐
│        │ Home > 업로드                     [🔍] [👤] │
│        ├──────────────────────────────────────────────┤
│        │ ┌─────────────────┐ ┌─────────────────────┐  │
│        │ │                 │ │ 📝 문서 정보         │  │
│        │ │     📁 드래그    │ │ ┌─────────────────┐  │  │
│        │ │   앤 드롭 영역   │ │ │제목              │  │  │
│        │ │                 │ │ └─────────────────┘  │  │
│        │ │ [파일 선택 버튼] │ │ 🏷️ 카테고리          │  │
│        │ │                 │ │ ┌─────────────────┐  │  │
│        │ └─────────────────┘ │ │인사 > 채용 [v]  │  │  │
│        │                     │ └─────────────────┘  │  │
│        │ 📊 업로드 진행률     │ 📝 설명              │  │
│        │ ▓▓▓▓▓░░░░░ 50%      │ ┌─────────────────┐  │  │
│        │                     │ │설명 입력...      │  │  │
│        │                     │ └─────────────────┘  │  │
│        │                     │ 🔒 권한 설정         │  │
│        │                     │ ◉ 팀 공유           │  │
│        │                     │ ○ 부서 공유         │  │
│        │                     │ ○ 전사 공유         │  │
│        │                     │ [업로드] [미리보기]  │  │
│        │                     └─────────────────────┘  │
└────────┴──────────────────────────────────────────────┘
```

### 4.4 AI 질의응답 화면 - "즉시 답변"

#### 📱 모바일 채팅 인터페이스
```
┌─────────────────────────────────┐
│ [←] AI 질의응답         [⚙️]   │
├─────────────────────────────────┤
│                                 │
│ 👤 "2025년 신입사원 채용 일정을  │
│    알려주세요"                   │
│                                 │
│        🤖 "2025년 신입사원 채용  │ ← 대화형 인터페이스
│        일정은 다음과 같습니다:    │
│                                 │
│        📅 서류접수: 3월 1일~15일  │
│        📝 1차 면접: 3월 20일~25일 │
│        📋 2차 면접: 3월 28일~30일 │
│                                 │
│        📄 참고 문서:             │
│        • 2025 채용 가이드라인    │ ← 참고 문서 링크
│        • 면접 일정표            │
│                                 │
│ [👍] [👎] [공유] [저장]         │ ← 피드백 버튼
├─────────────────────────────────┤
│ ┌─────────────────────────────┐ │
│ │ 💬 메시지를 입력하세요...    │ │ ← 입력창
│ └─────────────────────────────┘ │
│ [📎] [🎤] [📷] [전송]           │ ← 첨부/전송 버튼
└─────────────────────────────────┘
```

### 4.5 내 문서함 - "개인 지식 관리"

#### 📱 모바일 문서함
```
┌─────────────────────────────────┐
│ [☰] 내 문서함           [🔍]    │
├─────────────────────────────────┤
│ 📊 내 활동 요약                 │
│ 📤 업로드: 12건  👀 조회: 234회  │
│ ❤️ 좋아요: 45개  📥 다운로드: 78건│
├─────────────────────────────────┤
│ 📁 폴더별 보기                  │
│ ┌─────┐ ┌─────┐ ┌─────┐         │
│ │📁채용│ │📁교육│ │📁평가│ ...     │ ← 폴더 그리드
│ │ 8건 │ │ 3건 │ │ 1건 │         │
│ └─────┘ └─────┘ └─────┘         │
├─────────────────────────────────┤
│ 📄 최근 업로드                  │
│ ┌─────────────────────────────┐ │
│ │ 📄 2025 채용 가이드라인     │ │
│ │ 👀 234회 · ❤️ 12개 · 📅 2일전│ │ ← 통계 + 날짜
│ └─────────────────────────────┘ │
│ ┌─────────────────────────────┐ │
│ │ 📄 면접 질문 모음집         │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ [전체 보기] [필터] [정렬]        │
└─────────────────────────────────┘
```
```

### 3.2 라우팅 구조
```typescript
// App.tsx 라우팅 예시
const App = () => {
  return (
    <Router>
      <Routes>
        {/* 공통 라우트 */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        
        {/* 일반 사용자 라우트 */}
        <Route path="/user/*" element={
          <ProtectedRoute requiredRole="USER">
            <UserLayout />
          </ProtectedRoute>
        }>
          <Route index element={<UserDashboard />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="documents" element={<MyDocuments />} />
          <Route path="chat" element={<ChatPage />} />
        </Route>

        {/* 지식관리자 라우트 */}
        <Route path="/manager/*" element={
          <ProtectedRoute requiredRole="MANAGER">
            <ManagerLayout />
          </ProtectedRoute>
        }>
          <Route index element={<ManagerDashboard />} />
          <Route path="containers" element={<ContainerManagement />} />
          <Route path="permissions" element={<PermissionApproval />} />
          <Route path="quality" element={<QualityManagement />} />
          <Route path="support" element={<UserSupport />} />
          {/* 사용자 기능도 포함 */}
          <Route path="search" element={<SearchPage />} />
          <Route path="chat" element={<ChatPage />} />
        </Route>

        {/* 시스템관리자 라우트 */}
        <Route path="/admin/*" element={
          <ProtectedRoute requiredRole="ADMIN">
            <AdminLayout />
          </ProtectedRoute>
        }>
          <Route index element={<AdminDashboard />} />
          <Route path="monitoring" element={<SystemMonitoring />} />
          <Route path="users" element={<UserManagement />} />
          <Route path="security" element={<SecurityPolicies />} />
          <Route path="audit" element={<AuditLogs />} />
          {/* 모든 기능 포함 */}
          <Route path="manager/*" element={<ManagerFeatures />} />
          <Route path="user/*" element={<UserFeatures />} />
        </Route>
      </Routes>
    </Router>
  );
};
```

## 4. 레이아웃 설계

### 4.1 일반 사용자 레이아웃
```typescript
// UserLayout.tsx
const UserLayout = () => {
  return (
    <div className="user-layout">
      <Header userRole="USER" />
      <div className="main-content">
        <Sidebar menuItems={userMenuItems} />
        <div className="content-area">
          <Outlet />
        </div>
      </div>
    </div>
  );
};

const userMenuItems = [
  { path: "/user", icon: "🏠", label: "대시보드" },
  { path: "/user/search", icon: "🔍", label: "지식 검색" },
  { path: "/user/upload", icon: "📤", label: "문서 업로드" },
  { path: "/user/documents", icon: "📁", label: "내 문서" },
  { path: "/user/chat", icon: "💬", label: "AI 질의응답" },
];
```

### 4.2 지식관리자 레이아웃
```typescript
// ManagerLayout.tsx
const ManagerLayout = () => {
  return (
    <div className="manager-layout">
      <Header userRole="MANAGER" />
      <div className="main-content">
        <Sidebar menuItems={managerMenuItems} />
        <div className="content-area">
          <Outlet />
        </div>
      </div>
    </div>
  );
};

const managerMenuItems = [
  // 관리 기능
  { path: "/manager", icon: "📊", label: "관리 대시보드" },
  { path: "/manager/containers", icon: "🗂️", label: "컨테이너 관리" },
  { path: "/manager/permissions", icon: "🔐", label: "권한 승인" },
  { path: "/manager/quality", icon: "⭐", label: "품질 관리" },
  { path: "/manager/support", icon: "🛠️", label: "사용자 지원" },
  // 구분선
  { type: "divider" },
  // 일반 사용자 기능
  { path: "/manager/search", icon: "🔍", label: "지식 검색" },
  { path: "/manager/chat", icon: "💬", label: "AI 질의응답" },
];
```

### 4.3 시스템관리자 레이아웃
```typescript
// AdminLayout.tsx
const AdminLayout = () => {
  return (
    <div className="admin-layout">
      <Header userRole="ADMIN" />
      <div className="main-content">
        <Sidebar menuItems={adminMenuItems} />
        <div className="content-area">
          <Outlet />
        </div>
      </div>
    </div>
  );
};

const adminMenuItems = [
  // 시스템 관리 기능
  { path: "/admin", icon: "🏗️", label: "시스템 대시보드" },
  { path: "/admin/monitoring", icon: "📈", label: "시스템 모니터링" },
  { path: "/admin/users", icon: "👥", label: "사용자 관리" },
  { path: "/admin/security", icon: "🛡️", label: "보안 정책" },
  { path: "/admin/audit", icon: "📋", label: "감사 로그" },
  // 구분선
  { type: "divider" },
  // 하위 관리 기능
  { path: "/admin/manager", icon: "🗂️", label: "지식 관리" },
  { path: "/admin/user", icon: "🔍", label: "사용자 기능" },
];
```

## 5. 주요 화면 설계

### 5.1 일반 사용자 대시보드
```typescript
// pages/user/Dashboard.tsx
const UserDashboard = () => {
  return (
    <div className="user-dashboard">
      {/* 빠른 검색 */}
      <section className="quick-search">
        <h2>지식 검색</h2>
        <SearchInterface onSearch={handleSearch} />
      </section>
      
      {/* 최근 문서 */}
      <section className="recent-documents">
        <h3>최근 문서</h3>
        <DocumentGrid documents={recentDocuments} />
      </section>
      
      {/* 추천 지식 */}
      <section className="recommended-knowledge">
        <h3>추천 지식</h3>
        <KnowledgeCards recommendations={recommendations} />
      </section>
      
      {/* AI 질의응답 */}
      <section className="ai-chat">
        <h3>AI 질의응답</h3>
        <QuickChatInterface />
      </section>
    </div>
  );
};
```

### 5.2 지식관리자 대시보드
```typescript
// pages/manager/ManagerDashboard.tsx
const ManagerDashboard = () => {
  return (
    <div className="manager-dashboard">
      {/* 관리 현황 */}
      <section className="management-overview">
        <h2>관리 현황</h2>
        <div className="stats-grid">
          <StatCard title="관리 컨테이너" value={containerCount} />
          <StatCard title="대기 권한 요청" value={pendingRequests} />
          <StatCard title="품질 점검 필요" value={qualityReviewNeeded} />
          <StatCard title="활성 사용자" value={activeUsers} />
        </div>
      </section>
      
      {/* 권한 요청 대기 */}
      <section className="pending-permissions">
        <h3>권한 요청 승인 대기</h3>
        <PermissionRequestTable requests={pendingPermissions} />
      </section>
      
      {/* 컨테이너 상태 */}
      <section className="container-status">
        <h3>컨테이너 상태</h3>
        <ContainerStatusGrid containers={managedContainers} />
      </section>
      
      {/* 빠른 작업 */}
      <section className="quick-actions">
        <h3>빠른 작업</h3>
        <ActionButtonGrid actions={quickActions} />
      </section>
    </div>
  );
};
```

### 5.3 시스템관리자 대시보드
```typescript
// pages/admin/AdminDashboard.tsx
const AdminDashboard = () => {
  return (
    <div className="admin-dashboard">
      {/* 시스템 상태 */}
      <section className="system-status">
        <h2>시스템 상태</h2>
        <SystemMetrics metrics={systemMetrics} />
      </section>
      
      {/* 사용자 통계 */}
      <section className="user-statistics">
        <h3>사용자 통계</h3>
        <UserStatsChart data={userStats} />
      </section>
      
      {/* 최근 활동 */}
      <section className="recent-activities">
        <h3>최근 시스템 활동</h3>
        <ActivityTimeline activities={recentActivities} />
      </section>
      
      {/* 알림 및 경고 */}
      <section className="alerts">
        <h3>시스템 알림</h3>
        <AlertPanel alerts={systemAlerts} />
      </section>
    </div>
  );
};
```

## 6. 권한 기반 네비게이션

### 6.1 권한 체크 훅
```typescript
// hooks/usePermissions.ts
export const usePermissions = () => {
  const { user } = useAuth();
  
  const hasPermission = (permission: string) => {
    return user?.permissions?.includes(permission) || false;
  };
  
  const hasRole = (role: string) => {
    return user?.roles?.includes(role) || false;
  };
  
  const canAccessManager = () => {
    return hasRole('MANAGER') || hasRole('ADMIN');
  };
  
  const canAccessAdmin = () => {
    return hasRole('ADMIN');
  };
  
  return { hasPermission, hasRole, canAccessManager, canAccessAdmin };
};
```

### 6.2 보호된 라우트
```typescript
// components/common/ProtectedRoute.tsx
interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;
  requiredPermission?: string;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole,
  requiredPermission
}) => {
  const { user, isAuthenticated } = useAuth();
  const { hasRole, hasPermission } = usePermissions();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  if (requiredRole && !hasRole(requiredRole)) {
    return <Navigate to="/unauthorized" replace />;
  }
  
  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <Navigate to="/unauthorized" replace />;
  }
  
  return <>{children}</>;
};
```

## 7. 헤더 컴포넌트 통합 설계

### 7.1 역할별 헤더
```typescript
// components/common/Header.tsx
interface HeaderProps {
  userRole: 'USER' | 'MANAGER' | 'ADMIN';
}

const Header: React.FC<HeaderProps> = ({ userRole }) => {
  const { user, logout } = useAuth();
  
  const getRoleSpecificActions = () => {
    switch (userRole) {
      case 'ADMIN':
        return [
          { label: '시스템 관리', path: '/admin' },
          { label: '지식 관리', path: '/admin/manager' },
          { label: '사용자 모드', path: '/admin/user' }
        ];
      case 'MANAGER':
        return [
          { label: '관리 대시보드', path: '/manager' },
          { label: '사용자 모드', path: '/user' }
        ];
      case 'USER':
      default:
        return [];
    }
  };
  
  return (
    <header className={`header header--${userRole.toLowerCase()}`}>
      <div className="header__brand">
        <img src="/logo.png" alt="WKMS" />
        <h1>웅진 WKMS</h1>
        <span className="role-badge">{getRoleLabel(userRole)}</span>
      </div>
      
      <nav className="header__nav">
        {getRoleSpecificActions().map(action => (
          <Link key={action.path} to={action.path} className="nav-link">
            {action.label}
          </Link>
        ))}
      </nav>
      
      <div className="header__user">
        <UserDropdown user={user} onLogout={logout} />
      </div>
    </header>
  );
};
```

## 8. 구현 단계별 계획

### 8.1 Phase 1: 기본 구조 구축 (1-2주)
1. 프로젝트 구조 재구성
2. 라우팅 시스템 구축
3. 권한 기반 네비게이션 구현
4. 기본 레이아웃 컴포넌트 개발

### 8.2 Phase 2: 사용자 기능 개발 (2-3주)
1. 일반 사용자 대시보드
2. 검색 인터페이스 고도화
3. 문서 업로드 기능 향상
4. AI 질의응답 인터페이스

### 8.3 Phase 3: 관리자 기능 개발 (3-4주)
1. 지식관리자 대시보드
2. 컨테이너 관리 도구
3. 권한 승인 시스템
4. 품질 관리 도구

### 8.4 Phase 4: 시스템관리자 기능 개발 (2-3주)
1. 시스템관리자 대시보드
2. 사용자 관리 시스템
3. 시스템 모니터링 도구
4. 감사 로그 시스템

### 8.5 Phase 5: 통합 및 최적화 (1-2주)
1. 전체 기능 통합 테스트
2. UI/UX 최적화
3. 성능 최적화
4. 문서화 및 배포

## 9. 기술적 고려사항

### 9.1 상태 관리
- **Redux Toolkit**: 복잡한 상태 관리를 위한 글로벌 스토어
- **React Query**: 서버 상태 관리 및 캐싱
- **Context API**: 사용자 인증 및 권한 상태

### 9.2 컴포넌트 설계
- **Atomic Design**: 재사용 가능한 컴포넌트 계층 구조
- **TypeScript**: 타입 안전성 확보
- **Styled Components**: CSS-in-JS 스타일링

### 9.3 성능 최적화
- **Code Splitting**: 역할별 번들 분리
- **Lazy Loading**: 필요 시점에 컴포넌트 로드
- **Memoization**: 불필요한 리렌더링 방지

## 📋 7. 구현 가이드 및 고려사항

### 7.1 개발 우선순위

#### 1단계: 기본 역할 분리 (2주)
- 기본 라우팅 시스템 구축
- 사용자 역할별 레이아웃 컴포넌트 개발
- 권한 기반 네비게이션 구현

#### 2단계: 핵심 화면 구현 (4주)
- 일반 사용자 대시보드 및 검색 기능
- 지식관리자 컨테이너 관리 화면
- 시스템관리자 기본 관리 화면

#### 3단계: 반응형 최적화 (3주)
- 모바일 우선 반응형 디자인 적용
- 터치 인터랙션 및 제스처 구현
- 성능 최적화 및 코드 분할

#### 4단계: 고급 기능 (2주)
- 다크 모드 및 접근성 향상
- 실시간 알림 및 모니터링
- PWA 기능 추가

### 7.2 기술 스택 권장사항

#### 프론트엔드 핵심
- **React 18**: 최신 concurrent features 활용
- **TypeScript**: 타입 안전성 보장
- **Vite**: 빠른 개발 환경
- **React Router v6**: 중첩 라우팅 지원

#### UI/UX 라이브러리
- **Framer Motion**: 부드러운 애니메이션
- **Radix UI**: 접근성 우선 컴포넌트
- **Styled Components**: CSS-in-JS 스타일링
- **React Query**: 서버 상태 관리

#### 개발 도구
- **ESLint + Prettier**: 코드 품질 관리
- **Storybook**: 컴포넌트 문서화
- **Jest + RTL**: 테스트 자동화

### 7.3 성능 최적화 전략

#### 번들 최적화
```typescript
// 역할별 코드 분할 예시
const UserRoutes = lazy(() => import('./routes/UserRoutes'));
const ManagerRoutes = lazy(() => import('./routes/ManagerRoutes'));
const AdminRoutes = lazy(() => import('./routes/AdminRoutes'));
```

#### 메모리 최적화
- Virtual Scrolling으로 대용량 데이터 처리
- 이미지 lazy loading과 WebP 포맷 활용
- 불필요한 리렌더링 방지 (React.memo, useMemo)

### 7.4 보안 고려사항

#### 클라이언트 사이드 보안
- JWT 토큰 안전한 저장 (httpOnly 쿠키)
- XSS 방지를 위한 Content Security Policy
- 민감한 데이터 클라이언트 노출 최소화

#### 권한 검증
- 클라이언트와 서버 양쪽 권한 검증
- 역할 기반 UI 숨김과 서버 검증 분리
- API 호출 시 권한 헤더 포함

### 7.5 접근성 구현 가이드

#### 키보드 네비게이션
- Tab 순서 논리적 구성
- Skip links로 주요 콘텐츠 직접 접근
- 포커스 표시 명확하게 구현

#### 스크린 리더 지원
- 시맨틱 HTML 태그 사용
- ARIA 레이블과 역할 적절히 설정
- 동적 콘텐츠 변경 시 안내 메시지

### 7.6 테스트 전략

#### 단위 테스트
- 컴포넌트별 렌더링 테스트
- 사용자 인터랙션 시뮬레이션
- 권한별 접근 제어 테스트

#### 통합 테스트
- 역할별 워크플로우 테스트
- API 연동 테스트
- 반응형 레이아웃 테스트

#### E2E 테스트
- 사용자 시나리오 기반 테스트
- 크로스 브라우저 호환성 확인
- 성능 메트릭 자동 측정

---

## 💡 권장 구현 순서

1. **기본 구조 설정**: 프로젝트 셋업, 라우팅, 권한 시스템
2. **레이아웃 컴포넌트**: 역할별 기본 레이아웃 구현
3. **핵심 화면**: 각 역할의 주요 기능 화면 구현
4. **반응형 적용**: 모바일 최적화 및 터치 인터랙션
5. **성능 최적화**: 코드 분할, 지연 로딩, 캐싱
6. **접근성 향상**: WCAG 2.1 AA 준수, 키보드 네비게이션
7. **고급 기능**: 다크 모드, PWA, 실시간 알림
8. **테스트 및 최적화**: 종합 테스트, 성능 튜닝

이 순서로 개발하면 안정적이고 확장 가능한 역할 기반 UI 시스템을 구축할 수 있습니다.

---

## 📱 최신 멀티 디바이스 UI/UX 표준 통합

### 추가 설계 고려사항

위의 기본 설계에 **최신 반응형 웹 디자인 트렌드**를 반영한 멀티 디바이스 지원을 추가합니다:

#### 🎯 핵심 원칙
- **Mobile First Design**: 모바일 우선 설계로 점진적 향상
- **Progressive Enhancement**: 디바이스 성능에 따른 기능 확장
- **Touch-First Interaction**: 터치 중심 인터랙션 설계
- **Cross-Platform Consistency**: 모든 플랫폼에서 일관된 경험

#### 📐 반응형 Breakpoint 시스템
```scss
$breakpoints: (
  'mobile-s': 320px,   // 소형 스마트폰
  'mobile-m': 375px,   // 중형 스마트폰
  'mobile-l': 425px,   // 대형 스마트폰
  'tablet-p': 768px,   // 태블릿 세로
  'tablet-l': 1024px,  // 태블릿 가로
  'laptop': 1440px,    // 노트북
  'desktop': 1920px    // 데스크톱
);
```

#### 🎨 디바이스별 네비게이션 패턴
- **모바일**: 햄버거 메뉴 + 하단 탭바
- **태블릿**: 상단 탭 네비게이션 + 사이드 패널
- **데스크톱**: 사이드바 + 상단 브레드크럼

#### 🖱️ 인터랙션 최적화
- **터치 제스처**: 스와이프, 핀치줌, Pull-to-refresh
- **키보드 네비게이션**: 전체 기능 키보드 접근 가능
- **마우스 호버**: 데스크톱 전용 향상된 UX

#### 🌓 현대적 UI 특징
- **다크 모드**: 시스템 설정 연동 자동 테마 전환
- **글래스모피즘**: 반투명 레이어와 블러 효과
- **Micro-interactions**: 세밀한 피드백 애니메이션
- **Skeleton Loading**: 콘텐츠 로딩 시 사용자 경험 향상

#### ♿ 접근성 우선 설계
- **WCAG 2.1 AA 준수**: 모든 사용자 접근 가능
- **스크린 리더 지원**: 완전한 음성 네비게이션
- **고대비 모드**: 시각 장애인 지원
- **Reduced Motion**: 모션 민감성 사용자 고려

#### 🚀 성능 최적화
- **Virtual Scrolling**: 대용량 데이터 최적 렌더링
- **Lazy Loading**: 필요 시점 리소스 로딩
- **Image Optimization**: WebP, AVIF 차세대 포맷 지원
- **Code Splitting**: 역할별 번들 분리

자세한 UI/UX 표준은 별도 문서 `ui_ux_standards.md`에 정의되어 있습니다.
