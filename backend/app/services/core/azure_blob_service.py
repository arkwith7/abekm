"""Azure Blob Storage Service Wrapper

역할:
 - 원본 업로드 (raw)
 - 문서 처리 중간 산출물(intermediate) 저장 (extracted pages, layout json)
 - 파생 산출물(derived) 저장 (정규화 텍스트, 청크 JSON, 임베딩 메타 JSON)
 - 임시 접근을 위한 SAS URL 생성

설계 원칙:
 - 연결 문자열(connection string)이 있으면 우선 사용
 - 없으면 account name + key 조합 사용
 - 계정 키 없고 Managed Identity (Azure 환경) 사용 시 azure-identity 연동 (추후 확장 TODO)
"""
from __future__ import annotations
from typing import Optional
import os
import logging
from datetime import datetime, timedelta
from urllib.parse import quote

try:
    from azure.core.exceptions import ResourceNotFoundError
    from azure.storage.blob import (
        BlobServiceClient, BlobClient, ContainerClient,
        generate_blob_sas, BlobSasPermissions
    )
except ImportError:  # pragma: no cover
    BlobServiceClient = None  # type: ignore
    BlobSasPermissions = None  # type: ignore
    ResourceNotFoundError = None  # type: ignore

from app.core.config import settings

logger = logging.getLogger(__name__)

class AzureBlobService:
    def __init__(self) -> None:
        logging.getLogger("azure").setLevel(logging.WARNING)
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

        if BlobServiceClient is None:
            raise RuntimeError("azure-storage-blob 패키지가 설치되어 있지 않습니다. requirements.txt 업데이트 필요")

        self.account_name = settings.azure_blob_account_name or os.getenv("AZURE_BLOB_ACCOUNT_NAME")
        self.account_key = settings.azure_blob_account_key or os.getenv("AZURE_BLOB_ACCOUNT_KEY")
        self.conn_str = settings.azure_blob_connection_string or os.getenv("AZURE_BLOB_CONNECTION_STRING")
        self.enable_auto_container = settings.azure_blob_enable_auto_container

        if self.conn_str:
            self.client = BlobServiceClient.from_connection_string(self.conn_str)
        else:
            if not self.account_name or not self.account_key:
                raise RuntimeError("Azure Blob 인증 정보가 부족합니다 (account_name/account_key or connection string)")
            account_url = f"https://{self.account_name}.blob.core.windows.net" if not settings.azure_blob_path_style else f"http://127.0.0.1:10000/{self.account_name}"
            self.client = BlobServiceClient(account_url=account_url, credential=self.account_key)

        self.container_raw = settings.azure_blob_container_raw
        self.container_intermediate = settings.azure_blob_container_intermediate
        self.container_derived = settings.azure_blob_container_derived

        if self.enable_auto_container:
            for c in [self.container_raw, self.container_intermediate, self.container_derived]:
                try:
                    self.client.create_container(c)
                except Exception:
                    pass  # 이미 존재

    def _get_container(self, purpose: str) -> str:
        if purpose == 'raw':
            return self.container_raw
        if purpose == 'intermediate':
            return self.container_intermediate
        if purpose == 'derived':
            return self.container_derived
        raise ValueError(f"Unknown purpose: {purpose}")

    def upload_bytes(self, data: bytes, blob_path: str, purpose: str = 'raw', overwrite: bool = True) -> str:
        container = self._get_container(purpose)
        blob = self.client.get_blob_client(container=container, blob=blob_path)
        blob.upload_blob(data, overwrite=overwrite)
        url = blob.url
        logger.info(f"[AzureBlob] Uploaded bytes -> {url}")
        return url

    def upload_file(self, local_path: str, blob_path: str, purpose: str = 'raw', overwrite: bool = True) -> str:
        with open(local_path, 'rb') as f:
            return self.upload_bytes(f.read(), blob_path, purpose=purpose, overwrite=overwrite)

    def generate_sas_url(
        self,
        blob_path: str,
        purpose: str = 'raw',
        expiry_seconds: Optional[int] = None,
        content_disposition: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str:
        container = self._get_container(purpose)
        expiry = datetime.utcnow() + timedelta(seconds=expiry_seconds or settings.azure_blob_sas_expiry_seconds)
        if not self.account_name or not self.account_key:
            raise RuntimeError("SAS 생성에는 account name/key 필요 (Managed Identity 미구현)")
        
        # SAS 서명 생성: 원본 blob_name 사용 (한글 그대로)
        sas = generate_blob_sas(
            account_name=self.account_name,
            account_key=self.account_key,
            container_name=container,
            blob_name=blob_path,
            permission=BlobSasPermissions(read=True),
            expiry=expiry,
            content_disposition=content_disposition,
            content_type=content_type
        )
        
        # URL 생성: 인코딩된 경로 사용
        safe_blob_path = quote(blob_path, safe="/")
        base_url = f"https://{self.account_name}.blob.core.windows.net/{container}/{safe_blob_path}"
        return f"{base_url}?{sas}"

    def download_blob_to_bytes(self, blob_path: str, purpose: str = 'raw') -> bytes:
        """Blob에서 데이터를 바이트로 다운로드"""
        container = self._get_container(purpose)
        try:
            blob_client = self.client.get_blob_client(container=container, blob=blob_path)
            blob_data = blob_client.download_blob()
            return blob_data.readall()
        except Exception as e:
            logger.error(f"[AzureBlob] 다운로드 실패: {blob_path} - {e}")
            raise

    # --- Added helper methods ---
    def download_text(self, blob_path: str, purpose: str = 'raw', encoding: str = 'utf-8') -> str:
        data = self.download_blob_to_bytes(blob_path, purpose=purpose)
        return data.decode(encoding, errors='replace')

    def download_json(self, blob_path: str, purpose: str = 'raw', encoding: str = 'utf-8'):
        import json
        text = self.download_text(blob_path, purpose=purpose, encoding=encoding)
        return json.loads(text or 'null')

    def download_blob_to_file(self, blob_path: str, local_path: str, purpose: str = 'raw') -> None:
        """Blob에서 로컬 파일로 다운로드"""
        container = self._get_container(purpose)
        try:
            blob_client = self.client.get_blob_client(container=container, blob=blob_path)
            with open(local_path, 'wb') as f:
                blob_data = blob_client.download_blob()
                f.write(blob_data.readall())
            logger.info(f"[AzureBlob] 파일 다운로드 완료: {blob_path} → {local_path}")
        except Exception as e:
            logger.error(f"[AzureBlob] 파일 다운로드 실패: {blob_path} → {local_path} - {e}")
            raise

    def delete_blob(self, blob_path: str, purpose: str = 'raw') -> bool:
        container = self._get_container(purpose)
        try:
            self.client.get_blob_client(container, blob_path).delete_blob()
            return True
        except Exception as e:
            if ResourceNotFoundError is not None and isinstance(e, ResourceNotFoundError):
                logger.info("[AzureBlob] 삭제 요청 블롭 미존재 - %s", blob_path)
                return True
            logger.warning(f"[AzureBlob] 삭제 실패: {blob_path} - {e}")
            return False

azure_blob_service: Optional[AzureBlobService] = None

def get_azure_blob_service() -> AzureBlobService:
    global azure_blob_service
    if azure_blob_service is None:
        azure_blob_service = AzureBlobService()
    return azure_blob_service
