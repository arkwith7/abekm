#!/usr/bin/env python3
"""
WKMS 테스트 시스템 공통 유틸리티 함수들

이 모듈은 모든 테스트에서 공통으로 사용되는 유틸리티 함수들을 제공합니다.
"""

import os
import json
import yaml
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Tuple, Any
from datetime import datetime
import re
import requests
from pathlib import Path
import hashlib


class TestConfig:
    """테스트 설정 관리 클래스"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
    
    def _get_default_config_path(self) -> str:
        """기본 설정 파일 경로 반환"""
        current_dir = Path(__file__).parent
        return str(current_dir / "../config/test_config.yaml")
    
    def _load_config(self) -> Dict:
        """설정 파일 로드"""
        default_config = {
            "api": {
                "base_url": "http://localhost:8000",
                "timeout": 30,
                "retry_count": 3
            },
            "test": {
                "max_test_cases": 100,
                "parallel_workers": 4,
                "result_retention_days": 30
            },
            "thresholds": {
                "overall_score": 0.75,
                "reference_accuracy": 0.85,
                "content_relevance": 0.70,
                "response_time": 2.0
            }
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    default_config.update(user_config)
            except Exception as e:
                logging.warning(f"설정 파일 로드 실패: {e}, 기본 설정 사용")
        
        return default_config
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """점 표기법으로 설정값 조회 (예: 'api.base_url')"""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default


def setup_test_logger(name: str, level: str = "INFO") -> logging.Logger:
    """테스트용 로거 설정"""
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 기존 핸들러 제거 (중복 방지)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (로그 디렉토리 생성)
    log_dir = Path(__file__).parent / "../logs"
    log_dir.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(
        log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger


def check_api_health(base_url: str, timeout: int = 10) -> Dict[str, Any]:
    """API 서버 상태 확인"""
    
    health_info = {
        "is_healthy": False,
        "response_time": None,
        "status_code": None,
        "error": None
    }
    
    try:
        start_time = datetime.now()
        response = requests.get(f"{base_url}/health", timeout=timeout)
        end_time = datetime.now()
        
        health_info.update({
            "is_healthy": response.status_code == 200,
            "response_time": (end_time - start_time).total_seconds(),
            "status_code": response.status_code
        })
        
        if response.status_code == 200:
            try:
                health_info["details"] = response.json()
            except:
                health_info["details"] = response.text
                
    except requests.exceptions.RequestException as e:
        health_info["error"] = str(e)
    
    return health_info


def load_ground_truth(file_path: str) -> pd.DataFrame:
    """그라운드 트루스 데이터 로드 및 검증"""
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"그라운드 트루스 파일을 찾을 수 없습니다: {file_path}")
    
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        
        # 필수 컬럼 검증
        required_columns = ["question", "category", "expected_has_reference"]
        missing_columns = set(required_columns) - set(df.columns)
        
        if missing_columns:
            raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_columns}")
        
        # 데이터 타입 변환
        if "expected_has_reference" in df.columns:
            df["expected_has_reference"] = df["expected_has_reference"].astype(bool)
        
        return df
        
    except Exception as e:
        raise ValueError(f"그라운드 트루스 파일 로드 실패: {e}")


def save_test_results(results: List[Dict], output_path: str, format: str = "json") -> bool:
    """테스트 결과 저장"""
    
    try:
        # 디렉토리 생성
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        if format.lower() == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        elif format.lower() == "csv":
            df = pd.DataFrame(results)
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        else:
            raise ValueError(f"지원하지 않는 형식: {format}")
        
        return True
        
    except Exception as e:
        logging.error(f"결과 저장 실패: {e}")
        return False


def extract_keywords(text: str, max_keywords: int = 10, min_length: int = 2) -> List[str]:
    """텍스트에서 키워드 추출"""
    
    if not text:
        return []
    
    # 한글, 영어 단어 추출
    korean_words = re.findall(r'[가-힣]{2,}', text)
    english_words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    
    # 불용어 제거
    stopwords = {
        '있는', '하는', '되는', '같은', '이런', '그런', '어떤', '수도', '때문',
        '그리고', '또한', '하지만', '그러나', '따라서', '그래서', '이것', '그것',
        'the', 'and', 'are', 'for', 'with', 'can', 'you', 'have', 'what',
        'this', 'that', 'will', 'from', 'they', 'been', 'said', 'each'
    }
    
    # 빈도수 계산
    all_words = korean_words + english_words
    word_freq = {}
    
    for word in all_words:
        if word not in stopwords and len(word) >= min_length:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # 빈도수 기준 상위 키워드 선택
    top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:max_keywords]
    
    return [word for word, freq in top_keywords]


def calculate_text_similarity(text1: str, text2: str, method: str = "jaccard") -> float:
    """두 텍스트 간 유사도 계산"""
    
    if not text1 or not text2:
        return 0.0
    
    # 키워드 추출
    keywords1 = set(extract_keywords(text1))
    keywords2 = set(extract_keywords(text2))
    
    if not keywords1 or not keywords2:
        return 0.0
    
    if method == "jaccard":
        # 자카드 유사도
        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)
        return intersection / union if union > 0 else 0.0
    
    elif method == "cosine":
        # 코사인 유사도 (간단한 버전)
        intersection = len(keywords1 & keywords2)
        magnitude = np.sqrt(len(keywords1) * len(keywords2))
        return intersection / magnitude if magnitude > 0 else 0.0
    
    else:
        raise ValueError(f"지원하지 않는 유사도 방법: {method}")


def normalize_text(text: str) -> str:
    """텍스트 정규화"""
    
    if not text:
        return ""
    
    # 소문자 변환
    text = text.lower()
    
    # 특수문자 제거 (한글, 영어, 숫자, 공백만 유지)
    text = re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', text)
    
    # 연속된 공백을 하나로 변환
    text = re.sub(r'\s+', ' ', text)
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    return text


def compare_test_results(expected: Dict, actual: Dict, tolerance: float = 0.01) -> Dict[str, Any]:
    """테스트 결과 비교"""
    
    comparison = {
        "is_match": True,
        "differences": [],
        "similarity_score": 1.0
    }
    
    # 키 비교
    expected_keys = set(expected.keys())
    actual_keys = set(actual.keys())
    
    missing_keys = expected_keys - actual_keys
    extra_keys = actual_keys - expected_keys
    
    if missing_keys:
        comparison["differences"].append(f"누락된 키: {missing_keys}")
        comparison["is_match"] = False
    
    if extra_keys:
        comparison["differences"].append(f"추가된 키: {extra_keys}")
    
    # 값 비교
    common_keys = expected_keys & actual_keys
    mismatches = 0
    
    for key in common_keys:
        expected_val = expected[key]
        actual_val = actual[key]
        
        if isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
            # 숫자 비교 (허용 오차 적용)
            if abs(expected_val - actual_val) > tolerance:
                comparison["differences"].append(
                    f"{key}: 예상값 {expected_val}, 실제값 {actual_val}"
                )
                mismatches += 1
        elif expected_val != actual_val:
            # 일반 비교
            comparison["differences"].append(
                f"{key}: 예상값 {expected_val}, 실제값 {actual_val}"
            )
            mismatches += 1
    
    # 유사도 점수 계산
    if common_keys:
        comparison["similarity_score"] = 1.0 - (mismatches / len(common_keys))
    
    if mismatches > 0:
        comparison["is_match"] = False
    
    return comparison


def calculate_file_hash(file_path: str) -> str:
    """파일 해시값 계산 (데이터 무결성 확인용)"""
    
    hash_md5 = hashlib.md5()
    
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logging.error(f"파일 해시 계산 실패 {file_path}: {e}")
        return ""


def create_test_session_id() -> str:
    """테스트 세션 ID 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = hashlib.md5(str(datetime.now().microsecond).encode()).hexdigest()[:8]
    return f"test_{timestamp}_{random_suffix}"


def measure_performance(func):
    """성능 측정 데코레이터"""
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        start_memory = get_memory_usage()
        
        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
        
        end_time = datetime.now()
        end_memory = get_memory_usage()
        
        performance_info = {
            "function": func.__name__,
            "execution_time": (end_time - start_time).total_seconds(),
            "memory_delta": end_memory - start_memory,
            "success": success,
            "error": error,
            "timestamp": start_time.isoformat()
        }
        
        logging.info(f"성능 측정: {json.dumps(performance_info, default=str)}")
        
        if success:
            return result
        else:
            raise Exception(error)
    
    return wrapper


def get_memory_usage() -> float:
    """현재 메모리 사용량 조회 (MB)"""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


# 상수 정의
DEFAULT_CONFIG = TestConfig()
LOGGER = setup_test_logger("common_utils")

# 버전 정보
__version__ = "1.0.0"
__author__ = "WKMS Test Team"