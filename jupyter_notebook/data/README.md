# 📊 테스트 데이터 관리

이 디렉토리는 WKMS 시스템 테스트에 필요한 모든 데이터를 체계적으로 관리합니다.

## 📁 디렉토리 구조

```
data/
├── ground_truth/                   # 그라운드 트루스 데이터
│   ├── ground_truth_criteria.csv   # 메인 그라운드 트루스 (130개 케이스)
│   ├── documents_analysis.csv      # 업로드 문서 분석 결과
│   ├── documents_analysis_detail.json # 상세 문서 정보 (키워드, 요약 등)
│   └── ground_truth_v*.csv         # 버전별 그라운드 트루스 백업
├── test_results/                   # 테스트 결과 저장소
│   ├── rag_chat/                  # RAG 채팅 테스트 결과
│   │   ├── 2025-09-16/            # 날짜별 결과 저장
│   │   │   ├── rag_test_report.json
│   │   │   ├── rag_test_results.csv
│   │   │   └── rag_test_summary.md
│   │   └── latest -> 2025-09-16/  # 최신 결과 심볼릭 링크
│   ├── document_processing/        # 문서 처리 테스트 결과
│   │   ├── text_extraction/
│   │   ├── chunking_strategy/
│   │   └── embedding_generation/
│   └── hybrid_search/             # 하이브리드 검색 테스트 결과
│       ├── semantic_search/
│       ├── keyword_search/
│       └── fusion_algorithms/
├── sample_documents/              # 테스트용 샘플 문서
│   ├── pdf_samples/
│   ├── docx_samples/
│   ├── pptx_samples/
│   └── txt_samples/
├── benchmarks/                    # 벤치마크 데이터
│   ├── performance_baselines.json # 성능 기준선
│   ├── quality_metrics.csv       # 품질 지표 히스토리
│   └── comparison_data/           # 타 시스템 비교 데이터
└── README.md                      # 이 파일
```

## 🎯 데이터 유형별 설명

### 1. 그라운드 트루스 데이터 (`ground_truth/`)

#### `ground_truth_criteria.csv`
실제 업로드된 19개 문서를 분석하여 생성된 130개 테스트 케이스

**컬럼 구조**:
- `question`: 테스트 질문
- `category`: 카테고리 (document_existence, content_inquiry, ppt_generation, non_existent_content)
- `api_type`: API 유형 (general, ppt)
- `expected_has_reference`: 참고자료 존재 여부 (True/False)
- `expected_reference_file`: 예상 참고자료 파일명
- `expected_answer_type`: 예상 답변 유형 (확인, 설명, PPT 생성, 자료 없음 안내)
- `keywords`: 관련 키워드 (콤마 구분)
- `difficulty`: 난이도 (easy, medium, hard)
- `test_purpose`: 테스트 목적

#### `documents_analysis.csv`
업로드된 문서들의 기본 정보와 분석 결과

#### `documents_analysis_detail.json`
각 문서의 상세 정보 (키워드, 요약, 내용 등) JSON 형태

### 2. 테스트 결과 데이터 (`test_results/`)

#### 결과 파일 형식
- **JSON 리포트**: 상세한 테스트 결과, 통계 정보, 메타데이터
- **CSV 결과**: 표 형태의 테스트 결과 (분석/시각화 용도)
- **마크다운 요약**: 사람이 읽기 쉬운 요약 리포트

#### 날짜별 버전 관리
- 각 테스트 실행 결과는 날짜별 디렉토리에 저장
- `latest` 심볼릭 링크로 최신 결과 쉽게 접근
- 성능 변화 추적 및 회귀 분석 가능

### 3. 샘플 문서 (`sample_documents/`)

테스트용 표준 샘플 문서들:
- **PDF**: 다양한 레이아웃과 폰트의 PDF 문서
- **DOCX**: 표, 이미지, 복잡한 서식의 워드 문서  
- **PPTX**: 슬라이드, 차트, 애니메이션 포함 프레젠테이션
- **TXT**: 순수 텍스트 파일

## 🚀 데이터 관리 도구

### 그라운드 트루스 생성/업데이트
```bash
cd /home/admin/wkms-aws/jupyter_notebook/utils
python analyze_uploads_documents.py
```

### 테스트 결과 정리
```bash
cd /home/admin/wkms-aws/jupyter_notebook/data/test_results
python ../utils/organize_test_results.py
```

### 데이터 백업
```bash
cd /home/admin/wkms-aws/jupyter_notebook/data
tar -czf backup_$(date +%Y%m%d).tar.gz ground_truth/ test_results/
```

