# Archived Tools

이 디렉토리에는 현재 **사용되지 않는 휴면 Tool**들이 보관되어 있습니다.

## 아카이브된 파일 목록 (12개)

### 1. content_assembly_tool.py
- **기능**: 콘텐츠 조립 도구
- **상태**: Agent에서 참조하지 않음
- **사유**: 기능이 다른 Tool에 통합됨

### 2. content_planning_tools.py
- **기능**: 컨텍스트 분석 및 아웃라인 생성 (레거시)
- **포함 클래스**:
  - `ContextAnalyzerTool`
  - `OutlineGeneratorTool` (legacy)
- **상태**: `outline_generation_tool.py`로 대체됨
- **사유**: 기능 중복

### 3. style_analysis_tool.py
- **기능**: 스타일 분석 도구
- **상태**: Agent에서 참조하지 않음
- **사유**: 템플릿 분석 기능으로 충분

### 4. visualization_tools.py
- **기능**: 차트 및 다이어그램 생성
- **포함 클래스**:
  - `ChartGeneratorTool`
  - `DiagramBuilderTool`
- **상태**: `visualization_tool.py`로 대체됨
- **사유**: 기능 중복

### 5. presentation_pipeline_tool.py
- **기능**: 프레젠테이션 생성 파이프라인 오케스트레이터
- **상태**: Agent가 직접 오케스트레이션 수행
- **사유**: Agent 레벨에서 처리하는 것이 더 적절

### 6. assembly_tools.py
- **기능**: 슬라이드 빌드 및 조립
- **포함 클래스**:
  - `SlideBuilderTool`
  - `SlideAssemblerTool`
- **상태**: Builder Tool에 기능 통합됨
- **사유**: 과도한 추상화

### 7. design_tools.py
- **기능**: 템플릿 선택 및 레이아웃 최적화
- **포함 클래스**:
  - `TemplateSelectorTool`
  - `LayoutOptimizerTool`
- **상태**: Agent에서 참조하지 않음
- **사유**: 템플릿 관리는 Service 레이어에서 처리

### 8. template_application_tool.py
- **기능**: 템플릿 적용 도구
- **상태**: `templated_pptx_builder_tool.py`로 대체됨
- **사유**: 기능 중복

## 활성 Tool 목록 (7개)

현재 Agent에서 실제로 사용하는 도구들:

1. **outline_generation_tool.py** (공통)
   - 마크다운 → DeckSpec 변환
   - Quick + Template 모두 사용

2. **quick_pptx_builder_tool.py** (Quick 전용)
   - Quick PPT PPTX 생성
   - Service 레이어 사용

3. **template_analyzer_tool.py** (Template 전용)
   - 템플릿 구조 분석

4. **content_mapping_tool.py** (Template 전용)
   - AI 기반 콘텐츠-템플릿 매핑

5. **templated_pptx_builder_tool.py** (Template 전용)
   - Template PPT PPTX 생성
   - Service 레이어 사용

6. **visualization_tool.py** (공통, 거의 미사용)
   - 차트/다이어그램 메타데이터 생성

7. **ppt_quality_validator_tool.py** (공통, Optional)
   - PPT 품질 검증

## Tool 사용 매핑

| Tool | Quick PPT | Template PPT | 상태 |
|------|-----------|--------------|------|
| outline_generation_tool | ✅ | ✅ | 활성 |
| quick_pptx_builder_tool | ✅ | ❌ | 활성 |
| template_analyzer_tool | ❌ | ✅ | 활성 |
| content_mapping_tool | ❌ | ✅ | 활성 |
| templated_pptx_builder_tool | ❌ | ✅ | 활성 |
| visualization_tool | ✅ | ❌ | 활성 (거의 미사용) |
| ppt_quality_validator_tool | ✅ | ✅ | 활성 (Optional) |

## 아카이브 효과

- **파일 수**: 19개 → 7개 (63% 감소)
- **코드 복잡도**: 대폭 감소
- **유지보수성**: 개선
- **신규 개발자 온보딩**: 단순화

## 복원 방법

필요시 아카이브된 Tool을 복원할 수 있습니다:

```bash
# 예: content_assembly_tool 복원
cp archived/content_assembly_tool.py ./
```

단, 복원 전에:
1. Agent에서 해당 Tool을 사용하도록 코드 수정 필요
2. Tool이 여전히 필요한지 재검토 권장

## 참고 문서

- **아키텍처 분석**: `/COMPREHENSIVE_ARCHITECTURE_ANALYSIS.md`
- **통합 에이전트 구현**: `/UNIFIED_AGENT_IMPLEMENTATION_COMPLETE.md`

---

**아카이브 일자**: 2024-12-02  
**담당자**: GitHub Copilot
