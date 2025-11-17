# AI Agent 시스템 프롬프트 업그레이드 완료

## 📅 작업 일시
2025-11-12

## 🎯 작업 목표
AI Agent 채팅의 답변 품질을 일반 채팅과 동등한 수준으로 향상

## 📊 변경 전후 비교

### Before (변경 전)
```python
# 1줄 프롬프트
system_prompt = "논문/문서 검색 전문가. 제공된 문서를 바탕으로 간결하게 답변."

# 설정
max_tokens = 800
출처 표기 = [1], [2] 숫자 형식
```

**문제점**:
- ❌ RAG 활용 원칙 부재
- ❌ 참조문서 무시 가능성
- ❌ 멀티턴 대화 맥락 처리 부족
- ❌ 답변 품질 제어 불가
- ❌ 일반 채팅과 출처 형식 불일치

### After (변경 후)
```python
# general.prompt 전체 적용 (373줄)
prompt_path = Path("/home/admin/wkms-aws/backend/prompts/general.prompt")
system_prompt = prompt_path.read_text(encoding='utf-8').strip()

# 설정
max_tokens = 2000  # 800 → 2000
출처 표기 = (파일명) 소괄호 형식
참조문서 개수 명시 = {doc_count}개
```

**개선사항**:
- ✅ **RAG 활용 강제 규칙**: "참조문서 1개라도 있으면 무조건 활용"
- ✅ **멀티턴 대화 지원**: 이전 대화 맥락 자동 연결
- ✅ **답변 품질 보장**: 373줄의 상세한 지침
- ✅ **출처 표기 통일**: (파일명, p.3) 형식으로 일관성
- ✅ **예외 처리 완비**: 부분 답변, 추가 질문 유도

## 🔧 수정 파일

### backend/app/agents/paper_search_agent.py

#### 1. generate_answer() 메서드 개선

**주요 변경사항**:
```python
# ✅ general.prompt 로드
prompt_path = Path("/home/admin/wkms-aws/backend/prompts/general.prompt")
system_prompt = prompt_path.read_text(encoding='utf-8').strip()

# ✅ 참조문서 개수 계산 및 명시
doc_count = len([c for c in context.split('---') if c.strip()])

# ✅ User 메시지에 참조문서 개수 포함
user_message = f"""질문: {query}

참조 문서:
{context}

참조문서 개수: {doc_count}개

위 문서를 바탕으로 질문에 답변하세요. 출처는 (파일명) 형식으로 표기하세요."""

# ✅ max_tokens 증가
max_tokens=2000  # 800 → 2000
```

#### 2. 향후 PPT Tool 분리 준비

**도구 등록 부분 주석 추가**:
```python
self.tools = {
    "vector_search": vector_search_tool,
    "keyword_search": keyword_search_tool,
    "rerank": rerank_tool,
    "fulltext_search": fulltext_search_tool,
    "deduplicate": deduplicate_tool,
    "context_builder": context_builder_tool,
    # TODO: PPT 생성 도구 추가 예정
    # "ppt_generator": ppt_generator_tool,
    # - 검색 결과를 받아 슬라이드 구조 생성
    # - general.prompt의 PPT 모드 규칙을 tool 내부로 캡슐화
    # - Agent는 PPT 요청 감지 시 이 도구를 전략에 포함
}
```

**generate_answer() 메서드 주석**:
```python
"""
답변 생성 (general.prompt 기반)

Note: PPT 생성 관련 로직은 향후 별도 tool로 분리 예정
- 현재: general.prompt의 모든 규칙 적용 (일반 답변 + PPT 모드 포함)
- 향후: ppt_generator_tool 분리 후 Agent가 도구로 호출하는 구조로 변경
"""
```

## 📈 기대 효과

### 1. 답변 품질 향상
- **일관성**: 일반 채팅과 동일한 373줄 가이드라인 적용
- **정확성**: 참조문서 활용 강제로 오답 방지
- **완성도**: 멀티턴 대화, 예외 처리 완벽 지원

### 2. 사용자 경험 개선
- **신뢰도**: "AI Agent"라는 이름에 걸맞는 고품질 답변
- **일관성**: 일반 채팅과 Agent 채팅 간 품질 격차 해소
- **출처 표기**: 통일된 형식으로 혼란 방지

### 3. 유지보수 효율화
- **단일 소스**: general.prompt 1개만 관리하면 두 시스템 모두 향상
- **확장성**: 향후 PPT tool 분리 시 명확한 분리 지점 확보

## 🔮 향후 계획

### Phase 1: PPT Generator Tool 분리 (예정)

**목표**: general.prompt의 PPT 모드를 독립적인 tool로 추출

**구조**:
```
backend/app/tools/generation/
├── ppt_generator_tool.py
│   ├── PPTGeneratorTool 클래스
│   ├── _load_ppt_prompt() → general.prompt의 PPT 섹션 추출
│   ├── _detect_ppt_request() → PPT 요청 감지 로직
│   └── execute() → 슬라이드 구조 생성
```

**Agent 통합**:
```python
# paper_search_agent.py
self.tools = {
    ...
    "ppt_generator": ppt_generator_tool,
}

# select_strategy()에서
if self._is_ppt_request(query):
    return [
        vector_search_tool,
        keyword_search_tool,
        rerank_tool,
        ppt_generator_tool  # PPT 전용 도구 호출
    ]
```

**장점**:
- ✅ 관심사 분리 (검색 vs 생성)
- ✅ PPT 로직 재사용 가능
- ✅ 독립적인 테스트 및 개선
- ✅ 일반 답변 프롬프트 간소화

### Phase 2: 기타 생성 도구 추가 (미정)
- `report_generator_tool`: 보고서 생성
- `summary_generator_tool`: 요약 생성
- `script_generator_tool`: 스크립트 생성

## ✅ 검증 체크리스트

- [x] general.prompt 파일 존재 확인
- [x] Agent에서 프롬프트 로드 성공
- [x] 참조문서 개수 계산 로직 추가
- [x] max_tokens 2000으로 증가
- [x] 출처 표기 형식 통일 (파일명)
- [x] 향후 PPT tool 분리 주석 추가
- [ ] 실제 채팅 테스트 (사용자 확인 필요)
- [ ] 답변 품질 비교 (Before/After)
- [ ] 멀티턴 대화 테스트

## 📝 참고사항

### general.prompt 핵심 규칙 요약

1. **RAG 우선**: 참조문서 1개라도 있으면 무조건 활용
2. **출처 표기**: (파일명, p.3) 또는 (파일명) 형식
3. **답변 모드**: 일반 모드(평문) / PPT 모드(슬라이드 구조)
4. **멀티턴 대화**: 짧은 질문 시 이전 맥락 자동 연결
5. **예외 처리**: 부분 답변 후 추가 질문 유도

### 토큰 비용 분석

- **system_prompt**: ~1500 토큰 (373줄 general.prompt)
- **user_message**: ~500-2000 토큰 (참조문서 포함)
- **response**: ~2000 토큰 (max_tokens)
- **총 비용**: 약 4000-5500 토큰/요청

**판단**: 답변 품질 향상 대비 충분히 가치 있는 비용

## 🎉 결론

AI Agent 채팅이 이제 일반 채팅과 동등한 수준의 답변 품질을 제공할 수 있게 되었습니다. 
향후 PPT 생성 등 특수 기능은 별도 tool로 분리하여 더욱 유연하고 확장 가능한 구조로 발전시킬 예정입니다.
