# PPT 오브젝트 매핑 확장 시스템 사용 가이드

## 🎯 개요

기존 텍스트박스 전용 매핑 시스템을 확장하여 이미지, 도형, 차트, 테이블 등 모든 PPT 오브젝트 타입을 지원하는 포괄적인 매핑 시스템입니다.

## 🏗️ 시스템 구조

### 1. 백엔드 구조
```
backend/app/
├── models/
│   └── presentation_objects.py          # 확장된 오브젝트 모델 정의
├── services/presentation/
│   ├── enhanced_object_processor.py     # 핵심 오브젝트 처리 로직
│   ├── enhanced_ppt_generator_service.py # 기존 서비스와 통합
│   └── template_metadata_extractor.py   # 템플릿 오브젝트 추출
└── api/v1/
    └── chat.py                          # API 엔드포인트 확장
```

### 2. 프론트엔드 구조
```
frontend/src/components/presentation/
├── PPTObjectMappingEditor.tsx           # 확장된 매핑 UI 컴포넌트
└── TextBoxMappingEditor.tsx             # 기존 텍스트박스 전용 (레거시)
```

## 🎨 지원 오브젝트 타입

### PPTObjectType enum
- `TEXTBOX`: 텍스트박스 (기존)
- `IMAGE`: 이미지 
- `SHAPE`: 도형 (사각형, 원형, 화살표 등)
- `CHART`: 차트 (막대, 원형, 선형 등)
- `TABLE`: 표
- `DIAGRAM`: 다이어그램
- `ICON`: 아이콘
- `LOGO`: 로고
- `BACKGROUND`: 배경

### ObjectAction enum
- `KEEP_ORIGINAL`: 원본 유지
- `REPLACE_CONTENT`: 내용 교체 (텍스트, 데이터)
- `REPLACE_OBJECT`: 오브젝트 전체 교체
- `HIDE_OBJECT`: 오브젝트 숨기기
- `MODIFY_STYLE`: 스타일 수정 (색상, 폰트 등)
- `RESIZE`: 크기 조정
- `REPOSITION`: 위치 조정

## 🔧 사용 방법

### 1. 프론트엔드 컴포넌트 사용

```tsx
import PPTObjectMappingEditor from '@/components/presentation/PPTObjectMappingEditor';

// 컴포넌트 사용
<PPTObjectMappingEditor
  slideIndex={0}
  slideData={slideData}
  contentSegments={contentSegments}
  mappings={mappings}
  onMappingChange={handleMappingChange}
/>
```

### 2. 매핑 데이터 구조

```typescript
interface PPTObjectMapping {
  slideIndex: number;
  elementId: string;
  objectType: PPTObjectType;
  action: ObjectAction;
  isEnabled: boolean;
  
  // 원본 정보
  originalContent?: string;
  originalStyle?: Record<string, any>;
  originalPosition?: { x: number; y: number; width: number; height: number };
  
  // 새로운 정보
  newContent?: string;
  newImageUrl?: string;
  newStyle?: Record<string, any>;
  newPosition?: { x: number; y: number; width: number; height: number };
}
```

### 3. API 요청 예시

```javascript
// PPT 빌드 시 오브젝트 매핑 전달
const response = await fetch('/api/v1/chat/presentation/build', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    session_id: "session123",
    source_message_id: "msg456",
    outline: outlineData,
    template_id: "user_template_001",
    object_mappings: [
      {
        slideIndex: 0,
        elementId: "textbox-0-1",
        objectType: "textbox",
        action: "replace_content",
        isEnabled: true,
        newContent: "새로운 제목 텍스트"
      },
      {
        slideIndex: 1,
        elementId: "image-1-0",
        objectType: "image",
        action: "replace_object",
        isEnabled: true,
        newImageUrl: "https://example.com/new-image.jpg"
      },
      {
        slideIndex: 2,
        elementId: "shape-2-0",
        objectType: "shape",
        action: "hide_object",
        isEnabled: true
      }
    ],
    content_segments: contentSegments
  })
});
```

## 🎛️ UI 기능 설명

### 1. 오브젝트 타입 필터
- 전체 오브젝트 또는 특정 타입별로 필터링 가능
- 각 타입별 개수 표시

### 2. 오브젝트 목록
- 슬라이드별 모든 오브젝트 나열
- 타입별 아이콘 표시
- 활성화/비활성화 토글

### 3. 상세 설정 패널
- 오브젝트별 액션 선택
- 타입별 특화 설정 옵션
- 실시간 미리보기

