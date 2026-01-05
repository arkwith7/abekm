# 논문 실험 가이드

## 📋 개요

이 디렉토리는 논문 작성을 위한 선행기술 탐지 성능 평가 실험 코드를 포함합니다.

## 📁 디렉토리 구조

```
/home/arkwith/Dev/abekm/
├── backend/
│   ├── app/
│   │   └── evaluation/
│   │       ├── prior_art_evaluator.py    # 평가 프레임워크
│   │       └── metrics.py                 # 평가 지표
│   │
│   ├── scripts/
│   │   └── experiments/
│   │       ├── run_paper_experiment.py    # 실험 실행
│   │       ├── analyze_results.py         # 결과 분석
│   │       └── visualize_results.py       # 시각화
│   │
│   ├── data/
│   │   └── processed/
│   │       ├── kipris_semiconductor_ai_dataset_paper.jsonl  # 전체 1,500건
│   │       └── fulltext/
│   │           ├── paper_eval_sample.jsonl                  # 실험용 100건
│   │           ├── paper_fulltext_dataset_sample100.jsonl   # 전문 포함
│   │           ├── targets/                                  # 타겟 특허 전문
│   │           ├── prior_arts/                               # 선행기술 전문
│   │           └── fulltext_pdfs/                            # PDF 원문
│   │
│   └── results/
│       └── paper_experiment/              # 실험 결과 저장
│           ├── experiment_results_*.json
│           ├── analysis_report.json
│           └── charts/                    # 생성된 차트
│               ├── recall_comparison.png
│               └── ...
```

## 🚀 실험 실행 방법

### 1. 실험 실행 (Mock 버전)

```bash
cd /home/arkwith/Dev/abekm

# Python 가상환경 활성화
source .venv/bin/activate

# 실험 실행
python -m backend.scripts.experiments.run_paper_experiment
```

**출력**:
- 100건 테스트 케이스 실행
- Recall@K, Precision@K, F1-Score, MAP 계산
- 결과 저장: `backend/results/paper_experiment/experiment_results_*.json`

**실행 시간**: 약 10초 (Mock 버전, 실제 에이전트는 2~3시간 예상)

---

### 2. 결과 분석

```bash
python -m backend.scripts.experiments.analyze_results
```

**출력**:
- 케이스별 성능 분석
- Ground Truth 분포
- Best/Worst 케이스
- Baseline 비교
- 저장: `backend/results/paper_experiment/analysis_report.json`

---

### 3. 결과 시각화

```bash
# matplotlib, seaborn 필요
pip install matplotlib seaborn pandas

python -m backend.scripts.experiments.visualize_results
```

**생성되는 차트** (6개):
1. `recall_comparison.png` - Recall@K 비교 (현재 vs Baseline)
2. `precision_recall_curve.png` - Precision-Recall Curve
3. `recall_distribution.png` - Recall@100 분포 히스토그램
4. `metrics_comparison_bar.png` - 메트릭 비교 막대 차트
5. `ground_truth_vs_performance.png` - GT 개수 vs 성능
6. `all_k_performance.png` - 전체 K 값 성능

---

## 📊 평가 지표

### 1. Recall@K (재현율)
```
Recall@K = |Ground Truth ∩ Top-K Predictions| / |Ground Truth|
```
- **의미**: Ground Truth 중 상위 K개에서 찾은 비율
- **목표**: Recall@100 ≥ 80%

### 2. Precision@K (정밀도)
```
Precision@K = |Ground Truth ∩ Top-K Predictions| / K
```
- **의미**: 상위 K개 중 Ground Truth 비율

### 3. F1-Score@K
```
F1@K = 2 × (Precision × Recall) / (Precision + Recall)
```
- **의미**: Precision과 Recall의 조화 평균

### 4. MAP (Mean Average Precision)
```
MAP = (1/N) Σ AP_i
AP_i = (1/|GT_i|) Σ (Precision@k × rel(k))
```
- **의미**: 순위를 고려한 종합 평가

---

## 🎯 실험 목표

| 지표 | 목표 | Baseline (Boolean) | Baseline (ChatGPT) | 기대치 (ABEKM) |
|------|------|-------------------|-------------------|----------------|
| Recall@10 | - | 12% | 8% | **≥ 20%** |
| Recall@20 | - | 18% | 15% | **≥ 30%** |
| Recall@50 | - | 35% | 28% | **≥ 50%** |
| **Recall@100** | **≥ 80%** | 52% | 45% | **≥ 80%** |
| Precision@10 | - | 18% | 12% | **≥ 25%** |
| MAP | - | 0.28 | 0.22 | **≥ 0.45** |

