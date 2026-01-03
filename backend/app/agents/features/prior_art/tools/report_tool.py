"""Prior Art Report Tool - 선행기술조사 리포트 생성 도구

책임:
- 분석 결과 및 검색 결과를 바탕으로 Markdown 리포트 생성
- 리포트 파일 저장 (ChatAttachmentService 연동)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from app.services.chat.chat_attachment_service import ChatAttachmentService, StoredAttachment


class PriorArtReportTool(BaseTool):
    name: str = "prior_art_report"
    description: str = "선행기술조사 결과를 바탕으로 리포트를 생성하고 저장합니다."
    version: str = "1.0.0"

    def build_report(
        self,
        *,
        session_id: Optional[str],
        user_message: str,
        document_ids: Optional[List[str]],
        analysis_result: Dict[str, Any],
        search_metadata: Dict[str, Any],
        unique_patents: List[Any],
    ) -> Dict[str, str]:
        """
        Markdown 리포트 본문 생성
        
        Returns:
            Dict: {
                "report_md": str,
                "report_filename": str
            }
        """
        now_utc = datetime.utcnow()
        
        # Unpack analysis
        keywords = analysis_result.get("keywords", [])
        input_excerpt = analysis_result.get("summary_excerpt", "")

        # Unpack search metadata
        search_runs = search_metadata.get("search_runs", [])
        broad_query = search_metadata.get("broad_query") or ""
        balanced_query = search_metadata.get("balanced_query") or ""
        
        def _fmt_patent(p: Any) -> str:
            appl_no = getattr(p, "application_number", "")
            title = getattr(p, "title", "")
            applicant = getattr(p, "applicant", "")
            appl_date = getattr(p, "application_date", "")
            ipc = getattr(p, "ipc_code", "")
            abstract = (getattr(p, "abstract", "") or "").strip().replace("\r", "")
            if len(abstract) > 400:
                abstract = abstract[:400] + "…"
            lines = [
                f"- **{title or '(제목 없음)'}**",
                f"  - 출원번호: {appl_no}",
                f"  - 출원인: {applicant}",
                f"  - 출원일: {appl_date}",
                f"  - IPC: {ipc}",
            ]
            if abstract:
                lines.append(f"  - 초록: {abstract}")
            return "\n".join(lines)

        report_lines: List[str] = []
        report_lines.append("# 선행기술조사 리포트 (초안)")
        report_lines.append("")
        report_lines.append(f"- 생성 시각(UTC): {now_utc.isoformat()}")
        report_lines.append(f"- 세션: {session_id}")
        report_lines.append(f"- 질의: {user_message}")
        if document_ids:
            report_lines.append(f"- 선택 문서(document_ids): {', '.join(document_ids)}")
        report_lines.append("")

        report_lines.append("## 1) 입력 요약 (MVP)")
        report_lines.append("")
        report_lines.append(f"- 키워드(추출): {', '.join(keywords or [])}")
        report_lines.append(f"- 검색 질의(broad): {broad_query}")
        report_lines.append(f"- 검색 질의(balanced): {balanced_query}")
        if input_excerpt:
            report_lines.append("")
            report_lines.append("### 첨부 문서 발췌 (최대 1,200자)")
            report_lines.append("```text")
            report_lines.append(input_excerpt)
            report_lines.append("```")
        report_lines.append("")

        report_lines.append("## 2) 검색 실행 결과")
        report_lines.append("")
        for r in search_runs:
            label = r.get('label', 'query')
            returned = r.get('returned', 0)
            total_found = r.get('total_found', 0)
            q = r.get('query', '')
            report_lines.append(f"- {label}: returned={returned}, total_found={total_found} (query: {q})")
        report_lines.append("")

        report_lines.append("## 3) 선행기술 후보 목록 (Top 10)")
        report_lines.append("")
        top = unique_patents[:10]
        if not top:
            report_lines.append("- (결과 없음) 검색 조건이나 시스템 상태를 확인해주세요.")
        else:
            for idx, p in enumerate(top, start=1):
                report_lines.append(f"### 후보 {idx}")
                report_lines.append(_fmt_patent(p))
                report_lines.append("")

        report_lines.append("## 4) 비교/검토 체크리스트 (템플릿)")
        report_lines.append("")
        report_lines.append("- 독립항(1항) 대비 구성요소 매핑")
        report_lines.append("- 동일/유사 구성요소 존재 여부")
        report_lines.append("- 차이점(차별 구성) 및 효과")
        report_lines.append("- 신규성/진보성 리스크(초안)")
        report_lines.append("")
        report_lines.append("## 5) 다음 액션")
        report_lines.append("")
        report_lines.append("- 후보별 전문(청구항/명세서) 확인 및 구성요소 표 작성")
        report_lines.append("- broad/balanced 질의 조정(핵심 키워드, IPC, 출원인/출원일 필터)")
        report_lines.append("- 필요 시 해외(US/EP/WO) 확장 검색")
        report_lines.append("")

        report_md = "\n".join(report_lines)
        safe_ts = now_utc.strftime("%Y%m%d_%H%M%S")
        report_filename = f"prior-art-report-{safe_ts}.md"

        return {"report_md": report_md, "report_filename": report_filename}

    async def save_report(
        self,
        *,
        chat_attachment_service: 'ChatAttachmentService',
        owner_emp_no: str,
        report_md: str,
        report_filename: str,
    ) -> 'StoredAttachment':
        """
        리포트 파일 저장
        """
        # NOTE: chat_attachment_service 모듈은 import 시 디렉토리 생성 등 사이드이펙트가 있어
        # 타입 참조는 지연(import inside)로 처리한다.
        return await chat_attachment_service.save_bytes(
            report_md.encode("utf-8"),
            owner_emp_no=owner_emp_no,
            file_name=report_filename,
            mime_type="text/markdown",
        )

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("Use build_report and save_report methods.")

    def _run(self, *args, **kwargs):
        raise NotImplementedError("PriorArtReportTool supports async only.")


prior_art_report_tool = PriorArtReportTool()