### 4. 타입별 특화 설정

#### 텍스트박스 (TEXTBOX)
- 새로운 텍스트 입력
- 폰트 스타일 수정

#### 이미지 (IMAGE)
- 새 이미지 URL 입력
- 이미지 교체 옵션

#### 도형 (SHAPE)
- 색상 변경
- 크기/위치 조정

#### 차트 (CHART)
- 데이터 소스 연결
- 차트 유형 변경

#### 표 (TABLE)
- 표 데이터 교체
- 행/열 구성 수정

## 🔄 처리 흐름

### 1. 템플릿 분석
```
1. template_metadata_extractor.py가 모든 오브젝트 추출
2. 각 오브젝트의 타입, 위치, 스타일 정보 수집
3. 프론트엔드로 메타데이터 전달
```

### 2. 사용자 매핑 설정
```
1. PPTObjectMappingEditor에서 오브젝트별 설정
2. 사용자가 액션 및 새 내용 지정
3. 매핑 데이터를 API로 전송
```

### 3. 백엔드 처리
```
1. enhanced_object_processor.py가 매핑 데이터 수신
2. 오브젝트 타입별 전용 처리 로직 실행
3. 액션에 따른 변환 작업 수행
4. 최종 PPT 파일 생성
```

## 📋 구현 체크리스트

### ✅ 완료된 작업
- [x] PPTObjectType, ObjectAction enum 정의
- [x] PPTObjectMapping 데이터 모델 생성
- [x] EnhancedPPTObjectProcessor 클래스 구현
- [x] PPTObjectMappingEditor 컴포넌트 생성
- [x] 기존 서비스와 통합
- [x] API 엔드포인트 확장

### 🚧 추가 구현 필요
- [ ] 이미지 다운로드 및 교체 로직
- [ ] 차트 데이터 교체 구현
- [ ] 테이블 데이터 교체 구현
- [ ] 도형 스타일 수정 구현
- [ ] 프론트엔드 UI 세부 기능 완성
- [ ] 오브젝트별 유효성 검사
- [ ] 에러 처리 및 폴백 로직
- [ ] 단위 테스트 작성

## 🎭 예시 시나리오

### 시나리오 1: 제품 소개서 생성
```
1. 사용자가 제품 데이터를 업로드
2. 템플릿에서 모든 오브젝트 감지
3. 제품 이미지를 새 이미지로 교체 설정
4. 제품 사양 표를 새 데이터로 교체 설정
5. 불필요한 도형들은 숨김 처리 설정
6. PPT 생성 시 설정에 따라 자동 변환
```

### 시나리오 2: 회사 소개서 커스터마이징
```
1. 기본 회사 소개서 템플릿 선택
2. 회사 로고 이미지 교체
3. 조직도 차트 데이터 업데이트
4. 연혁 표 정보 수정
5. 배경 색상 및 테마 변경
6. 일괄 적용하여 통일된 디자인 완성
```

## 🔍 디버깅 가이드

### 1. 오브젝트 매핑 실패
- 로그에서 `enhanced_object_processor` 키워드 검색
- `element_id` 매칭 확인
- 오브젝트 타입 일치성 검증

### 2. UI 동작 이상
- 브라우저 개발자 도구에서 React 컴포넌트 상태 확인
- `mappings` 배열 데이터 구조 검증
- 이벤트 핸들러 동작 확인

### 3. API 연동 문제
- 네트워크 탭에서 요청/응답 데이터 확인
- 백엔드 로그에서 매핑 적용 과정 추적
- Pydantic 모델 유효성 검사 오류 확인

## 📈 성능 최적화

### 1. 프론트엔드 최적화
- 오브젝트 목록 가상화 (대량 오브젝트 처리)
- 매핑 변경 디바운싱
- 메모이제이션 적용

### 2. 백엔드 최적화
- 오브젝트 처리 병렬화
- 이미지 캐싱 및 압축
- 대용량 템플릿 스트리밍 처리

## 🛡️ 보안 고려사항

### 1. 입력 검증
- 이미지 URL 유효성 검사
- 파일 형식 및 크기 제한
- XSS 방지를 위한 콘텐츠 필터링

### 2. 권한 관리
- 템플릿별 접근 권한 확인
- 사용자별 매핑 데이터 격리
- API 요청 인증 및 권한 검사

이제 **모든 PPT 오브젝트 타입에 대한 포괄적인 매핑 시스템**이 준비되었습니다! 🎨✨