---

## 🔧 실제 에이전트 연동 방법

현재는 Mock 버전으로 동작합니다. 실제 에이전트와 연동하려면:

### 1. `run_paper_experiment.py` 수정

```python
# 기존 (Mock)
async def run_prior_art_search_mock(...):
    ...

# 실제 에이전트로 교체
from backend.app.agents.prior_art_agent import PriorArtAgent

async def run_prior_art_search_real(
    patent_data: Dict[str, Any],
    top_k: int = 100
) -> List[str]:
    """실제 에이전트 호출"""
    
    agent = PriorArtAgent()
    
    # 쿼리 구성
    query = f"""
    특허 제목: {patent_data['title']}
    초록: {patent_data['abstract'][:500]}...
    IPC 분류: {patent_data['ipc']}
    
    위 발명에 대한 선행기술을 검색해주세요.
    상위 {top_k}개의 가장 관련성 높은 선행 특허를 찾아주세요.
    """
    
    # 검색 실행
    results = await agent.search_prior_art(
        query=query,
        top_k=top_k
    )
    
    # 특허번호 리스트 반환
    return [r.patent_id for r in results]
```

### 2. 함수 호출 변경

```python
# run_experiment_batch() 함수에서
predictions = await run_prior_art_search_real(case, top_k=top_k)  # Mock → Real
```

---

## 📝 예상 논문 기여도

### 실험 결과 (예상)

```
Recall@100 = 82% (목표 80% 달성!)
Precision@10 = 28%
MAP = 0.52

vs Boolean Search: +30%p (52% → 82%)
vs ChatGPT-4o RAG: +37%p (45% → 82%)
vs Patsnap Agent: +1%p (81% → 82%)
```

### 학술적 기여

1. **한국 특허 데이터셋 기반 실험** (PANORAMA는 USPTO만)
2. **반도체/AI 도메인 특화 성능 검증**
3. **Ground Truth 기반 정량적 평가** (Recall/Precision/F1/MAP)
4. **대규모 실험** (1,500건 데이터셋, 100건 실험)

### 실무적 기여

1. **중소기업도 사용 가능한 오픈소스 솔루션**
2. **KIPRIS 데이터 활용 레시피 제공**
3. **재현 가능한 실험 프로토콜**
4. **즉시 실행 가능** (1일 이내 실험 완료)

---

## 🐛 문제 해결

### Q1. Mock 버전의 성능이 낮게 나옵니다

A: Mock 버전은 Ground Truth의 50%만 반환하도록 설계되어 있습니다. 실제 에이전트 연동 후 성능이 향상됩니다.

### Q2. 차트에 한글이 깨집니다

A: matplotlib 한글 폰트 설정을 확인하세요:
```bash
# Linux
sudo apt-get install fonts-nanum

# macOS
brew install font-nanum
```

### Q3. 실험이 너무 느립니다

A: 배치 사이즈를 줄이거나 병렬 처리를 추가하세요:
```python
# 병렬 처리 예시
results = await asyncio.gather(*[
    run_prior_art_search(case) for case in test_cases
])
```

---

## 📚 참고 자료

- [논문 PDF](../../../01.docs/Live-APAS Research Proposal.pdf)
- [평가 메트릭 문서](../../app/evaluation/PRIOR_ART_EVALUATION.md)
- [KIPRIS 데이터셋 보완 의견](../../../01.docs/KIPRIS_데이터셋_실험설계_보완의견.md)

---

## ✅ 체크리스트

실험 실행 전 확인:

- [ ] 데이터셋 준비 완료 (`paper_eval_sample.jsonl` 100건)
- [ ] Python 가상환경 활성화
- [ ] 필요한 패키지 설치 (`matplotlib`, `seaborn`, `pandas`)
- [ ] 에이전트 구현 완료 (또는 Mock 버전 사용)
- [ ] 결과 저장 디렉토리 생성 (`backend/results/paper_experiment/`)

실험 완료 후:

- [ ] 실험 결과 저장 확인 (`.json` 파일)
- [ ] 결과 분석 실행 (`analyze_results.py`)
- [ ] 차트 생성 (`visualize_results.py`)
- [ ] 논문에 차트 삽입
- [ ] 실험 결과 문서화

---

**작성일**: 2026년 1월 5일  
**버전**: 1.0
