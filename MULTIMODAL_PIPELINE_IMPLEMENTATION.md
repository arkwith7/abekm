# 멀티모달 파이프라인 구현 가이드

## 개요

이 문서는 InsightBridge 시스템에서 텍스트, 이미지, 음성 등 다양한 모달리티를 통합 처리하는 멀티모달 파이프라인 구현 방법을 설명합니다.

## 아키텍처 개요

### 멀티모달 처리 파이프라인
```
[입력 문서] → [모달리티 감지] → [전처리] → [특징 추출] → [벡터 임베딩] → [통합 저장]
     ↓              ↓              ↓            ↓             ↓             ↓
   다양한 형식    텍스트/이미지    정규화/정제   AI 모델 처리   벡터 생성    데이터베이스
```

### 지원 모달리티
1. **텍스트**: PDF, Word, PPT의 텍스트 콘텐츠
2. **이미지**: 문서 내 이미지, 차트, 다이어그램
3. **표**: 테이블 데이터의 구조화된 정보
4. **메타데이터**: 문서 속성, 생성일, 작성자 등

## 구현 컴포넌트

### 1. 모달리티 감지기 (Modality Detector)

```python
from typing import List, Dict, Any
import fitz  # PyMuPDF
from PIL import Image
import pandas as pd

class ModalityDetector:
    """문서에서 다양한 모달리티를 감지하고 분류"""
    
    def __init__(self):
        self.supported_formats = {
            'text': ['.txt', '.md', '.docx'],
            'pdf': ['.pdf'],
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp'],
            'presentation': ['.pptx', '.ppt']
        }
    
    def detect_modalities(self, file_path: str) -> Dict[str, List[Any]]:
        """파일에서 모든 모달리티 감지"""
        modalities = {
            'text': [],
            'images': [],
            'tables': [],
            'metadata': {}
        }
        
        if file_path.lower().endswith('.pdf'):
            modalities = self._process_pdf(file_path)
        elif file_path.lower().endswith(('.pptx', '.ppt')):
            modalities = self._process_presentation(file_path)
        elif file_path.lower().endswith(('.docx', '.doc')):
            modalities = self._process_document(file_path)
        
        return modalities
```

이 멀티모달 파이프라인을 통해 다양한 형태의 문서에서 더 풍부하고 정확한 정보를 추출할 수 있습니다.
