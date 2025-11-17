# 🤖 RAG 채팅 시스템 테스트

이 디렉토리는 RAG(Retrieval Augmented Generation) 채팅 시스템의 성능과 기능을 종합적으로 테스트하기 위한 도구들을 포함합니다.

## 📁 파일 구성

```
rag_chat/
├── automated_rag_tester.py        # 자동화된 RAG 테스트 실행기
├── multiturn_improvement/         # 멀티턴 대화 개선 관련
│   ├── context_filtering.py       # 컨텍스트 필터링 알고리즘
│   ├── topic_detection.py         # 주제 전환 감지 로직
│   └── conversation_analysis.py   # 대화 흐름 분석 도구
├── performance_benchmarks/        # 성능 벤치마크 테스트
│   ├── response_time_test.py      # 응답 시간 측정
│   ├── accuracy_evaluation.py     # 정확도 평가
│   └── scalability_test.py        # 확장성 테스트
└── README.md                      # 이 파일
```

## 🎯 주요 기능

### 1. 자동화된 종합 테스트 (`automated_rag_tester.py`)
- **130개 테스트 케이스** 자동 실행
- **실제 업로드 문서 기반** 그라운드 트루스 사용
- **통계적 유의성 검정** 포함
- **JSON/CSV/Markdown** 형태 리포트 생성

#### 평가 지표
- **참고자료 정확성** (40%): 예상 참고자료 유무와 실제 결과 비교
- **내용 관련성** (40%): 키워드 매칭 및 응답 품질 평가
- **답변 유형 정확성** (20%): 확인/설명/PPT생성/자료없음 등 응답 유형 체크

### 2. 멀티턴 대화 개선
- **주제 전환 감지**: 이전 대화와 현재 질문의 관련성 분석
- **적응적 컨텍스트 필터링**: 관련성 기반 선택적 대화 히스토리 포함
- **의도별 임계값 조정**: PPT/일반질문/인사말 등 의도에 따른 맞춤형 처리

## 🚀 사용 방법

### 기본 테스트 실행
```bash
cd /home/admin/wkms-aws/jupyter_notebook/tests/rag_chat
source /home/admin/wkms-aws/.venv/bin/activate
python automated_rag_tester.py
```

### 샘플 테스트 (빠른 확인용)
```python
# automated_rag_tester.py 파일 수정
# main() 함수에서 max_tests 파라미터 조정
results = await tester.run_all_tests(ground_truth_file, max_tests=10)
```

### 커스텀 테스트 실행
```python
from automated_rag_tester import RAGChatTester, TestResultAnalyzer

# 테스터 초기화
tester = RAGChatTester("http://localhost:8000")

# 단일 테스트 실행
test_case = {
    "question": "AI 기술에 대해 알려주세요",
    "category": "content_inquiry",
    "api_type": "general",
    "expected_has_reference": True,
    "keywords": "AI, 인공지능, 기술"
}

result = await tester.run_single_test(test_case)
```

## 📊 결과 분석

### 자동 생성되는 리포트
1. **JSON 리포트** (`rag_test_report.json`): 상세한 테스트 결과 데이터
2. **CSV 리포트** (`rag_test_results.csv`): 표 형태의 결과 데이터
3. **마크다운 요약** (`rag_test_summary.md`): 사람이 읽기 쉬운 요약 리포트

### 주요 통계 지표
- **전체 평균 점수**: 모든 테스트 케이스의 종합 점수
- **카테고리별 성능**: 문서존재확인, 내용질의, PPT생성 등 카테고리별 분석
- **API 타입별 성능**: General API vs PPT API 성능 비교
- **응답 시간 분석**: 평균 응답 시간 및 분산

## 🔧 고급 설정

### 테스트 서버 URL 변경
```python
tester = RAGChatTester("http://your-server:port")
```

### 평가 임계값 조정
```python
# content_relevance_score 계산에서 임계값 조정
def evaluate_content_relevance(self, question: str, response: str, keywords: str) -> float:
    # 키워드 매칭 가중치 조정 (기본값: 0.6)
    keyword_score = keyword_matches / len(keywords_list) if keywords_list else 0
    length_score = min(len(response.split()) / 20, 1.0)
    
    # 가중치 조정 가능
    relevance_score = (keyword_score * 0.7 + length_score * 0.3) - negative_penalty
```

### 새로운 평가 지표 추가
```python
@dataclass
class TestResult:
    # 기존 필드들...
    custom_metric: float  # 새로운 평가 지표 추가
    
    # overall_score 계산 시 반영
    overall_score = (
        reference_accuracy * 0.3 +
        content_relevance_score * 0.3 +
        answer_type_correct * 0.2 +
        custom_metric * 0.2
    )
```

## 🐛 트러블슈팅

### 공통 문제

1. **연결 오류**: 백엔드 서버가 실행 중인지 확인
   ```bash
   curl http://localhost:8000/health
   ```

2. **메모리 부족**: 테스트 케이스 수를 줄여서 실행
   ```python
   results = await tester.run_all_tests(ground_truth_file, max_tests=20)
   ```

3. **타임아웃 오류**: API 호출 타임아웃 시간 조정
   ```python
   async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
   ```

### 성능 최적화

1. **병렬 처리**: 여러 세션으로 동시 테스트 실행
2. **결과 캐싱**: 동일한 질문에 대한 결과 재사용
3. **점진적 테스트**: 실패한 케이스만 재실행

## 📈 향후 개발 계획

- [ ] **실시간 모니터링**: 테스트 진행 상황 실시간 표시
- [ ] **A/B 테스트**: 여러 모델 버전 동시 비교
- [ ] **사용자 피드백 통합**: 실제 사용자 평가 반영
- [ ] **성능 회귀 탐지**: 이전 버전 대비 성능 변화 감지
- [ ] **자동 알람**: 성능 저하 시 자동 알림 시스템

---

**마지막 업데이트**: 2025-09-16  
**관련 이슈**: [멀티턴 대화 개선](../../../ai_agent_chat_test.ipynb)