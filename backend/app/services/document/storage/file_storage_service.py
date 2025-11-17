"""
파일 저장 서비스 - TB_FILE_BSS_INFO, TB_FILE_DTL_INFO 테이블 관리
"""
import os
import shutil
from datetime import datetime
from typing import Optional, Dict, Any, List, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import logging

from app.core.database import get_db, get_async_session_local
from app.models import TbFileBssInfo, TbFileDtlInfo
from app.core.config import settings
from app.services.core.aws_service import S3Service
from app.services.core.azure_blob_service import get_azure_blob_service, AzureBlobService

logger = logging.getLogger(__name__)

class FileStorageService:
    def __init__(self):
        self.backend = getattr(settings, 'storage_backend', 'local')
        self.s3: Optional[S3Service] = None
        self.azure_blob: Optional[AzureBlobService] = None
        if self.backend == 's3':
            self.s3 = S3Service()
        elif self.backend == 'azure_blob':
            try:
                self.azure_blob = get_azure_blob_service()
            except Exception as e:  # pragma: no cover
                logger.error(f"Azure Blob 초기화 실패: {e}")
                raise
    
    async def save_file_basic_info(
        self,
        file_logical_name: str,
        file_physical_name: str,
        file_extension: str,
        file_path: str,
        file_hash: str,
        file_size: int,
        knowledge_container_id: str,
        owner_emp_no: str,
        korean_metadata: Dict[str, Any],
        chunk_count: int,
        user_id: int
    ) -> Optional[int]:
        """
        파일 기본 정보를 TB_FILE_BSS_INFO에 저장
        """
        try:
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                # 저장 백엔드에 따라 경로/키 확정
                if self.backend == 's3' and self.s3:
                    # S3 object key 구성: {container}/{physical}
                    object_key = f"{knowledge_container_id}/{file_physical_name}"
                    # 로컬 임시 파일을 S3 업로드
                    await self.s3.upload_file(file_path=file_path, object_key=object_key)
                    # 로컬 임시 파일 제거 (성공 시)
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception:
                        pass
                    permanent_path = object_key  # DB에는 S3 object key 저장
                elif self.backend == 'azure_blob' and self.azure_blob:
                    # Blob Path 설계:
                    # raw 컨테이너: {container_id}/raw/{file_physical_name}
                    blob_path = f"{knowledge_container_id}/raw/{file_physical_name}"
                    try:
                        self.azure_blob.upload_file(local_path=file_path, blob_path=blob_path, purpose='raw')
                        # 원본 로컬 삭제 (옵션)
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception:
                            pass
                        permanent_path = blob_path  # blob key 저장
                    except Exception as e:
                        logger.error(f"Azure Blob 업로드 실패: {e}")
                        return None
                else:
                    # 로컬 디스크 보관
                    permanent_dir = os.path.join(getattr(settings, 'upload_dir', 'uploads'), knowledge_container_id)
                    os.makedirs(permanent_dir, exist_ok=True)
                    permanent_path = os.path.join(permanent_dir, file_physical_name)
                    if os.path.exists(file_path) and file_path != permanent_path:
                        shutil.move(file_path, permanent_path)
                
                # TB_FILE_BSS_INFO 레코드 생성
                file_bss_info = TbFileBssInfo(
                    drcy_sno=1,  # 기본 디렉토리
                    file_lgc_nm=file_logical_name,
                    file_psl_nm=file_physical_name,
                    file_extsn=file_extension.lstrip('.'),
                    path=permanent_path,
                    knowledge_container_id=knowledge_container_id,
                    owner_emp_no=owner_emp_no,
                    korean_metadata=korean_metadata,
                    chunk_count=chunk_count,
                    created_by=owner_emp_no,
                    last_modified_by=owner_emp_no,
                    del_yn='N'
                )
                
                session.add(file_bss_info)
                await session.flush()  # ID 생성을 위해 flush
                
                file_bss_info_sno = cast(int, file_bss_info.file_bss_info_sno)
                
                await session.commit()
                
                logger.info(f"파일 기본 정보 저장 완료: {file_bss_info_sno} - {file_logical_name}")
                return file_bss_info_sno
                
        except Exception as e:
            logger.error(f"파일 기본 정보 저장 실패: {e}")
            return None
    
    async def save_file_detail_info(
        self,
        file_bss_info_sno: int,
        content_text: str,
        document_title: str,
        metadata_json: Dict[str, Any]
    ) -> bool:
        """
        파일 상세 정보를 TB_FILE_DTL_INFO에 저장하고 TB_FILE_BSS_INFO 링크 업데이트
        """
        try:
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                # TB_FILE_DTL_INFO 레코드 생성 (실제 컬럼명 사용)
                file_dtl_info = TbFileDtlInfo(
                    sj=document_title,  # 제목
                    cn=content_text[:1000] if content_text else "",  # 내용 요약 (길이 제한)
                    sumry=content_text[:500] if content_text else "",  # 요약
                    created_by=metadata_json.get("uploaded_by", "system"),
                    last_modified_by=metadata_json.get("uploaded_by", "system")
                )
                
                session.add(file_dtl_info)
                await session.flush()  # ID 생성을 위해 flush
                
                file_dtl_info_sno = file_dtl_info.file_dtl_info_sno
                
                # TB_FILE_BSS_INFO의 file_dtl_info_sno 업데이트
                from sqlalchemy import update
                stmt = (update(TbFileBssInfo)
                       .where(TbFileBssInfo.file_bss_info_sno == file_bss_info_sno)
                       .values(file_dtl_info_sno=file_dtl_info_sno))
                
                await session.execute(stmt)
                await session.commit()
                
                logger.info(f"파일 상세 정보 저장 완료: BSS({file_bss_info_sno}) -> DTL({file_dtl_info_sno})")
                return True
                
        except Exception as e:
            logger.error(f"파일 상세 정보 저장 실패: {e}")
            return False
    
    async def get_file_info(self, file_bss_info_sno: int) -> Optional[Dict[str, Any]]:
        """
        파일 정보 조회
        """
        try:
            # get_async_session_local을 사용하여 세션 생성
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                # TB_FILE_BSS_INFO와 TB_FILE_DTL_INFO 조인 조회 (올바른 조인 조건 사용)
                stmt = (select(TbFileBssInfo, TbFileDtlInfo)
                       .outerjoin(TbFileDtlInfo, TbFileBssInfo.file_dtl_info_sno == TbFileDtlInfo.file_dtl_info_sno)
                       .where(TbFileBssInfo.file_bss_info_sno == file_bss_info_sno)
                       .where(TbFileBssInfo.del_yn == 'N'))
                
                result = await session.execute(stmt)
                row = result.first()
                
                if not row:
                    return None
                
                file_bss, file_dtl = row
                
                return {
                    "file_bss_info_sno": file_bss.file_bss_info_sno,
                    "file_logical_name": file_bss.file_lgc_nm,
                    "file_physical_name": file_bss.file_psl_nm,
                    "file_extension": file_bss.file_extsn,
                    "file_path": file_bss.path,
                    "knowledge_container_id": file_bss.knowledge_container_id,
                    "owner_emp_no": file_bss.owner_emp_no,
                    "korean_metadata": file_bss.korean_metadata,
                    "chunk_count": file_bss.chunk_count,
                    "created_date": file_bss.created_date,
                    "content_text": file_dtl.cn if file_dtl else None,  # 내용 요약
                    "document_title": file_dtl.sj if file_dtl else None,  # 제목
                    "summary": file_dtl.sumry if file_dtl else None  # 요약
                }
                
        except Exception as e:
            logger.error(f"파일 정보 조회 실패: {e}")
            return None
    
    async def list_files_in_container(
        self, 
        knowledge_container_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        컨테이너 내 파일 목록 조회
        """
        try:
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                stmt = (select(TbFileBssInfo)
                       .where(TbFileBssInfo.knowledge_container_id == knowledge_container_id)
                       .where(TbFileBssInfo.del_yn == 'N')
                       .order_by(TbFileBssInfo.created_date.desc())
                       .offset(skip)
                       .limit(limit))
                
                result = await session.execute(stmt)
                files = result.scalars().all()
                
                return [
                    {
                        "file_bss_info_sno": file_info.file_bss_info_sno,
                        "file_logical_name": file_info.file_lgc_nm,
                        "file_physical_name": file_info.file_psl_nm,
                        "file_extension": file_info.file_extsn,
                        "knowledge_container_id": file_info.knowledge_container_id,
                        "owner_emp_no": file_info.owner_emp_no,
                        "chunk_count": file_info.chunk_count,
                        "created_date": file_info.created_date,
                        "last_modified_date": file_info.last_modified_date,
                        "access_count": file_info.access_count
                    }
                    for file_info in files
                ]
                
        except Exception as e:
            logger.error(f"컨테이너 파일 목록 조회 실패: {e}")
            return []

# 싱글톤 인스턴스
file_storage_service = FileStorageService()
