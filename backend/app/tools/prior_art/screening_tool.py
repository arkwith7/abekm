"""Prior Art Screening Tool - 선행기술 후보 스크리닝 도구

책임:
- 검색 결과 후보 정리(필수 필드 체크, 중복 제거)
- 관련도 점수 산정(키워드 기반 단순 휴리스틱)
- 컷오프(최소 관련도) 및 불용 후보 제거
- 최종 정렬/상위 N 선정

주의:
- 이 도구는 "검색 실행"을 수행하지 않는다.
- 모델 객체(KiprisPatentBasic 등)에는 변경을 가하지 않고, 정렬/필터링에만 사용한다.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool


class PriorArtScreeningTool(BaseTool):
    name: str = "prior_art_screening"
    description: str = "검색 결과 후보를 스크리닝(중복 제거/관련도 컷오프/불용 후보 제거)합니다."
    version: str = "1.0.0"

    def _normalize_keywords(self, keywords: Optional[List[str]]) -> List[str]:
        stop = {
            # Generic terms that appear in many patents and overwhelm scoring
            "방법", "장치", "시스템", "단계", "제공", "수행", "식별", "기초", "수신",
            "입력", "데이터", "변경", "정보", "관련", "위한", "통해", "상기", "본", "일",
            "실시", "개시",
            # Boilerplate-ish
            "공개", "특허", "공보", "번호", "일자", "대한민국", "특허청", "출원", "출원인",
        }

        normalized: List[str] = []
        for kw in (keywords or []):
            k = (kw or "").strip().lower()
            if len(k) < 2:
                continue
            if k in stop:
                continue
            if k not in normalized:
                normalized.append(k)
        return normalized

    def _score(self, patent: Any, normalized_keywords: List[str]) -> int:
        if not normalized_keywords:
            return 0
        hay = f"{getattr(patent, 'title', '')} {getattr(patent, 'abstract', '')}".lower()
        hits = 0
        seen = set()
        for kw in normalized_keywords:
            if not kw or kw in seen:
                continue
            if kw in hay:
                # Weight longer tokens more (more discriminative)
                hits += 2 if len(kw) >= 4 else 1
                seen.add(kw)
        return hits

    def screen_and_rank(
        self,
        *,
        candidates: List[Any],
        target_keywords: Optional[List[str]] = None,
        min_relevance_score: Optional[int] = None,
        max_candidates: Optional[int] = None,
    ) -> Tuple[List[Any], Dict[str, int]]:
        """스크리닝 수행.

        Args:
            candidates: 검색 결과 후보(중복 포함 가능)
            target_keywords: 관련도 산정에 사용할 키워드
            min_relevance_score: 최소 관련도 컷오프. None이면 자동 결정(키워드 있으면 1, 없으면 0)
            max_candidates: 상위 N개로 제한 (None이면 제한 없음)

        Returns:
            (screened_candidates, stats)
        """
        total_in = len(candidates or [])
        normalized_keywords = self._normalize_keywords(target_keywords)

        if min_relevance_score is None:
            # If we have enough keywords, require a bit more than a single common-token hit.
            # Weighted scoring: 2 points roughly equals one meaningful long-token hit.
            if normalized_keywords:
                min_relevance_score = 2 if len(normalized_keywords) >= 8 else 1
            else:
                min_relevance_score = 0

        # 1) 기본 유효성 필터 + 중복 제거(출원번호 기준)
        combined: Dict[str, Any] = {}
        invalid = 0
        for p in (candidates or []):
            app_no = getattr(p, 'application_number', None) or ''
            title = (getattr(p, 'title', None) or '').strip()
            abstract = (getattr(p, 'abstract', None) or '').strip()

            if not app_no:
                invalid += 1
                continue

            # 제목/초록이 모두 비어있으면 불용 후보로 간주
            if not title and not abstract:
                invalid += 1
                continue

            if app_no not in combined:
                combined[app_no] = p

        deduped = list(combined.values())

        # 2) 관련도 컷오프
        screened: List[Any] = []
        dropped_low_score = 0
        for p in deduped:
            s = self._score(p, normalized_keywords)
            if s < (min_relevance_score or 0):
                dropped_low_score += 1
                continue
            screened.append(p)

        # 3) 정렬: 관련도(score) 우선, 그 다음 출원일 내림차순
        def _date(p: Any) -> str:
            return getattr(p, 'application_date', None) or ''

        screened.sort(
            key=lambda p: (self._score(p, normalized_keywords), _date(p)),
            reverse=True,
        )

        if max_candidates is not None and max_candidates >= 0:
            screened = screened[:max_candidates]

        stats = {
            'total_in': total_in,
            'invalid_or_empty_dropped': invalid,
            'deduped': len(deduped),
            'low_relevance_dropped': dropped_low_score,
            'total_out': len(screened),
        }

        logger.info(
            "✅ [PriorArtScreening] in=%d deduped=%d out=%d (invalid=%d low_score=%d min_score=%d)",
            total_in,
            len(deduped),
            len(screened),
            invalid,
            dropped_low_score,
            min_relevance_score,
        )

        return screened, stats

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("Use screen_and_rank().")

    def _run(self, *args, **kwargs):
        raise NotImplementedError("PriorArtScreeningTool supports async only.")


prior_art_screening_tool = PriorArtScreeningTool()
