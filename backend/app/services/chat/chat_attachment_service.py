import asyncio
import logging
import mimetypes
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import aiofiles
from fastapi import UploadFile

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
    path: Path
    owner_emp_no: str
    created_at: float

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

        user_dir = self.base_dir / owner_emp_no
        user_dir.mkdir(parents=True, exist_ok=True)

        dest_path = user_dir / f"{asset_id}-{file_name}"

        size = 0
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
            created_at=time.time()
        )
        self._storage[asset_id] = stored

        logger.info(
            "📎 Chat attachment stored: id=%s name=%s size=%s bytes mime=%s",
            asset_id,
            file_name,
            size,
            mime_type
        )

        return stored

    def get(self, asset_id: str) -> Optional[StoredAttachment]:
        return self._storage.get(asset_id)


chat_attachment_service = ChatAttachmentService()

