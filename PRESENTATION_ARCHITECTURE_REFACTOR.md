# PPT 생성 아키텍처 리팩터링 계획

## 🎯 목표
Agent-Tool-Service 패턴으로 명확한 책임 분리 및 확장성 확보

## 📊 현재 상태 분석

### 문제점
1. **API → Service 직접 호출**: 에이전트 우회
2. **거대 서비스 클래스**: 1,000+ 라인의 모놀리식 서비스
3. **중복된 로직**: quick/templated/enhanced 간 유사 코드
4. **테스트 어려움**: 강결합으로 인한 모킹 복잡도

### 영향받는 파일
```
backend/app/
├── api/v1/presentation.py                    # 리팩터링 필요 ⚠️
├── services/presentation/
│   ├── quick_ppt_generator_service.py        # → tools로 이동 🔄
│   ├── templated_ppt_generator_service.py    # → tools로 이동 🔄
│   ├── enhanced_ppt_generator_service.py     # → tools로 이동 🔄
│   ├── ppt_template_manager.py               # 유지 (core utility) ✅
│   ├── ppt_models.py                         # 유지 (data models) ✅
│   └── ...
├── tools/presentation/
│   ├── outline_generation_tool.py            # 신규 생성 🆕
│   ├── template_application_tool.py          # 신규 생성 🆕
│   ├── content_assembly_tool.py              # assembly_tools 확장 🔄
│   └── presentation_pipeline_tool.py         # 강화 🔄
└── agents/presentation/
    └── presentation_agent.py                 # 강화 🔄
```

---

## 🏗️ 새로운 아키텍처

### Phase 1: 도구 추출 (Tools Extraction)

#### 1.1 `OutlineGenerationTool` 생성
```python
# backend/app/tools/presentation/outline_generation_tool.py
class OutlineGenerationTool(BaseTool):
    """Generate structured presentation outline from context."""
    
    async def _arun(
        self,
        context_text: str,
        topic: str,
        max_slides: int = 8,
        presentation_type: str = "general",
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        # quick_ppt_service.generate_fixed_outline() 로직 이동
        pass
```

**이동 대상:**
- `quick_ppt_generator_service.py::generate_fixed_outline()` → 도구 메서드
- `templated_ppt_generator_service.py::generate_enhanced_outline()` → 도구 메서드

#### 1.2 `TemplateApplicationTool` 생성
```python
# backend/app/tools/presentation/template_application_tool.py
class TemplateApplicationTool(BaseTool):
    """Apply template and generate PPTX file."""
    
    async def _arun(
        self,
        outline: Dict[str, Any],
        template_id: Optional[str] = None,
        text_box_mappings: Optional[List] = None,
        slide_management: Optional[List] = None,
    ) -> str:  # Returns file path
        # templated_ppt_service.build_enhanced_pptx_with_slide_management() 로직
        pass
```

**이동 대상:**
- `quick_ppt_generator_service.py::build_quick_pptx()` → 도구 메서드
- `templated_ppt_generator_service.py::build_enhanced_pptx_with_slide_management()` → 도구 메서드

#### 1.3 `VisualizationTool` 확장
```python
# backend/app/tools/presentation/visualization_tool.py (기존 파일 확장)
class VisualizationTool(BaseTool):
    """Add charts, tables, diagrams to slides."""
    
    async def _arun(
        self,
        slide_spec: Dict[str, Any],
        visualization_hints: Dict[str, Any],
    ) -> Dict[str, Any]:
        # _detect_visualization_hints, _create_sample_chart 등 통합
        pass
```

---

### Phase 2: 에이전트 강화 (Agent Enhancement)

#### 2.1 `PresentationAgent` 의사결정 로직
```python
# backend/app/agents/presentation/presentation_agent.py
class PresentationAgent:
    """Orchestrates presentation generation pipeline."""
    
    async def generate(
        self,
        context_text: str,
        topic: Optional[str] = None,
        options: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        # 1. 전략 선택
        strategy = self._select_strategy(context_text, options)
        
        # 2. 도구 체인 구성
        if strategy == "quick":
            tools = [outline_generation_tool, visualization_tool, assembly_tool]
        elif strategy == "templated":
            tools = [outline_generation_tool, template_application_tool, assembly_tool]
        elif strategy == "html":
            tools = [content_structurer, html_generator]
        
        # 3. 도구 실행 파이프라인
        result = await self._execute_pipeline(tools, context_text, options)
        return result
```

#### 2.2 전략 선택 알고리즘
```python
def _select_strategy(self, context_text: str, options: Dict) -> str:
    """Decide which generation strategy to use."""
    
    # 1. 명시적 요청 확인
    if options.get("force_quick"):
        return "quick"
    if options.get("template_id"):
        return "templated"
    
    # 2. 컨텍스트 복잡도 분석
    complexity = self._analyze_complexity(context_text)
    
    if complexity == "simple":
        return "quick"      # 빠른 생성
    elif complexity == "moderate":
        return "templated"  # 템플릿 기반
    else:
        return "html"       # 고급 HTML 생성
```

---

### Phase 3: API 레이어 단순화 (API Simplification)

