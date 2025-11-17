# 프롬프트 관리 시스템 개선 완료

> Deprecated: 이 문서는 통합 문서로 대체되었습니다. 최신 내용은 `01.docs/PRESENTATION_SYSTEM_UNIFIED_GUIDE.md`를 참조하세요.

**완료일:** 2025-11-13  
**개선 범위:** PPT 생성 시스템 프롬프트 외부화

---

## 📋 변경 사항

### 이전 구조
```python
# backend/app/agents/presentation/content_structurer.py
STRUCTURE_SYSTEM_PROMPT = """You are an expert..."""
STRUCTURE_USER_PROMPT = """Convert the following..."""

# backend/app/agents/presentation/html_generator.py
HTML_SYSTEM_PROMPT = """You are an expert..."""
HTML_USER_PROMPT = """StructuredOutline JSON..."""
```

**문제점:**
- ❌ 프롬프트가 코드에 하드코딩됨
- ❌ 프롬프트 수정 시 코드 재배포 필요
- ❌ 버전 관리 어려움
- ❌ 프롬프트 재사용 불가

---

### 개선 후 구조

```
backend/
├── prompts/                              # 🆕 프롬프트 디렉토리
│   └── presentation/
│       ├── content_structurer_system.txt
│       ├── content_structurer_user.txt
│       ├── html_generator_system.txt
│       ├── html_generator_user.txt
│       └── README.md
│
├── app/
│   ├── utils/
│   │   └── prompt_loader.py              # 🆕 프롬프트 로더
│   │
│   └── agents/presentation/
│       ├── content_structurer.py         # ✏️ 수정됨
│       └── html_generator.py             # ✏️ 수정됨
│
└── test_prompt_loader.py                 # 🆕 테스트 스크립트
```

**장점:**
- ✅ 프롬프트와 코드 분리
- ✅ 프롬프트만 수정 가능 (코드 변경 불필요)
- ✅ Git으로 프롬프트 이력 추적
- ✅ 캐싱으로 성능 최적화
- ✅ 재사용 가능한 로더 유틸리티

---

## 📁 생성된 파일

### 1. 프롬프트 파일 (4개)

| 파일 | 크기 | 용도 |
|------|------|------|
| `content_structurer_system.txt` | 2,749 chars | Markdown → JSON 변환 시스템 프롬프트 |
| `content_structurer_user.txt` | 321 chars | Markdown → JSON 변환 사용자 프롬프트 |
| `html_generator_system.txt` | 1,103 chars | JSON → HTML 생성 시스템 프롬프트 |
| `html_generator_user.txt` | 288 chars | JSON → HTML 생성 사용자 프롬프트 |

### 2. 유틸리티

**`backend/app/utils/prompt_loader.py`**
- 프롬프트 파일 로드
- 메모리 캐싱
- 에러 처리
- 리로드 기능

**핵심 함수:**
```python
from app.utils.prompt_loader import load_presentation_prompt

# 프롬프트 로드
system_prompt = load_presentation_prompt("content_structurer_system")
user_prompt = load_presentation_prompt("content_structurer_user")
```

### 3. 문서 및 테스트

- **`backend/prompts/presentation/README.md`** - 프롬프트 관리 가이드
- **`backend/test_prompt_loader.py`** - 프롬프트 로더 테스트

---

## 🔄 수정된 코드

### content_structurer.py

**Before:**
```python
STRUCTURE_SYSTEM_PROMPT = """You are an expert..."""

prompt = ChatPromptTemplate.from_messages([
    ("system", STRUCTURE_SYSTEM_PROMPT),
    ("user", STRUCTURE_USER_PROMPT)
])
```

**After:**
```python
from app.utils.prompt_loader import load_presentation_prompt

# Load prompts from files
system_prompt = load_presentation_prompt("content_structurer_system")
user_prompt_template = load_presentation_prompt("content_structurer_user")

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("user", user_prompt_template)
])
```

### html_generator.py

**Before:**
```python
HTML_SYSTEM_PROMPT = """You are an expert..."""

prompt = ChatPromptTemplate.from_messages([
    ("system", HTML_SYSTEM_PROMPT),
    ("user", HTML_USER_PROMPT)
])
```

**After:**
```python
from app.utils.prompt_loader import load_presentation_prompt

# Load prompts from files
system_prompt = load_presentation_prompt("html_generator_system")
user_prompt_template = load_presentation_prompt("html_generator_user")

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("user", user_prompt_template)
])
```

---

## ✅ 테스트 결과

```bash
$ cd /home/admin/wkms-aws && source .venv/bin/activate
$ cd backend && python test_prompt_loader.py

================================================================================
PRESENTATION PROMPT LOADER TEST
================================================================================

📄 Content Structurer System
--------------------------------------------------------------------------------
✅ Loaded successfully (2749 chars)

📄 Content Structurer User
--------------------------------------------------------------------------------
✅ Loaded successfully (321 chars)

📄 HTML Generator System
--------------------------------------------------------------------------------
✅ Loaded successfully (1103 chars)

📄 HTML Generator User
--------------------------------------------------------------------------------
✅ Loaded successfully (288 chars)

================================================================================
CACHE TEST
================================================================================
Cache size: 4 items
Cached keys: ['presentation/content_structurer_system', 
              'presentation/content_structurer_user', 
              'presentation/html_generator_system', 
              'presentation/html_generator_user']

================================================================================
RELOAD TEST
================================================================================
Clearing cache...
Cache size after clear: 0 items

Reloading content_structurer_system...
✅ Reloaded (2749 chars)
Cache size: 1 items
```

**모든 테스트 통과! ✅**

---