## 📊 데이터 분석 및 활용

### 성능 트렌드 분석
```python
import pandas as pd
import matplotlib.pyplot as plt

# 시간별 성능 변화 추적
results_dir = "/home/admin/wkms-aws/jupyter_notebook/data/test_results/rag_chat/"
dates = ["2025-09-15", "2025-09-16"]

performance_data = []
for date in dates:
    df = pd.read_csv(f"{results_dir}/{date}/rag_test_results.csv")
    avg_score = df["overall_score"].mean()
    performance_data.append({"date": date, "average_score": avg_score})

trend_df = pd.DataFrame(performance_data)
trend_df.plot(x="date", y="average_score", kind="line")
```

### 카테고리별 성능 비교
```python
# 최신 테스트 결과 로드
latest_results = pd.read_csv("test_results/rag_chat/latest/rag_test_results.csv")

# 카테고리별 성능 분석
category_performance = latest_results.groupby("category")["overall_score"].agg([
    "mean", "std", "count"
]).round(3)

print(category_performance)
```

### 그라운드 트루스 품질 검증
```python
# 그라운드 트루스 데이터 검증
gt_df = pd.read_csv("ground_truth/ground_truth_criteria.csv")

# 카테고리별 분포 확인
print("카테고리별 분포:")
print(gt_df["category"].value_counts())

# 난이도별 분포 확인  
print("\n난이도별 분포:")
print(gt_df["difficulty"].value_counts())

# 누락된 키워드 확인
missing_keywords = gt_df[gt_df["keywords"].isna()]
if not missing_keywords.empty:
    print(f"\n키워드가 누락된 케이스: {len(missing_keywords)}개")
```

## 🔧 데이터 품질 관리

### 데이터 검증 규칙
1. **그라운드 트루스 일관성**: 동일한 질문에 대한 일관된 기대값
2. **참고자료 존재성**: expected_reference_file이 실제 존재하는지 확인
3. **키워드 정확성**: 추출된 키워드가 실제 문서 내용과 일치하는지 검증
4. **카테고리 균형**: 각 카테고리별 테스트 케이스 적절한 분포

### 자동 검증 스크립트
```bash
cd /home/admin/wkms-aws/jupyter_notebook/utils
python validate_ground_truth.py
```

### 데이터 정합성 체크
```python
def validate_ground_truth(csv_path):
    df = pd.read_csv(csv_path)
    
    # 필수 컬럼 확인
    required_columns = ["question", "category", "expected_has_reference"]
    missing_columns = set(required_columns) - set(df.columns)
    if missing_columns:
        print(f"❌ 누락된 컬럼: {missing_columns}")
    
    # 중복 질문 확인
    duplicates = df[df.duplicated("question")]
    if not duplicates.empty:
        print(f"❌ 중복된 질문: {len(duplicates)}개")
    
    # 유효하지 않은 카테고리 확인
    valid_categories = ["document_existence", "content_inquiry", "ppt_generation", "non_existent_content"]
    invalid_categories = df[~df["category"].isin(valid_categories)]
    if not invalid_categories.empty:
        print(f"❌ 유효하지 않은 카테고리: {len(invalid_categories)}개")
    
    print("✅ 그라운드 트루스 검증 완료")
```

## 📈 성능 기준선 (Baseline)

### 현재 성능 기준
- **전체 평균 점수**: 0.75 이상
- **참고자료 정확도**: 0.85 이상
- **내용 관련성**: 0.70 이상
- **평균 응답 시간**: 2.0초 이하

### 성능 알람 임계값
- **심각**: 전체 평균 점수 0.60 미만
- **경고**: 전체 평균 점수 0.65 미만
- **주의**: 이전 대비 10% 이상 성능 저하

## 🤝 데이터 기여 가이드

### 새로운 테스트 케이스 추가
1. `ground_truth/ground_truth_criteria.csv`에 새 행 추가
2. 필수 컬럼 모두 채우기
3. 검증 스크립트로 품질 확인
4. 버전 백업 생성

### 샘플 문서 추가
1. 적절한 `sample_documents/` 하위 디렉토리에 파일 추가
2. 파일명 규칙: `category_description_v1.ext`
3. 메타데이터 파일 생성 (JSON 형태)

### 테스트 결과 기여
1. 테스트 실행 후 결과를 날짜별 디렉토리에 저장
2. 성능 개선/저하 원인 분석 노트 추가
3. 비정상적인 결과는 별도 이슈로 문서화

---

**마지막 업데이트**: 2025-09-16  
**데이터 버전**: v1.0  
**관리자**: WKMS 테스트팀