import asyncio
import logging
import mimetypes
import re
import time
import uuid
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

import aiofiles
import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings

logger = logging.getLogger(__name__)


def _normalize_filename(filename: str) -> str:
    # 기본 이름 설정
    name = filename or "attachment"
    name = name.strip().replace("\\", "/").split("/")[-1]
    # 허용되지 않는 문자는 언더스코어로 변경
    name = re.sub(r"[^\w.\-가-힣 ]", "_", name)
    # 연속된 공백 축소
    name = re.sub(r"\s+", " ", name)
    return name[:120]


def _detect_category(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("audio/"):
        return "audio"
    return "document"


@dataclass
class StoredAttachment:
    asset_id: str
    file_name: str
    mime_type: str
    size: int
    category: str
    path: Union[Path, str]  # Local Path or S3 Key
    owner_emp_no: str
    created_at: float
    storage_backend: str = "local"  # "local" or "s3"

    @property
    def download_url(self) -> str:
        return f"/api/v1/chat/assets/{self.asset_id}"

    @property
    def preview_url(self) -> Optional[str]:
        if self.category == "image":
            return self.download_url
        return None


class ChatAttachmentService:
    def __init__(self):
        self._storage: Dict[str, StoredAttachment] = {}
        self.base_dir = Path(settings.chat_attachment_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.storage_backend = settings.storage_backend.lower()
        self.s3_client = None
        self.s3_bucket = None
        
        if self.storage_backend == "s3":
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region
                )
                self.s3_bucket = settings.aws_s3_bucket
                logger.info(f"ChatAttachmentService initialized with S3 backend (bucket: {self.s3_bucket})")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                # Fallback to local? Or raise error?
                # For now, log error. save() will fail if s3_client is None.
        else:
            logger.info("ChatAttachmentService initialized at %s", self.base_dir)

    async def save(
        self,
        upload: UploadFile,
        owner_emp_no: str
    ) -> StoredAttachment:
        asset_id = uuid.uuid4().hex
        file_name = _normalize_filename(upload.filename or f"attachment-{asset_id}")
        mime_type = upload.content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        category = _detect_category(mime_type)
        
        size = 0
        dest_path: Union[Path, str] = ""
        
        if self.storage_backend == "s3" and self.s3_client and self.s3_bucket:
            # S3 Upload
            s3_key = f"chat-attachments/{asset_id}"
            dest_path = s3_key
            
            # Read file content into memory (assuming reasonable size for chat attachments)
            # If file is huge, we should use multipart upload or stream, but UploadFile is async.
            content = await upload.read()
            size = len(content)
            
            metadata = {
                "owner_emp_no": str(owner_emp_no),
                "file_name": str(file_name), # Ensure string (might contain unicode)
                "mime_type": str(mime_type),
                "category": str(category)
            }
            
            # Encode metadata values to ensure they are ASCII safe for S3 headers if needed?
            # Boto3 handles unicode in Metadata, but let's be safe.
            # Actually, S3 user metadata headers are x-amz-meta-*, and should be ASCII.
            # If filename has Korean, it might fail.
            # Let's URL encode the filename in metadata just in case.
            import urllib.parse
            metadata["file_name_encoded"] = urllib.parse.quote(file_name)
            
            def _upload_to_s3():
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=content,
                    ContentType=mime_type,
                    Metadata=metadata
                )
            
            await run_in_threadpool(_upload_to_s3)
            await upload.close()
            
        else:
            # Local Storage
            user_dir = self.base_dir / owner_emp_no
            user_dir.mkdir(parents=True, exist_ok=True)

            dest_path = user_dir / f"{asset_id}-{file_name}"

            async with aiofiles.open(dest_path, "wb") as out_file:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    await out_file.write(chunk)

            await upload.close()

        stored = StoredAttachment(
            asset_id=asset_id,
            file_name=file_name,
            mime_type=mime_type,
            size=size,
            category=category,
            path=dest_path,
            owner_emp_no=owner_emp_no,
            created_at=time.time(),
            storage_backend=self.storage_backend if (self.storage_backend == "s3" and self.s3_client) else "local"
        )
        self._storage[asset_id] = stored

        logger.info(
            "📎 Chat attachment stored (%s): id=%s name=%s size=%s bytes mime=%s",
            stored.storage_backend,
            asset_id,
            file_name,
            size,
            mime_type
        )

        return stored

    def get(self, asset_id: str) -> Optional[StoredAttachment]:
        # 1. 메모리 캐시 확인
        if asset_id in self._storage:
            return self._storage[asset_id]
            
        # 2. S3 검색
        if self.storage_backend == "s3" and self.s3_client and self.s3_bucket:
            try:
                s3_key = f"chat-attachments/{asset_id}"
                response = self.s3_client.head_object(Bucket=self.s3_bucket, Key=s3_key)
                
                metadata = response.get("Metadata", {})
                
                # Decode filename
                import urllib.parse
                file_name = metadata.get("file_name", "unknown")
                if "file_name_encoded" in metadata:
                    try:
                        file_name = urllib.parse.unquote(metadata["file_name_encoded"])
                    except:
                        pass
                
                stored = StoredAttachment(
                    asset_id=asset_id,
                    file_name=file_name,
                    mime_type=metadata.get("mime_type", response.get("ContentType", "application/octet-stream")),
                    size=response.get("ContentLength", 0),
                    category=metadata.get("category", "document"),
                    path=s3_key,
                    owner_emp_no=metadata.get("owner_emp_no", "unknown"),
                    created_at=response.get("LastModified").timestamp(),
                    storage_backend="s3"
                )
                
                self._storage[asset_id] = stored
                logger.info(f"📎 Recovered attachment from S3: {asset_id}")
                return stored
            except ClientError as e:
                if e.response['Error']['Code'] == "404":
                    pass # Not found
                else:
                    logger.error(f"Error checking S3 for attachment {asset_id}: {e}")
            except Exception as e:
                logger.error(f"Error checking S3 for attachment {asset_id}: {e}")

        # 3. 디스크 검색 (서버 재시작/멀티 워커 대응)
        # 파일명 패턴: {asset_id}-{filename}
        try:
            # base_dir 하위의 모든 파일 중 asset_id로 시작하는 파일 검색
            found_files = list(self.base_dir.rglob(f"{asset_id}-*"))
            if found_files:
                file_path = found_files[0]
                
                # 파일명에서 원래 파일명 복원 (asset_id-filename 형식)
                # asset_id 길이만큼 자르고 구분자(-) 제거
                filename_part = file_path.name[len(asset_id)+1:]
                
                # owner_emp_no는 상위 디렉토리 이름
                owner_emp_no = file_path.parent.name
                
                stat = file_path.stat()
                mime_type = mimetypes.guess_type(filename_part)[0] or "application/octet-stream"
                
                stored = StoredAttachment(
                    asset_id=asset_id,
                    file_name=filename_part,
                    mime_type=mime_type,
                    size=stat.st_size,
                    category=_detect_category(mime_type),
                    path=file_path,
                    owner_emp_no=owner_emp_no,
                    created_at=stat.st_ctime,
                    storage_backend="local"
                )
                
                # 캐시 복구
                self._storage[asset_id] = stored
                logger.info(f"📎 Recovered attachment from disk: {asset_id}")
                return stored
                
        except Exception as e:
            logger.error(f"Error searching for attachment {asset_id}: {e}")
            
        return None


chat_attachment_service = ChatAttachmentService()