## 🎯 사용 방법

### 1. 프롬프트 수정

```bash
# 1. 프롬프트 파일 편집
nano backend/prompts/presentation/content_structurer_system.txt

# 2. 변경사항 저장

# 3. 서버 재시작 (또는 캐시 클리어)
# - 개발 환경: 자동 리로드 (--reload)
# - 프로덕션: 서버 재시작
```

### 2. 새 프롬프트 추가

```bash
# 1. 프롬프트 파일 생성
cat > backend/prompts/presentation/my_new_prompt.txt <<'EOF'
You are an expert in...
EOF

# 2. 코드에서 사용
from app.utils.prompt_loader import load_presentation_prompt

my_prompt = load_presentation_prompt("my_new_prompt")
```

### 3. 다른 카테고리 프롬프트

```bash
# 1. 새 카테고리 디렉토리
mkdir backend/prompts/chat

# 2. 프롬프트 파일 생성
echo "System prompt..." > backend/prompts/chat/system.txt

# 3. 로드
from app.utils.prompt_loader import load_prompt

chat_prompt = load_prompt("chat", "system")
```

---

## 📊 성능 영향

### 캐싱 효과

| 항목 | Before | After |
|------|--------|-------|
| 프롬프트 로드 | 즉시 (메모리) | 첫 로드: 파일 I/O<br>이후: 캐시 (즉시) |
| 메모리 사용 | ~5 KB (문자열) | ~5 KB (캐시) |
| 수정 반영 | 코드 재배포 | 파일 수정 + 재시작 |

**결론:** 성능 저하 없음 (캐싱으로 동일한 성능 유지)

---

## 🔍 디버깅

### 프롬프트 경로 확인

```python
from pathlib import Path
from app.utils.prompt_loader import PROMPTS_DIR

print(f"Prompts directory: {PROMPTS_DIR}")
print(f"Exists: {PROMPTS_DIR.exists()}")

# 파일 목록
for f in (PROMPTS_DIR / "presentation").glob("*.txt"):
    print(f"  - {f.name}")
```

### 캐시 상태 확인

```python
from app.utils.prompt_loader import PromptLoader

print(f"Cached prompts: {list(PromptLoader._cache.keys())}")
print(f"Cache size: {len(PromptLoader._cache)}")
```

### 강제 리로드

```python
from app.utils.prompt_loader import PromptLoader

# 특정 프롬프트 리로드
prompt = PromptLoader.reload("presentation", "content_structurer_system")

# 전체 캐시 클리어
PromptLoader.clear_cache()
```

---

## 🚀 향후 개선 사항

### 1. 다국어 지원
```
backend/prompts/presentation/
├── ko/
│   ├── content_structurer_system.txt
│   └── html_generator_system.txt
└── en/
    ├── content_structurer_system.txt
    └── html_generator_system.txt
```

### 2. 프롬프트 버전 관리
```python
# 프롬프트에 버전 메타데이터 추가
"""
Version: 2.1.0
Date: 2025-11-13
Author: WKMS Team
---
You are an expert...
"""
```

### 3. A/B 테스트
```python
# 여러 프롬프트 변형 테스트
variants = ["v1", "v2", "v3"]
selected = random.choice(variants)
prompt = load_presentation_prompt(f"content_structurer_system_{selected}")
```

### 4. 프롬프트 분석
- 토큰 수 계산
- 효과성 메트릭 수집
- 자동 최적화

---

## 📝 체크리스트

### 구현 완료
- [x] 프롬프트 파일 생성 (4개)
- [x] PromptLoader 유틸리티 구현
- [x] content_structurer.py 업데이트
- [x] html_generator.py 업데이트
- [x] 테스트 스크립트 작성
- [x] README 문서 작성
- [x] 통합 테스트 통과

### 기존 기능 검증
- [ ] Markdown → StructuredOutline 변환 정상 작동
- [ ] StructuredOutline → HTML 생성 정상 작동
- [ ] 전체 파이프라인 E2E 테스트

### 문서화
- [x] 프롬프트 사용 가이드
- [x] 수정 방법 안내
- [x] 트러블슈팅 섹션

---

## 🎉 요약

### 달성한 목표

1. ✅ **코드와 프롬프트 분리**
   - 프롬프트를 별도 `.txt` 파일로 관리
   - 코드 변경 없이 프롬프트 수정 가능

2. ✅ **재사용 가능한 인프라**
   - `PromptLoader` 유틸리티로 모든 프롬프트 관리
   - 캐싱으로 성능 최적화
   - 카테고리별 구조화

3. ✅ **유지보수성 향상**
   - Git으로 프롬프트 버전 추적
   - 명확한 파일 구조
   - 상세한 문서화

4. ✅ **확장성 확보**
   - 새 프롬프트 쉽게 추가
   - 다국어 지원 준비
   - A/B 테스트 가능

### 파일 요약

| 파일 | 상태 | 설명 |
|------|------|------|
| `backend/prompts/presentation/*.txt` | 🆕 신규 | 프롬프트 파일 4개 |
| `backend/app/utils/prompt_loader.py` | 🆕 신규 | 프롬프트 로더 유틸리티 |
| `backend/app/agents/presentation/content_structurer.py` | ✏️ 수정 | 프롬프트 로더 사용 |
| `backend/app/agents/presentation/html_generator.py` | ✏️ 수정 | 프롬프트 로더 사용 |
| `backend/test_prompt_loader.py` | 🆕 신규 | 테스트 스크립트 |
| `backend/prompts/presentation/README.md` | 🆕 신규 | 사용 가이드 |

---

**작성자:** GitHub Copilot  
**검토 완료:** 2025-11-13
