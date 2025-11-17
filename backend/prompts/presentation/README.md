# Presentation Prompts

이 디렉토리는 PPT 생성 파이프라인에서 사용하는 LLM 프롬프트를 관리합니다.

## 📁 파일 구조

```
backend/prompts/presentation/
├── content_structurer_system.txt    # StructuredOutline 생성 시스템 프롬프트
├── content_structurer_user.txt      # StructuredOutline 생성 사용자 프롬프트
├── html_generator_system.txt        # HTML 생성 시스템 프롬프트
├── html_generator_user.txt          # HTML 생성 사용자 프롬프트
└── README.md                         # 본 문서
```

## 🎯 프롬프트 용도

### 1. Content Structurer Prompts

**파일:** `content_structurer_system.txt`, `content_structurer_user.txt`

**역할:** Markdown → StructuredOutline JSON 변환

**사용 위치:** `backend/app/agents/presentation/content_structurer.py`

**시스템 프롬프트 내용:**
- 프레젠테이션 디자이너 역할 정의
- 슬라이드 구성 가이드라인 (title, bullets, grid 등)
- Layout 타입별 사용 시나리오
- Visual elements 활용법 (icons, bullets, grid, image)
- 콘텐츠 품질 기준
- 예제 JSON 구조

**사용자 프롬프트 내용:**
- 입력 Markdown 전달
- 최대 슬라이드 수 제한
- 타겟 청중 정보
- 프레젠테이션 스타일

### 2. HTML Generator Prompts

**파일:** `html_generator_system.txt`, `html_generator_user.txt`

**역할:** StructuredOutline JSON → Interactive HTML

**사용 위치:** `backend/app/agents/presentation/html_generator.py`

**시스템 프롬프트 내용:**
- 프론트엔드 엔지니어 역할 정의
- HTML 문서 구조 요구사항 (DOCTYPE, self-contained)
- Tailwind CSS + Lucide Icons 사용
- 슬라이드 네비게이션 구현
- 테마 색상 적용
- 한국어 UI 로컬라이제이션

**사용자 프롬프트 내용:**
- StructuredOutline JSON 전달
- Base template 참조 제공
- HTML 생성 요청

## 🔧 사용 방법

### 코드에서 프롬프트 로드

```python
from app.utils.prompt_loader import load_presentation_prompt

# 프롬프트 로드
system_prompt = load_presentation_prompt("content_structurer_system")
user_prompt = load_presentation_prompt("content_structurer_user")

# LangChain 프롬프트 템플릿에 사용
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("user", user_prompt)
])
```

### 프롬프트 변수 치환

사용자 프롬프트는 변수를 포함할 수 있습니다:

```python
# content_structurer_user.txt에는 {markdown}, {max_slides} 등의 변수 포함
messages = prompt.format_messages(
    markdown="## 제목\n내용...",
    max_slides=15,
    audience="general",
    style="business"
)
```

## ✏️ 프롬프트 수정

### 1. 파일 직접 편집

```bash
# 시스템 프롬프트 수정
nano backend/prompts/presentation/content_structurer_system.txt

# 변경사항 저장 후 서버 재시작
```

### 2. 프롬프트 캐시

프롬프트는 메모리에 캐시됩니다. 수정 사항을 반영하려면:

**옵션 1: 서버 재시작**
```bash
# 개발 환경
Ctrl+C (서버 종료)
python -m uvicorn app.main:app --reload
```

**옵션 2: 캐시 클리어 (개발용)**
```python
from app.utils.prompt_loader import PromptLoader

# 캐시 초기화
PromptLoader.clear_cache()

# 또는 특정 프롬프트만 리로드
PromptLoader.reload("presentation", "content_structurer_system")
```

## 📝 프롬프트 작성 가이드

### 1. 명확한 역할 정의

```txt
You are an expert [role] specializing in [specialty].

Your task is to [clear objective].
```

### 2. 구조화된 가이드라인

```txt
## Guidelines:

1. **Section Name:**
   - Bullet point 1
   - Bullet point 2

2. **Another Section:**
   - ...
```

### 3. 구체적인 예제 제공

```txt
## Example:
```json
{
  "field": "value",
  ...
}
```
```

### 4. 제약사항 명시

```txt
## Constraints:
- Maximum X items
- Use only Y format
- Must include Z
```

### 5. 출력 형식 지정

```txt
## Output Format:
Return a valid JSON object matching the [SchemaName] schema.
```

## 🎨 프롬프트 최적화 팁

### 1. 명확성 우선
- 모호한 표현 제거
- 구체적인 예제 포함
- 기대하는 출력 형식 명시

### 2. 컨텍스트 제공
- 배경 정보 제공 (왜 이 작업이 필요한가?)
- 제약사항 명확히 (토큰 제한, 슬라이드 수 등)

### 3. 반복 최소화
- 중복 지침 제거
- 핵심 내용에 집중

### 4. 테스트 및 개선
- 다양한 입력으로 테스트
- 실패 케이스 분석
- 점진적 개선

## 🔍 트러블슈팅

### 문제: 프롬프트 변경이 반영 안 됨

**해결책:**
```bash
# 서버 재시작
pkill -f uvicorn
python -m uvicorn app.main:app --reload
```

### 문제: FileNotFoundError

**원인:** 프롬프트 파일 경로가 잘못됨

**해결책:**
```python
# 올바른 파일 위치 확인
# backend/prompts/presentation/[prompt_name].txt

# 파일 존재 확인
ls -la backend/prompts/presentation/
```

### 문제: 변수 치환 오류

**원인:** 프롬프트 템플릿의 변수명과 코드의 변수명 불일치

**해결책:**
```python
# 프롬프트 파일의 {변수명}과
# format_messages(변수명=값) 일치 확인
```

## 📊 버전 관리

### Git에서 프롬프트 추적

```bash
# 변경사항 확인
git diff backend/prompts/presentation/

# 변경사항 커밋
git add backend/prompts/presentation/
git commit -m "feat: Update content structurer prompt for better icon usage"
```

### 프롬프트 버전 히스토리

```bash
# 특정 프롬프트의 변경 이력
git log --follow backend/prompts/presentation/content_structurer_system.txt

# 이전 버전으로 롤백
git checkout <commit-hash> backend/prompts/presentation/content_structurer_system.txt
```

## 🚀 새 프롬프트 추가

### 1. 프롬프트 파일 생성

```bash
# 새 카테고리 디렉토리
mkdir -p backend/prompts/new_category

# 프롬프트 파일
touch backend/prompts/new_category/my_prompt_system.txt
touch backend/prompts/new_category/my_prompt_user.txt
```

### 2. 프롬프트 내용 작성

```txt
# my_prompt_system.txt
You are an expert in [domain].

Your task is to [objective].

## Guidelines:
...
```

### 3. 코드에서 사용

```python
from app.utils.prompt_loader import load_prompt

system_prompt = load_prompt("new_category", "my_prompt_system")
user_prompt = load_prompt("new_category", "my_prompt_user")
```

## 📚 관련 문서

- **아키텍처:** `/home/admin/wkms-aws/01.docs/PPT_GENERATION_ARCHITECTURE.md`
- **구현 현황:** `/home/admin/wkms-aws/01.docs/PPT_IMPLEMENTATION_COMPLETE.md`
- **Prompt Loader:** `/home/admin/wkms-aws/backend/app/utils/prompt_loader.py`

---

**관리자:** WKMS 개발팀  
**최종 업데이트:** 2025-11-13
