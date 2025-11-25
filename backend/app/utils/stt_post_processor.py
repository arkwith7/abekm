"""
STT 결과 후처리 유틸리티
AWS Transcribe의 오인식을 보정하는 간단한 사전 기반 수정
"""
import re
from typing import Dict

# 일반적인 오인식 패턴 사전
COMMON_MISRECOGNITIONS: Dict[str, str] = {
    # 의료/기술 용어 - 인슐린 관련
    "실링 페이지": "인슐린 펌프",
    "실링페이지": "인슐린펌프",
    "인설린": "인슐린",
    "인슐린 분투": "인슐린 펌프",  # "펌프" → "분투" 오인식
    "인슐린 풍토": "인슐린 펌프",  # 🆕 "펌프" → "풍토" 오인식
    "분투": "펌프",  # 단독 "분투" → "펌프"
    "풍토": "펌프",  # 🆕 단독 "풍토" → "펌프"
    "펌푸": "펌프",
    
    # 질병명
    "당뇨": "당뇨병",  # 맥락상 "당뇨병"이 정확
    "욕병": "당뇨병",  # 🆕 "당뇨병" → "욕병" 오인식
    "욕병이나": "당뇨병이나",  # 🆕 "당뇨병이나" → "욕병이나"
    "항암과": "당뇨와",  # 🆕 "당뇨와" → "항암과" 오인식 (문법 보정)
    
    # 일반 용어
    "데이타": "데이터",
    "프로그램": "프로그램",
    "시스템": "시스템",
    
    # 자주 오인식되는 기술 용어 추가 가능
}

# 유사 발음 패턴 (정규식)
PATTERN_CORRECTIONS = [
    # 띄어쓰기 오류
    (r'페\s*이\s*지', '페이지'),
    (r'데\s*이\s*터', '데이터'),
    (r'시\s*스\s*템', '시스템'),
]


def post_process_transcript(text: str) -> str:
    """
    STT 결과 텍스트를 후처리하여 오인식 보정
    
    Args:
        text: 원본 STT 결과 텍스트
        
    Returns:
        보정된 텍스트
    """
    if not text or not isinstance(text, str):
        return text
    
    processed = text
    
    # 1. 사전 기반 직접 교체
    for wrong, correct in COMMON_MISRECOGNITIONS.items():
        if wrong in processed:
            processed = processed.replace(wrong, correct)
    
    # 2. 정규식 패턴 교체
    for pattern, replacement in PATTERN_CORRECTIONS:
        processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)
    
    return processed


def should_post_process(text: str, is_partial: bool = False) -> bool:
    """
    후처리가 필요한지 판단
    
    Args:
        text: STT 결과 텍스트
        is_partial: 부분 결과 여부
        
    Returns:
        후처리 필요 여부
    """
    # 부분 결과는 후처리하지 않음 (너무 자주 변경됨)
    if is_partial:
        return False
    
    # 알려진 오인식 패턴이 있는지 확인
    for wrong in COMMON_MISRECOGNITIONS.keys():
        if wrong in text:
            return True
    
    return False
