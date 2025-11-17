# 오픈소스 문서처리 파이프라인 테스트 가이드

## 📋 개요

`opensource_pipeline_test.ipynb`는 WKMS에서 구현된 오픈소스 기반 멀티모달 문서 처리 파이프라인을 종합적으로 테스트하기 위한 Jupyter 노트북입니다.

## 🎯 주요 기능

### 1. OCR 엔진 테스트
- **EasyOCR**: 한국어 특화 OCR (CPU 최적화)
- **PaddleOCR**: 고품질 OCR 엔진
- **Tesseract**: 기본 OCR 엔진

### 2. 이미지 전처리
- 한국어 OCR 최적화 전처리
- 해상도 조정 및 대비 향상
- 노이즈 제거 및 선명도 향상

### 3. 다중 엔진 폴백 시스템
- 신뢰도 기반 자동 엔진 선택
- 문서 언어별 최적 엔진 우선순위
- 실패시 자동 폴백 처리

### 4. PDF 처리 엔진
- **PyMuPDF**: 고성능 텍스트 추출
- **pdfplumber**: 표 구조 인식
- **camelot**: 고급 표 구조 분석

### 5. 성능 벤치마크
- 처리 시간 측정
- 신뢰도 분석
- 한국어 텍스트 비율 계산
- 엔진별 성능 비교

## 🚀 실행 방법

### 1. 사전 요구사항

```bash
# 필수 라이브러리 설치
cd /home/admin/wkms-aws
pip install -r backend/requirements.txt

# 추가 시각화 라이브러리
pip install matplotlib jupyter
```

### 2. 노트북 실행

```bash
# Jupyter Lab 실행
cd /home/admin/wkms-aws/jupyter_notebook
jupyter lab opensource_pipeline_test.ipynb
```

또는

```bash
# Jupyter Notebook 실행
jupyter notebook opensource_pipeline_test.ipynb
```

### 3. 단계별 실행

노트북의 각 셀을 순서대로 실행하면 됩니다:

1. **환경 설정** (셀 1-2): 라이브러리 import 및 경로 설정
2. **OCR 엔진 확인** (셀 3): 설치된 OCR 엔진들 확인
3. **이미지 전처리기** (셀 4): 한국어 OCR 최적화 전처리 구현
4. **EasyOCR 구현** (셀 5): EasyOCR 처리기 구현 및 초기화
5. **다중 OCR 시스템** (셀 6-7): Tesseract, PaddleOCR, 폴백 시스템 구현
6. **PDF 처리** (셀 8): PDF 처리 엔진들 구현
7. **테스트 이미지 생성** (셀 9): 한국어 및 표 구조 테스트 이미지 생성
8. **종합 테스트** (셀 10): 모든 기능의 성능 테스트 및 벤치마크

## 📊 테스트 결과 해석

### OCR 성능 메트릭

- **신뢰도 (Confidence)**: 0.0-1.0 범위, 높을수록 좋음
- **한국어 비율**: 추출된 텍스트 중 한국어 문자 비율
- **처리 시간**: 이미지 처리에 소요된 시간 (초)
- **블록 수**: 인식된 텍스트 블록의 개수

### 권장 임계값

- **신뢰도**: 0.7 이상 권장
- **한국어 문서**: 한국어 비율 0.5 이상
- **처리 시간**: 이미지당 5초 이내 권장

## 🔧 문제 해결

### 1. OCR 엔진 설치 실패

```bash
# EasyOCR 설치 문제
pip install --upgrade easyocr

# PaddleOCR 설치 문제  
pip install paddleocr

# Tesseract 설치 (Ubuntu/Debian)
sudo apt-get install tesseract-ocr tesseract-ocr-kor
pip install pytesseract
```

### 2. 메모리 부족 오류

```python
# 이미지 크기 조정
def resize_image_if_large(image, max_size=2000):
    if max(image.size) > max_size:
        ratio = max_size / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        return image.resize(new_size, Image.Resampling.LANCZOS)
    return image
```

### 3. 폰트 관련 오류

```bash
# 한국어 폰트 설치 (Ubuntu)
sudo apt-get install fonts-nanum fonts-nanum-coding fonts-nanum-extra
```

### 4. PDF 처리 오류

```bash
# PDF 처리 라이브러리 재설치
pip install --upgrade PyMuPDF pdfplumber
pip install "camelot-py[cv]"

# 시스템 의존성 설치 (Ubuntu)
sudo apt-get install python3-tk ghostscript
```

## 🎯 성능 최적화 팁

### 1. EasyOCR 최적화

```python
# GPU 사용 (가능한 경우)
reader = easyocr.Reader(['ko', 'en'], gpu=True)

# 모델 캐싱
reader = easyocr.Reader(['ko', 'en'], download_enabled=False)
```

### 2. 배치 처리 최적화

```python
# 여러 이미지 동시 처리
def batch_ocr_processing(image_paths, batch_size=5):
    results = []
    for i in range(0, len(image_paths), batch_size):
        batch = image_paths[i:i+batch_size]
        batch_results = [process_image(path) for path in batch]
        results.extend(batch_results)
    return results
```

### 3. 메모리 관리

```python
# 처리 후 메모리 정리
import gc

def process_with_cleanup(image_path):
    result = ocr_engine.extract_text(image_path)
    gc.collect()  # 가비지 컬렉션 강제 실행
    return result
```

## 📈 실제 운영 적용 가이드

### 1. 프로덕션 설정

```python
# 프로덕션 환경용 OCR 설정
PRODUCTION_CONFIG = {
    'confidence_threshold': 0.75,
    'korean_priority': ['easyocr', 'paddleocr', 'tesseract'],
    'max_processing_time': 10,  # 10초 제한
    'enable_preprocessing': True,
    'enable_fallback': True
}
```

### 2. 모니터링 및 로깅

```python
import logging

# OCR 성능 로깅
def log_ocr_performance(result):
    logging.info(f"OCR Engine: {result['engine']}, "
                f"Confidence: {result['confidence']:.3f}, "
                f"Processing Time: {result['processing_time']:.2f}s")
```

### 3. 에러 핸들링

```python
def robust_ocr_processing(image_path, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = multi_ocr.process_with_fallback(image_path)
            if result['success']:
                return result
        except Exception as e:
            logging.warning(f"OCR attempt {attempt + 1} failed: {e}")
            time.sleep(1)  # 재시도 간격
    
    return {'success': False, 'error': 'Max retries exceeded'}
```

## 📞 지원 및 문의

이 테스트 노트북 사용 중 문제가 발생하거나 추가 기능이 필요한 경우:

1. 백엔드 로그 확인: `/home/admin/wkms-aws/logs/`
2. 라이브러리 버전 확인: `pip list | grep -E "(easyocr|paddleocr|tesseract)"`
3. 시스템 리소스 확인: `htop` 또는 `nvidia-smi` (GPU 사용시)

**오픈소스 기반 멀티모달 문서 처리 파이프라인을 통해 WKMS의 문서 처리 성능을 크게 향상시킬 수 있습니다!** 🚀
