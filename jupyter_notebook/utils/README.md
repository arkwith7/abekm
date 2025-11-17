# 🛠️ 공통 유틸리티 도구

이 디렉토리는 WKMS 테스트 시스템에서 공통으로 사용되는 유틸리티 함수와 도구들을 포함합니다.

## 📁 파일 구성

```
utils/
├── analyze_uploads_documents.py    # 업로드 문서 분석 및 그라운드 트루스 생성
├── test_data_generator.py         # 테스트 데이터 생성 도구
├── common_test_utils.py           # 공통 테스트 유틸리티 함수
├── document_processor.py          # 문서 처리 공통 함수
├── result_analyzer.py             # 테스트 결과 분석 도구
├── data_validator.py             # 데이터 검증 도구
└── README.md                     # 이 파일
```

## 🔧 주요 도구 설명

### 1. `analyze_uploads_documents.py`
**목적**: 실제 업로드된 문서들을 분석하여 정확한 그라운드 트루스 생성

**기능**:
- DOCX, PDF, PPTX 파일 내용 자동 추출
- 키워드 자동 추출 및 요약 생성
- 테스트 케이스 자동 생성 (130개)
- 문서별 상세 정보 JSON 저장

**사용법**:
```bash
cd /home/admin/wkms-aws/jupyter_notebook/utils
python analyze_uploads_documents.py
```

**출력 파일**:
- `../data/ground_truth/ground_truth_criteria.csv`
- `../data/ground_truth/documents_analysis.csv`
- `../data/ground_truth/documents_analysis_detail.json`

### 2. `test_data_generator.py` (개발 예정)
**목적**: 다양한 테스트 시나리오를 위한 합성 데이터 생성

**기능**:
- 난이도별 테스트 케이스 생성
- 에지 케이스 자동 생성
- 부정적 케이스 (없는 내용 질의) 생성
- A/B 테스트용 데이터셋 분할

### 3. `common_test_utils.py` (개발 예정)
**목적**: 모든 테스트에서 공통으로 사용되는 유틸리티 함수

**포함 기능**:
```python
# 공통 설정 관리
def load_test_config(config_file: str) -> Dict

# API 연결 테스트
def check_api_health(base_url: str) -> bool

# 결과 비교 및 검증
def compare_test_results(expected: Dict, actual: Dict) -> float

# 로깅 및 모니터링
def setup_test_logger(name: str) -> Logger

# 파일 I/O 유틸리티
def save_test_results(results: List[Dict], output_path: str)
def load_ground_truth(file_path: str) -> pd.DataFrame

# 텍스트 처리 유틸리티
def extract_keywords(text: str, max_keywords: int = 10) -> List[str]
def calculate_text_similarity(text1: str, text2: str) -> float
def normalize_text(text: str) -> str

# 통계 분석
def calculate_statistical_significance(group1: List[float], group2: List[float]) -> Dict
def generate_performance_summary(test_results: List[TestResult]) -> Dict
```

## 🚀 사용 가이드

### 기본 사용 패턴

#### 1. 문서 분석 실행
```python
from analyze_uploads_documents import DocumentAnalyzer, create_ground_truth_from_documents

# 문서 분석기 초기화
analyzer = DocumentAnalyzer("/home/admin/wkms-aws/backend/uploads")

# 모든 문서 분석
documents_info = analyzer.analyze_all_documents()

# 그라운드 트루스 생성
ground_truth_df = create_ground_truth_from_documents(documents_info)
```

#### 2. 공통 유틸리티 사용 (예상)
```python
from common_test_utils import load_test_config, setup_test_logger, compare_test_results

# 설정 로드
config = load_test_config("../config/test_config.yaml")

# 로거 설정
logger = setup_test_logger("rag_test")

# 결과 비교
similarity_score = compare_test_results(expected_result, actual_result)
```

#### 3. 결과 분석 (예상)
```python
from result_analyzer import TestResultAnalyzer

# 분석기 초기화
analyzer = TestResultAnalyzer(test_results)

# 통계 분석 수행
stats = analyzer.calculate_statistics()

# 시각화 생성
analyzer.generate_performance_charts("../data/test_results/charts/")
```

## 🔧 개발자 가이드

