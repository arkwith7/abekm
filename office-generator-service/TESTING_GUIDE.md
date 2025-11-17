# Office Generator 테스트 가이드

## 📁 준비된 테스트 파일

### 1. 샘플 JSON 파일

#### `test-samples/simple-test.json`
- **용도:** 기본 기능 테스트
- **슬라이드:** 3개 (title, bullets, title)
- **추천:** 첫 테스트용

#### `test-samples/sample-structured-outline.json`
- **용도:** 전체 기능 테스트
- **슬라이드:** 7개 (모든 레이아웃 타입 포함)
- **추천:** 완전한 기능 검증용

---

## 🚀 테스트 방법

### 방법 1: 자동 테스트 스크립트 (추천)

```bash
cd office-generator-service

# Office Generator 서비스 시작 (별도 터미널)
npm start

# 간단한 테스트
./test-pptx-convert.sh test-samples/simple-test.json

# 전체 기능 테스트
./test-pptx-convert.sh test-samples/sample-structured-outline.json
```

**결과:**
- ✅ 성공 시: `test-output/test_YYYYMMDD_HHMMSS.pptx` 생성
- ❌ 실패 시: 에러 메시지 출력

---

### 방법 2: curl 직접 사용

```bash
# Office Generator 시작 확인
curl http://localhost:3001/api/pptx/health

# PPTX 생성 요청
curl -X POST http://localhost:3001/api/pptx/convert \
  -H "Content-Type: application/json" \
  -d @- <<'EOF' \
  --output test-output/manual-test.pptx
{
  "outlineJson": {
    "title": "수동 테스트",
    "theme": "business",
    "slides": [
      {
        "title": "제목 슬라이드",
        "content": "부제목",
        "layout": "title",
        "visual_elements": null
      },
      {
        "title": "내용",
        "content": "",
        "layout": "title-and-bullets",
        "visual_elements": {
          "icons": ["check", "star"],
          "bullets": ["항목 1", "항목 2"],
          "grid": null,
          "image": null
        }
      }
    ],
    "metadata": {
      "author": "Test User"
    }
  }
}
EOF
```

---

### 방법 3: Postman / Insomnia 사용

**설정:**
- **Method:** POST
- **URL:** `http://localhost:3001/api/pptx/convert`
- **Headers:** `Content-Type: application/json`
- **Body (raw JSON):**

```json
{
  "outlineJson": {
    "title": "Postman 테스트",
    "theme": "modern",
    "slides": [
      {
        "title": "시작",
        "content": "Postman으로 테스트",
        "layout": "title",
        "visual_elements": null
      }
    ]
  }
}
```

**응답 설정:**
- **Save Response:** "Save to file"로 설정
- **파일명:** `test.pptx`

---

### 방법 4: Python 스크립트

```python
import requests
import json

# JSON 파일 로드
with open('test-samples/simple-test.json', 'r') as f:
    outline_json = json.load(f)

# 요청 페이로드
payload = {
    "outlineJson": outline_json,
    "options": {
        "theme": "business"
    }
}

# Office Generator 호출
response = requests.post(
    'http://localhost:3001/api/pptx/convert',
    json=payload,
    timeout=60
)

# PPTX 저장
if response.status_code == 200:
    with open('test-output/python-test.pptx', 'wb') as f:
        f.write(response.content)
    print(f"✓ PPTX 생성 완료: {len(response.content)} bytes")
else:
    print(f"✗ 실패: HTTP {response.status_code}")
    print(response.text)
```

---

## 🎨 레이아웃 타입별 테스트

### 1. Title Slide
```json
{
  "title": "제목",
  "content": "부제목",
  "layout": "title",
  "visual_elements": null
}
```

### 2. Title and Bullets
```json
{
  "title": "불릿 포인트",
  "content": "",
  "layout": "title-and-bullets",
  "visual_elements": {
    "icons": ["check", "arrow-right", "star"],
    "bullets": ["항목 1", "항목 2", "항목 3"],
    "grid": null,
    "image": null
  }
}
```

