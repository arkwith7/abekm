"""
학술논문 섹션 자동 감지 서비스
"""
import re
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SectionDetector:
    """학술논문의 표준 섹션(Abstract, Introduction, Methods, Results, Discussion, Conclusion, References)을 감지"""

    # 섹션 헤더 패턴 (대소문자 무관, 번호 포함 가능)
    SECTION_PATTERNS = {
        "abstract": [
            r"^\s*ABSTRACT\s*$",
            r"^\s*Abstract\s*$",
        ],
        "introduction": [
            r"^\s*(?:\d+\.?\s+)?INTRODUCTION\s*$",
            r"^\s*(?:\d+\.?\s+)?Introduction\s*$",
            r"^\s*(?:\d+\.?\s+)?BACKGROUND\s*$",
        ],
        "methods": [
            r"^\s*(?:\d+\.?\s+)?METHODS?\s*$",
            r"^\s*(?:\d+\.?\s+)?Methods?\s*$",
            r"^\s*(?:\d+\.?\s+)?MATERIALS?\s+AND\s+METHODS?\s*$",
            r"^\s*(?:\d+\.?\s+)?METHODOLOGY\s*$",
            r"^\s*(?:\d+\.?\s+)?EXPERIMENTAL\s+(?:DESIGN|SETUP|METHODS?)\s*$",
        ],
        "results": [
            r"^\s*(?:\d+\.?\s+)?RESULTS?\s*$",
            r"^\s*(?:\d+\.?\s+)?Results?\s*$",
            r"^\s*(?:\d+\.?\s+)?FINDINGS?\s*$",
        ],
        "discussion": [
            r"^\s*(?:\d+\.?\s+)?DISCUSSION\s*$",
            r"^\s*(?:\d+\.?\s+)?Discussion\s*$",
            r"^\s*(?:\d+\.?\s+)?RESULTS?\s+AND\s+DISCUSSION\s*$",
        ],
        "conclusion": [
            r"^\s*(?:\d+\.?\s+)?CONCLUSI?ONS?\s*$",
            r"^\s*(?:\d+\.?\s+)?Conclusi?ons?\s*$",
            r"^\s*(?:\d+\.?\s+)?SUMMARY\s*$",
        ],
        "references": [
            r"^\s*REFERENCES?\s*$",
            r"^\s*References?\s*$",
            r"^\s*BIBLIOGRAPHY\s*$",
            r"^\s*Bibliography\s*$",
            r"^\s*WORKS?\s+CITED\s*$",
        ],
        "acknowledgments": [
            r"^\s*ACKNOWLEDG[E]?MENTS?\s*$",
            r"^\s*Acknowledg[e]?ments?\s*$",
        ],
    }

    # 섹션 순서 (일반적인 논문 구조)
    SECTION_ORDER = [
        "abstract",
        "introduction",
        "methods",
        "results",
        "discussion",
        "conclusion",
        "acknowledgments",
        "references",
    ]

    def __init__(self):
        # 패턴 컴파일 (성능 최적화)
        self.compiled_patterns: Dict[str, List[re.Pattern]] = {}
        for section_type, patterns in self.SECTION_PATTERNS.items():
            self.compiled_patterns[section_type] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE) for pattern in patterns
            ]

    def detect_sections(
        self, full_text: str, pages: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        전체 텍스트에서 섹션 헤더를 감지하고 섹션 정보 리스트 반환

        Args:
            full_text: 문서 전체 텍스트
            pages: 페이지 정보 리스트 (page_no, text 포함), 선택사항

        Returns:
            섹션 정보 리스트: [{
                "type": str,          # 섹션 타입 (abstract, introduction, ...)
                "title": str,         # 원본 헤더 텍스트
                "start_pos": int,     # 전체 텍스트 내 시작 위치
                "end_pos": int,       # 전체 텍스트 내 종료 위치 (다음 섹션 시작 또는 끝)
                "page_start": int,    # 시작 페이지 번호 (1-based)
                "page_end": int,      # 종료 페이지 번호
                "word_count": int,    # 단어 수
            }]
        """
        if not full_text or not full_text.strip():
            logger.warning("[SECTION-DETECT] 텍스트가 비어있음")
            return []

        # 1) 텍스트를 라인 단위로 분할
        lines = full_text.split("\n")
        detected_sections: List[Tuple[str, str, int, Optional[int]]] = []  # (type, title, start_pos, page_no)

        current_pos = 0
        page_boundaries = self._build_page_boundaries(full_text, pages) if pages else []

        # 2) 각 라인을 스캔하여 섹션 헤더 패턴 매칭
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                current_pos += len(line) + 1  # +1 for newline
                continue

            # 각 섹션 타입의 패턴과 매칭
            for section_type in self.SECTION_ORDER:
                patterns = self.compiled_patterns.get(section_type, [])
                for pattern in patterns:
                    if pattern.match(line_stripped):
                        # 페이지 번호 찾기
                        page_no = self._find_page_number(current_pos, page_boundaries)
                        detected_sections.append((section_type, line_stripped, current_pos, page_no))
                        logger.debug(
                            f"[SECTION-DETECT] 발견: {section_type} at pos={current_pos}, page={page_no}, title='{line_stripped}'"
                        )
                        break  # 첫 매칭 패턴만 사용

            current_pos += len(line) + 1  # +1 for newline

        # 3) 감지된 섹션이 없으면 빈 리스트 반환
        if not detected_sections:
            logger.warning("[SECTION-DETECT] 섹션 헤더를 찾지 못함")
            return []

        # 4) 섹션 경계 계산 (다음 섹션 시작 또는 문서 끝)
        sections = []
        for i, (section_type, title, start_pos, page_start) in enumerate(detected_sections):
            if i + 1 < len(detected_sections):
                end_pos = detected_sections[i + 1][2]  # 다음 섹션 시작 위치
                page_end = detected_sections[i + 1][3] or page_start
            else:
                end_pos = len(full_text)
                page_end = page_boundaries[-1][2] if page_boundaries else page_start

            section_text = full_text[start_pos:end_pos]
            word_count = len(section_text.split())

            sections.append(
                {
                    "type": section_type,
                    "title": title,
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "page_start": page_start or 1,
                    "page_end": page_end or (page_start or 1),
                    "word_count": word_count,
                }
            )

        logger.info(
            f"[SECTION-DETECT] {len(sections)}개 섹션 감지: {', '.join([s['type'] for s in sections])}"
        )
        return sections

    def _build_page_boundaries(self, full_text: str, pages: List[Dict]) -> List[Tuple[int, int, int]]:
        """
        페이지 정보로부터 각 페이지의 텍스트 시작/종료 위치 계산

        Returns:
            List[(start_pos, end_pos, page_no)]
        """
        boundaries = []
        current_pos = 0

        for page in pages:
            page_no = page.get("page_no", 1)
            page_text = page.get("text", "")
            page_marker = f"\n[페이지 {page_no}]\n"

            # full_text에서 페이지 마커 위치 찾기
            marker_pos = full_text.find(page_marker, current_pos)
            if marker_pos >= 0:
                start_pos = marker_pos
                end_pos = start_pos + len(page_marker) + len(page_text)
                boundaries.append((start_pos, end_pos, page_no))
                current_pos = end_pos
            else:
                # 페이지 마커가 없는 경우 대략적인 위치 추정
                end_pos = current_pos + len(page_text)
                boundaries.append((current_pos, end_pos, page_no))
                current_pos = end_pos

        return boundaries

    def _find_page_number(self, pos: int, page_boundaries: List[Tuple[int, int, int]]) -> Optional[int]:
        """주어진 텍스트 위치가 속한 페이지 번호 찾기"""
        for start, end, page_no in page_boundaries:
            if start <= pos < end:
                return page_no
        return None

    def get_section_summary(self, sections: List[Dict]) -> Dict:
        """
        섹션 감지 결과 요약 통계

        Returns:
            {
                "total_sections": int,
                "sections_found": List[str],
                "total_words": int,
                "abstract_words": int,
                "references_start_page": int,
            }
        """
        if not sections:
            return {
                "total_sections": 0,
                "sections_found": [],
                "total_words": 0,
                "abstract_words": 0,
                "references_start_page": None,
            }

        sections_found = [s["type"] for s in sections]
        total_words = sum(s["word_count"] for s in sections)
        abstract_words = next((s["word_count"] for s in sections if s["type"] == "abstract"), 0)
        references_start_page = next(
            (s["page_start"] for s in sections if s["type"] == "references"), None
        )

        return {
            "total_sections": len(sections),
            "sections_found": sections_found,
            "total_words": total_words,
            "abstract_words": abstract_words,
            "references_start_page": references_start_page,
        }
