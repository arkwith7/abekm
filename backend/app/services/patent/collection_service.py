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
from sqlalchemy import select, update
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

    # ---------------------------
    # 특허 데이터 저장
    # ---------------------------
    async def save_patent_to_database(
        self,
        patent_data: Dict[str, Any],
        container_id: str,
        user_emp_no: str,
        auto_generate_embeddings: bool = True,
    ) -> Optional[int]:
        """
        1) 서지정보 저장
        2) 문서 메타 저장 (tb_file_bss_info)
        3) 향후 임베딩/파이프라인 연동을 위해 file_sno 반환
        """
        app_no = patent_data.get("applicationNumber")
        if not app_no:
            logger.warning("⚠️ applicationNumber 누락으로 스킵")
            return None

        # 중복 체크
        existing = await self.session.execute(
            select(TbPatentBibliographicInfo).where(
                TbPatentBibliographicInfo.application_number == app_no
            )
        )
        if existing.scalar_one_or_none():
            logger.info(f"ℹ️ 이미 존재하는 특허: {app_no}")
            return None

        try:
            # 1. 서지정보 저장 (날짜 변환 포함)
            biblio = TbPatentBibliographicInfo(
                application_number=app_no,
                publication_number=patent_data.get("publicationNumber"),
                title=patent_data.get("inventionTitle"),
                abstract=patent_data.get("abstract"),
                # 날짜 필드 - 문자열을 date 객체로 변환
                application_date=self._parse_date(patent_data.get("applicationDate")),
                publication_date=self._parse_date(patent_data.get("publicationDate")),
                registration_date=self._parse_date(patent_data.get("registrationDate")),
                # 기타 필드
                jurisdiction=patent_data.get("country", "KR"),
                legal_status=patent_data.get("legalStatus", "APPLICATION"),
                data_source="KIPRIS",
                knowledge_container_id=container_id,
                imported_by=user_emp_no,
            )
            self.session.add(biblio)
            await self.session.flush()

            # 2. 문서 메타 저장
            pub_no = patent_data.get('publicationNumber', 'unknown')
            file_lgc_nm = f"{app_no}.pdf"
            file_psl_nm = f"{app_no}_{pub_no}.pdf"
            local_path = f"uploads/patents/{app_no}.pdf"
            
            file_record = TbFileBssInfo(
                drcy_sno=1,
                file_lgc_nm=file_lgc_nm,
                file_psl_nm=file_psl_nm,
                file_extsn="pdf",
                path=local_path,
                knowledge_container_id=container_id,
                document_type="patent",
                owner_emp_no=user_emp_no,
                created_by=user_emp_no,
                processing_status="pending",  # 처리 대기 상태
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
            return file_record.file_bss_info_sno

        except Exception as e:
            logger.error(f"❌ 특허 저장 실패: {app_no}, {e}")
            await self.session.rollback()
            return None

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
            
            # 2. 임베딩 생성
            embedding_service = EmbeddingService()
            try:
                # Bedrock Titan 사용 (기본)
                embeddings = await embedding_service.get_embeddings_batch(
                    texts=[combined_text],
                    provider="bedrock",
                    model="amazon.titan-embed-text-v2:0"
                )
                embedding_vector = embeddings[0] if embeddings else None
            except Exception as e:
                logger.warning(f"⚠️ Bedrock 임베딩 실패, Azure OpenAI로 재시도: {e}")
                try:
                    # 대체: Azure OpenAI
                    embeddings = await embedding_service.get_embeddings_batch(
                        texts=[combined_text],
                        provider="azure_openai"
                    )
                    embedding_vector = embeddings[0] if embeddings else None
                except Exception as e2:
                    logger.error(f"❌ 모든 임베딩 시도 실패: {e2}")
                    embedding_vector = None
            
            if not embedding_vector:
                logger.error(f"❌ 특허 {file_sno}: 임베딩 생성 실패")
                return
            
            # 3. 청크 세션 생성 (문서 처리 파이프라인 호환)
            from datetime import datetime as dt
            chunk_session = DocChunkSession(
                file_bss_info_sno=file_sno,
                extraction_session_id=None,  # 특허는 추출 세션 없음
                strategy_name="patent_bibliographic",
                params_json={"source": "KIPRIS", "fields": ["title", "abstract"]},
                started_at=dt.now(),
                completed_at=dt.now(),
                status="success",
                chunk_count=1,
            )
            self.session.add(chunk_session)
            await self.session.flush()
            
            # 4. 청크 생성
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
            
            # 5. 임베딩 저장 (DocEmbedding)
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
            
            # 6. 검색 인덱스 저장 (TbDocumentSearchIndex)
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
        KIPRIS에서 PDF 다운로드 후 S3 업로드
        
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
            
            # 2. KIPRIS에서 PDF 다운로드
            success = await kipris_client.download_patent_pdf(
                application_number=application_number,
                save_path=str(local_path)
            )
            
            if not success or not local_path.exists():
                logger.warning(f"⚠️ PDF 다운로드 실패: {application_number}")
                return False
            
            # 3. S3 업로드
            s3_service = S3Service()
            s3_key = f"patents/{application_number}.pdf"
            s3_url = await s3_service.upload_file(
                file_path=str(local_path),
                object_key=s3_key
            )
            
            # 4. DB 업데이트 (S3 경로로 변경)
            from sqlalchemy import update
            stmt = (
                update(TbFileBssInfo)
                .where(TbFileBssInfo.file_bss_info_sno == file_sno)
                .values(
                    path=s3_url,
                    processing_status="completed",
                )
            )
            await self.session.execute(stmt)
            await self.session.commit()
            
            # 5. 로컬 파일 삭제 (옵션)
            try:
                local_path.unlink()
            except Exception:
                pass
            
            logger.info(f"✅ PDF S3 업로드 완료: {application_number} → {s3_url}")
            return True
            
        except Exception as e:
            logger.error(f"❌ PDF 다운로드/업로드 실패: {application_number}, {e}")
            return False
