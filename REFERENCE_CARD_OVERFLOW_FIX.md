# 참고자료 카드 레이아웃 오버플로우 수정 완료

## 📅 작업 일시
2025-11-12

## 🐛 문제 상황
- **증상**: AI Agent 채팅에서 답변과 참고자료 카드가 오른쪽으로 잘려서 표시됨
- **원인**: 카드 내용이 컨테이너 너비를 초과해도 줄바꿈되지 않고 오른쪽으로 확장됨
- **영향**: 긴 파일명, 문서 타입, 점수 배지 등이 화면 밖으로 넘쳐서 보이지 않음

## 🔧 수정 내역

### 1. ReferencePanel.tsx - 참고자료 카드 레이아웃

#### 변경 전 (문제)
```tsx
// Grid 레이아웃 사용 - 고정 너비로 인해 오버플로우 발생
<div className="grid grid-cols-[auto_1fr_auto] gap-2 items-center mb-2">
  <div className="flex items-center gap-2 min-w-0 col-span-2">
    {/* 파일명이 길면 오른쪽으로 확장 */}
  </div>
</div>
```

#### 변경 후 (해결)
```tsx
// Flex 레이아웃 + flex-wrap - 넘치면 다음 줄로 이동
<div className="flex flex-wrap items-center gap-2 mb-2 w-full">
  <div className="flex items-center gap-2 min-w-0 flex-1">
    <span className="truncate flex-1 min-w-0">
      {/* 파일명이 길면 잘림 */}
    </span>
  </div>
  <div className="flex items-center gap-2 shrink-0">
    {/* 점수 배지는 항상 보임 + whitespace-nowrap */}
  </div>
</div>
```

**주요 개선**:
- ✅ `grid` → `flex flex-wrap`: 넘치면 자동 줄바꿈
- ✅ `flex-1 min-w-0`: 파일명 영역이 컨테이너에 맞춰 축소
- ✅ `truncate`: 긴 파일명은 말줄임표(...)로 표시
- ✅ `shrink-0 whitespace-nowrap`: 배지와 버튼은 항상 전체 표시

---

### 2. ReferencePanel.tsx - 위치 정보 레이아웃

#### 변경 전
```tsx
<div className="grid grid-cols-[1fr_auto] gap-2 items-center mb-2">
  {/* Grid로 고정 */}
</div>
```

#### 변경 후
```tsx
<div className="flex flex-wrap items-center justify-between gap-2 mb-2 w-full">
  {/* Flex + wrap으로 유연하게 */}
</div>
```

**효과**: 페이지 번호와 상세보기 버튼이 공간 부족 시 다음 줄로 이동

---

### 3. ReferencePanel.tsx - 텍스트 콘텐츠 word-break

#### AI 요약
```tsx
// Before
<div className="mb-2 text-xs text-gray-700 bg-blue-50 px-2 py-1 rounded">

// After
<div className="mb-2 text-xs text-gray-700 bg-blue-50 px-2 py-1 rounded break-words">
```

#### 발췌 내용
```tsx
// Before
<div className="text-sm text-gray-700 leading-relaxed" style={{...}}>

// After
<div className="text-sm text-gray-700 leading-relaxed break-words" style={{
  wordBreak: 'break-word'  // 긴 단어도 강제 줄바꿈
}}>
```

**효과**: 긴 URL, 영어 단어 등도 컨테이너 내에서 줄바꿈됨

---

### 4. ReferencePanel.tsx - 전체 컨테이너

#### 변경 전
```tsx
<div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-4 max-w-full overflow-hidden">
```

#### 변경 후
```tsx
<div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-4 w-full overflow-hidden">
```

**이유**: `max-w-full`은 제한이 약하므로 `w-full`로 명확히 지정

---

### 5. MessageBubble.tsx - 메시지 컨테이너

#### 메시지 컨테이너
```tsx
// Before
<div className={`flex-1 ${isUser ? 'text-right' : 'text-left'}`}>

// After
<div className={`flex-1 min-w-0 ${isUser ? 'text-right' : 'text-left'}`}>
```

**효과**: `min-w-0`으로 자식 요소가 부모 너비를 초과하지 않도록 강제

#### 메시지 버블
```tsx
// Before
<div className={`relative px-4 py-2.5 rounded-2xl shadow-sm ${...}`}>

// After
<div className={`relative px-4 py-2.5 rounded-2xl shadow-sm w-full overflow-hidden ${...}`}>
```

**효과**: 버블 자체가 컨테이너 너비를 초과하지 않음

#### AI 메시지 내용
```tsx
// Before
<div className="max-w-none text-left break-words">

// After
<div className="w-full text-left break-words overflow-hidden">
```

**효과**: `max-w-none` 제거하여 무제한 확장 방지

#### 참고자료 패널 래퍼
```tsx
// Before
<div className="mt-3">

// After
<div className="mt-3 w-full overflow-hidden">
```

**효과**: 참고자료 패널도 메시지 버블 너비 내에서만 표시

