"""
특허 문서 섹션 감지 서비스

한국 특허 문서의 정형화된 구조를 감지하고 섹션별로 분류:
- 청구항 (Claims) - 독립항/종속항
- 발명의 명칭 (Title)
- 기술분야 (Technical Field)
- 발명의 배경 (Background)
- 선행기술문헌 (Prior Art)
- 해결하고자 하는 과제 (Problem to Solve)
- 과제의 해결 수단 (Solution)
- 발명의 효과 (Effects)
- 도면의 간단한 설명 (Brief Description of Drawings)
- 발명을 실시하기 위한 구체적인 내용 (Detailed Description)
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PatentSection:
    """특허 섹션 정보"""
    section_type: str  # claims, background, detailed_description 등
    title: str  # 섹션 제목 (한글)
    start_pos: int  # 텍스트 시작 위치
    end_pos: int  # 텍스트 종료 위치
    content: str  # 섹션 내용
    subsections: List['PatentSection'] = None  # 하위 섹션 (청구항의 경우 각 항)
    priority: int = 0  # 우선순위 (0=최고, 청구항은 항상 0)


class PatentSectionDetector:
    """
    한국 특허 문서 섹션 감지기
    
    특허청 표준 양식에 따른 섹션 헤더 패턴을 사용하여
    각 섹션을 자동으로 감지하고 분류
    """
    
    # 섹션 헤더 패턴 (우선순위 순서)
    SECTION_PATTERNS = [
        # 청구항 (가장 중요 - 우선순위 0)
        {
            "type": "claims",
            "patterns": [
                r"^\s*\[?\s*청\s*구\s*항?\s*\]?",
                r"^\s*\[?\s*특허\s*청구\s*범위\s*\]?",
                r"^\s*Claims?\s*:",
            ],
            "priority": 0
        },
        # 발명의 명칭
        {
            "type": "title",
            "patterns": [
                r"^\s*\[?\s*발명의\s*명칭\s*\]?",
                r"^\s*\[?\s*Title\s*of\s*Invention\s*\]?",
            ],
            "priority": 1
        },
        # 기술분야
        {
            "type": "technical_field",
            "patterns": [
                r"^\s*\[?\s*기술\s*분야\s*\]?",
                r"^\s*\[?\s*Technical\s*Field\s*\]?",
            ],
            "priority": 2
        },
        # 발명의 배경
        {
            "type": "background",
            "patterns": [
                r"^\s*\[?\s*발명의\s*배경\s*\]?",
                r"^\s*\[?\s*Background\s*(?:of\s*the\s*Invention)?\s*\]?",
            ],
            "priority": 3
        },
        # 선행기술문헌
        {
            "type": "prior_art",
            "patterns": [
                r"^\s*\[?\s*선행\s*기술\s*문헌\s*\]?",
                r"^\s*\[?\s*Prior\s*Art\s*(?:Documents?)?\s*\]?",
            ],
            "priority": 4
        },
        # 해결하고자 하는 과제
        {
            "type": "problem",
            "patterns": [
                r"^\s*\[?\s*해결하고자\s*하는\s*과제\s*\]?",
                r"^\s*\[?\s*Problem\s*to\s*(?:be\s*)?Solve[d]?\s*\]?",
            ],
            "priority": 5
        },
        # 과제의 해결 수단
        {
            "type": "solution",
            "patterns": [
                r"^\s*\[?\s*과제의\s*해결\s*수단\s*\]?",
                r"^\s*\[?\s*Means\s*(?:for\s*)?Solving\s*(?:the\s*)?Problem\s*\]?",
            ],
            "priority": 6
        },
        # 발명의 효과
        {
            "type": "effects",
            "patterns": [
                r"^\s*\[?\s*발명의\s*효과\s*\]?",
                r"^\s*\[?\s*Effects?\s*of\s*(?:the\s*)?Invention\s*\]?",
            ],
            "priority": 7
        },
        # 도면의 간단한 설명
        {
            "type": "brief_description_drawings",
            "patterns": [
                r"^\s*\[?\s*도면의\s*간단한\s*설명\s*\]?",
                r"^\s*\[?\s*Brief\s*Description\s*of\s*(?:the\s*)?Drawings?\s*\]?",
            ],
            "priority": 8
        },
        # 발명을 실시하기 위한 구체적인 내용 / 상세한 설명
        {
            "type": "detailed_description",
            "patterns": [
                r"^\s*\[?\s*발명을\s*실시하기\s*위한\s*구체적인\s*내용\s*\]?",
                r"^\s*\[?\s*발명의\s*상세한\s*설명\s*\]?",
                r"^\s*\[?\s*Detailed\s*Description\s*(?:of\s*the\s*Invention)?\s*\]?",
            ],
            "priority": 9
        },
        # 도면 (보통 맨 끝)
        {
            "type": "drawings",
            "patterns": [
                r"^\s*\[?\s*도\s*면\s*\]?",
                r"^\s*\[?\s*Drawings?\s*\]?",
            ],
            "priority": 10
        },
    ]
    
    # 섹션 타입별 한글 이름
    SECTION_NAMES = {
        "claims": "청구항",
        "title": "발명의 명칭",
        "technical_field": "기술분야",
        "background": "발명의 배경",
        "prior_art": "선행기술문헌",
        "problem": "해결하고자 하는 과제",
        "solution": "과제의 해결 수단",
        "effects": "발명의 효과",
        "brief_description_drawings": "도면의 간단한 설명",
        "detailed_description": "발명을 실시하기 위한 구체적인 내용",
        "drawings": "도면",
    }
    
    def detect_sections(self, full_text: str) -> List[PatentSection]:
        """
        전체 텍스트에서 특허 섹션 감지
        
        Args:
            full_text: 특허 문서 전체 텍스트
        
        Returns:
            감지된 섹션 리스트 (우선순위/위치 순)
        """
        if not full_text:
            logger.warning("[PATENT-SECTION] 빈 텍스트")
            return []
        
        logger.info(f"[PATENT-SECTION] 섹션 감지 시작 (텍스트 길이: {len(full_text):,}자)")
        
        # 줄 단위로 분할
        lines = full_text.split('\n')
        
        # 섹션 헤더 찾기
        section_markers = []
        
        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # 각 패턴에 대해 매칭 시도
            for section_def in self.SECTION_PATTERNS:
                for pattern in section_def["patterns"]:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        # 섹션 시작 위치 계산
                        start_pos = sum(len(l) + 1 for l in lines[:line_idx])
                        section_markers.append({
                            "type": section_def["type"],
                            "title": line_stripped,
                            "line_idx": line_idx,
                            "start_pos": start_pos,
                            "priority": section_def["priority"]
                        })
                        logger.debug(
                            f"[PATENT-SECTION] 섹션 발견: {section_def['type']} "
                            f"(라인 {line_idx}, 우선순위 {section_def['priority']})"
                        )
                        break
        
        if not section_markers:
            logger.warning("[PATENT-SECTION] 섹션 헤더를 찾을 수 없음")
            return []
        
        # 섹션 마커를 위치순으로 정렬
        section_markers.sort(key=lambda x: x["start_pos"])
        
        # 섹션 객체 생성
        sections = []
        for i, marker in enumerate(section_markers):
            # 다음 섹션 시작 또는 문서 끝까지
            end_pos = section_markers[i + 1]["start_pos"] if i + 1 < len(section_markers) else len(full_text)
            
            content = full_text[marker["start_pos"]:end_pos].strip()
            
            section = PatentSection(
                section_type=marker["type"],
                title=self.SECTION_NAMES.get(marker["type"], marker["type"]),
                start_pos=marker["start_pos"],
                end_pos=end_pos,
                content=content,
                priority=marker["priority"]
            )
            
            # 청구항인 경우 개별 항 파싱
            if marker["type"] == "claims":
                section.subsections = self._parse_claims(content)
                logger.info(f"[PATENT-SECTION] 청구항 파싱: {len(section.subsections or [])}개 항 발견")
            
            sections.append(section)
        
        logger.info(f"[PATENT-SECTION] ✅ {len(sections)}개 섹션 감지 완료")
        self._log_section_summary(sections)
        
        return sections
    
    def _parse_claims(self, claims_text: str) -> List[PatentSection]:
        """
        청구항 텍스트에서 개별 항 파싱
        
        청구항 번호 패턴:
        - "청구항 1"
        - "제1항"
        - "[청구항 1]"
        - "Claim 1."
        """
        if not claims_text:
            return []
        
        # 청구항 번호 패턴
        claim_pattern = re.compile(
            r'(?:^\s*|(?<=\n)\s*)'  # 줄 시작 또는 개행 후
            r'(?:'
            r'청구항\s*\d+|'  # "청구항 1"
            r'제\s*\d+\s*항|'  # "제1항"
            r'\[청구항\s*\d+\]|'  # "[청구항 1]"
            r'Claim\s*\d+\.?'  # "Claim 1."
            r')',
            re.MULTILINE | re.IGNORECASE
        )
        
        # 청구항 위치 찾기
        claim_matches = list(claim_pattern.finditer(claims_text))
        
        if not claim_matches:
            logger.warning("[PATENT-CLAIMS] 청구항 번호를 찾을 수 없음")
            return []
        
        claims = []
        for i, match in enumerate(claim_matches):
            claim_start = match.start()
            claim_end = claim_matches[i + 1].start() if i + 1 < len(claim_matches) else len(claims_text)
            
            claim_content = claims_text[claim_start:claim_end].strip()
            claim_number = re.search(r'\d+', match.group()).group()
            
            claims.append(PatentSection(
                section_type=f"claim_{claim_number}",
                title=f"청구항 {claim_number}",
                start_pos=claim_start,
                end_pos=claim_end,
                content=claim_content,
                priority=0  # 모든 청구항은 최고 우선순위
            ))
        
        return claims
    
    def _log_section_summary(self, sections: List[PatentSection]):
        """섹션 감지 결과 요약 로그"""
        section_types = [s.section_type for s in sections]
        claims_count = sum(1 for s in sections if s.section_type == "claims")
        
        # 청구항 하위 항 개수
        total_claims = 0
        for section in sections:
            if section.section_type == "claims" and section.subsections:
                total_claims = len(section.subsections)
        
        logger.info("[PATENT-SECTION] ===== 섹션 감지 요약 =====")
        logger.info(f"[PATENT-SECTION] 전체 섹션: {len(sections)}개")
        logger.info(f"[PATENT-SECTION] 섹션 타입: {', '.join(section_types)}")
        if claims_count > 0:
            logger.info(f"[PATENT-SECTION] 청구항: {total_claims}개 항")
        logger.info("[PATENT-SECTION] ============================")
    
    def get_section_summary(self, sections: List[PatentSection]) -> Dict:
        """
        섹션 감지 결과 요약 (API 응답용)
        
        Returns:
            {
                "total_sections": int,
                "sections_found": List[str],
                "claims_count": int,
                "has_detailed_description": bool,
                "has_drawings": bool
            }
        """
        sections_found = []
        claims_count = 0
        
        for section in sections:
            sections_found.append(section.title)
            if section.section_type == "claims" and section.subsections:
                claims_count = len(section.subsections)
        
        return {
            "total_sections": len(sections),
            "sections_found": sections_found,
            "claims_count": claims_count,
            "has_detailed_description": any(s.section_type == "detailed_description" for s in sections),
            "has_drawings": any(s.section_type == "drawings" for s in sections),
        }
