"""Patent Analysis Tool - 입력 특허/문서 분석 도구

책임:
- 입력 텍스트(특허 명세서, 기술 문서 등) 분석
- 핵심 키워드 추출 (KoreanNLPService 활용)
- 기술 분야 및 IPC 코드 추정 (향후 확장)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

from app.services.core.korean_nlp_service import korean_nlp_service


class PatentAnalysisTool(BaseTool):
    name: str = "patent_analysis"
    description: str = "입력된 특허/문서 텍스트를 분석하여 핵심 키워드와 기술적 특징을 추출합니다."
    version: str = "1.0.0"

    async def analyze(
        self,
        *,
        text: str,
        fallback_query: Optional[str] = None,
        max_length: int = 8000,
    ) -> Dict[str, Any]:
        """
        텍스트 분석 및 키워드 추출 실행
        
        Args:
            text: 분석할 문서 텍스트
            fallback_query: 텍스트가 부족할 경우 사용할 대체 질의
            max_length: 분석할 최대 텍스트 길이
            
        Returns:
            Dict: {
                "keywords": List[str],
                "summary_excerpt": str,
                "original_length": int,
                "ipc_candidates": List[str],
                "ipc_code": Optional[str],
                "applicant_candidates": List[str],
                "applicant": Optional[str]
            }
        """
        clean_text = (text or "").strip().replace("\r", "")
        input_excerpt = clean_text[:1200] if clean_text else ""

        def _extract_focus_text(src: str) -> str:
            """Extract more semantically meaningful segments from patent-like text.

            Goal: avoid boilerplate (gazette headers, authority/metadata) dominating keywords.
            """
            if not src:
                return ""

            # 1) Invention title (KR)
            title = ""
            title_patterns = [
                r"\(\s*54\s*\)\s*발명의\s*명칭\s*(.+)",
                r"(?:^|\n)\s*발명의\s*명칭\s*[:：]?\s*(.+)",
            ]
            for pat in title_patterns:
                m = re.search(pat, src)
                if m:
                    title = (m.group(1) or "").strip()
                    title = re.split(r"\s{2,}|\t|\n", title)[0].strip()
                    break

            # 2) Abstract / summary (KR)
            abstract = ""
            abstract_markers = [r"\(\s*57\s*\)", r"요\s*약", r"요\s*약\s*[:：]", r"요\s*약\n"]
            start_idx = -1
            for pat in abstract_markers:
                m = re.search(pat, src)
                if m:
                    start_idx = m.end()
                    break
            if start_idx >= 0:
                tail = src[start_idx: start_idx + 6000]
                # Stop at the next major section marker
                stop_pat = re.compile(
                    r"(?:\n\s*대\s*표\s*도\s*-|\n\s*명\s*세\s*서|\n\s*청\s*구\s*범\s*위|\n\s*청\s*구\s*항|\n\s*-\s*\d+\s*-)",
                    re.IGNORECASE,
                )
                sm = stop_pat.search(tail)
                abstract = (tail[: sm.start()] if sm else tail).strip()

            # 3) First claim excerpt (optional)
            claim = ""
            cm = re.search(r"(?:\n|^)\s*청\s*구\s*항\s*1\b", src)
            if cm:
                claim_tail = src[cm.end(): cm.end() + 1500]
                claim = claim_tail.strip()

            parts = [p for p in [title, abstract, claim] if p]
            return "\n\n".join(parts).strip()

        focus_text = _extract_focus_text(clean_text)

        analysis_target = (focus_text[:max_length] if focus_text else clean_text[:max_length]) if clean_text else (fallback_query or "")

        # Remove very common gazette boilerplate tokens that pollute keyword extraction.
        # Keep this conservative; we only strip clear metadata words.
        boilerplate_patterns = [
            r"대한민국\s*특허청", r"공개\s*특허\s*공보", r"공개\s*특허", r"공개\s*번호", r"공개\s*일자",
            r"출원\s*번호", r"출원\s*일자", r"국제\s*특허\s*분류", r"CPC\s*특허\s*분류", r"특허\s*분류",
            r"발명자", r"대리인", r"심사\s*청구\s*일자", r"전체\s*청구\s*항\s*수", r"대표\s*도",
        ]
        if analysis_target:
            for pat in boilerplate_patterns:
                analysis_target = re.sub(pat, " ", analysis_target)
            analysis_target = re.sub(r"\s+", " ", analysis_target).strip()
        
        extracted_keywords: List[str] = []
        if analysis_target:
            try:
                analysis = await korean_nlp_service.analyze_text_for_search(analysis_target)
                extracted_keywords = list(analysis.get("keywords") or [])
            except Exception as e:
                logger.warning(f"⚠️ [PatentAnalysisTool] 키워드 추출 실패: {e}")

        # Post-filter: drop obvious boilerplate singletons that still slip through.
        stopwords = {
            "공개", "특허", "공보", "번호", "일자", "대한민국", "특허청",
            "출원", "출원인", "발명", "발명자", "국제", "분류", "대표도",
        }
        extracted_keywords = [
            k for k in extracted_keywords
            if k and k.strip() and k.strip() not in stopwords
        ]
        
        # 키워드가 없으면 fallback_query에서라도 추출 시도 (단순 공백 분리 등)
        if not extracted_keywords and fallback_query:
            extracted_keywords = fallback_query.split()

        # ---- Heuristic hint extraction (MVP+) ----
        ipc_candidates: List[str] = []
        applicant_candidates: List[str] = []

        if clean_text:
            # IPC 패턴: 예) AНав? → A61K 31/00, H04L 9/00 등
            ipc_re = re.compile(r"\b([A-H]\d{2}[A-Z]\s*\d{1,2}\s*/\s*\d{1,4})\b")
            for m in ipc_re.finditer(clean_text[:20000]):
                ipc = re.sub(r"\s+", "", m.group(1))
                if ipc and ipc not in ipc_candidates:
                    ipc_candidates.append(ipc)
                if len(ipc_candidates) >= 5:
                    break

            # 출원인/Applicant 라인 휴리스틱
            applicant_re = re.compile(r"(?:^|\n)\s*(?:출원인|Applicant)\s*[:：]\s*(.{2,80})")
            for m in applicant_re.finditer(clean_text[:20000]):
                cand = (m.group(1) or "").strip()
                cand = re.split(r"\s{2,}|\t|\n", cand)[0].strip()
                cand = cand.strip("-•· ")
                if cand and cand not in applicant_candidates:
                    applicant_candidates.append(cand)
                if len(applicant_candidates) >= 3:
                    break

        ipc_code = ipc_candidates[0] if ipc_candidates else None
        applicant = applicant_candidates[0] if applicant_candidates else None

        return {
            "keywords": extracted_keywords,
            "summary_excerpt": input_excerpt,
            "original_length": len(clean_text),
            "ipc_candidates": ipc_candidates,
            "ipc_code": ipc_code,
            "applicant_candidates": applicant_candidates,
            "applicant": applicant,
        }

    async def _arun(self, *args, **kwargs):
        return await self.analyze(*args, **kwargs)

    def _run(self, *args, **kwargs):
        raise NotImplementedError("PatentAnalysisTool supports async only.")


patent_analysis_tool = PatentAnalysisTool()
