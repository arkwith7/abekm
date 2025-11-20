import boto3
import os
from typing import List, Optional, Any
from loguru import logger
from app.core.config import settings

class AWSService:
    """AWS 서비스 기본 클래스"""
    
    def __init__(self):
        # 환경 변수와 settings(소문자 필드) 모두 지원
        aws_access_key_id = getattr(settings, 'aws_access_key_id', None) or os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = getattr(settings, 'aws_secret_access_key', None) or os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = getattr(settings, 'aws_region', None) or os.getenv('AWS_REGION', 'ap-northeast-2')

        self.session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )

class S3Service(AWSService):
    """AWS S3 서비스 클래스"""
    
    def __init__(self):
        super().__init__()
        self.s3_client = self.session.client('s3')
        # settings의 소문자 필드 또는 환경 변수 사용
        self.bucket_name = getattr(settings, 'aws_s3_bucket', None) or os.getenv('AWS_S3_BUCKET')
        self._purpose_prefix = {
            'raw': 'raw',
            'intermediate': 'intermediate',
            'derived': 'derived'
        }

    def _build_key(self, blob_path: str, purpose: str = 'raw') -> str:
        """스토리지 purpose에 맞는 S3 키 생성"""
        prefix = self._purpose_prefix.get(purpose, 'raw')
        normalized = blob_path.lstrip('/')
        if normalized.startswith(f"{prefix}/"):
            return normalized
        return f"{prefix}/{normalized}"
    
    async def upload_file(self, file_path: str, object_key: str) -> str:
        """파일을 S3에 업로드"""
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, object_key)
            region = getattr(settings, 'aws_region', None) or os.getenv('AWS_REGION', 'ap-northeast-2')
            url = f"https://{self.bucket_name}.s3.{region}.amazonaws.com/{object_key}"
            logger.info(f"File uploaded to S3: {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise e
    
    async def download_file(self, object_key: str, local_path: str) -> str:
        """S3에서 파일 다운로드"""
        try:
            self.s3_client.download_file(self.bucket_name, object_key, local_path)
            logger.info(f"File downloaded from S3: {object_key}")
            return local_path
        except Exception as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise e
    
    async def delete_file(self, object_key: str) -> bool:
        """S3에서 파일 삭제"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_key)
            logger.info(f"File deleted from S3: {object_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
    
    def upload_bytes(self, data: bytes, blob_path: str, purpose: str = 'raw', content_type: Optional[str] = None) -> str:
        """바이트 데이터를 S3에 업로드 (Azure Blob 호환 API)
        
        Args:
            data: 업로드할 바이트 데이터
            blob_path: S3 키 (purpose 프리픽스 제외)
            purpose: 'raw', 'intermediate', 'derived' 중 하나
            content_type: MIME 타입 (선택)
        
        Returns:
            S3 URL
        """
        try:
            full_key = self._build_key(blob_path, purpose)
            
            put_params = {
                'Bucket': self.bucket_name,
                'Key': full_key,
                'Body': data
            }
            if content_type:
                put_params['ContentType'] = content_type
            
            self.s3_client.put_object(**put_params)
            
            region = getattr(settings, 'aws_region', None) or os.getenv('AWS_REGION', 'ap-northeast-2')
            url = f"https://{self.bucket_name}.s3.{region}.amazonaws.com/{full_key}"
            logger.info(f"Bytes uploaded to S3: {url} ({len(data)} bytes, purpose={purpose})")
            return url
        except Exception as e:
            logger.error(f"Failed to upload bytes to S3: {e}")
            raise e
    
    def download_bytes(self, blob_path: str, purpose: str = 'raw') -> bytes:
        """S3에서 바이트 데이터 다운로드 (Azure Blob 호환 API)"""
        full_key = self._build_key(blob_path, purpose)
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
            data = response['Body'].read()
            logger.info(f"Bytes downloaded from S3: {full_key} ({len(data)} bytes)")
            return data
        except self.s3_client.exceptions.NoSuchKey:
            logger.warning(f"S3 key not found: {full_key}")
            return b''
        except Exception as e:
            logger.error(f"Failed to download bytes from S3: {e}")
            raise e

    def download_text(self, object_key: str, encoding: str = 'utf-8') -> str:
        """S3에서 텍스트 파일 다운로드"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=object_key)
            text = response['Body'].read().decode(encoding, errors='replace')
            logger.info(f"Text file downloaded from S3: {object_key} ({len(text)} chars)")
            return text
        except self.s3_client.exceptions.NoSuchKey:
            logger.warning(f"Text file not found in S3: {object_key}")
            return ""
        except Exception as e:
            logger.error(f"Failed to download text from S3: {e}")
            raise e

    def generate_presigned_url(
        self,
        object_key: str,
        expires_in: int = 3600,
        response_content_disposition: Optional[str] = None,
        response_content_type: Optional[str] = None,
    ) -> str:
        """GET 객체용 프리사인드 URL 생성"""
        try:
            params: dict[str, Any] = {
                'Bucket': self.bucket_name,
                'Key': object_key,
            }
            if response_content_disposition:
                params['ResponseContentDisposition'] = response_content_disposition
            if response_content_type:
                params['ResponseContentType'] = response_content_type

            url = self.s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params=params,
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

class BedrockService(AWSService):
    """AWS Bedrock 서비스 클래스"""
    
    def __init__(self):
        super().__init__()
        self.bedrock_client = self.session.client('bedrock-runtime')
        # 호환을 위해 존재하지 않는 속성 접근을 피함
        self.model_id = getattr(settings, 'bedrock_text_model_id', None) or getattr(settings, 'bedrock_llm_model_id', 'anthropic.claude-3-haiku-20240307-v1:0')
    
    async def generate_text(self, prompt: str, max_tokens: int = 1000) -> str:
        """Bedrock을 사용한 텍스트 생성"""
        try:
            import json
            
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
            
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=body
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
            
        except Exception as e:
            logger.error(f"Failed to generate text with Bedrock: {e}")
            raise e

class OpenSearchService(AWSService):
    """AWS OpenSearch 서비스 클래스"""
    
    def __init__(self):
        super().__init__()
        try:
            from opensearchpy import OpenSearch, RequestsHttpConnection
            from opensearchpy.connection.http_auth import AWSV4SignerAuth
            
            credentials = self.session.get_credentials()
            region = getattr(settings, 'aws_region', None) or os.getenv('AWS_REGION', 'ap-northeast-2')
            auth = AWSV4SignerAuth(credentials, region, 'es')
            
            self.client = OpenSearch(
                hosts=[{'host': getattr(settings, 'opensearch_endpoint', ''), 'port': 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                pool_maxsize=20,
            )
        except ImportError:
            logger.warning("OpenSearch client not available. Install opensearch-py.")
            self.client = None
    
    async def index_document(self, index: str, doc_id: str, document: dict) -> bool:
        """문서를 OpenSearch에 인덱싱"""
        if not self.client:
            return False
            
        try:
            response = self.client.index(
                index=index,
                id=doc_id,
                body=document
            )
            logger.info(f"Document indexed: {doc_id}")
            return response['result'] == 'created' or response['result'] == 'updated'
        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            return False
    
    async def search_documents(self, index: str, query: dict, size: int = 10) -> List[dict]:
        """OpenSearch에서 문서 검색"""
        if not self.client:
            return []
            
        try:
            response = self.client.search(
                index=index,
                body=query,
                size=size
            )
            return [hit['_source'] for hit in response['hits']['hits']]
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return []
