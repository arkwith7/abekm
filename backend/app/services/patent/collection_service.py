"""
특허 수집 비즈니스 로직
- 수집 설정 CRUD
- 작업 상태 관리
- 특허 데이터 저장 (서지정보 + 문서 레코드)
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_
from loguru import logger

from app.models.patent import (
    TbPatentCollectionSettings,
    TbPatentCollectionTasks,
    TbPatentBibliographicInfo,
)
# 문서 메타 모델 (파일 기본 정보)
from app.models.document import TbFileBssInfo, TbDocumentSearchIndex
from app.models.document.multimodal_models import DocEmbedding, DocChunk, DocChunkSession
# S3 및 임베딩 서비스
from app.services.core.aws_service import S3Service
from app.services.core.embedding_service import EmbeddingService
import os
from pathlib import Path


class PatentCollectionService:
    """특허 수집 서비스"""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[date]:
        """
        KIPRIS 날짜 문자열(YYYYMMDD)을 date 객체로 변환
        
        Args:
            date_str: YYYYMMDD 형식의 문자열 (예: '20230614')
            
        Returns:
            date 객체 또는 None
        """
        if not date_str:
            return None
        
        try:
            # YYYYMMDD 형식
            if len(date_str) == 8:
                return datetime.strptime(date_str, '%Y%m%d').date()
            # YYYY-MM-DD 형식 (이미 표준 형식인 경우)
            elif '-' in date_str:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                logger.warning(f"⚠️ 알 수 없는 날짜 형식: {date_str}")
                return None
        except Exception as e:
            logger.warning(f"⚠️ 날짜 파싱 실패: {date_str}, {e}")
            return None

    # ---------------------------
    # 설정 관리
    # ---------------------------
    async def create_collection_setting(
        self,
        user_emp_no: str,
        container_id: str,
        search_config: Dict[str, Any],
        max_results: int = 100,
        auto_download_pdf: bool = False,
        auto_generate_embeddings: bool = True,
        schedule_type: str = "manual",
        schedule_config: Optional[Dict[str, Any]] = None,
    ) -> TbPatentCollectionSettings:
        setting = TbPatentCollectionSettings(
            user_emp_no=user_emp_no,
            container_id=container_id,
            search_config=search_config,
            max_results=max_results,
            auto_download_pdf=auto_download_pdf,
            auto_generate_embeddings=auto_generate_embeddings,
            schedule_type=schedule_type,
            schedule_config=schedule_config,
        )
        self.session.add(setting)
        await self.session.commit()
        await self.session.refresh(setting)
        logger.info(f"✅ 특허 수집 설정 생성: {setting.setting_id}")
        return setting

    async def get_user_settings(
        self,
        user_emp_no: str,
        container_id: Optional[str] = None,
    ) -> List[TbPatentCollectionSettings]:
        query = select(TbPatentCollectionSettings).where(
            TbPatentCollectionSettings.user_emp_no == user_emp_no,
            TbPatentCollectionSettings.is_active.is_(True),
        )
        if container_id:
            query = query.where(TbPatentCollectionSettings.container_id == container_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_setting_by_id(
        self,
        user_emp_no: str,
        setting_id: int,
        include_inactive: bool = False,
    ) -> Optional[TbPatentCollectionSettings]:
        query = select(TbPatentCollectionSettings).where(
            TbPatentCollectionSettings.setting_id == setting_id,
            TbPatentCollectionSettings.user_emp_no == user_emp_no,
        )
        if not include_inactive:
            query = query.where(TbPatentCollectionSettings.is_active.is_(True))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_collection_setting(
        self,
        user_emp_no: str,
        setting_id: int,
        *,
        container_id: Optional[str] = None,
        search_config: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
        auto_download_pdf: Optional[bool] = None,
        auto_generate_embeddings: Optional[bool] = None,
        schedule_type: Optional[str] = None,
        schedule_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[TbPatentCollectionSettings]:
        setting = await self.get_user_setting_by_id(user_emp_no, setting_id)
        if not setting:
            return None

        values: Dict[str, Any] = {}
        if container_id is not None:
            values["container_id"] = container_id
        if search_config is not None:
            values["search_config"] = search_config
        if max_results is not None:
            values["max_results"] = max_results
        if auto_download_pdf is not None:
            values["auto_download_pdf"] = auto_download_pdf
        if auto_generate_embeddings is not None:
            values["auto_generate_embeddings"] = auto_generate_embeddings
        if schedule_type is not None:
            values["schedule_type"] = schedule_type
        if schedule_config is not None:
            values["schedule_config"] = schedule_config

        if not values:
            return setting

        await self.session.execute(
            update(TbPatentCollectionSettings)
            .where(
                TbPatentCollectionSettings.setting_id == setting_id,
                TbPatentCollectionSettings.user_emp_no == user_emp_no,
                TbPatentCollectionSettings.is_active.is_(True),
            )
            .values(**values)
        )
        await self.session.commit()
        updated = await self.get_user_setting_by_id(user_emp_no, setting_id)
        if updated:
            logger.info(f"✅ 특허 수집 설정 수정: {setting_id}")
        return updated

    async def deactivate_collection_setting(
        self,
        user_emp_no: str,
        setting_id: int,
    ) -> bool:
        setting = await self.get_user_setting_by_id(user_emp_no, setting_id)
        if not setting:
            return False

        await self.session.execute(
            update(TbPatentCollectionSettings)
            .where(
                TbPatentCollectionSettings.setting_id == setting_id,
                TbPatentCollectionSettings.user_emp_no == user_emp_no,
                TbPatentCollectionSettings.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await self.session.commit()
        logger.info(f"✅ 특허 수집 설정 비활성화(삭제): {setting_id}")
        return True

    # ---------------------------
    # 작업 관리
    # ---------------------------
    async def create_task_record(
        self,
        task_id: str,
        setting_id: Optional[int],
        user_emp_no: str,
    ) -> TbPatentCollectionTasks:
        task = TbPatentCollectionTasks(
            task_id=task_id,
            setting_id=setting_id,
            user_emp_no=user_emp_no,
            status="pending",
            progress_current=0,
            progress_total=0,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def update_task_progress(
        self,
        task_id: str,
        progress_current: int,
        progress_total: int,
        status: str = "running",
        collected_count: Optional[int] = None,
        skipped_count: Optional[int] = None,
        error_count: Optional[int] = None,
    ) -> None:
        values: Dict[str, Any] = {
            "status": status,
            "progress_current": progress_current,
            "progress_total": progress_total,
        }
        if collected_count is not None:
            values["collected_count"] = collected_count
        if error_count is not None:
            values["error_count"] = error_count
        await self.session.execute(
            update(TbPatentCollectionTasks)
            .where(TbPatentCollectionTasks.task_id == task_id)
            .values(**values)
        )
        await self.session.commit()

        # 완료 시 설정의 last_collection_result 업데이트
        if status == "completed":
            # task에서 setting_id 가져오기
            task_result = await self.session.execute(
                select(TbPatentCollectionTasks).where(
                    TbPatentCollectionTasks.task_id == task_id
                )
            )
            task = task_result.scalar_one_or_none()
            if task and task.setting_id:
                # 총 보유 건수 계산 (신규 + 스킵 = 해당 조건으로 보유 중인 특허)
                total_owned = (collected_count or 0) + (skipped_count or 0)
                await self.session.execute(
                    update(TbPatentCollectionSettings)
                    .where(TbPatentCollectionSettings.setting_id == task.setting_id)
                    .values(
                        last_collection_date=datetime.utcnow(),
                        last_collection_result={
                            "new": collected_count or 0,      # 신규 저장
                            "skipped": skipped_count or 0,    # 이미 존재
                            "errors": error_count or 0,       # 오류
                            "total_owned": total_owned,       # 총 보유
                            "searched": progress_total,       # 검색 결과
                        }
                    )
                )
                await self.session.commit()
                logger.info(f"✅ 설정 {task.setting_id} 수집 결과: 신규={collected_count}, 스킵={skipped_count}, 총 보유={total_owned}")

    # ---------------------------
    # 특허 데이터 저장
    # ---------------------------
    async def save_patent_to_database(
        self,
        patent_data: Dict[str, Any],
        container_id: str,
        user_emp_no: str,
        auto_generate_embeddings: bool = True,
    ) -> tuple[Optional[int], bool]:
        """
        1) 서지정보 저장
        2) 문서 메타 저장 (tb_file_bss_info)
        3) (file_sno, is_new) 튜플 반환
           - is_new=True: 신규 저장됨
           - is_new=False: 이미 존재하여 스킵됨
        """
        app_no = patent_data.get("applicationNumber")
        if not app_no:
            logger.warning("⚠️ applicationNumber 누락으로 스킵")
            return (None, False)

        # 중복 체크 (서지정보 기준). 이미 존재하더라도 문서 목록 엔트리(TbFileBssInfo)가 없으면 생성한다.
        existing_biblio_result = await self.session.execute(
            select(TbPatentBibliographicInfo).where(
                TbPatentBibliographicInfo.application_number == app_no
            )
        )
        existing_biblio = existing_biblio_result.scalar_one_or_none()

        # 특허 접근 URL 생성 (원본 파일 저장하지 않고 URL만 저장)
        pub_no = str(patent_data.get('publicationNumber') or '').strip()
        # Google Patents URL에는 KR 접두사 필요!
        if pub_no:
            source_url = f"https://patents.google.com/?q=KR{pub_no}"
        else:
            source_url = f"https://patents.google.com/?q=KR{app_no}"

        # 🔍 사용자 기준 전역 중복 체크 (모든 컨테이너 대상)
        # 동일 사용자가 이미 해당 특허를 어느 컨테이너에든 등록했는지 확인
        # ✅ 중복 체크는 .url 뿐 아니라, 이미 PDF로 변환된 경우(.pdf)도 포함해야 함
        # (PDF 다운로드 옵션으로 기존 .url 레코드가 .pdf로 변경될 수 있음)
        existing_file_result = await self.session.execute(
            select(TbFileBssInfo).where(
                TbFileBssInfo.document_type == 'patent',
                TbFileBssInfo.owner_emp_no == user_emp_no,  # 사용자 기준 전역 체크
                TbFileBssInfo.del_yn != 'Y',
                or_(
                TbFileBssInfo.file_psl_nm == f"{app_no}.url",
                    TbFileBssInfo.file_psl_nm == f"{app_no}.pdf",
                ),
            )
        )
        existing_file = existing_file_result.scalar_one_or_none()
        if existing_file:
            existing_container = existing_file.knowledge_container_id
            if existing_container == container_id:
                logger.info(f"ℹ️ 이미 존재하는 특허: {app_no} (동일 컨테이너) → file_sno={existing_file.file_bss_info_sno}")
            else:
                logger.info(f"ℹ️ 이미 존재하는 특허: {app_no} (다른 컨테이너: {existing_container}) → file_sno={existing_file.file_bss_info_sno}")
            return (int(existing_file.file_bss_info_sno), False)  # 스킵됨

        try:
            # 1. 서지정보 저장 (날짜 변환 포함)
            if not existing_biblio:
                biblio = TbPatentBibliographicInfo(
                    application_number=app_no,
                    publication_number=patent_data.get("publicationNumber"),
                    title=patent_data.get("inventionTitle") or app_no,
                    abstract=patent_data.get("abstract"),
                    # 날짜 필드 - 문자열을 date 객체로 변환
                    application_date=self._parse_date(patent_data.get("applicationDate")),
                    publication_date=self._parse_date(patent_data.get("publicationDate")),
                    registration_date=self._parse_date(patent_data.get("registrationDate")),
                    # 기타 필드
                    jurisdiction=patent_data.get("country", "KR"),
                    legal_status=patent_data.get("legalStatus", "APPLICATION"),
                    data_source="KIPRIS",
                    source_url=source_url,
                    knowledge_container_id=container_id,
                    imported_by=user_emp_no,
                )
                self.session.add(biblio)
                await self.session.flush()
            else:
                # 기존 서지정보에 URL/컨테이너/수집자 정보가 비어있으면 보강
                await self.session.execute(
                    update(TbPatentBibliographicInfo)
                    .where(TbPatentBibliographicInfo.patent_id == existing_biblio.patent_id)
                    .values(
                        knowledge_container_id=existing_biblio.knowledge_container_id or container_id,
                        imported_by=existing_biblio.imported_by or user_emp_no,
                        source_url=existing_biblio.source_url or source_url,
                    )
                )

            # 2. 문서 메타 저장
            title = (patent_data.get("inventionTitle") or "").strip() or app_no
            file_lgc_nm = title
            file_psl_nm = f"{app_no}.url"
            file_extsn = "url"
            
            file_record = TbFileBssInfo(
                drcy_sno=1,
                file_lgc_nm=file_lgc_nm,
                file_psl_nm=file_psl_nm,
                file_extsn=file_extsn,
                path=source_url,
                knowledge_container_id=container_id,
                document_type="patent",
                owner_emp_no=user_emp_no,
                created_by=user_emp_no,
                processing_status="completed",  # 서지 임베딩/인덱싱 완료 기준으로 completed
                processing_completed_at=datetime.utcnow(),
                korean_metadata={
                    "applicationNumber": app_no,
                    "publicationNumber": pub_no or None,
                    "data_source": "KIPRIS",
                    "source_url": source_url,
                },
            )
            self.session.add(file_record)
            await self.session.flush()  # file_sno 생성
            
            # 3. 임베딩 생성 (제목 + 초록)
            if auto_generate_embeddings:
                await self._generate_patent_embeddings(
                    file_record.file_bss_info_sno,
                    patent_data,
                    container_id,
                    user_emp_no
                )
            
            await self.session.commit()
            await self.session.refresh(file_record)

            logger.info(f"✅ 특허 저장 완료: {app_no} → file_sno={file_record.file_bss_info_sno}")
            return (file_record.file_bss_info_sno, True)  # 신규 저장됨

        except Exception as e:
            logger.error(f"❌ 특허 저장 실패: {app_no}, {e}")
            await self.session.rollback()
            return (None, False)

    async def _generate_patent_embeddings(
        self,
        file_sno: int,
        patent_data: Dict[str, Any],
        container_id: str,
        user_emp_no: str,
    ) -> None:
        """
        특허 서지정보(제목+초록)로부터 임베딩 생성 및 검색 인덱스 저장
        
        Args:
            file_sno: 파일 일련번호
            patent_data: 특허 데이터
            container_id: 컨테이너 ID
            user_emp_no: 사용자 사번
        """
        try:
            # 1. 텍스트 결합 (제목 + 초록)
            title = patent_data.get("inventionTitle", "")
            abstract = patent_data.get("abstract", "")
            
            if not title and not abstract:
                logger.warning(f"⚠️ 특허 {file_sno}: 제목과 초록이 모두 비어있어 임베딩 스킵")
                return
            
            combined_text = f"{title}\n\n{abstract}".strip()
            
            # 2. 임베딩 생성 (EmbeddingService 기본 설정 사용)
            embedding_service = EmbeddingService()
            try:
                embeddings = await embedding_service.get_embeddings_batch(
                    texts=[combined_text]
                )
                embedding_vector = embeddings[0] if embeddings else None
            except Exception as e:
                logger.error(f"❌ 임베딩 생성 실패: {e}")
                embedding_vector = None
            
            if not embedding_vector:
                logger.error(f"❌ 특허 {file_sno}: 임베딩 생성 실패")
                return
            
            # 3. 추출 세션 생성 (특허용 - 청크 세션 FK 충족)
            from datetime import datetime as dt
            from app.models.document.multimodal_models import DocExtractionSession
            
            extraction_session = DocExtractionSession(
                file_bss_info_sno=file_sno,
                provider="kipris",  # 특허 데이터 제공자
                model_profile="patent_bibliographic",
                pipeline_type="patent",
                started_at=dt.now(),
                completed_at=dt.now(),
                status="success",
                page_count_detected=1,
            )
            self.session.add(extraction_session)
            await self.session.flush()
            
            # 4. 청크 세션 생성 (문서 처리 파이프라인 호환)
            chunk_session = DocChunkSession(
                file_bss_info_sno=file_sno,
                extraction_session_id=extraction_session.extraction_session_id,  # FK 연결
                strategy_name="patent_bibliographic",
                params_json={"source": "KIPRIS", "fields": ["title", "abstract"]},
                started_at=dt.now(),
                completed_at=dt.now(),
                status="success",
                chunk_count=1,
            )
            self.session.add(chunk_session)
            await self.session.flush()
            
            # 5. 청크 생성
            chunk = DocChunk(
                chunk_session_id=chunk_session.chunk_session_id,
                file_bss_info_sno=file_sno,
                chunk_index=0,
                source_object_ids=[],  # 특허는 객체 추출 없음
                content_text=combined_text,
                token_count=len(combined_text.split()),
                modality="text",
                section_heading=title,
            )
            self.session.add(chunk)
            await self.session.flush()
            
            # 6. 임베딩 저장 (DocEmbedding)
            from app.core.config import settings
            provider = getattr(settings, 'default_embedding_provider', 'bedrock')
            dimension = len(embedding_vector)
            
            # 벤더별 컬럼 할당
            embedding_data = {
                "chunk_id": chunk.chunk_id,
                "file_bss_info_sno": file_sno,
                "provider": provider,
                "model_name": "amazon.titan-embed-text-v2:0" if provider == "bedrock" else "text-embedding-3-small",
                "modality": "text",
                "dimension": dimension,
            }
            
            if provider == "bedrock" and dimension == 1024:
                embedding_data["aws_vector_1024"] = embedding_vector
            elif provider == "azure_openai" and dimension == 1536:
                embedding_data["azure_vector_1536"] = embedding_vector
            else:
                # 레거시 동적 벡터
                embedding_data["vector"] = embedding_vector
            
            doc_embedding = DocEmbedding(**embedding_data)
            self.session.add(doc_embedding)
            
            # 7. 검색 인덱스 저장 (TbDocumentSearchIndex)
            search_index = TbDocumentSearchIndex(
                file_bss_info_sno=file_sno,
                knowledge_container_id=container_id,
                document_title=title[:500] if title else "",  # 제목 (최대 500자)
                full_content=combined_text,  # 전체 내용
                content_summary=combined_text[:1000],  # 요약 (최대 1000자)
                document_type="patent",  # 문서 유형
                language_code="ko",
                has_images=False,  # 특허 서지정보는 이미지 없음
                has_tables=False,
                indexing_status="indexed",
                access_level="normal",
            )
            self.session.add(search_index)
            
            logger.info(f"✅ 특허 임베딩 생성 완료: file_sno={file_sno}, dim={len(embedding_vector)}")
            
        except Exception as e:
            logger.error(f"❌ 임베딩 생성 중 오류: {e}")
            # 임베딩 실패해도 특허 저장은 유지 (rollback 하지 않음)

    async def download_and_upload_patent_pdf(
        self,
        application_number: str,
        file_sno: int,
        kipris_client,
    ) -> bool:
        """
        KIPRIS에서 공개전문 PDF 다운로드 후 S3 업로드 및 DB 업데이트
        
        KIPRIS Plus API의 getPubFullTextInfoSearch를 사용하여:
        1. PDF 다운로드 URL 조회
        2. PDF 다운로드
        3. S3 업로드
        4. DB의 file_extsn, path 업데이트
        
        Args:
            application_number: 출원번호
            file_sno: 파일 일련번호
            kipris_client: KIPRIS API 클라이언트
        
        Returns:
            성공 여부
        """
        try:
            # 1. 로컬 경로 생성
            upload_dir = Path("uploads/patents")
            upload_dir.mkdir(parents=True, exist_ok=True)
            local_path = upload_dir / f"{application_number}.pdf"
            
            # 2. KIPRIS에서 공개전문 PDF 다운로드 (새 API 사용)
            success = await kipris_client.download_full_text_pdf(
                application_number=application_number,
                save_path=str(local_path)
            )
            
            if not success or not local_path.exists():
                logger.warning(f"⚠️ PDF 다운로드 실패 (공개 전문 없을 수 있음): {application_number}")
                return False
            
            file_size = local_path.stat().st_size
            logger.info(f"📥 PDF 다운로드 완료: {application_number} ({file_size/1024:.1f} KB)")
            
            # 3. S3 업로드 시도 (S3 설정이 없으면 로컬 경로 사용)
            final_path = str(local_path)
            try:
                s3_service = S3Service()
                s3_key = f"patents/{application_number}.pdf"
                s3_url = await s3_service.upload_file(
                    file_path=str(local_path),
                    object_key=s3_key
                )
                if s3_url:
                    final_path = s3_url
                    # S3 업로드 성공 시 로컬 파일 삭제
                    try:
                        local_path.unlink()
                    except Exception:
                        pass
                    logger.info(f"☁️ S3 업로드 완료: {application_number} → {s3_url}")
            except Exception as s3_err:
                logger.warning(f"⚠️ S3 업로드 실패 (로컬 파일 유지): {s3_err}")
                # S3 실패 시 로컬 경로 사용
                final_path = f"/uploads/patents/{application_number}.pdf"
            
            # 4. DB 업데이트 (PDF 경로, 확장자 변경)
            stmt = (
                update(TbFileBssInfo)
                .where(TbFileBssInfo.file_bss_info_sno == file_sno)
                .values(
                    file_psl_nm=f"{application_number}.pdf",
                    file_extsn="pdf",
                    path=final_path,
                    processing_status="completed",
                )
            )
            await self.session.execute(stmt)
            await self.session.commit()
            
            logger.info(f"✅ PDF 처리 완료: {application_number} → {final_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ PDF 다운로드/업로드 실패: {application_number}, {e}")
            return False
