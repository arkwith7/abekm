"""
적응형 섹션 감지 서비스 (Adaptive Section Detection)
=======================================================

기존 패턴 매칭 방식의 한계를 극복하기 위한 2단계 접근:
1. 구조 감지: 논문의 모든 섹션 헤더를 형식 기반으로 감지 (내용 누락 방지)
2. 의미 매핑: 감지된 헤더를 표준 섹션과 유사도 기반으로 매핑

장점:
- 모든 섹션 헤더 감지 → 내용 누락 없음
- 비표준 헤더도 처리 가능 ("Methodology" → "methods")
- 미분류 섹션도 보존 (type="other")
"""
import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class AdaptiveSectionDetector:
    """적응형 섹션 감지기 - 논문 구조를 먼저 감지하고 의미 기반으로 분류"""

    # 표준 섹션 타입과 관련 키워드 (의미 매핑용)
    STANDARD_SECTIONS = {
        "abstract": [
            "abstract", "summary", "executive summary", "synopsis", "overview"
        ],
        "introduction": [
            "introduction", "background", "overview", "motivation", "preliminaries",
            "preamble", "prologue"
        ],
        "methods": [
            "methods", "methodology", "materials", "experimental", "approach",
            "procedure", "design", "setup", "implementation", "materials and methods",
            "experimental design", "experimental setup", "research methods"
        ],
        "results": [
            "results", "findings", "observations", "outcomes", "data",
            "experimental results", "empirical results"
        ],
        "discussion": [
            "discussion", "analysis", "interpretation", "implications",
            "results and discussion", "discussion and analysis"
        ],
        "conclusion": [
            "conclusion", "conclusions", "summary", "closing", "final remarks",
            "future work", "concluding remarks", "summary and conclusion"
        ],
        "references": [
            "references", "bibliography", "works cited", "literature cited",
            "citations", "bibliographic references"
        ],
        "acknowledgments": [
            "acknowledgments", "acknowledgements", "acknowledgment", "acknowledgement",
            "thanks", "credits"
        ],
        "appendix": [
            "appendix", "appendices", "supplementary", "additional", "supplemental"
        ]
    }

    # 섹션 헤더 감지를 위한 패턴
    HEADER_PATTERNS = [
        # 1. 번호 패턴: "1. Introduction", "1.1 Data Collection"
        re.compile(r"^\s*(\d+(\.\d+)*\.?\s+)([A-Z][^\n]{2,80})$", re.MULTILINE),
        
        # 2. 대문자 전체: "ABSTRACT", "INTRODUCTION"
        re.compile(r"^\s*([A-Z][A-Z\s]{2,80})$", re.MULTILINE),
        
        # 3. Title Case: "Research Methodology", "Data Analysis"
        re.compile(r"^\s*([A-Z][a-z]+(\s+[A-Z][a-z]+){0,8})$", re.MULTILINE),
        
        # 4. 로마 숫자: "I. Introduction", "II. Methods"
        re.compile(r"^\s*([IVXLCDM]+\.\s+)([A-Z][^\n]{2,80})$", re.MULTILINE),
    ]

    def __init__(self):
        """초기화"""
        # 표준 섹션 키워드를 소문자로 정규화
        self.standard_keywords: Dict[str, Set[str]] = {
            section_type: set(kw.lower() for kw in keywords)
            for section_type, keywords in self.STANDARD_SECTIONS.items()
        }
        
        # 섹션 순서 (논문 일반적 구조)
        self.section_order = [
            "abstract", "introduction", "methods", "results",
            "discussion", "conclusion", "acknowledgments", "references", "appendix"
        ]
        
        logger.info("[ADAPTIVE-SECTION] AdaptiveSectionDetector 초기화 완료")

    def detect_sections(
        self, full_text: str, pages: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        적응형 섹션 감지: Azure DI role 우선 → 패턴 매칭 폴백 → 의미 매핑
        
        Args:
            full_text: 문서 전체 텍스트
            pages: 페이지 정보 (선택, Azure DI의 section_headers 포함 가능)
        
        Returns:
            섹션 정보 리스트: [{
                "type": str,              # 표준 섹션 타입 또는 "other"
                "original_title": str,    # 원본 헤더 텍스트
                "normalized_title": str,  # 정규화된 헤더
                "mapped_type": str,       # 매핑된 표준 타입 (있으면)
                "confidence": float,      # 매핑 신뢰도 (0~1)
                "detection_source": str,  # "azure_di_role" | "pattern_match"
                "start_pos": int,
                "end_pos": int,
                "page_start": int,
                "page_end": int,
                "word_count": int,
            }]
        """
        if not full_text or not full_text.strip():
            logger.warning("[ADAPTIVE-SECTION] 텍스트가 비어있음")
            return []

        # 🎯 1단계: Azure DI의 role 기반 섹션 헤더 추출 (우선)
        if pages:
            logger.debug(f"[ADAPTIVE-SECTION] 페이지 데이터 제공됨 - {len(pages)}페이지")
            # 디버깅: 첫 페이지의 section_headers 확인
            if pages:
                first_page = pages[0]
                section_headers_count = len(first_page.get('section_headers', []))
                paragraphs_count = len(first_page.get('paragraphs', []))
                logger.debug(f"[ADAPTIVE-SECTION] 첫 페이지 - section_headers: {section_headers_count}, paragraphs: {paragraphs_count}")
        
        azure_headers = self._extract_azure_di_headers(pages) if pages else []
        
        if azure_headers:
            logger.info(f"[ADAPTIVE-SECTION] 🎯 Azure DI role 기반 헤더 {len(azure_headers)}개 감지")
            for i, h in enumerate(azure_headers[:5], 1):  # 처음 5개만 로깅
                logger.debug(f"  {i}. {h['text'][:50]} (page={h.get('page_no')}, pos={h['start_pos']})")
            all_headers = azure_headers
        else:
            logger.info("[ADAPTIVE-SECTION] Azure DI role 정보 없음, 패턴 매칭으로 폴백")
            # 2단계: 패턴 기반 헤더 감지 (폴백)
            all_headers = self._detect_all_headers(full_text)
        
        if not all_headers:
            logger.warning("[ADAPTIVE-SECTION] 헤더를 찾지 못함")
            return []

        logger.info(f"[ADAPTIVE-SECTION] {len(all_headers)}개 헤더 감지됨")

        # 2단계: 각 헤더를 표준 섹션으로 매핑
        sections = []
        page_boundaries = self._build_page_boundaries(full_text, pages) if pages else []

        for i, header in enumerate(all_headers):
            # 의미 매핑 (확정 매핑 + 가장 가까운 섹션)
            mapped_type, confidence, closest_type, closest_score = self._map_to_standard(header["text"])
            
            # 다음 헤더까지를 섹션 범위로 설정
            if i + 1 < len(all_headers):
                end_pos = all_headers[i + 1]["start_pos"]
            else:
                end_pos = len(full_text)
            
            # 페이지 번호 찾기
            page_start = self._find_page_number(header["start_pos"], page_boundaries)
            page_end = self._find_page_number(end_pos - 1, page_boundaries) or page_start
            
            # 섹션 텍스트 및 단어 수
            section_text = full_text[header["start_pos"]:end_pos]
            word_count = len(section_text.split())
            
            # 감지 소스 (Azure DI role vs 패턴 매칭)
            detection_source = header.get("detection_source", "pattern_match")
            
            section_info = {
                "type": mapped_type or "other",
                "original_title": header["text"],
                "normalized_title": self._normalize_header(header["text"]),
                "mapped_type": mapped_type,
                "confidence": confidence,
                "closest_standard_section": closest_type,  # 가장 가까운 표준 섹션
                "closest_similarity": closest_score,        # 유사도 점수
                "detection_source": detection_source,  # 🎯 Azure DI role | pattern_match
                "index": i,  # 섹션 순서 인덱스 (순서 보존용)
                "start_pos": header["start_pos"],
                "end_pos": end_pos,
                "page_start": page_start or 1,
                "page_end": page_end or page_start or 1,
                "word_count": word_count,
            }
            sections.append(section_info)
            
            # 로깅: "other"인 경우 가장 가까운 섹션 표시
            source_emoji = "🎯" if detection_source == "azure_di_role" else "🔍"
            if mapped_type:
                log_msg = f"[ADAPTIVE-SECTION] {source_emoji} '{header['text']}' → {mapped_type} (신뢰도: {confidence:.2f})"
            else:
                log_msg = (
                    f"[ADAPTIVE-SECTION] {source_emoji} '{header['text']}' → other "
                    f"(가장 가까운: {closest_type}, 유사도: {closest_score:.2f})"
                )
            logger.debug(log_msg)

        # 3단계: 감지된 섹션 타입 집계
        detected_types = [s["type"] for s in sections if s["type"] != "other"]
        other_sections = [s for s in sections if s["type"] == "other"]
        
        logger.info(
            f"[ADAPTIVE-SECTION] 매핑 완료 - 총 {len(sections)}개 섹션, "
            f"표준 매핑: {len(detected_types)}개, 기타: {len(other_sections)}개"
        )
        logger.info(f"[ADAPTIVE-SECTION] 감지된 표준 섹션: {', '.join(set(detected_types))}")
        
        # "other" 섹션의 가장 가까운 표준 섹션 분포 로깅
        if other_sections:
            closest_distribution = {}
            for s in other_sections:
                closest = s.get("closest_standard_section", "unknown")
                closest_distribution[closest] = closest_distribution.get(closest, 0) + 1
            
            logger.info(
                f"[ADAPTIVE-SECTION] 'other' 섹션의 근접 분포: "
                f"{', '.join([f'{k}({v})' for k, v in closest_distribution.items()])}"
            )

        return sections

    def _extract_azure_di_headers(self, pages: List[Dict]) -> List[Dict]:
        """
        Azure DI의 role 기반 섹션 헤더 추출
        
        Args:
            pages: Azure DI가 반환한 페이지 정보 (section_headers 포함)
        
        Returns:
            [{"text": str, "start_pos": int, "detection_source": "azure_di_role", "page_no": int}, ...]
        """
        headers = []
        current_text_pos = 0
        
        total_section_headers = 0
        for page in pages:
            section_headers = page.get('section_headers', [])
            total_section_headers += len(section_headers)
        
        logger.debug(f"[ADAPTIVE-SECTION][AZURE-DI] 전체 {len(pages)}페이지에서 {total_section_headers}개 section_headers 발견")
        
        for page in pages:
            page_no = page.get('page_no', 1)
            page_text = page.get('text', '')
            
            # Azure DI의 section_headers 추출
            section_headers = page.get('section_headers', [])
            
            if section_headers:
                logger.debug(f"[ADAPTIVE-SECTION][AZURE-DI] 페이지 {page_no}: {len(section_headers)}개 헤더")
            
            for header_info in section_headers:
                header_text = header_info.get('content', '').strip()
                if not header_text:
                    continue
                
                role = header_info.get('role', 'unknown')
                logger.debug(f"[ADAPTIVE-SECTION][AZURE-DI] 헤더 발견 - page={page_no}, role={role}, text='{header_text[:50]}'")
                
                # 전체 텍스트에서 헤더 위치 찾기
                search_start = current_text_pos
                header_pos = page_text.find(header_text, search_start - current_text_pos if search_start >= current_text_pos else 0)
                
                if header_pos == -1:
                    # 페이지 텍스트에서 못 찾으면 대략적인 위치 사용
                    header_pos = current_text_pos
                else:
                    header_pos = current_text_pos + header_pos
                
                headers.append({
                    'text': header_text,
                    'start_pos': header_pos,
                    'detection_source': 'azure_di_role',
                    'page_no': page_no,
                    'role': header_info.get('role', 'sectionHeading'),
                    'confidence': header_info.get('confidence', 1.0)
                })
                
                logger.debug(
                    f"[AZURE-DI-HEADER] page={page_no}, role={header_info.get('role')}, "
                    f"text='{header_text[:50]}', pos={header_pos}"
                )
            
            # 다음 페이지를 위한 위치 업데이트
            current_text_pos += len(page_text) + 2  # "\n\n" 구분자 고려
        
        # 위치 순서대로 정렬
        headers.sort(key=lambda x: x['start_pos'])
        
        logger.info(f"[ADAPTIVE-SECTION] Azure DI role 기반 헤더 {len(headers)}개 추출 완료")
        return headers

    def _detect_all_headers(self, full_text: str) -> List[Dict]:
        """
        논문의 모든 섹션 헤더 감지 (형식 기반)
        
        Returns:
            [{"text": str, "start_pos": int, "pattern_type": str}, ...]
        """
        headers = []
        seen_positions = set()
        
        for pattern_idx, pattern in enumerate(self.HEADER_PATTERNS):
            for match in pattern.finditer(full_text):
                start_pos = match.start()
                
                # 중복 위치 제거 (여러 패턴에 매칭될 수 있음)
                if start_pos in seen_positions:
                    continue
                
                # 헤더 텍스트 추출
                header_text = match.group(0).strip()
                
                # 너무 짧거나 긴 헤더 제외
                if len(header_text) < 3 or len(header_text) > 100:
                    continue
                
                # 숫자만 있는 경우 제외
                if header_text.replace(".", "").replace(" ", "").isdigit():
                    continue

                normalized_text = self._normalize_header(header_text)
                normalized_tokens = [t for t in normalized_text.split() if t]
                alpha_chars = sum(1 for ch in normalized_text if ch.isalpha())

                # 최소 글자/토큰 수 필터: 표/지표 단일 토큰(예: CLB, DMA) 제거
                if alpha_chars < 4:
                    continue
                if not normalized_tokens:
                    continue
                if len(normalized_tokens) == 1 and len(normalized_tokens[0]) < 4:
                    continue
                
                headers.append({
                    "text": header_text,
                    "start_pos": start_pos,
                    "pattern_type": f"pattern_{pattern_idx}",
                    "detection_source": "pattern_match"  # 🔍 패턴 매칭 표시
                })
                seen_positions.add(start_pos)
        
        # 위치 순서대로 정렬
        headers.sort(key=lambda x: x["start_pos"])
        
        return headers

    def _normalize_header(self, header: str) -> str:
        """
        헤더 텍스트 정규화 (비교용)
        
        - 소문자 변환
        - 번호 제거
        - 특수문자 제거
        - 불필요한 공백 제거
        """
        # 번호 패턴 제거: "1.", "1.1", "I.", "II." 등
        normalized = re.sub(r"^[\divxlcdm]+\.?\s*", "", header, flags=re.IGNORECASE)
        
        # 소문자 변환
        normalized = normalized.lower()
        
        # 특수문자 제거 (공백 유지)
        normalized = re.sub(r"[^\w\s]", "", normalized)
        
        # 연속 공백 제거
        normalized = re.sub(r"\s+", " ", normalized).strip()
        
        return normalized

    def _map_to_standard(self, header: str) -> Tuple[Optional[str], float, Optional[str], float]:
        """
        헤더를 표준 섹션으로 매핑 (키워드 매칭 + 유사도)
        
        Returns:
            (mapped_type, confidence, closest_type, closest_score)
            - mapped_type: 표준 섹션 타입 (신뢰도 0.6 이상) 또는 None
            - confidence: 매핑 신뢰도 (0~1)
            - closest_type: 가장 가까운 표준 섹션 (신뢰도 무관)
            - closest_score: 가장 가까운 섹션의 유사도 (0~1)
        """
        normalized = self._normalize_header(header)
        
        best_match_type = None
        best_score = 0.0
        closest_type = None
        closest_score = 0.0
        
        def _length_ratio(a: str, b: str) -> float:
            shorter = min(len(a), len(b))
            longer = max(len(a), len(b)) or 1
            return shorter / longer

        # 1차: 키워드 정확 매칭
        for section_type, keywords in self.standard_keywords.items():
            if normalized in keywords:
                return section_type, 1.0, section_type, 1.0  # 완벽한 매칭
            
            # 부분 매칭 (키워드가 헤더에 포함)
            for keyword in keywords:
                keyword_norm = keyword.lower()
                if keyword_norm in normalized and len(keyword_norm) >= 4:
                    score = _length_ratio(normalized, keyword_norm)
                    if score > best_score:
                        best_score = score
                        best_match_type = section_type
                    if score > closest_score:
                        closest_score = score
                        closest_type = section_type
                elif normalized in keyword_norm and len(normalized) >= 4:
                    score = _length_ratio(normalized, keyword_norm)
                    if score > best_score:
                        best_score = score
                        best_match_type = section_type
                    if score > closest_score:
                        closest_score = score
                        closest_type = section_type
        
        # 2차: 문자열 유사도 (Fuzzy Matching)
        if best_score < 0.8:  # 정확 매칭이 없으면 유사도 검사
            for section_type, keywords in self.standard_keywords.items():
                for keyword in keywords:
                    similarity = SequenceMatcher(None, normalized, keyword).ratio()
                    if similarity > best_score:
                        best_score = similarity
                        best_match_type = section_type
                    if similarity > closest_score:
                        closest_score = similarity
                        closest_type = section_type
        
        # 매핑 결정: 신뢰도 0.6 이상만 확정 매핑
        if best_score >= 0.6:
            return best_match_type, best_score, best_match_type, best_score
        
        # 신뢰도 미달이지만 가장 가까운 섹션 정보는 반환
        return None, 0.0, closest_type, closest_score

    def _build_page_boundaries(
        self, full_text: str, pages: List[Dict]
    ) -> List[Tuple[int, int, int]]:
        """
        페이지 경계 계산 (페이지 번호 매핑용)
        
        Returns:
            [(start_pos, end_pos, page_no), ...]
        """
        boundaries = []
        current_pos = 0

        for page in pages:
            page_no = page.get("page_no", 1)
            page_text = page.get("text", "")
            
            # 페이지 마커가 있는지 확인
            page_marker = f"\n[페이지 {page_no}]\n"
            marker_pos = full_text.find(page_marker, current_pos)
            
            if marker_pos >= 0:
                start_pos = marker_pos
                end_pos = start_pos + len(page_marker) + len(page_text)
            else:
                # 마커 없으면 순차적으로 배치
                end_pos = current_pos + len(page_text)
                start_pos = current_pos
            
            boundaries.append((start_pos, end_pos, page_no))
            current_pos = end_pos

        return boundaries

    def _find_page_number(
        self, pos: int, page_boundaries: List[Tuple[int, int, int]]
    ) -> Optional[int]:
        """주어진 위치의 페이지 번호 찾기"""
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
                "mapped_sections": int,
                "unmapped_sections": int,
                "sections_found": List[str],
                "other_sections": List[str],
                "abstract_words": int,
                "references_start_page": int,
                "azure_di_role_used": bool,  # 🎯 Azure DI role 사용 여부
                "azure_di_sections": int,    # 🎯 Azure DI로 감지된 섹션 수
            }
        """
        if not sections:
            return {
                "total_sections": 0,
                "mapped_sections": 0,
                "unmapped_sections": 0,
                "sections_found": [],
                "other_sections": [],
                "abstract_words": 0,
                "references_start_page": None,
                "azure_di_role_used": False,
                "azure_di_sections": 0,
            }

        mapped_sections = [s for s in sections if s["type"] != "other"]
        unmapped_sections = [s for s in sections if s["type"] == "other"]
        
        sections_found = [s["type"] for s in mapped_sections]
        other_sections = [s["original_title"] for s in unmapped_sections]
        
        # 🎯 Azure DI role 사용 여부 집계
        azure_di_sections = [s for s in sections if s.get("detection_source") == "azure_di_role"]
        azure_di_role_used = len(azure_di_sections) > 0
        
        # "other" 섹션의 가장 가까운 표준 섹션 집계
        other_sections_with_proximity = []
        for s in unmapped_sections:
            other_sections_with_proximity.append({
                "title": s["original_title"],
                "closest_section": s.get("closest_standard_section"),
                "similarity": s.get("closest_similarity", 0.0),
                "index": s.get("index", 0),
                "detection_source": s.get("detection_source", "pattern_match")
            })
        
        abstract_words = next(
            (s["word_count"] for s in sections if s["type"] == "abstract"), 0
        )
        references_start_page = next(
            (s["page_start"] for s in sections if s["type"] == "references"), None
        )

        return {
            "total_sections": len(sections),
            "mapped_sections": len(mapped_sections),
            "unmapped_sections": len(unmapped_sections),
            "sections_found": sections_found,
            "other_sections": other_sections,
            "other_sections_proximity": other_sections_with_proximity,  # 근접 정보 추가
            "abstract_words": abstract_words,
            "references_start_page": references_start_page,
            "azure_di_role_used": azure_di_role_used,  # 🎯 Azure DI role 사용
            "azure_di_sections": len(azure_di_sections),  # 🎯 Azure DI 섹션 수
        }