#### 3.1 단일 진입점 패턴
```python
# backend/app/api/v1/presentation.py
@router.post("/agent/presentation/generate")
async def generate_presentation(
    req: PresentationRequest,
    current_user: User = Depends(get_current_user),
):
    """🆕 통합 생성 엔드포인트 - 에이전트가 전략 선택"""
    
    # ✅ 에이전트에 위임
    agent = PresentationAgent()
    result = await agent.generate(
        context_text=req.context_text,
        topic=req.topic,
        options=req.options,
    )
    
    return PresentationResponse(**result)
```

#### 3.2 레거시 엔드포인트 정리
```python
# ❌ 제거 예정:
# - /agent/presentation/build-quick
# - /agent/presentation/build-with-template
# - /agent/presentation/build-from-message

# ✅ 유지 (특수 목적):
# - /agent/presentation/download/{filename}
# - /agent/presentation/templates
# - /agent/presentation/view/{filename}
```

---

## 📦 마이그레이션 단계

### Step 1: 도구 생성 (병렬 작업)
- [ ] `OutlineGenerationTool` 구현
- [ ] `TemplateApplicationTool` 구현
- [ ] `VisualizationTool` 확장
- [ ] `ContentAssemblyTool` 통합

### Step 2: 에이전트 업그레이드
- [ ] `PresentationAgent` 의사결정 로직 추가
- [ ] 도구 체인 파이프라인 구현
- [ ] 에러 핸들링 및 재시도 로직

### Step 3: API 전환
- [ ] 새로운 통합 엔드포인트 생성
- [ ] 기존 엔드포인트 → 새 엔드포인트 래핑 (하위 호환)
- [ ] 프론트엔드 업데이트
- [ ] 레거시 엔드포인트 deprecation 표시

### Step 4: 서비스 정리
- [ ] `quick_ppt_generator_service.py` → 유틸리티 함수로 축소
- [ ] `templated_ppt_generator_service.py` → 코어 로직만 남김
- [ ] `enhanced_ppt_generator_service.py` → 제거 or 통합

### Step 5: 테스트 및 최적화
- [ ] 도구별 단위 테스트
- [ ] 에이전트 통합 테스트
- [ ] 성능 벤치마크 (기존 대비)
- [ ] 문서화 업데이트

---

## 🎁 기대 효과

### 1. 명확한 책임 분리
```
API → Agent → Tools → Services
(위임) (조정) (실행) (핵심 로직)
```

### 2. 확장성
- 새로운 전략 추가: 에이전트에 조건 추가만
- 새로운 도구 추가: 도구 등록 후 체인에 삽입
- A/B 테스트: 전략별 성능 측정 용이

### 3. 테스트 가능성
```python
# 도구 단위 테스트
async def test_outline_generation_tool():
    tool = OutlineGenerationTool()
    result = await tool._arun(context_text="...", topic="Test")
    assert result["slides_count"] > 0

# 에이전트 모킹 테스트
async def test_presentation_agent_quick_strategy(mocker):
    mock_tool = mocker.patch("OutlineGenerationTool._arun")
    agent = PresentationAgent()
    await agent.generate(context_text="simple text", options={"force_quick": True})
    mock_tool.assert_called_once()
```

### 4. 유지보수성
- 각 파일 < 500 라인 (현재: 1,000~2,000 라인)
- 단일 책임 원칙 준수
- 의존성 그래프 단순화

---

## 🚨 위험 요소 및 완화 방안

### 위험 1: 기존 API 호출 중단
**완화:** 래퍼 엔드포인트로 하위 호환 유지
```python
@router.post("/agent/presentation/build-quick")
async def build_quick_legacy(req: QuickPresentationBuildRequest):
    # 새 통합 엔드포인트로 전달
    return await generate_presentation(
        PresentationRequest(
            context_text=req.message,
            options={"force_quick": True, "max_slides": req.max_slides}
        )
    )
```

### 위험 2: 성능 저하 (레이어 추가)
**완화:** 
- 에이전트 오버헤드 < 50ms (측정 필요)
- 도구 간 데이터 복사 최소화 (참조 전달)
- 캐싱 전략 적용

### 위험 3: 복잡도 증가
**완화:**
- 명확한 문서화
- 다이어그램 제공
- 온보딩 가이드 작성

---

## 📅 타임라인 (예상)

- **Week 1**: Phase 1 완료 (도구 추출)
- **Week 2**: Phase 2 완료 (에이전트 강화)
- **Week 3**: Phase 3 완료 (API 전환)
- **Week 4**: Phase 4-5 완료 (정리 및 테스트)

---

## 🔗 참고 자료

### 유사 사례
- LangChain Agent Toolkit 패턴
- LlamaIndex Tool 추상화
- Semantic Kernel Planner 아키텍처

### 설계 원칙
- **Single Responsibility Principle**: 각 컴포넌트는 하나의 명확한 책임
- **Dependency Inversion**: 고수준(Agent)이 저수준(Tool) 인터페이스에 의존
- **Open/Closed Principle**: 확장에 열려있고 수정에 닫혀있음

---

## ✅ 체크리스트

- [ ] 팀 리뷰 및 승인
- [ ] 프론트엔드 팀 공유
- [ ] 마이그레이션 스크립트 작성
- [ ] 롤백 계획 수립
- [ ] 모니터링 대시보드 준비

---

**작성일**: 2025-11-28  
**담당**: Backend Team  
**우선순위**: High  
**난이도**: Medium-High
