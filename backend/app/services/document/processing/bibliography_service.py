"""
Bibliographic metadata extraction and persistence for academic papers.
Lightweight heuristics now; can be improved later.
"""
import re
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    TbAcademicDocumentMetadata,
)

logger = logging.getLogger(__name__)


DOI_PATTERN = re.compile(r"10\.\d{4,}/\S+", re.IGNORECASE)


class BibliographyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_document_metadata(
        self,
        file_bss_info_sno: int,
        full_text: str,
        sections_summary: Optional[Dict[str, Any]] = None,
        first_page_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract minimal metadata (title, abstract, doi, year) and upsert into tb_academic_document_metadata.
        """
        logger.info(f"[BIBLIO] 📚 upsert_document_metadata 호출: file_bss_info_sno={file_bss_info_sno}")
        try:
            title = self._guess_title(full_text, first_page_text)
            abstract = self._get_abstract_from_sections(sections_summary, full_text)
            doi = self._extract_doi(full_text)
            year = self._extract_year(full_text)
            
            logger.info(f"[BIBLIO] 🔍 추출된 메타데이터:")
            logger.info(f"  - title: {title[:80] if title else None}...")
            logger.info(f"  - abstract: {'있음' if abstract else '없음'} ({len(abstract) if abstract else 0}자)")
            logger.info(f"  - doi: {doi}")
            logger.info(f"  - year: {year}")

            # Idempotent upsert strategy
            # 1) Prefer matching by DOI (unique). If found, update fields in-place (do NOT change PK file_bss_info_sno).
            # 2) If no DOI or not found, upsert by file_bss_info_sno.
            row = None

            if doi:
                res_by_doi = await self.db.execute(
                    select(TbAcademicDocumentMetadata).where(TbAcademicDocumentMetadata.doi == doi)
                )
                row = res_by_doi.scalar_one_or_none()
                if row:
                    logger.info("[BIBLIO] 🔄 기존 DOI 레코드 발견 – 병합 업데이트 진행")
                    self._merge_metadata_fields(row, title=title, abstract=abstract, year=year)
                else:
                    # No row with this DOI exists; check by PK to avoid duplicate PK insert
                    res_by_pk = await self.db.execute(
                        select(TbAcademicDocumentMetadata).where(
                            TbAcademicDocumentMetadata.file_bss_info_sno == file_bss_info_sno
                        )
                    )
                    row = res_by_pk.scalar_one_or_none()
                    if row is None:
                        logger.info("[BIBLIO] 🆕 신규 메타데이터 INSERT (PK=파일, DOI 지정)")
                        row = TbAcademicDocumentMetadata(
                            file_bss_info_sno=file_bss_info_sno,
                            title=title,
                            abstract=abstract,
                            doi=doi,
                            year=year,
                        )
                        self.db.add(row)
                    else:
                        logger.info("[BIBLIO] ✏️ 기존 PK 레코드에 DOI/필드 업데이트")
                        self._merge_metadata_fields(row, title=title, abstract=abstract, year=year, doi=doi)
            else:
                # No DOI extracted – fallback to file PK upsert
                res_by_pk = await self.db.execute(
                    select(TbAcademicDocumentMetadata).where(
                        TbAcademicDocumentMetadata.file_bss_info_sno == file_bss_info_sno
                    )
                )
                row = res_by_pk.scalar_one_or_none()
                if row is None:
                    logger.info("[BIBLIO] 🆕 DOI 없음 – 신규 메타데이터 INSERT (PK=파일)")
                    row = TbAcademicDocumentMetadata(
                        file_bss_info_sno=file_bss_info_sno,
                        title=title,
                        abstract=abstract,
                        doi=None,
                        year=year,
                    )
                    self.db.add(row)
                else:
                    logger.info("[BIBLIO] ✏️ DOI 없음 – 기존 PK 레코드 업데이트")
                    self._merge_metadata_fields(row, title=title, abstract=abstract, year=year)

            await self.db.commit()
            logger.info(f"[BIBLIO] ✅ DB 커밋 성공: file_bss_info_sno={file_bss_info_sno}")
            return {"success": True, "file_bss_info_sno": file_bss_info_sno, "doi": doi, "year": year, "title": title}
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[BIBLIO] ❌ upsert 실패: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _merge_metadata_fields(
        self,
        row: "TbAcademicDocumentMetadata",
        *,
        title: Optional[str] = None,
        abstract: Optional[str] = None,
        year: Optional[str] = None,
        doi: Optional[str] = None,
    ) -> None:
        """Merge non-empty fields into existing row without overwriting non-empty values."""
        if title and not getattr(row, "title", None):
            setattr(row, "title", title)
        if abstract and not getattr(row, "abstract", None):
            setattr(row, "abstract", abstract)
        if year and not getattr(row, "year", None):
            setattr(row, "year", year)
        if doi and not getattr(row, "doi", None):
            setattr(row, "doi", doi)

    def _extract_doi(self, text: str) -> Optional[str]:
        if not text:
            return None
        m = DOI_PATTERN.search(text)
        return m.group(0) if m else None

    def _extract_year(self, text: str) -> Optional[str]:
        # naive: first occurrence of 20xx or 19xx
        m = re.search(r"\b(20\d{2}|19\d{2})\b", text)
        return m.group(1) if m else None

    def _guess_title(self, full_text: str, first_page_text: Optional[str]) -> Optional[str]:
        """
        학술논문 제목 추출 (개선된 버전)
        - "[페이지 N]" 같은 헤더 제외
        - 제목으로 보이는 줄 찾기 (적절한 길이, 대문자 시작 등)
        """
        source = first_page_text or full_text
        if not source:
            return None
        
        lines = source.splitlines()

        def looks_like_journal_info(s: str) -> bool:
            s_lower = s.lower()
            journal_keywords = [
                "journal", "issn", "volume", "vol.", "vol ", "no.", "no ", "publisher", "proceedings",
                "학회", "학회지", "學會", "學會誌", "doi:", "kits", "society"
            ]
            if any(k in s_lower for k in journal_keywords):
                return True
            # dates and issue-like patterns
            if re.search(r"\b(19|20)\d{2}\b", s):  # year present in same line – often journal header
                if re.search(r"\b(no\.|vol\.|issue|pp\.|pages)\b", s_lower):
                    return True
            # mostly digits/symbols
            letters = sum(ch.isalpha() for ch in s)
            nonletters = max(1, len(s) - letters)
            if letters / nonletters < 0.3:
                return True
            # explicit known words seen in logs
            if "it서비스" in s_lower or "服務" in s:
                return True
            return False
        for i, line in enumerate(lines):
            l = line.strip()
            
            # 헤더 패턴 제외
            if l.startswith('[페이지') or l.startswith('[Page'):
                continue
            if re.match(r'^\d+\s*$', l):  # 단순 페이지 번호
                continue
            if len(l) < 10:  # 너무 짧은 줄 제외
                continue
            if len(l) > 300:  # 너무 긴 줄 제외
                continue
            
            # 제목으로 보이는 조건
            # 1. 첫 글자가 대문자이거나 한글
            # 2. 길이가 적당함 (10-300자)
            # 3. DOI나 저널 정보가 아님
            if l.lower().startswith('doi:') or l.lower().startswith('journal'):
                continue
            if re.match(r'^\d{4}年|^\d{4}-\d{2}-\d{2}', l):  # 날짜 형식 제외
                continue
            if looks_like_journal_info(l):
                continue
            
            # 대문자로 시작하거나 한글이 포함된 경우 제목으로 간주
            if l[0].isupper() or any('\uAC00' <= c <= '\uD7A3' for c in l):
                return l
        
        # 못 찾으면 첫 번째 적절한 길이의 줄 반환
        for line in lines:
            l = line.strip()
            if 10 < len(l) < 300 and not l.startswith('[') and not looks_like_journal_info(l):
                return l
        
        return None

    def _get_abstract_from_sections(self, summary: Optional[Dict[str, Any]], full_text: Optional[str] = None) -> Optional[str]:
        """
        sections.json 또는 full_text에서 abstract 추출
        
        전략:
        1. sections 배열에서 type/mapped_type='abstract' 찾기
        2. 실패하면 full_text에서 패턴 매칭으로 추출
        """
        if not full_text:
            return None
        
        # 전략 1: sections 배열에서 찾기
        if summary:
            sections = summary.get('sections', [])
            
            for sec in sections:
                sec_type = sec.get('type', '')
                mapped_type = sec.get('mapped_type', '')
                
                # abstract로 매핑된 섹션 찾기
                if sec_type == 'abstract' or mapped_type == 'abstract':
                    if sec.get('start_pos') is not None and sec.get('end_pos') is not None:
                        start = sec['start_pos']
                        end = sec['end_pos']
                        abstract_text = full_text[start:end].strip()
                        if len(abstract_text) > 50:  # 최소 길이 체크
                            return abstract_text
        
        # 전략 2: full_text에서 패턴 매칭으로 찾기
        # "Abstract" 키워드 다음부터 "Introduction", "Keywords", "1." 등이 나올 때까지
        abstract_pattern = re.compile(
            r'\bAbstract\b\s*[:\n](.*?)(?=\b(?:Introduction|Keywords|Background|1\.|2\.|INTRODUCTION|METHODS|Results|DISCUSSION)\b)',
            re.IGNORECASE | re.DOTALL
        )
        
        match = abstract_pattern.search(full_text)
        if match:
            abstract_text = match.group(1).strip()
            # 헤더 정보 제거 (DOI, 저자명 등)
            # "[페이지 N]" 같은 패턴 제거
            abstract_text = re.sub(r'\[페이지 \d+\]', '', abstract_text)
            abstract_text = re.sub(r'\[Page \d+\]', '', abstract_text)
            # 표/지표 잡음 제거
            noise_tokens = [
                r"\bAVE\b", r"\bBCI\b", r"P-Value", r"\bDMA\b", r"\bIWB\b", r"\bOLB\b", r"\bCLB\b", r"\bRC\b",
                r"\bOE\b", r"\bWL\b", r"\bMGA\b"
            ]
            abstract_text = re.sub("|".join(noise_tokens), " ", abstract_text, flags=re.IGNORECASE)
            # 연속된 공백 정리
            abstract_text = re.sub(r'\s+', ' ', abstract_text).strip()
            
            if len(abstract_text) > 100:  # 최소 100자 이상이어야 실제 초록으로 간주
                return abstract_text
        
        # 전략 3: 간단한 fallback - Abstract 키워드 다음 1000자
        simple_match = re.search(r'\bAbstract\b\s*[:\n]', full_text, re.IGNORECASE)
        if simple_match:
            start_pos = simple_match.end()
            # 다음 1000자를 가져와서 정리
            candidate = full_text[start_pos:start_pos + 1500]
            # "[페이지 N]" 이후 시작
            page_match = re.search(r'\[페이지 \d+\]\s*', candidate)
            if page_match:
                candidate = candidate[page_match.end():]
            
            # Introduction 전까지만
            intro_match = re.search(r'\b(?:Introduction|Keywords|1\.|2\.|Methods|Results|Discussion)\b', candidate, re.IGNORECASE)
            if intro_match:
                candidate = candidate[:intro_match.start()]
            
            # 잡음 제거 후 공백 정리
            candidate = re.sub("|".join([r"\bAVE\b", r"\bBCI\b", r"P-Value"]), " ", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r'\s+', ' ', candidate).strip()
            if len(candidate) > 100:
                return candidate[:1000]  # 최대 1000자로 제한
        
        logger.warning(f"[BIBLIO] Abstract 추출 실패 - 모든 전략 시도했으나 발견 못함")
        return None