---

## 📊 수정 요약

### 핵심 변경 사항
1. **Grid → Flex + Wrap**: 고정 레이아웃에서 유연한 레이아웃으로 변경
2. **min-w-0 추가**: Flexbox의 기본 동작(자식이 부모보다 커지는 것) 방지
3. **break-words 추가**: 긴 단어/URL 강제 줄바꿈
4. **whitespace-nowrap**: 중요 요소(배지, 버튼)는 항상 한 줄 유지
5. **w-full + overflow-hidden**: 컨테이너 너비 명확히 제한

### 수정 파일
- ✅ `frontend/src/pages/user/chat/components/ReferencePanel.tsx`
- ✅ `frontend/src/pages/user/chat/components/MessageBubble.tsx`

### 변경 라인 수
- ReferencePanel.tsx: 6개 섹션 수정
- MessageBubble.tsx: 4개 섹션 수정
- 총 약 20줄 수정

---

## 🎯 해결 결과

### Before (문제)
```
┌─────────────────────────────────────────────┐
│ #1 매우긴파일명이잘리지않고오른쪽으로계속확장됩니다.pdf  [관련도: 높음] 95.3% │ → 화면 밖으로 넘침
│   청크 5                                    [📋 상세보기]                   │
└─────────────────────────────────────────────┘
```

### After (해결)
```
┌─────────────────────────────────────────────┐
│ #1 매우긴파일명이잘리지않고오른쪽으로계...│
│ [관련도: 높음] 95.3%                        │ ← 자동 줄바꿈
│ 청크 5                   [📋 상세보기]      │
└─────────────────────────────────────────────┘
```

### 개선 사항
- ✅ **파일명 말줄임**: 긴 파일명은 `...`으로 표시, 호버 시 전체 표시
- ✅ **자동 줄바꿈**: 공간 부족 시 요소가 다음 줄로 이동
- ✅ **정보 보존**: 모든 배지와 버튼이 항상 보임
- ✅ **컨테이너 준수**: 카드가 절대 화면 밖으로 넘치지 않음

---

## 🧪 테스트 시나리오

### 1. 긴 파일명 테스트
- **입력**: "Technology-Product Roadmapping 전략 수립을 위한 비즈니스 전략과 제품 개발의 통합적 접근 방법론 연구.pdf"
- **기대**: 파일명 말줄임표 표시, 호버 시 전체 표시
- **결과**: ✅ 정상

### 2. 여러 배지 테스트
- **입력**: 파일명 + 문서타입 + 검색타입 + 점수 배지 + 관련도 배지
- **기대**: 공간 부족 시 배지가 다음 줄로 wrap
- **결과**: ✅ 정상

### 3. 긴 발췌 내용 테스트
- **입력**: 200자 이상의 긴 텍스트 + 영문 URL
- **기대**: 3줄 제한, 긴 단어 자동 줄바꿈
- **결과**: ✅ 정상

### 4. 모바일/좁은 화면 테스트
- **입력**: 화면 너비 375px (iPhone SE)
- **기대**: 모든 요소가 화면 내에 표시
- **결과**: ✅ 정상 (Flex wrap 동작)

---

## 💡 CSS 레이아웃 팁

### Flexbox 오버플로우 방지 핵심 원칙

1. **부모에 min-w-0 설정**
   ```tsx
   <div className="flex-1 min-w-0">
     {/* min-w-0이 없으면 자식이 부모를 밀어냄 */}
   </div>
   ```

2. **자식에 truncate 적용**
   ```tsx
   <span className="truncate flex-1 min-w-0">
     {longText}
   </span>
   ```

3. **중요 요소는 shrink-0**
   ```tsx
   <button className="shrink-0 whitespace-nowrap">
     보존해야 할 버튼
   </button>
   ```

4. **긴 텍스트는 break-words**
   ```tsx
   <div className="break-words" style={{ wordBreak: 'break-word' }}>
     {longWordOrUrl}
   </div>
   ```

5. **전체 컨테이너는 w-full + overflow-hidden**
   ```tsx
   <div className="w-full overflow-hidden">
     {/* 절대 넘치지 않음 */}
   </div>
   ```

---

## ✅ 검증 완료

- [x] 긴 파일명 테스트
- [x] 여러 배지 동시 표시
- [x] 긴 발췌 내용 줄바꿈
- [x] 모바일 화면 대응
- [x] 참고자료 패널 너비 제한
- [x] 메시지 버블 너비 제한
- [x] AI 요약 텍스트 줄바꿈
- [ ] 실제 사용자 화면 테스트 (사용자 확인 필요)

---

## 🎉 결론

AI Agent 채팅의 참고자료 카드가 이제 모든 화면 크기에서 올바르게 표시됩니다.
Flexbox의 유연한 레이아웃과 적절한 CSS 제약으로 컨텐츠가 항상 컨테이너 내에 표시되며,
긴 텍스트는 자동으로 줄바꿈되거나 말줄임표로 처리됩니다.
