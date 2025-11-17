# PPT 생성 아키텍처 설계서

> Deprecated: 이 문서는 통합 문서로 대체되었습니다. 최신 내용은 `01.docs/PRESENTATION_SYSTEM_UNIFIED_GUIDE.md`를 참조하세요.

**작성일:** 2025-11-13  
**작성자:** AI Assistant  
**버전:** 1.0  
**상태:** 구현 중

---

## 📋 목차

1. [개요](#1-개요)
2. [사용자 시나리오](#2-사용자-시나리오)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [데이터 흐름](#4-데이터-흐름)
5. [모듈별 역할 정의](#5-모듈별-역할-정의)
6. [API 명세](#6-api-명세)
7. [데이터 모델](#7-데이터-모델)
8. [구현 계획](#8-구현-계획)
9. [변경 이력](#9-변경-이력)

---

## 1. 개요

### 1.1 목적

AI Agent 채팅에서 사용자의 추상적인 요청을 받아 **마크다운 → HTML 프리뷰 → PPTX 파일** 형태로 프레젠테이션을 생성하는 시스템 구축

### 1.2 핵심 설계 원칙

| 원칙 | 설명 |
|------|------|
| **모듈 독립성** | Frontend, Backend, Office Generator는 독립적으로 배포/확장 가능 |
| **설정 기반 연계** | 하드코딩 제거, 환경변수/설정 파일로 서비스 통합 |
| **이중 출력** | HTML(프리뷰/편집용) + PPTX(다운로드용) 동시 제공 |
| **구조화 데이터 우선** | HTML 파싱 복잡도 회피, JSON 기반 변환 |
| **확장 가능성** | 레이아웃 템플릿 추가로 새 디자인 지원 |

### 1.3 기술 스택

| 영역 | 기술 | 역할 |
|------|------|------|
| **Frontend** | React.js, TypeScript | UI, 프리뷰, 다운로드 |
| **Backend** | FastAPI, Python 3.9+ | LLM 오케스트레이션, 파일 관리 |
| **Office Generator** | Node.js 18+, PptxGenJS | HTML/JSON → PPTX 변환 |
| **LLM** | GPT-4 (Azure OpenAI) | 컨텐츠 구조화, HTML 생성 |
| **Database** | PostgreSQL, Redis | 데이터 저장, 캐싱 |

---

## 2. 사용자 시나리오

### 2.1 End-to-End 시나리오

```
[사용자] AI Agent 채팅창에서 자료 요청
   ↓
   "이번 분기 실적 분석을 PPT로 만들어줘"
   ↓
[LLM Step 1] 마크다운 형태로 구조화된 답변 생성
   ↓
   ## 분기 실적 분석
   - 매출 증가율: 15%
   - 주요 성과: ...
   ↓
[사용자] 채팅 화면에서 "PPT 생성" 버튼 클릭
   ↓
[LLM Step 2] 마크다운 → Structured Outline (JSON)
   ↓
   {
     "title": "2025 Q3 실적 분석",
     "slides": [
       {
         "title": "매출 현황",
         "layout": "title-and-bullets",
         "visual_elements": {
           "bullets": ["매출 증가율 15%", ...],
           "icons": ["trending-up", "dollar-sign"]
         }
       }
     ]
   }
   ↓
[LLM Step 3] Structured Outline → Interactive HTML
   ↓
   <!DOCTYPE html>
   <html>
     <!-- Tailwind CSS, Lucide Icons -->
     <script>
       const slides = [
         { title: "매출 현황", content: `...` }
       ];
     </script>
   </html>
   ↓
[Backend] HTML 파일 저장 (/uploads/presentations/xxx.html)
   ↓
[Frontend] HTML 프리뷰 표시 (선택적 편집 가능)
   ↓
[사용자] "PPTX로 변환" 버튼 클릭
   ↓
[Office Generator] Structured Data → PPTX 변환
   ↓
[Backend] PPTX 파일 저장 (/uploads/presentations/xxx.pptx)
   ↓
[Frontend] 다운로드 링크 표시
   ↓
[사용자] PPT 파일 다운로드 완료
```

### 2.2 사용자 경험 흐름

```
┌─────────────────────────────────────────────────────────┐
│ AI Agent 채팅 UI                                        │
│                                                         │
│ 🤖 AI: "2025 Q3 실적 분석 자료를 정리했습니다."        │
│                                                         │
│ ## 매출 현황                                            │
│ - 매출 증가율: 15%                                      │
│ - 전년 대비: +2.3B 원                                   │
│                                                         │
│ [🎨 PPT 생성] [📊 차트 포함] [🎯 비즈니스 스타일]      │
└─────────────────────────────────────────────────────────┘
                      ↓ 클릭
┌─────────────────────────────────────────────────────────┐
│ 프리뷰 모달                                             │
│                                                         │
│ ┌─────────────────────────────────────────────────┐   │
│ │ [← →] 슬라이드 1/8                              │   │
│ │                                                 │   │
│ │   📊 2025 Q3 실적 분석                          │   │
│ │   ─────────────────────                        │   │
│ │   • 매출 증가율 15%                             │   │
│ │   • 전년 대비 +2.3B 원                          │   │
│ └─────────────────────────────────────────────────┘   │
│                                                         │
│ [🔄 HTML 편집] [💾 PPTX 다운로드] [❌ 닫기]           │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 시스템 아키텍처

### 3.1 전체 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                    Configuration Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Frontend     │  │ Backend      │  │ Office Gen   │       │
│  │ .env         │  │ config.py    │  │ config/      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│   Frontend   │───▶│   Backend API    │───▶│ Office Gen   │
│   React.js   │    │   FastAPI        │    │  Node.js     │
│              │    │                  │    │              │
│ Roles:       │    │ Roles:           │    │ Roles:       │
│ - UI/UX      │    │ - LLM Orchestr.  │    │ - HTML→PPTX  │
│ - 프리뷰     │    │ - File Mgmt      │    │ - JSON→PPTX  │
│ - 다운로드   │    │ - Auth           │    │ - Layout Eng │
└──────────────┘    └──────────────────┘    └──────────────┘
        │                     │                     │
        │            ┌────────┴────────┐            │
        │            ▼                 ▼            │
        │    ┌──────────────┐  ┌──────────────┐    │
        │    │  PostgreSQL  │  │    Redis     │    │
        │    │   (Data)     │  │  (Cache)     │    │
        │    └──────────────┘  └──────────────┘    │
        │                                           │
        └───────────────────────────────────────────┘
         파일 다운로드 (/api/v1/presentations/download)
```

### 3.2 레이어별 책임

#### 3.2.1 Frontend Layer

| 컴포넌트 | 책임 | 기술 |
|---------|------|------|
| **AI Agent Chat** | 사용자 대화 인터페이스 | React, TypeScript |
| **PPT Generation Panel** | 스타일 선택, 옵션 설정 | React State Management |
| **HTML Preview Modal** | iframe 기반 HTML 프리뷰 | React Modal |
| **Download Manager** | 파일 다운로드 처리 | Fetch API |

#### 3.2.2 Backend Layer

| 모듈 | 책임 | 위치 |
|------|------|------|
| **Presentation Agent** | 요청 라우팅, 에이전트 실행 | `/agents/presentation/` |
| **Content Structurer** | 마크다운 → JSON 변환 (LLM) | `/agents/presentation/content_structurer.py` |
| **HTML Generator** | JSON → HTML 생성 (LLM) | `/agents/presentation/html_generator.py` |
| **Office Generator Client** | Node.js 서비스 HTTP 호출 | `/clients/office_generator_client.py` |
| **Service Registry** | 외부 서비스 설정 관리 | `/core/service_registry.py` |
| **File Manager** | 파일 저장/조회/삭제 | `/services/file_manager.py` |

#### 3.2.3 Office Generator Layer

| 모듈 | 책임 | 위치 |
|------|------|------|
| **API Routes** | HTTP 엔드포인트 | `/src/routes/pptx.routes.js` |
| **Structured Converter** | JSON → PPTX 변환 | `/src/converters/structured-to-pptx.js` |
| **Layout Templates** | 슬라이드 레이아웃 정의 | `/src/templates/layout-templates.js` |
| **Icon Fetcher** | Lucide 아이콘 SVG 다운로드 | `/src/utils/icon-fetcher.js` |
| **Theme Manager** | 색상 테마 관리 | `/src/generators/pptx/theme-manager.js` |

---

## 4. 데이터 흐름

### 4.1 상세 데이터 파이프라인

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: 사용자 요청                                     │
│                                                         │
│ POST /api/v1/agent/presentation/generate                │
│ {                                                       │
│   "session_id": "uuid",                                 │
│   "message_id": "msg_123",  // 마크다운 답변 메시지    │
│   "style": "business",                                  │
│   "output_format": "both"   // html | pptx | both      │
│ }                                                       │
└────────────┬────────────────────────────────────────────┘
             ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: Content Structuring (LLM Phase 1)              │
│                                                         │
│ Input: Markdown from message_id                        │
│ "## 실적 분석\n- 매출 15% 증가\n- ..."                 │
│                                                         │
│ LLM Prompt:                                             │
│ "마크다운을 슬라이드 구조로 변환하세요"                │
│                                                         │
│ Output: StructuredOutline                               │
│ {                                                       │
│   "title": "2025 Q3 실적 분석",                         │
│   "theme": "business",                                  │
│   "slides": [                                           │
│     {                                                   │
│       "title": "매출 현황",                             │
│       "content": "매출이 15% 증가했습니다.",            │
│       "layout": "title-and-bullets",                    │
│       "visual_elements": {                              │
│         "bullets": ["매출 15% 증가", "..."],            │
│         "icons": ["trending-up", "dollar-sign"],        │
│         "grid": null,                                   │
│         "image": null                                   │
│       }                                                 │
│     },                                                  │
│     {                                                   │
│       "title": "분기별 추이",                           │
│       "layout": "two-column-grid",                      │
│       "visual_elements": {                              │
│         "grid": {                                       │
│           "cols": 2,                                    │
│           "items": [                                    │
│             {"title": "Q1", "description": "..."},      │
│             {"title": "Q2", "description": "..."}       │
│           ]                                             │
│         }                                               │
│       }                                                 │
│     }                                                   │
│   ]                                                     │
│ }                                                       │
└────────────┬────────────────────────────────────────────┘
             ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: HTML Generation (LLM Phase 2)                  │
│                                                         │
│ Input: StructuredOutline (위 JSON)                      │
│                                                         │
│ LLM Prompt:                                             │
│ "ELLMER논문_HTML_PT.html 템플릿을 참고하여,             │
│  Tailwind CSS + Lucide Icons 기반                      │
│  완전한 HTML 프레젠테이션을 생성하세요."               │
│                                                         │
│ Output: Complete HTML File                              │
│ <!DOCTYPE html>                                         │
│ <html lang="ko">                                        │
│ <head>                                                  │
│   <script src="https://cdn.tailwindcss.com"></script>  │
│   <script src="https://unpkg.com/lucide@latest">       │
│   </script>                                             │
│ </head>                                                 │
│ <body>                                                  │
│   <div id="presentation-container">...</div>           │
│   <script>                                              │
│     const slides = [                                    │
│       { title: "매출 현황", content: `...` },          │
│       { title: "분기별 추이", content: `...` }         │
│     ];                                                  │
│     function renderSlide() { ... }                      │
│   </script>                                             │
│ </body>                                                 │
│ </html>                                                 │
└────────────┬────────────────────────────────────────────┘
             ▼
┌─────────────────────────────────────────────────────────┐
│ Step 4A: HTML 파일 저장 (if output_format = html/both) │
│                                                         │
│ File Path:                                              │
│ /uploads/presentations/2025Q3_analysis_abc123.html     │
│                                                         │
│ Response to Frontend:                                   │
│ {                                                       │
│   "html_url": "/api/v1/presentations/view/abc123.html",│
│   "preview_available": true                             │
│ }                                                       │
└────────────┬────────────────────────────────────────────┘
             │
             ▼ (if output_format = pptx/both)
┌─────────────────────────────────────────────────────────┐
│ Step 4B: PPTX 변환 요청                                 │
│                                                         │
│ Backend → Office Generator                              │
│ POST http://office-generator:3001/api/pptx/convert     │
│ {                                                       │
│   "slides": [  // StructuredOutline.slides             │
│     {                                                   │
│       "title": "매출 현황",                             │
│       "layout": "title-and-bullets",                    │
│       "visual_elements": { ... }                        │
│     }                                                   │
│   ],                                                    │
│   "metadata": {                                         │
│     "title": "2025 Q3 실적 분석",                       │
│     "author": "WKMS AI Agent",                          │
│     "theme": "business"                                 │
│   }                                                     │
│ }                                                       │
└────────────┬────────────────────────────────────────────┘
             ▼
┌─────────────────────────────────────────────────────────┐
│ Step 5: PPTX 생성 (Office Generator)                   │
│                                                         │
│ For each slide in slides:                              │
│   1. Layout Template 선택                               │
│      - layout = "title-and-bullets"                     │
│        → TitleAndBulletsLayout 인스턴스                │
│                                                         │
│   2. PptxGenJS 슬라이드 생성                            │
│      const slide = pptx.addSlide()                      │
│                                                         │
│   3. 레이아웃 적용                                      │
│      layout.apply(slide, slideData)                     │
│      → 제목 텍스트 추가 (x=0.5, y=0.5, ...)            │
│                                                         │
│   4. Visual Elements 추가                               │
│      - Icons: Lucide SVG 다운로드 → Base64 → addImage  │
│      - Bullets: addText with bullet=true                │
│      - Grid: 좌표 계산 → 반복 addText                  │
│                                                         │
│ Output: PPTX Binary Buffer                              │
└────────────┬────────────────────────────────────────────┘
             ▼
┌─────────────────────────────────────────────────────────┐
│ Step 6: PPTX 파일 저장                                  │
│                                                         │
│ Backend receives PPTX buffer                            │
│ Save to: /uploads/presentations/2025Q3_analysis.pptx   │
│                                                         │
│ Final Response to Frontend:                             │
│ {                                                       │
│   "html_url": "/api/v1/presentations/view/abc123.html",│
│   "pptx_url": "/api/v1/chat/presentation/download/     │
│                2025Q3_analysis.pptx",                   │
│   "preview_available": true,                            │
│   "slide_count": 8                                      │
│ }                                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 모듈별 역할 정의

### 5.1 Frontend (React.js)

#### 5.1.1 컴포넌트 구조

```
src/
├── pages/
│   └── user/
│       └── chat/
│           ├── AgentChatPage.tsx          # AI Agent 채팅 메인
│           └── components/
│               ├── MessageBubble.tsx      # 메시지 표시
│               ├── PresentationPanel.tsx  # PPT 생성 UI ⭐ 신규
│               └── PresentationPreview.tsx # HTML 프리뷰 모달 ⭐ 신규
├── services/
│   └── api/
│       └── presentationApi.ts             # API 호출 로직 ⭐ 신규
└── types/
    └── presentation.ts                    # 타입 정의 ⭐ 신규
```

#### 5.1.2 주요 기능

**PresentationPanel.tsx**
```typescript
interface PresentationPanelProps {
  messageId: string;
  sessionId: string;
  markdownContent: string;
}

const PresentationPanel: React.FC<PresentationPanelProps> = ({
  messageId,
  sessionId,
  markdownContent
}) => {
  const [style, setStyle] = useState<'business' | 'modern' | 'playful'>('business');
  const [outputFormat, setOutputFormat] = useState<'both'>('both');
  const [loading, setLoading] = useState(false);
  
  const handleGenerate = async () => {
    setLoading(true);
    
    const result = await generatePresentation({
      session_id: sessionId,
      message_id: messageId,
      style,
      output_format: outputFormat
    });
    
    if (result.html_url) {
      // HTML 프리뷰 모달 열기
      openPreview(result.html_url);
    }
    
    if (result.pptx_url) {
      // 다운로드 링크 표시
      showDownloadLink(result.pptx_url);
    }
  };
  
  return (
    <div className="flex gap-2">
      <select value={style} onChange={(e) => setStyle(e.target.value)}>
        <option value="business">비즈니스</option>
        <option value="modern">모던</option>
        <option value="playful">경쾌함</option>
      </select>
      
      <button onClick={handleGenerate} disabled={loading}>
        {loading ? '생성 중...' : '🎨 PPT 생성'}
      </button>
    </div>
  );
};
```

### 5.2 Backend (FastAPI)

#### 5.2.1 디렉토리 구조

```
backend/app/
├── agents/
│   └── presentation/
│       ├── __init__.py
│       ├── presentation_agent.py          # 기존 유지
│       ├── content_structurer.py          # ⭐ 신규
│       └── html_generator.py              # ⭐ 신규
├── clients/
│   └── office_generator_client.py         # ⭐ 신규
├── core/
│   ├── config.py                          # 수정
│   └── service_registry.py                # ⭐ 신규
├── api/
│   └── v1/
│       └── presentation.py                # 수정 (신규 엔드포인트 추가)
├── services/
│   └── file_manager.py                    # ⭐ 신규
└── models/
    └── presentation.py                    # ⭐ 신규 (Pydantic 모델)
```

#### 5.2.2 핵심 모듈 명세

**content_structurer.py**
```python
"""
Content Structurer - 마크다운 → 구조화된 JSON 변환
"""
from typing import List
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate

class StructuredSlide(BaseModel):
    title: str
    content: str
    layout: Literal["title", "title-and-bullets", "two-column-grid", "divider", "image-placeholder"]
    visual_elements: Optional[VisualElements] = None

class VisualElements(BaseModel):
    icons: List[str] = []
    bullets: List[str] = []
    grid: Optional[GridLayout] = None
    image: Optional[ImageSpec] = None

class StructuredOutline(BaseModel):
    title: str
    theme: str = "business"
    slides: List[StructuredSlide]

async def structure_markdown_to_outline(
    markdown: str,
    llm,
    max_slides: int = 15
) -> StructuredOutline:
    """
    LLM을 사용하여 마크다운을 구조화된 슬라이드 아웃라인으로 변환
    
    Args:
        markdown: 입력 마크다운 텍스트
        llm: LangChain LLM 인스턴스
        max_slides: 최대 슬라이드 수
    
    Returns:
        StructuredOutline 객체
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", STRUCTURE_SYSTEM_PROMPT),
        ("user", "{markdown}")
    ])
    
    # LLM 호출 (Structured Output)
    structured_llm = llm.with_structured_output(StructuredOutline)
    result = await structured_llm.ainvoke({
        "markdown": markdown,
        "max_slides": max_slides
    })
    
    return result
```

**html_generator.py**
```python
"""
HTML Generator - 구조화된 아웃라인 → Interactive HTML
"""
async def generate_presentation_html(
    outline: StructuredOutline,
    llm,
    template_path: str = "templates/presentation_base.html"
) -> str:
    """
    구조화된 아웃라인을 Tailwind CSS 기반 HTML 프레젠테이션으로 변환
    
    Args:
        outline: StructuredOutline 객체
        llm: LangChain LLM 인스턴스
        template_path: HTML 템플릿 파일 경로
    
    Returns:
        완전한 HTML 문자열
    """
    # HTML 템플릿 로드
    with open(template_path, 'r', encoding='utf-8') as f:
        base_template = f.read()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", HTML_GENERATION_SYSTEM_PROMPT),
        ("user", "Outline: {outline}\nTemplate: {template}")
    ])
    
    response = await llm.ainvoke(prompt.format_messages(
        outline=outline.model_dump_json(),
        template=base_template
    ))
    
    return response.content
```

**office_generator_client.py**
```python
"""
Office Generator Client - Node.js 서비스 HTTP 클라이언트
"""
import aiohttp
from app.core.service_registry import get_service_registry, ServiceType

class OfficeGeneratorClient:
    def __init__(self):
        registry = get_service_registry()
        self.service_config = registry.get_service(ServiceType.OFFICE_GENERATOR)
    
    async def convert_to_pptx(
        self,
        slides: List[Dict],
        metadata: Dict
    ) -> bytes:
        """
        구조화된 슬라이드 데이터를 PPTX로 변환
        
        Args:
            slides: 슬라이드 JSON 배열
            metadata: 메타데이터 (title, author, theme)
        
        Returns:
            PPTX 파일 바이너리
        """
        url = f"{self.service_config.base_url}/api/pptx/convert"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                "slides": slides,
                "metadata": metadata
            }) as response:
                if response.status != 200:
                    raise Exception(f"PPTX conversion failed: {response.status}")
                
                return await response.read()
```

### 5.3 Office Generator (Node.js)

#### 5.3.1 디렉토리 구조

```
office-generator-service/
├── src/
│   ├── routes/
│   │   └── pptx.routes.js                 # 수정
│   ├── converters/
│   │   └── structured-to-pptx.js          # ⭐ 신규
│   ├── templates/
│   │   ├── layout-templates.js            # ⭐ 신규
│   │   ├── TitleSlideLayout.js
│   │   ├── TitleAndBulletsLayout.js
│   │   ├── TwoColumnGridLayout.js
│   │   └── DividerSlideLayout.js
│   ├── utils/
│   │   └── icon-fetcher.js                # ⭐ 신규
│   └── server.js
└── package.json
```

#### 5.3.2 핵심 모듈 명세

**structured-to-pptx.js**
```javascript
const PptxGenJS = require('pptxgenjs');
const LayoutTemplates = require('../templates/layout-templates');
const IconFetcher = require('../utils/icon-fetcher');

class StructuredToPptxConverter {
  constructor() {
    this.pptx = new PptxGenJS();
    this.layoutTemplates = new LayoutTemplates();
    this.iconFetcher = new IconFetcher();
  }
  
  async convert(slides, metadata) {
    // 메타데이터 설정
    this.pptx.author = metadata.author || 'WKMS AI Agent';
    this.pptx.title = metadata.title || 'Presentation';
    this.pptx.layout = 'CUSTOM';
    this.pptx.defineLayout({ name: 'CUSTOM', width: 10, height: 5.625 });
    
    // 슬라이드 생성
    for (const slideData of slides) {
      await this.addSlide(slideData);
    }
    
    return await this.pptx.write({ outputType: 'nodebuffer' });
  }
  
  async addSlide(slideData) {
    const slide = this.pptx.addSlide();
    
    // 레이아웃 템플릿 가져오기
    const layout = this.layoutTemplates.get(slideData.layout);
    
    // 기본 레이아웃 적용 (제목, 배경색 등)
    layout.apply(slide, slideData);
    
    // Visual Elements 추가
    if (slideData.visual_elements) {
      await this.addVisualElements(slide, slideData.visual_elements, layout);
    }
  }
  
  async addVisualElements(slide, elements, layout) {
    // 아이콘 추가
    if (elements.icons && elements.icons.length > 0) {
      for (let i = 0; i < elements.icons.length; i++) {
        const iconSvg = await this.iconFetcher.fetch(elements.icons[i]);
        const position = layout.getIconPosition(i);
        
        slide.addImage({
          data: `data:image/svg+xml;base64,${Buffer.from(iconSvg).toString('base64')}`,
          ...position
        });
      }
    }
    
    // 불릿 포인트 추가
    if (elements.bullets && elements.bullets.length > 0) {
      const bulletPosition = layout.getBulletPosition();
      const bulletText = elements.bullets.map(b => ({
        text: b,
        options: { bullet: { code: '2022' } }
      }));
      
      slide.addText(bulletText, bulletPosition);
    }
    
    // 그리드 추가
    if (elements.grid) {
      const { cols, items } = elements.grid;
      
      items.forEach((item, index) => {
        const row = Math.floor(index / cols);
        const col = index % cols;
        const position = layout.getGridPosition(row, col, cols);
        
        // 제목
        slide.addText(item.title, {
          ...position,
          fontSize: 18,
          bold: true,
          color: '1F2937'
        });
        
        // 설명
        slide.addText(item.description, {
          ...position,
          y: position.y + 0.5,
          fontSize: 14,
          color: '6B7280'
        });
      });
    }
  }
}
```

---

## 6. API 명세

### 6.1 Backend API

#### 6.1.1 프레젠테이션 생성

```
POST /api/v1/agent/presentation/generate
```

**Request:**
```json
{
  "session_id": "uuid-string",
  "message_id": "msg_123",
  "style": "business",
  "output_format": "both",
  "options": {
    "max_slides": 15,
    "include_icons": true,
    "theme_color": "blue"
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "html_url": "/api/v1/presentations/view/abc123.html",
  "pptx_url": "/api/v1/chat/presentation/download/2025Q3_analysis.pptx",
  "preview_available": true,
  "slide_count": 8,
  "metadata": {
    "title": "2025 Q3 실적 분석",
    "created_at": "2025-11-13T10:30:00Z",
    "file_size_bytes": 524288
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "LLM generation failed",
  "error_code": "LLM_ERROR",
  "details": "..."
}
```

#### 6.1.2 HTML 프리뷰

```
GET /api/v1/presentations/view/{file_id}
```

**Response:**
- Content-Type: `text/html`
- Body: HTML 파일 내용

#### 6.1.3 PPTX 다운로드

```
GET /api/v1/chat/presentation/download/{filename}
```

**Response:**
- Content-Type: `application/vnd.openxmlformats-officedocument.presentationml.presentation`
- Content-Disposition: `attachment; filename="..."`

### 6.2 Office Generator API

#### 6.2.1 PPTX 변환

```
POST /api/pptx/convert
```

**Request:**
```json
{
  "slides": [
    {
      "title": "매출 현황",
      "content": "매출이 15% 증가했습니다.",
      "layout": "title-and-bullets",
      "visual_elements": {
        "bullets": ["매출 15% 증가", "전년 대비 +2.3B"],
        "icons": ["trending-up", "dollar-sign"],
        "grid": null,
        "image": null
      }
    }
  ],
  "metadata": {
    "title": "2025 Q3 실적 분석",
    "author": "WKMS AI Agent",
    "theme": "business"
  }
}
```

**Response:**
- Binary PPTX file
- Header: `X-Generation-Time-Ms: 2500`

---

## 7. 데이터 모델

### 7.1 Pydantic 모델 (Backend)

```python
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class GridItem(BaseModel):
    """그리드 아이템"""
    title: str
    description: str
    bg_color: str = "gray-50"

class GridLayout(BaseModel):
    """그리드 레이아웃"""
    cols: int = Field(ge=1, le=4, description="열 개수")
    items: List[GridItem]

class ImageSpec(BaseModel):
    """이미지 스펙"""
    url: str
    alt: str = ""
    width: Optional[str] = None
    height: Optional[str] = None

class VisualElements(BaseModel):
    """슬라이드 시각 요소"""
    icons: List[str] = Field(default_factory=list, description="Lucide 아이콘 이름 배열")
    bullets: List[str] = Field(default_factory=list, description="불릿 포인트 텍스트")
    grid: Optional[GridLayout] = None
    image: Optional[ImageSpec] = None

class StructuredSlide(BaseModel):
    """구조화된 슬라이드"""
    title: str
    content: str = ""
    layout: Literal[
        "title",
        "title-and-bullets",
        "two-column-grid",
        "divider",
        "image-placeholder"
    ] = "title-and-bullets"
    visual_elements: Optional[VisualElements] = None

class StructuredOutline(BaseModel):
    """구조화된 프레젠테이션 아웃라인"""
    title: str
    theme: str = Field(default="business", description="business|modern|playful")
    slides: List[StructuredSlide] = Field(min_items=1, max_items=30)

class PresentationRequest(BaseModel):
    """프레젠테이션 생성 요청"""
    session_id: str
    message_id: str
    style: Literal["business", "modern", "playful"] = "business"
    output_format: Literal["html", "pptx", "both"] = "both"
    options: Optional[Dict] = None

class PresentationResponse(BaseModel):
    """프레젠테이션 생성 응답"""
    success: bool
    html_url: Optional[str] = None
    pptx_url: Optional[str] = None
    preview_available: bool = False
    slide_count: int = 0
    metadata: Optional[Dict] = None
    error: Optional[str] = None
```

### 7.2 TypeScript 타입 (Frontend)

```typescript
// types/presentation.ts

export type LayoutType = 
  | 'title'
  | 'title-and-bullets'
  | 'two-column-grid'
  | 'divider'
  | 'image-placeholder';

export type ThemeStyle = 'business' | 'modern' | 'playful';
export type OutputFormat = 'html' | 'pptx' | 'both';

export interface GridItem {
  title: string;
  description: string;
  bg_color?: string;
}

export interface GridLayout {
  cols: number;
  items: GridItem[];
}

export interface VisualElements {
  icons?: string[];
  bullets?: string[];
  grid?: GridLayout;
  image?: {
    url: string;
    alt?: string;
  };
}

export interface StructuredSlide {
  title: string;
  content?: string;
  layout: LayoutType;
  visual_elements?: VisualElements;
}

export interface PresentationRequest {
  session_id: string;
  message_id: string;
  style: ThemeStyle;
  output_format: OutputFormat;
  options?: Record<string, any>;
}

export interface PresentationResponse {
  success: boolean;
  html_url?: string;
  pptx_url?: string;
  preview_available: boolean;
  slide_count: number;
  metadata?: {
    title: string;
    created_at: string;
    file_size_bytes: number;
  };
  error?: string;
}
```

---

## 8. 구현 계획

### 8.1 Phase 1: 핵심 인프라 (Week 1)

- [x] Service Registry 구현
- [x] Office Generator Client 구현
- [ ] File Manager 구현
- [ ] Pydantic 모델 정의
- [ ] Office Generator 기본 구조 셋업

### 8.2 Phase 2: LLM 파이프라인 (Week 2)

- [ ] Content Structurer 구현
  - [ ] LLM Prompt 작성
  - [ ] Structured Output 파싱
- [ ] HTML Generator 구현
  - [ ] HTML 템플릿 작성
  - [ ] LLM 기반 HTML 생성
- [ ] 통합 테스트

### 8.3 Phase 3: PPTX 변환 엔진 (Week 3)

- [ ] Layout Templates 구현
  - [ ] TitleSlideLayout
  - [ ] TitleAndBulletsLayout
  - [ ] TwoColumnGridLayout
  - [ ] DividerSlideLayout
- [ ] Icon Fetcher 구현
- [ ] Structured-to-PPTX Converter 구현
- [ ] 단위 테스트

### 8.4 Phase 4: Frontend 통합 (Week 4)

- [ ] PresentationPanel 컴포넌트
- [ ] PresentationPreview 모달
- [ ] API 통합
- [ ] E2E 테스트

### 8.5 Phase 5: 배포 및 모니터링 (Week 5)

- [ ] Docker 이미지 빌드
- [ ] docker-compose 설정
- [ ] Health Check 구현
- [ ] 로깅/메트릭 수집
- [ ] 프로덕션 배포

---

## 9. 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| 2025-11-13 | 1.0 | 초안 작성 | AI Assistant |

