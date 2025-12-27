"""
Celery 특허 수집 작업
"""
import asyncio
from celery import shared_task
from loguru import logger

from app.core.database import get_async_session_local
from app.core.config import settings
from app.services.patent.kipris_client import KIPRISClient
from app.services.patent.collection_service import PatentCollectionService
from app.models.document import TbFileBssInfo


@shared_task(bind=True, name="collect_patents_from_kipris")
def collect_patents_from_kipris(
    self,
    setting_id: int,
    user_emp_no: str,
    container_id: str,
    search_config: dict,
    max_results: int,
    auto_download_pdf: bool,
    auto_generate_embeddings: bool = True,
):
    """KIPRIS에서 특허 수집 (비동기 Celery 작업)"""
    
    logger.info(f"🔧 태스크 시작: setting_id={setting_id}, auto_download_pdf={auto_download_pdf}")

    async def _run():
        async_session_local = get_async_session_local()
        async with async_session_local() as session:
            service = PatentCollectionService(session)
            client = KIPRISClient(settings.kipris_api_key)

            task_id = self.request.id
            await service.create_task_record(task_id, setting_id, user_emp_no)

            try:
                # 1) KIPRIS 검색
                patents = await client.search_patents(
                    ipc_codes=search_config.get("ipc_codes"),
                    keywords=search_config.get("keywords"),
                    applicants=search_config.get("applicants"),
                    max_results=max_results,
                )
                total = len(patents)
                logger.info(f"🔍 검색 결과 {total}건")

                new_count = 0      # 신규 저장된 특허
                skipped_count = 0  # 이미 존재하여 스킵된 특허
                errors = 0

                for idx, patent in enumerate(patents, 1):
                    try:
                        doc_id, is_new = await service.save_patent_to_database(
                            patent_data=patent,
                            container_id=container_id,
                            user_emp_no=user_emp_no,
                            auto_generate_embeddings=auto_generate_embeddings,
                        )
                        if doc_id:
                            app_no = patent.get("applicationNumber")
                            if is_new:
                                new_count += 1
                            else:
                                skipped_count += 1

                            # PDF 다운로드 옵션: 신규뿐 아니라, 기존 URL 특허도 PDF로 업그레이드 가능
                            if auto_download_pdf and app_no:
                                try:
                                    file_row = await session.get(TbFileBssInfo, int(doc_id))
                                    current_ext = (getattr(file_row, "file_extsn", "") or "").lower() if file_row else ""
                                    if current_ext != "pdf":
                                        pdf_success = await service.download_and_upload_patent_pdf(
                                        application_number=app_no,
                                        file_sno=doc_id,
                                        kipris_client=client,
                                    )
                                    if pdf_success:
                                            logger.info(f"✅ PDF 처리 완료: {app_no} (file_sno={doc_id})")
                                    else:
                                            logger.warning(f"⚠️ PDF 처리 실패 (서지정보는 유지): {app_no} (file_sno={doc_id})")
                                except Exception as e:  # noqa: BLE001
                                    logger.warning(f"⚠️ PDF 업그레이드 체크 중 오류: {app_no} (file_sno={doc_id}): {e}")
                    except Exception as e:  # noqa: BLE001
                        logger.error(f"❌ 특허 처리 실패: {e}")
                        errors += 1

                    # 진행률 업데이트
                    collected = new_count + skipped_count
                    await service.update_task_progress(
                        task_id=task_id,
                        progress_current=idx,
                        progress_total=total,
                        collected_count=collected,
                        error_count=errors,
                        status="running",
                    )
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": idx, 
                            "total": total, 
                            "new": new_count, 
                            "skipped": skipped_count, 
                            "errors": errors
                        },
                    )

                # 완료 처리
                await service.update_task_progress(
                    task_id=task_id,
                    progress_current=total,
                    progress_total=total,
                    collected_count=new_count,      # 신규 저장된 건수
                    skipped_count=skipped_count,    # 스킵된 건수
                    error_count=errors,
                    status="completed",
                )
                logger.info(f"✅ 특허 수집 완료: 신규={new_count}, 스킵={skipped_count}, 오류={errors}")
                return {
                    "status": "completed", 
                    "new": new_count,
                    "skipped": skipped_count,
                    "errors": errors, 
                    "total": total
                }

            except Exception as e:  # noqa: BLE001
                logger.error(f"❌ 특허 수집 실패: {e}")
                await service.update_task_progress(
                    task_id=task_id,
                    progress_current=0,
                    progress_total=0,
                    collected_count=0,
                    error_count=1,
                    status="failed",
                )
                raise
            finally:
                await client.close()

    return asyncio.run(_run())