### 새로운 유틸리티 추가

#### 1. 파일 생성
```python
# 새로운 유틸리티 파일: new_utility.py
"""
새로운 기능에 대한 설명
"""

def new_utility_function(param1: str, param2: int) -> Dict:
    """
    새로운 유틸리티 함수
    
    Args:
        param1: 매개변수 설명
        param2: 매개변수 설명
    
    Returns:
        Dict: 반환값 설명
    """
    # 구현 내용
    pass
```

#### 2. 테스트 코드 작성
```python
# tests/test_new_utility.py
import unittest
from utils.new_utility import new_utility_function

class TestNewUtility(unittest.TestCase):
    def test_new_utility_function(self):
        result = new_utility_function("test", 123)
        self.assertIsInstance(result, dict)
        # 추가 검증 로직
```

#### 3. 문서화 업데이트
- README.md에 새로운 함수 설명 추가
- docstring으로 상세 문서화
- 사용 예제 코드 제공

### 코딩 가이드라인

#### 네이밍 컨벤션
- **함수명**: `snake_case` (예: `extract_keywords`)
- **클래스명**: `PascalCase` (예: `DocumentAnalyzer`)
- **상수명**: `UPPER_CASE` (예: `MAX_KEYWORDS`)
- **파일명**: `snake_case.py` (예: `common_test_utils.py`)

#### 에러 처리
```python
def safe_function(risky_param: str) -> Optional[Dict]:
    """안전한 함수 구현 예제"""
    try:
        result = risky_operation(risky_param)
        return result
    except SpecificException as e:
        logger.warning(f"예상된 오류 발생: {e}")
        return None
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        raise
```

#### 타입 힌트
```python
from typing import List, Dict, Optional, Union, Tuple

def typed_function(
    text_list: List[str], 
    config: Dict[str, Union[str, int]], 
    optional_param: Optional[bool] = None
) -> Tuple[List[str], float]:
    """모든 매개변수와 반환값에 타입 힌트 사용"""
    pass
```

## 📊 성능 최적화

### 메모리 사용 최적화
```python
# 대용량 파일 처리 시 제너레이터 사용
def process_large_dataset(file_path: str) -> Generator[Dict, None, None]:
    with open(file_path, 'r') as f:
        for line in f:
            yield process_line(line)

# 메모리 사용량 모니터링
import psutil
import os

def monitor_memory_usage(func):
    """메모리 사용량 모니터링 데코레이터"""
    def wrapper(*args, **kwargs):
        process = psutil.Process(os.getpid())
        before = process.memory_info().rss / 1024 / 1024  # MB
        result = func(*args, **kwargs)
        after = process.memory_info().rss / 1024 / 1024  # MB
        print(f"메모리 사용량: {after - before:.2f} MB 증가")
        return result
    return wrapper
```

### 실행 시간 최적화
```python
import time
from functools import wraps

def measure_time(func):
    """실행 시간 측정 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} 실행 시간: {end - start:.2f}초")
        return result
    return wrapper

# 병렬 처리
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

def parallel_process(items: List[str], process_func: callable, max_workers: int = 4) -> List:
    """병렬 처리 유틸리티"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_func, items))
    return results
```

## 🧪 테스트 가이드

### 단위 테스트
```bash
cd /home/admin/wkms-aws/jupyter_notebook/utils
python -m pytest tests/ -v
```

### 통합 테스트
```bash
# 전체 파이프라인 테스트
python test_integration.py
```

### 성능 테스트
```bash
# 벤치마크 실행
python benchmark_utils.py
```

## 🔗 의존성 관리

### 필수 라이브러리
```
pandas>=1.5.0
numpy>=1.21.0
python-docx>=0.8.11
PyPDF2>=3.0.0
python-pptx>=0.6.21
openpyxl>=3.0.9
scipy>=1.9.0
aiohttp>=3.8.0
```

### 선택적 라이브러리
```
matplotlib>=3.5.0  # 시각화
seaborn>=0.11.0    # 통계 시각화
plotly>=5.0.0      # 인터랙티브 차트
jupyter>=1.0.0     # 노트북 환경
```

---

**마지막 업데이트**: 2025-09-16  
**버전**: v1.0  
**기여자**: WKMS 개발팀