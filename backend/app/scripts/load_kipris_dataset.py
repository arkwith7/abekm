#!/usr/bin/env python3
"""
KIPRIS 데이터셋 적재 스크립트
================================

목적:
- backend/data/processed/ 아래의 JSONL + PDF를 시스템 DB/벡터 인덱스에 적재
- 정식 파이프라인(PatentPipeline) 사용: PDF 파싱→섹션 청킹→임베딩→검색 인덱스

사용법:
    # 컨테이너 내부에서
    docker exec -it abkms-backend python -m app.scripts.load_kipris_dataset --limit 10

    # 로컬 venv에서
    source .venv/bin/activate
    python -m app.scripts.load_kipris_dataset --limit 10

옵션:
    --limit N          처리할 최대 건수 (기본: 전체)
    --container-id ID  특허를 저장할 컨테이너 ID (기본: KIPRIS_EVAL)
    --user USER        사용자 사번 (기본: system)
    --skip-existing    이미 DB에 있는 특허는 스킵
    --dry-run          실제 적재 없이 시뮬레이션만
"""
import asyncio
import argparse
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# SQLAlchemy 및 모델
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_async_session_local
from app.models import TbFileBssInfo

# 파이프라인 라우터
from app.services.document.pipeline_router import PipelineRouter

# 설정
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class KIPRISDatasetLoader:
    """KIPRIS 데이터셋 적재 클래스"""
    
    def __init__(
        self,
        container_id: str = "KIPRIS_EVAL",
        user_emp_no: str = "system",
        skip_existing: bool = True
    ):
        self.container_id = container_id
        self.user_emp_no = user_emp_no
        self.skip_existing = skip_existing
        self.session_factory = get_async_session_local()
        
        # 데이터 경로
        self.base_dir = Path(__file__).parent.parent.parent / "data" / "processed"
        self.jsonl_path = self.base_dir / "kipris_semiconductor_ai_dataset_paper.jsonl"
        self.pdf_dir = self.base_dir / "fulltext_pdfs"
        
        # 통계
        self.stats = {
            "total": 0,
            "loaded": 0,
            "skipped": 0,
            "failed": 0,
            "errors": []
        }
    
    async def load_dataset(self, limit: Optional[int] = None, dry_run: bool = False):
        """데이터셋 전체 적재"""
        logger.info(f"🚀 KIPRIS 데이터셋 적재 시작")
        logger.info(f"   📁 JSONL: {self.jsonl_path}")
        logger.info(f"   📁 PDF: {self.pdf_dir}")
        logger.info(f"   📦 컨테이너: {self.container_id}")
        logger.info(f"   👤 사용자: {self.user_emp_no}")
        logger.info(f"   ⚙️ 스킵 기존: {self.skip_existing}")
        logger.info(f"   🔢 제한: {limit or '없음'}")
        logger.info(f"   🧪 Dry-run: {dry_run}")
        
        if not self.jsonl_path.exists():
            logger.error(f"❌ JSONL 파일을 찾을 수 없음: {self.jsonl_path}")
            return
        
        if not self.pdf_dir.exists():
            logger.error(f"❌ PDF 디렉토리를 찾을 수 없음: {self.pdf_dir}")
            return
        
        # JSONL 읽기
        patents = []
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if limit and len(patents) >= limit:
                    break
                patents.append(json.loads(line))
        
        self.stats["total"] = len(patents)
        logger.info(f"📊 처리 대상: {len(patents)}건")
        
        # 각 특허 처리
        for idx, patent_data in enumerate(patents, 1):
            try:
                await self._process_patent(patent_data, idx, dry_run)
            except Exception as e:
                error_msg = f"특허 {idx} 처리 실패: {e}"
                logger.error(f"❌ {error_msg}")
                self.stats["failed"] += 1
                self.stats["errors"].append(error_msg)
        
        # 결과 요약
        self._print_summary()
    
    async def _process_patent(self, patent_data: Dict[str, Any], idx: int, dry_run: bool):
        """개별 특허 처리"""
        target = patent_data.get("target_patent", {})
        app_no = target.get("application_number")
        pub_no = target.get("publication_number")
        title = target.get("title", "")
        
        if not app_no:
            logger.warning(f"⚠️ [{idx}] 출원번호 없음, 스킵")
            self.stats["skipped"] += 1
            return
        
        # PDF 파일 찾기
        pdf_path = self._find_pdf(app_no, pub_no)
        if not pdf_path:
            logger.warning(f"⚠️ [{idx}] {app_no}: PDF 없음, 스킵")
            self.stats["skipped"] += 1
            return
        
        # 기존 데이터 체크
        if self.skip_existing and not dry_run:
            async with self.session_factory() as session:
                exists = await self._check_existing(session, app_no)
                if exists:
                    logger.info(f"⏭️  [{idx}] {app_no}: 이미 적재됨, 스킵")
                    self.stats["skipped"] += 1
                    return
        
        logger.info(f"📄 [{idx}/{self.stats['total']}] {app_no}: {title[:60]}...")
        
        if dry_run:
            logger.info(f"   🧪 [DRY-RUN] PDF 경로: {pdf_path}")
            logger.info(f"   🧪 [DRY-RUN] 실제 적재 생략")
            self.stats["loaded"] += 1
            return
        
        # 실제 적재
        try:
            await self._load_patent_document(
                app_no=app_no,
                pub_no=pub_no,
                title=title,
                pdf_path=pdf_path,
                patent_data=target
            )
            logger.info(f"   ✅ [{idx}] {app_no}: 적재 완료")
            self.stats["loaded"] += 1
            
        except Exception as e:
            logger.error(f"   ❌ [{idx}] {app_no}: 적재 실패 - {e}")
            self.stats["failed"] += 1
            self.stats["errors"].append(f"{app_no}: {e}")
    
    def _find_pdf(self, app_no: str, pub_no: Optional[str]) -> Optional[Path]:
        """PDF 파일 찾기 (출원번호 또는 공개번호 기준)"""
        # 1) 출원번호로 찾기
        candidates = [
            self.pdf_dir / f"{app_no}.pdf",
            self.pdf_dir / f"KR{app_no}.pdf",
        ]
        
        # 2) 공개번호로 찾기
        if pub_no:
            candidates.extend([
                self.pdf_dir / f"{pub_no}.pdf",
                self.pdf_dir / f"KR{pub_no}.pdf",
            ])
        
        for path in candidates:
            if path.exists():
                return path
        
        return None
    
    async def _check_existing(self, session: AsyncSession, app_no: str) -> bool:
        """이미 적재된 특허인지 확인"""
        # 파일명에 출원번호가 포함된 레코드 찾기
        stmt = select(TbFileBssInfo).where(
            TbFileBssInfo.document_type == 'patent',
            TbFileBssInfo.file_lgc_nm.like(f"%{app_no}%"),
            TbFileBssInfo.del_yn != 'Y'
        )
        result = await session.execute(stmt)
        return result.first() is not None
    
    async def _load_patent_document(
        self,
        app_no: str,
        pub_no: Optional[str],
        title: str,
        pdf_path: Path,
        patent_data: Dict[str, Any]
    ):
        """특허 문서를 시스템 파이프라인으로 적재"""
        async with self.session_factory() as session:
            # 1) TbFileBssInfo 생성 (기본 정보)
            from app.models import TbFileDtlInfo
            import hashlib
            
            file_name = f"{app_no}_{title[:50]}.pdf"
            file_size = pdf_path.stat().st_size
            file_hash = hashlib.md5(pdf_path.read_bytes()).hexdigest()
            
            # 상세 정보
            file_dtl = TbFileDtlInfo(
                sj=title or app_no,
                cn=patent_data.get("abstract", "")[:1000],
                file_sz=file_size,
                authr=self.user_emp_no,
                created_by=self.user_emp_no,
                last_modified_by=self.user_emp_no
            )
            session.add(file_dtl)
            await session.flush()
            
            # 기본 정보
            file_bss = TbFileBssInfo(
                drcy_sno=1,
                file_dtl_info_sno=file_dtl.file_dtl_info_sno,
                file_lgc_nm=file_name,
                file_psl_nm=file_name,
                file_extsn="pdf",
                path=str(pdf_path),  # 로컬 경로 저장
                knowledge_container_id=self.container_id,
                owner_emp_no=self.user_emp_no,
                created_by=self.user_emp_no,
                last_modified_by=self.user_emp_no,
                korean_metadata={
                    "application_number": app_no,
                    "publication_number": pub_no,
                    "file_hash": file_hash,
                    "data_source": "KIPRIS",
                    "ipc": patent_data.get("ipc"),
                    "applicants": patent_data.get("applicants"),
                },
                document_type="patent",
                processing_status="pending",
                processing_options={
                    "extract_claims": True,
                    "priority_claims": True,
                    "technical_field_extraction": True
                }
            )
            session.add(file_bss)
            await session.flush()
            await session.commit()
            
            document_id = file_bss.file_bss_info_sno
            
            # 2) 파이프라인 실행 (PatentPipeline)
            logger.info(f"   🔄 파이프라인 시작: doc_id={document_id}")
            
            result = await PipelineRouter.process_document(
                document_type="patent",
                document_id=document_id,
                file_path=str(pdf_path),
                file_name=file_name,
                container_id=self.container_id,
                processing_options={
                    "extract_claims": True,
                    "priority_claims": True,
                    "technical_field_extraction": True
                },
                user_emp_no=self.user_emp_no
            )
            
            if not result.get("success"):
                # 파이프라인 실패 시 DB 레코드 삭제
                await session.rollback()
                raise Exception(f"파이프라인 실패: {result.get('error')}")
            
            # 3) 처리 상태 업데이트
            from sqlalchemy import update
            stmt = (
                update(TbFileBssInfo)
                .where(TbFileBssInfo.file_bss_info_sno == document_id)
                .values(
                    processing_status="completed",
                    processing_completed_at=datetime.now()
                )
            )
            await session.execute(stmt)
            await session.commit()
            
            stats = result.get("statistics", {})
            logger.info(f"   📊 청크: {stats.get('total_chunks', 0)}")
            logger.info(f"   📊 임베딩: {stats.get('total_embeddings', 0)}")
    
    def _print_summary(self):
        """결과 요약 출력"""
        logger.info("=" * 60)
        logger.info("📊 적재 완료 요약")
        logger.info("=" * 60)
        logger.info(f"   총 대상:     {self.stats['total']}건")
        logger.info(f"   ✅ 적재 완료:  {self.stats['loaded']}건")
        logger.info(f"   ⏭️  스킵:      {self.stats['skipped']}건")
        logger.info(f"   ❌ 실패:      {self.stats['failed']}건")
        
        if self.stats["errors"]:
            logger.info("")
            logger.info("오류 목록:")
            for error in self.stats["errors"][:10]:  # 최대 10개만
                logger.info(f"   - {error}")
            if len(self.stats["errors"]) > 10:
                logger.info(f"   ... 외 {len(self.stats['errors']) - 10}건")


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="KIPRIS 데이터셋을 시스템 DB/벡터 인덱스에 적재"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리할 최대 건수 (기본: 전체)"
    )
    parser.add_argument(
        "--container-id",
        type=str,
        default="KIPRIS_EVAL",
        help="컨테이너 ID (기본: KIPRIS_EVAL)"
    )
    parser.add_argument(
        "--user",
        type=str,
        default="system",
        help="사용자 사번 (기본: system)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="이미 적재된 특허는 스킵 (기본: True)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 적재 없이 시뮬레이션만"
    )
    
    args = parser.parse_args()
    
    loader = KIPRISDatasetLoader(
        container_id=args.container_id,
        user_emp_no=args.user,
        skip_existing=args.skip_existing
    )
    
    await loader.load_dataset(
        limit=args.limit,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main())
