"""
특허 문서 섹션 감지 서비스 (Multi-Country Patent Document Section Detector)

한국/미국/유럽/일본/중국 특허 문서의 정형화된 구조를 감지하고 섹션별로 분류:
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

국가별 특성:
- KR 한국: 띄어쓰기 변형 대응 ("기 술 분 야")
- US 미국: Abstract, Summary 섹션 지원
- JP 일본: 한자+가나 패턴, 번호 체계
- CN 중국: 간체자 패턴
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
    다국어 특허 문서 섹션 감지기
    
    한국/미국/유럽/일본/중국 특허청 표준 양식에 따른 섹션 헤더 패턴을 사용하여
    각 섹션을 자동으로 감지하고 분류
    
    특징:
    - 띄어쓰기 유연 매칭 ("기술분야" ≈ "기 술 분 야")
    - 국가별 번호 체계 대응 ([0001], 【0001】)
    - 영문/한글/한자/간체자 동시 지원
    """
    
    # 섹션 헤더 패턴 (우선순위 순서)
    SECTION_PATTERNS = [
        # ========== 청구항 / Claims (최고 우선순위) ==========
        {
            "type": "claims",
            "patterns": [
                # 한국 - 띄어쓰기 유연
                r"^\s*\[?\s*청\s*구\s*범\s*위\s*\]?",  # 청구범위 (표준)
                r"^\s*\[?\s*청\s*구\s*항\s*\]?",  # 청구항
                r"^\s*\[?\s*특\s*허\s*청\s*구\s*범\s*위\s*\]?",
                r"^\s*명\s*세\s*서",  # 명세서 (청구범위 포함)
                # 미국
                r"^\s*Claims?\s*$",
                r"^\s*What\s+is\s+claimed\s+is:\s*$",
                # 일본
                r"^\s*【?特許請求の範囲】?",
                r"^\s*【?請求項\d+】?",
                # 중국
                r"^\s*权利要求书",
                r"^\s*权利要求\d+",
            ],
            "priority": 0
        },
        
        # ========== 발명의 명칭 / Title ==========
        {
            "type": "title",
            "patterns": [
                # 한국
                r"^\s*\[?\s*발\s*명\s*의\s*명\s*칭\s*\]?\s*$",
                # KIPO 공보 상단 테이블 형태: '| (54) 발명의 명칭 ... |'
                r"^\s*\|?\s*\(\s*54\s*\)\s*발\s*명\s*의\s*명\s*칭\b.*$",
                # 변형: '(54)발명의명칭:' 등
                r"^\s*\|?\s*\(\s*54\s*\)\s*발\s*명\s*의\s*명\s*칭\s*[:：].*$",
                # 미국
                r"^\s*\[?\s*Title\s*of\s*(?:the\s*)?Invention\s*\]?",
                # 일본
                r"^\s*【?発明の名称】?",
                # 중국
                r"^\s*发明名称",
            ],
            "priority": 1
        },
        
        # ========== 요약 / Abstract (미국 특허) ==========
        {
            "type": "abstract",
            "patterns": [
                r"^\s*\[?\s*요\s*약\s*\]?",  # 한국
                r"^\s*\(\s*57\s*\)\s*요\s*약",  # (57) 요 약
                r"^\s*Abstract\s*$",  # 미국
                r"^\s*【?要約】?",  # 일본
                r"^\s*摘要",  # 중국
            ],
            "priority": 1
        },
        
        # ========== 기술분야 / Technical Field ==========
        {
            "type": "technical_field",
            "patterns": [
                # 한국 - 띄어쓰기 유연
                r"^\s*\[?\s*기\s*술\s*분\s*야\s*\]?",
                r"^\s*기\s*술\s*분\s*야\s*$",  # 제목만 있는 경우
                # 미국
                r"^\s*\[?\s*Technical\s*Field\s*\]?",
                r"^\s*Field\s*of\s*(?:the\s*)?Invention",
                # 일본
                r"^\s*【?技術分野】?",
                # 중국
                r"^\s*技术领域",
            ],
            "priority": 2
        },
        
        # ========== 배경기술 / Background ==========
        {
            "type": "background",
            "patterns": [
                # 한국 - 띄어쓰기 유연
                r"^\s*\[?\s*발\s*명\s*의\s*배\s*경\s*\]?",
                r"^\s*\[?\s*배\s*경\s*기\s*술\s*\]?",
                r"^\s*배\s*경\s*기\s*술\s*$",
                # 미국
                r"^\s*\[?\s*Background\s*(?:of\s*(?:the\s*)?Invention)?\s*\]?",
                r"^\s*Description\s*of\s*(?:the\s*)?Related\s*Art",
                # 일본
                r"^\s*【?背景技術】?",
                # 중국
                r"^\s*背景技术",
            ],
            "priority": 3
        },
        
        # ========== 선행기술문헌 / Prior Art ==========
        {
            "type": "prior_art",
            "patterns": [
                # 한국
                r"^\s*\[?\s*선\s*행\s*기\s*술\s*문\s*헌\s*\]?",
                # KIPO 공보 상단 테이블 형태: '| (56) 선행기술조사문헌 ... |'
                r"^\s*\|?\s*\(\s*56\s*\)\s*선\s*행\s*기\s*술\s*(?:조\s*사\s*)?문\s*헌\b.*$",
                # 변형: '(56) 선행기술조사문헌' / '선행기술조사문헌'
                r"^\s*\[?\s*선\s*행\s*기\s*술\s*(?:조\s*사\s*)?문\s*헌\s*\]?\s*$",
                # 문헌 구분 헤더 (특허문헌/비특허문헌/인용문헌/참고문헌)
                r"^\s*\[?\s*(?:특\s*허|비\s*특\s*허)\s*문\s*헌\s*\]?\s*$",
                r"^\s*\[?\s*인\s*용\s*문\s*헌\s*\]?\s*$",
                r"^\s*\[?\s*참\s*고\s*문\s*헌\s*\]?\s*$",
                # 미국
                r"^\s*\[?\s*Prior\s*Art\s*(?:Documents?)?\s*\]?",
                r"^\s*References\s*Cited",
                # 일본
                r"^\s*【?先行技術文献】?",
                # 중국
                r"^\s*现有技术",
            ],
            "priority": 4
        },
        
        # ========== 발명의 내용 (Summary) ==========
        {
            "type": "summary",
            "patterns": [
                r"^\s*\[?\s*발\s*명\s*의\s*내\s*용\s*\]?",
                r"^\s*Summary\s*of\s*(?:the\s*)?Invention",
                r"^\s*【?発明の内容】?",  # 일본
                r"^\s*发明内容",  # 중국
            ],
            "priority": 4
        },
        
        # ========== 해결하려는 과제 / Problem ==========
        {
            "type": "problem",
            "patterns": [
                # 한국 - 다양한 변형
                r"^\s*\[?\s*해\s*결\s*하\s*려\s*는\s*과\s*제\s*\]?",
                r"^\s*\[?\s*해\s*결\s*하\s*고\s*자\s*하\s*는\s*과\s*제\s*\]?",
                r"^\s*\[?\s*발\s*명\s*이\s*해\s*결\s*하\s*고\s*자\s*하\s*는\s*과\s*제\s*\]?",
                r"^\s*해\s*결\s*하\s*려\s*는\s*과\s*제\s*$",
                # 미국
                r"^\s*\[?\s*Problem\s*(?:to\s*be\s*)?Solve[d]?\s*\]?",
                r"^\s*Technical\s*Problem",
                # 일본
                r"^\s*【?発明が解決しようとする課題】?",
                # 중국
                r"^\s*要解决的技术问题",
            ],
            "priority": 5
        },
        
        # ========== 과제의 해결 수단 / Solution ==========
        {
            "type": "solution",
            "patterns": [
                # 한국
                r"^\s*\[?\s*과\s*제\s*의\s*해\s*결\s*수\s*단\s*\]?",
                r"^\s*과\s*제\s*의\s*해\s*결\s*수\s*단\s*$",
                # 미국
                r"^\s*\[?\s*(?:Means\s*(?:for\s*)?)?Solv(?:ing|ution)\s*(?:to\s*)?(?:the\s*)?(?:Problem|Technical\s*Problem)\s*\]?",
                r"^\s*Technical\s*Solution",
                # 일본
                r"^\s*【?課題を解決するための手段】?",
                # 중국
                r"^\s*技术方案",
            ],
            "priority": 6
        },
        
        # ========== 발명의 효과 / Effects ==========
        {
            "type": "effects",
            "patterns": [
                # 한국
                r"^\s*\[?\s*발\s*명\s*의\s*효\s*과\s*\]?",
                r"^\s*발\s*명\s*의\s*효\s*과\s*$",
                # 미국
                r"^\s*\[?\s*(?:Advantageous\s*)?Effects?\s*of\s*(?:the\s*)?Invention\s*\]?",
                r"^\s*Advantages\s*of\s*the\s*Invention",
                # 일본
                r"^\s*【?発明の効果】?",
                # 중국
                r"^\s*有益效果",
            ],
            "priority": 7
        },
        
        # ========== 도면의 간단한 설명 / Brief Description of Drawings ==========
        {
            "type": "brief_description_drawings",
            "patterns": [
                # 한국
                r"^\s*\[?\s*도\s*면\s*의\s*간\s*단\s*한\s*설\s*명\s*\]?",
                r"^\s*도\s*면\s*의\s*간\s*단\s*한\s*설\s*명\s*$",
                # 미국
                r"^\s*\[?\s*Brief\s*Description\s*of\s*(?:the\s*)?Drawings?\s*\]?",
                # 일본
                r"^\s*【?図面の簡単な説明】?",
                # 중국
                r"^\s*附图说明",
            ],
            "priority": 8
        },
        
        # ========== 발명을 실시하기 위한 구체적인 내용 / Detailed Description ==========
        {
            "type": "detailed_description",
            "patterns": [
                # 한국 - 다양한 변형
                r"^\s*\[?\s*발\s*명\s*을\s*실\s*시\s*하\s*기\s*위\s*한\s*구\s*체\s*적\s*인\s*내\s*용\s*\]?",
                r"^\s*\[?\s*발\s*명\s*의\s*상\s*세\s*한\s*설\s*명\s*\]?",
                r"^\s*발\s*명\s*을\s*실\s*시\s*하\s*기\s*위\s*한\s*구\s*체\s*적\s*인\s*내\s*용\s*$",
                # 미국
                r"^\s*\[?\s*Detailed\s*Description\s*(?:of\s*(?:the\s*)?(?:Invention|Preferred\s*Embodiments?))?\s*\]?",
                r"^\s*Description\s*of\s*(?:the\s*)?Embodiments?",
                # 일본
                r"^\s*【?発明を実施するための形態】?",
                r"^\s*【?実施例】?",
                # 중국
                r"^\s*具体实施方式",
            ],
            "priority": 9
        },
        
        # ========== 산업상 이용 가능성 (일본) ==========
        {
            "type": "industrial_applicability",
            "patterns": [
                r"^\s*\[?\s*산\s*업\s*상\s*이\s*용\s*가\s*능\s*성\s*\]?",
                r"^\s*【?産業上の利用可能性】?",  # 일본
                r"^\s*Industrial\s*Applicability",
            ],
            "priority": 9
        },
        
        # ========== 도면 / Drawings ==========
        {
            "type": "drawings",
            "patterns": [
                # 한국
                r"^\s*\[?\s*도\s*면\s*\]?",
                r"^\s*대\s*표\s*도",  # 대표도
                # 미국
                r"^\s*\[?\s*Drawings?\s*\]?",
                # 일본
                r"^\s*【?図面】?",
                # 중국
                r"^\s*附图",
            ],
            "priority": 10
        },
        
        # ========== 부호의 설명 (일본) ==========
        {
            "type": "reference_numerals",
            "patterns": [
                r"^\s*【?符号の説明】?",  # 일본
                r"^\s*\[?\s*부\s*호\s*의\s*설\s*명\s*\]?",  # 한국 (드물게 사용)
            ],
            "priority": 10
        },
    ]
    
    # 섹션 타입별 한글 이름
    SECTION_NAMES = {
        "claims": "청구항",
        "title": "발명의 명칭",
        "abstract": "요약",
        "technical_field": "기술분야",
        "background": "배경기술",
        "prior_art": "선행기술문헌",
        "summary": "발명의 내용",
        "problem": "해결하려는 과제",
        "solution": "과제의 해결 수단",
        "effects": "발명의 효과",
        "brief_description_drawings": "도면의 간단한 설명",
        "detailed_description": "발명을 실시하기 위한 구체적인 내용",
        "industrial_applicability": "산업상 이용 가능성",
        "drawings": "도면",
        "reference_numerals": "부호의 설명",
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
        sections: List[PatentSection] = []
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
                priority=marker["priority"],
            )

            # 청구항인 경우 개별 항 파싱
            if marker["type"] == "claims":
                section.subsections = self._parse_claims(content)
                logger.info(f"[PATENT-SECTION] 청구항 파싱: {len(section.subsections or [])}개 항 발견")

            sections.append(section)

        # 선행기술문헌 섹션이 명시적으로 없을 경우, 인용/문헌번호 패턴 기반으로 작은 구간을 합성
        self._maybe_add_synthesized_prior_art_section(full_text, sections)

        # 위치순 정렬 유지
        sections.sort(key=lambda s: s.start_pos)
        
        logger.info(f"[PATENT-SECTION] ✅ {len(sections)}개 섹션 감지 완료")
        self._log_section_summary(sections)
        
        return sections

    # ---------------------------------------------------------------------
    # Prior Art (선행기술문헌) 보강: 헤더가 없으면 인용 패턴으로 합성
    # ---------------------------------------------------------------------
    _PRIOR_ART_KEYWORDS_RE = re.compile(
        r"(?:선\s*행\s*기\s*술\s*(?:조\s*사\s*)?문\s*헌|특\s*허\s*문\s*헌|비\s*특\s*허\s*문\s*헌|인\s*용\s*문\s*헌|참\s*고\s*문\s*헌|references\s+cited|prior\s+art)",
        re.IGNORECASE,
    )

    # 대표적인 특허문헌 식별자 (너무 광범위해지는 것을 방지하기 위해 country-code 기반 패턴 우선)
    _PATENT_DOCNO_RES: List[re.Pattern] = [
        # KR 공개/등록/출원: 10-YYYY-XXXXXXX
        re.compile(r"\b(?:KR\s*)?10-\d{4}-\d{6,7}\b", re.IGNORECASE),
        # WO: WOYYYY/XXXXXX
        re.compile(r"\bWO\s*\d{4}\s*/\s*\d{5,7}\b", re.IGNORECASE),
        # JP: JPYYYY-XXXXXX (공보에서 흔함)
        re.compile(r"\bJP\s*\d{4}\s*-\s*\d{5,7}\b", re.IGNORECASE),
        # EP: EP + 6~8 digits
        re.compile(r"\bEP\s*\d{6,8}\b", re.IGNORECASE),
        # US: US 7,123,456 / US7123456 / US 2008/0123456
        re.compile(r"\bUS\s*(?:\d{4}\s*/\s*\d{6,7}|\d{1,2}[, ]?\d{3}[, ]?\d{3,4}|\d{7,9})\b", re.IGNORECASE),
        # CN: CN + digits
        re.compile(r"\bCN\s*\d{6,12}\b", re.IGNORECASE),
    ]

    def extract_prior_art_citations(self, text: str, exclude: Optional[List[str]] = None) -> List[str]:
        """텍스트에서 특허문헌 번호를 추출해 정규화된 문자열 리스트로 반환.

        Args:
            text: 대상 텍스트
            exclude: 제외할 문헌번호(대상 문서의 자기번호 등). 공백/대소문자 무시.
        """
        if not text:
            return []

        exclude_keys = set()
        for ex in exclude or []:
            if not ex:
                continue
            exclude_keys.add(re.sub(r"\s+", "", ex).upper())

        citations: List[str] = []
        for pattern in self._PATENT_DOCNO_RES:
            for match in pattern.finditer(text):
                raw = match.group(0)
                normalized = re.sub(r"\s+", " ", raw).strip()
                key = normalized.upper().replace(" ", "")
                if key in exclude_keys:
                    continue
                citations.append(normalized)

        # 중복 제거 (순서 유지)
        seen = set()
        deduped: List[str] = []
        for c in citations:
            key = c.upper().replace(" ", "")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)
        return deduped

    def _extract_self_doc_numbers(self, full_text: str) -> List[str]:
        """문서 자체(공개/등록/출원) 번호로 보이는 값을 추정해서 반환.

        선행기술 합성 시 '자기번호'로 인해 전체 문서가 prior_art로 오염되는 것을 방지한다.
        """
        if not full_text:
            return []
        # 문서 상단에 반복 등장하는 KR 10-YYYY-XXXXXXX 를 우선 자기번호 후보로 간주
        kr_pat = self._PATENT_DOCNO_RES[0]
        matches = list(kr_pat.finditer(full_text[:3000]))
        if not matches:
            return []
        first = re.sub(r"\s+", " ", matches[0].group(0)).strip()
        return [first]

    def _maybe_add_synthesized_prior_art_section(self, full_text: str, sections: List[PatentSection]) -> None:
        """prior_art 섹션이 없으면 인용 패턴이 있는 구간을 prior_art로 합성한다.

        원칙:
        - 근거(문헌번호/키워드)가 있을 때만 합성한다. (없는 문서는 억지로 만들지 않음)
        - 합성 구간은 가능한 작게 만들어 기존 섹션 매핑을 오염시키지 않는다.
        """
        if not full_text or not sections:
            return
        if any(s.section_type == "prior_art" for s in sections):
            return

        # 1) 가능한 경우 배경기술 섹션 내부에서만 문헌번호를 탐색 (오탐/과대 범위 방지)
        background = next((s for s in sections if s.section_type == "background"), None)
        search_text = background.content if background else full_text
        base_offset = background.start_pos if background else 0

        self_doc_numbers = self._extract_self_doc_numbers(full_text)

        lines = search_text.split("\n")

        # 후보 라인: (A) 문헌 키워드 포함 + (B) 문헌번호(국가코드/형식) 포함
        # - 키워드 없는 단순 번호는 대부분 자기번호/머리말 반복이므로 제외
        candidate_line_idxs: List[int] = []
        for idx, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            has_keyword = bool(self._PRIOR_ART_KEYWORDS_RE.search(line_stripped))
            has_docno = any(p.search(line_stripped) for p in self._PATENT_DOCNO_RES)

            if has_keyword and has_docno:
                candidate_line_idxs.append(idx)
                continue

            # 특허문헌/비특허문헌 라벨은 다음 줄들에 번호가 오는 경우가 많아서 작은 창을 확인
            if has_keyword:
                window = "\n".join(lines[idx: min(len(lines), idx + 4)])
                window_citations = self.extract_prior_art_citations(window, exclude=self_doc_numbers)
                if window_citations:
                    candidate_line_idxs.append(idx)

        if not candidate_line_idxs:
            return

        # 합성 구간: 후보 라인 주변의 매우 작은 범위만 포함 (배경기술 내부에 고정)
        first_idx = min(candidate_line_idxs)
        last_idx = max(candidate_line_idxs)

        start_idx = max(0, first_idx - 1)
        end_idx = min(len(lines) - 1, last_idx + 2)

        start_pos = base_offset + sum(len(l) + 1 for l in lines[:start_idx])
        end_pos = base_offset + sum(len(l) + 1 for l in lines[: end_idx + 1])

        # 배경기술을 넘어가지 않도록 클램프
        if background:
            start_pos = max(start_pos, background.start_pos)
            end_pos = min(end_pos, background.end_pos)

        content = full_text[start_pos:end_pos].strip()
        citations = self.extract_prior_art_citations(content, exclude=self_doc_numbers)
        if not citations:
            return

        synthesized = PatentSection(
            section_type="prior_art",
            title=self.SECTION_NAMES.get("prior_art", "prior_art"),
            start_pos=start_pos,
            end_pos=end_pos,
            content=content,
            priority=4,
        )
        sections.append(synthesized)
    
    def _parse_claims(self, claims_text: str) -> List[PatentSection]:
        """
        청구항 텍스트에서 개별 항 파싱 (다국어 지원)
        
        청구항 번호 패턴:
        - 한국: "청구항 1", "제1항", "[청구항 1]"
        - 미국: "Claim 1."
        - 일본: "【請求項1】"
        - 중국: "权利要求1"
        """
        if not claims_text:
            return []
        
        # 청구항 번호 패턴 (다국어 지원)
        claim_pattern = re.compile(
            r'(?:^\s*|(?<=\n)\s*)'  # 줄 시작 또는 개행 후
            r'(?:'
            r'청구항\s*\d+|'  # 한국: "청구항 1"
            r'제\s*\d+\s*항|'  # 한국: "제1항"
            r'\[청구항\s*\d+\]|'  # 한국: "[청구항 1]"
            r'Claim\s*\d+\.?|'  # 미국: "Claim 1."
            r'【?請求項\d+】?|'  # 일본: "【請求項1】"
            r'权利要求\d+'  # 중국: "权利要求1"
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