### 3. Two-Column Grid
```json
{
  "title": "그리드 레이아웃",
  "content": "",
  "layout": "two-column-grid",
  "visual_elements": {
    "icons": [],
    "bullets": [],
    "grid": {
      "cols": 2,
      "items": [
        {"title": "항목 1", "description": "설명 1", "bg_color": "blue-50"},
        {"title": "항목 2", "description": "설명 2", "bg_color": "green-50"}
      ]
    },
    "image": null
  }
}
```

### 4. Divider
```json
{
  "title": "섹션 구분",
  "content": "부제목 (선택)",
  "layout": "divider",
  "visual_elements": null
}
```

### 5. Image Placeholder
```json
{
  "title": "이미지 슬라이드",
  "content": "",
  "layout": "image-placeholder",
  "visual_elements": {
    "icons": [],
    "bullets": [],
    "grid": null,
    "image": {
      "url": "placeholder",
      "alt": "이미지 설명",
      "width": null,
      "height": null
    }
  }
}
```

---

## 🔍 테스트 체크리스트

### 기본 기능
- [ ] Office Generator 서비스 시작됨 (`npm start`)
- [ ] Health check 응답 확인 (`/api/pptx/health`)
- [ ] 간단한 JSON으로 PPTX 생성 성공
- [ ] 생성된 PPTX 파일 PowerPoint에서 열림

### 레이아웃 테스트
- [ ] Title 레이아웃 정상 렌더링
- [ ] Title-and-bullets 레이아웃 정상 렌더링
- [ ] Two-column-grid 레이아웃 정상 렌더링
- [ ] Divider 레이아웃 정상 렌더링
- [ ] Image-placeholder 레이아웃 정상 렌더링

### 아이콘 테스트
- [ ] 아이콘 매핑 정상 작동 (check → ✓)
- [ ] 여러 아이콘 동시 표시
- [ ] 지원하지 않는 아이콘 → 기본 아이콘 (•)

### 에러 처리
- [ ] 잘못된 JSON → 400 에러
- [ ] 누락된 필드 → 명확한 에러 메시지
- [ ] 지원하지 않는 layout → 기본 슬라이드

---

## 📊 예상 결과

### 성공 시
```
HTTP 200 OK
Content-Type: application/vnd.openxmlformats-officedocument.presentationml.presentation
Content-Disposition: attachment; filename="프레젠테이션제목.pptx"
Content-Length: 123456
X-Generation-Time-Ms: 856

[Binary PPTX Data]
```

### 실패 시
```json
{
  "error": "Invalid StructuredOutline: title is required",
  "statusCode": 400
}
```

---

## 🐛 트러블슈팅

### 1. "Office Generator is not running"
```bash
cd office-generator-service
npm install
npm start
```

### 2. "Module not found"
```bash
cd office-generator-service
npm install
```

### 3. "Invalid JSON"
- JSON 파일 문법 확인
- [jsonlint.com](https://jsonlint.com)에서 검증

### 4. "Empty PPTX"
- `slides` 배열이 비어있는지 확인
- 최소 1개 이상의 슬라이드 필요

---

## 📝 커스텀 JSON 만들기

### 템플릿
```json
{
  "title": "내 프레젠테이션",
  "theme": "business",
  "slides": [
    {
      "title": "슬라이드 제목",
      "content": "부제목 (선택)",
      "layout": "title|title-and-bullets|two-column-grid|divider|image-placeholder",
      "visual_elements": {
        "icons": ["아이콘명1", "아이콘명2"],
        "bullets": ["텍스트1", "텍스트2"],
        "grid": { "cols": 2, "items": [...] },
        "image": { "url": "...", "alt": "..." }
      }
    }
  ],
  "metadata": {
    "author": "작성자",
    "company": "회사명"
  }
}
```

### 지원 아이콘
`check`, `star`, `heart`, `arrow-right`, `trending-up`, `target`, `award`, `users`, `briefcase`, `calendar`, `clock`, `mail`, `phone`, `settings`, `search`, `download`, `upload`, `wifi`, `battery`, `thumbs-up` 등 100+

---

## 🎯 다음 단계

테스트 성공 후:
1. Backend 통합 테스트 (`backend/app/services/office_generator_client.py`)
2. 전체 파이프라인 테스트 (Markdown → JSON → PPTX)
3. Frontend 연동
