"""
Patent Core Utilities - 특허 공통 유틸리티

IPC 코드 파싱, 날짜 변환, 특허번호 정규화 등 공용 유틸리티 함수
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from .models import PatentJurisdiction


# =============================================================================
# IPC/CPC 코드 유틸리티
# =============================================================================

def parse_ipc_code(ipc_code: str) -> Dict[str, str]:
    """
    IPC 코드 파싱
    
    예: "G06N 3/08" -> {"section": "G", "class": "06", "subclass": "N", ...}
    
    Args:
        ipc_code: IPC 코드 문자열
        
    Returns:
        Dict[str, str]: 파싱된 IPC 구성 요소
    """
    # 공백 제거 및 대문자 변환
    code = ipc_code.strip().upper()
    
    result = {
        "section": "",       # 섹션 (A-H)
        "class": "",         # 클래스 (01-99)
        "subclass": "",      # 서브클래스 (A-Z)
        "group": "",         # 그룹
        "subgroup": "",      # 서브그룹
        "full": code,        # 원본
    }
    
    # 패턴: A01B 1/00 또는 A01B1/00 또는 A01B
    pattern = r'^([A-H])(\d{2})([A-Z])?\s*(\d+)?/?(\d+)?'
    match = re.match(pattern, code)
    
    if match:
        result["section"] = match.group(1) or ""
        result["class"] = match.group(2) or ""
        result["subclass"] = match.group(3) or ""
        result["group"] = match.group(4) or ""
        result["subgroup"] = match.group(5) or ""
    
    return result


def get_ipc_section_name(section: str) -> str:
    """
    IPC 섹션 이름 반환
    
    Args:
        section: 섹션 코드 (A-H)
        
    Returns:
        str: 섹션 이름 (한글)
    """
    sections = {
        "A": "생활필수품",
        "B": "처리조작; 운수",
        "C": "화학; 야금",
        "D": "섬유; 제지",
        "E": "고정구조물",
        "F": "기계공학; 조명; 가열; 무기; 폭파",
        "G": "물리학",
        "H": "전기",
    }
    return sections.get(section.upper(), "알 수 없음")


def extract_main_ipc(ipc_codes: List[str]) -> Optional[str]:
    """
    주 IPC 코드 추출 (첫 번째 코드)
    
    Args:
        ipc_codes: IPC 코드 목록
        
    Returns:
        Optional[str]: 주 IPC 코드
    """
    return ipc_codes[0] if ipc_codes else None


def group_by_ipc_section(patents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    IPC 섹션별로 특허 그룹화
    
    Args:
        patents: 특허 목록 (ipc_codes 필드 포함)
        
    Returns:
        Dict[str, List]: 섹션별 특허 목록
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    
    for patent in patents:
        ipc_codes = patent.get("ipc_codes", [])
        main_ipc = extract_main_ipc(ipc_codes)
        
        if main_ipc:
            parsed = parse_ipc_code(main_ipc)
            section = parsed["section"]
            
            if section not in grouped:
                grouped[section] = []
            grouped[section].append(patent)
    
    return grouped


# =============================================================================
# 날짜 유틸리티
# =============================================================================

def parse_patent_date(date_str: Optional[str]) -> Optional[date]:
    """
    특허 날짜 문자열 파싱
    
    지원 형식: YYYY-MM-DD, YYYYMMDD, YYYY/MM/DD
    
    Args:
        date_str: 날짜 문자열
        
    Returns:
        Optional[date]: 파싱된 날짜
    """
    if not date_str:
        return None
    
    # 숫자만 추출
    digits = re.sub(r'\D', '', date_str)
    
    if len(digits) == 8:
        try:
            return datetime.strptime(digits, "%Y%m%d").date()
        except ValueError:
            pass
    
    # 다양한 형식 시도
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    
    return None


def format_date(d: Optional[date], format_str: str = "%Y-%m-%d") -> Optional[str]:
    """
    날짜를 문자열로 변환
    
    Args:
        d: 날짜 객체
        format_str: 출력 형식
        
    Returns:
        Optional[str]: 날짜 문자열
    """
    return d.strftime(format_str) if d else None


def get_date_range_years(years: int = 5) -> Tuple[str, str]:
    """
    최근 N년 날짜 범위 반환
    
    Args:
        years: 연도 수
        
    Returns:
        Tuple[str, str]: (시작일, 종료일) YYYY-MM-DD 형식
    """
    end = date.today()
    start = date(end.year - years, end.month, end.day)
    
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


# =============================================================================
# 특허번호 유틸리티
# =============================================================================

def normalize_patent_number(patent_number: str, jurisdiction: str = "KR") -> str:
    """
    특허번호 정규화
    
    Args:
        patent_number: 원본 특허번호
        jurisdiction: 관할권
        
    Returns:
        str: 정규화된 특허번호
    """
    # 공백 및 특수문자 제거
    normalized = re.sub(r'[\s\-\.]', '', patent_number.strip())
    
    return normalized


def extract_jurisdiction(patent_number: str) -> Optional[PatentJurisdiction]:
    """
    특허번호에서 관할권 추출
    
    Args:
        patent_number: 특허번호
        
    Returns:
        Optional[PatentJurisdiction]: 관할권
    """
    patterns = {
        PatentJurisdiction.KR: r'^(KR|10-|20-)',
        PatentJurisdiction.US: r'^(US|[0-9]{7,8}$)',
        PatentJurisdiction.EP: r'^EP',
        PatentJurisdiction.WO: r'^WO',
        PatentJurisdiction.CN: r'^CN',
        PatentJurisdiction.JP: r'^(JP|特)',
    }
    
    upper = patent_number.upper().strip()
    for jurisdiction, pattern in patterns.items():
        if re.match(pattern, upper):
            return jurisdiction
    
    return None


def parse_korean_patent_number(patent_number: str) -> Dict[str, str]:
    """
    한국 특허번호 파싱
    
    예: "10-2023-0123456" -> {"type": "10", "year": "2023", "serial": "0123456"}
    
    Args:
        patent_number: 한국 특허번호
        
    Returns:
        Dict[str, str]: 파싱된 구성 요소
    """
    # 숫자만 추출
    digits = re.sub(r'\D', '', patent_number)
    
    result = {
        "type": "",      # 10(특허), 20(실용신안)
        "year": "",      # 출원년도
        "serial": "",    # 일련번호
        "original": patent_number,
    }
    
    # 10-2023-0123456 형식
    if len(digits) >= 13:
        result["type"] = digits[0:2]
        result["year"] = digits[2:6]
        result["serial"] = digits[6:]
    
    return result


# =============================================================================
# 텍스트 유틸리티
# =============================================================================

def clean_text(text: str) -> str:
    """
    텍스트 정제 (HTML 태그 제거, 공백 정규화)
    
    Args:
        text: 원본 텍스트
        
    Returns:
        str: 정제된 텍스트
    """
    # HTML 태그 제거
    cleaned = re.sub(r'<[^>]+>', '', text)
    
    # 연속 공백 정규화
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    텍스트에서 키워드 추출 (간단한 빈도 기반)
    
    Args:
        text: 텍스트
        max_keywords: 최대 키워드 수
        
    Returns:
        List[str]: 키워드 목록
    """
    # 한글/영문 단어 추출
    words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', text.lower())
    
    # 빈도 계산
    word_count: Dict[str, int] = {}
    for word in words:
        word_count[word] = word_count.get(word, 0) + 1
    
    # 빈도순 정렬
    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    
    return [word for word, _ in sorted_words[:max_keywords]]


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    텍스트 길이 제한
    
    Args:
        text: 텍스트
        max_length: 최대 길이
        suffix: 잘린 경우 추가할 접미사
        
    Returns:
        str: 제한된 텍스트
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix
