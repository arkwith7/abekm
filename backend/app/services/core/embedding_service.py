import asyncio
import boto3
import json
import logging
import os
import time
from typing import Dict, List, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 이미 초기화되었으면 스킵
        if EmbeddingService._initialized:
            return
            
        self.bedrock_client = None
        self.openai_client = None
        self.azure_openai_client = None
        self._embedding_cache: Dict[str, Tuple[float, List[float]]] = {}
        self._embedding_inflight: Dict[str, asyncio.Future[List[float]]] = {}
        self._embedding_cache_ttl = getattr(settings, "embedding_cache_ttl_seconds", 120)
        
        # 기본 임베딩 프로바이더 설정
        self.default_provider = getattr(settings, 'default_embedding_provider', 'bedrock')
        
        # Azure OpenAI 클라이언트 초기화
        self._init_azure_openai_client()
        
        # Bedrock 클라이언트 초기화 (환경변수 사용)
        self._init_bedrock_client()
        
        # OpenAI 클라이언트 초기화 (대체)
        self._init_openai_client()
        
        # 초기화 완료 플래그 설정
        EmbeddingService._initialized = True
    
    def _init_azure_openai_client(self):
        """Azure OpenAI 클라이언트 초기화"""
        try:
            if hasattr(settings, 'azure_openai_endpoint') and settings.azure_openai_endpoint:
                from openai import AsyncAzureOpenAI
                self.azure_openai_client = AsyncAzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    api_version=settings.azure_openai_api_version,
                    azure_endpoint=settings.azure_openai_endpoint
                )
                logger.info(f"✅ Azure OpenAI embedding client initialized - Endpoint: {settings.azure_openai_endpoint}")
                print(f"✅ Azure OpenAI 임베딩 클라이언트 초기화 성공")
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            print(f"❌ Azure OpenAI 클라이언트 초기화 실패: {e}")
    
    def _init_bedrock_client(self):
        """Bedrock 클라이언트 초기화"""
        try:
            # AWS 자격증명이 설정에 있는지 확인
            if hasattr(settings, 'aws_access_key_id') and settings.aws_access_key_id:
                self.bedrock_client = boto3.client(
                    'bedrock-runtime',
                    region_name=settings.aws_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key
                )
                logger.info(f"✅ AWS Bedrock client initialized - Region: {settings.aws_region}")
                print(f"✅ AWS Bedrock 클라이언트 초기화 성공 - Region: {settings.aws_region}")
            else:
                # 환경변수에서 직접 읽기 시도
                aws_key = os.getenv('AWS_ACCESS_KEY_ID')
                aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
                aws_region = os.getenv('AWS_REGION', 'ap-northeast-2')
                
                if aws_key and aws_secret:
                    self.bedrock_client = boto3.client(
                        'bedrock-runtime',
                        region_name=aws_region,
                        aws_access_key_id=aws_key,
                        aws_secret_access_key=aws_secret
                    )
                    logger.info(f"✅ AWS Bedrock client initialized from env vars - Region: {aws_region}")
                    print(f"✅ AWS Bedrock 클라이언트 초기화 성공 (환경변수) - Region: {aws_region}")
                else:
                    logger.warning("❌ AWS credentials not found in settings or environment")
                    print("❌ AWS 자격증명을 찾을 수 없음")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            print(f"❌ Bedrock 클라이언트 초기화 실패: {e}")
    
    def _init_openai_client(self):
        """OpenAI 클라이언트 초기화"""
        try:
            if settings.openai_api_key:
                from openai import AsyncOpenAI
                self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
                logger.info("OpenAI embedding client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        텍스트에 대한 임베딩 벡터 생성 (설정된 차원으로 통일)
        """
        if not isinstance(text, str):
            text = str(text)

        now = time.time()
        cached = self._embedding_cache.get(text)
        if cached and now - cached[0] <= self._embedding_cache_ttl:
            logger.debug("임베딩 캐시 적중")
            return cached[1]

        inflight = self._embedding_inflight.get(text)
        if inflight:
            logger.debug("동일 임베딩 요청 진행 중 - 기존 Future 재사용")
            return await asyncio.shield(inflight)

        async def _compute() -> List[float]:
            try:
                vector = await self._generate_embedding(text)
                self._embedding_cache[text] = (time.time(), vector)
                return vector
            finally:
                self._embedding_inflight.pop(text, None)

        task = asyncio.create_task(_compute())
        self._embedding_inflight[text] = task
        return await task

    async def _generate_embedding(self, text: str) -> List[float]:
        try:
            # 기본 프로바이더에 따라 시도
            if self.default_provider == 'azure_openai' and self.azure_openai_client:
                embedding = await self._get_azure_openai_embedding(text)
                return self._normalize_embedding_dimension(embedding)
            
            # 1. AWS Bedrock 임베딩 시도
            elif self.default_provider == 'bedrock' and self.bedrock_client:
                embedding = await self._get_bedrock_embedding(text)
                return self._normalize_embedding_dimension(embedding)
            
            # 2. OpenAI 임베딩 시도
            elif self.default_provider == 'openai' and self.openai_client:
                embedding = await self._get_openai_embedding(text)
                return self._normalize_embedding_dimension(embedding)
            
            # 폴백 시도: 사용 가능한 다른 클라이언트 사용
            if self.azure_openai_client:
                embedding = await self._get_azure_openai_embedding(text)
                return self._normalize_embedding_dimension(embedding)
            elif self.bedrock_client:
                embedding = await self._get_bedrock_embedding(text)
                return self._normalize_embedding_dimension(embedding)
            elif self.openai_client:
                embedding = await self._get_openai_embedding(text)
                return self._normalize_embedding_dimension(embedding)
            
            # 3. 모든 클라이언트가 없는 경우 더미 벡터 반환
            logger.warning("No embedding service available, returning dummy vector")
            return [0.0] * settings.vector_dimension
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # 오류 발생 시 더미 벡터 반환
            return [0.0] * settings.get_current_embedding_dimension()
    
    async def _get_azure_openai_embedding(self, text: str) -> List[float]:
        """Azure OpenAI를 사용한 임베딩 생성"""
        try:
            response = await self.azure_openai_client.embeddings.create(
                model=settings.azure_openai_embedding_deployment,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Azure OpenAI embedding error: {e}")
            raise
    
    async def _get_bedrock_embedding(self, text: str) -> List[float]:
        """AWS Bedrock을 사용한 임베딩 생성"""
        try:
            import json
            
            # AWS Bedrock embedding model에 따라 입력 형식 조정
            embedding_model_id = settings.get_current_embedding_model()
            if "titan-embed" in embedding_model_id:
                # Amazon Titan Embedding 모델 사용
                request_body = json.dumps({
                    "inputText": text
                })
                
                response = self.bedrock_client.invoke_model(
                    modelId=embedding_model_id,
                    body=request_body,
                    contentType="application/json",
                    accept="application/json"
                )
                
                response_body = json.loads(response['body'].read())
                return response_body['embedding']
            
            else:
                # 다른 Bedrock embedding 모델에 대한 폴백
                logger.warning(f"Unsupported Bedrock embedding model: {embedding_model_id}")
                raise ValueError(f"Unsupported embedding model: {embedding_model_id}")
            
        except Exception as e:
            logger.error(f"AWS Bedrock embedding error: {e}")
            raise
    
    async def _get_openai_embedding(self, text: str) -> List[float]:
        """OpenAI를 사용한 임베딩 생성"""
        try:
            response = await self.openai_client.embeddings.create(
                model=settings.openai_embedding_model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise
    
    async def get_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        여러 텍스트에 대한 임베딩 벡터 일괄 생성 (배치 최적화)
        
        Azure OpenAI는 최대 2048개 텍스트를 한 번에 처리 가능하지만,
        안정성을 위해 batch_size(기본 100)개씩 나눠서 처리합니다.
        
        Args:
            texts: 임베딩할 텍스트 리스트
            batch_size: 한 번의 API 호출에 포함할 텍스트 수 (기본 100)
            
        Returns:
            임베딩 벡터 리스트 (입력 텍스트 순서와 동일)
        """
        if not texts:
            return []
            
        try:
            # Azure OpenAI 배치 처리 (최대 성능)
            if self.default_provider == 'azure_openai' and self.azure_openai_client:
                return await self._get_azure_openai_embeddings_batch(texts, batch_size)
            
            # OpenAI 배치 처리
            elif self.default_provider == 'openai' and self.openai_client:
                return await self._get_openai_embeddings_batch(texts, batch_size)
            
            # Bedrock은 배치 API가 없으므로 개별 처리 (폴백)
            elif self.default_provider == 'bedrock' and self.bedrock_client:
                logger.warning(f"[BATCH-EMB] Bedrock은 배치 API 미지원 - {len(texts)}개 개별 처리")
                embeddings = []
                for text in texts:
                    embedding = await self.get_embedding(text)
                    embeddings.append(embedding)
                return embeddings
            
            # 폴백: 사용 가능한 다른 클라이언트 사용
            if self.azure_openai_client:
                return await self._get_azure_openai_embeddings_batch(texts, batch_size)
            elif self.openai_client:
                return await self._get_openai_embeddings_batch(texts, batch_size)
            elif self.bedrock_client:
                logger.warning(f"[BATCH-EMB] Bedrock은 배치 API 미지원 - {len(texts)}개 개별 처리")
                embeddings = []
                for text in texts:
                    embedding = await self.get_embedding(text)
                    embeddings.append(embedding)
                return embeddings
            
            # 모든 클라이언트가 없는 경우 더미 벡터 반환
            logger.warning(f"[BATCH-EMB] 임베딩 서비스 없음 - {len(texts)}개 더미 벡터 반환")
            return [[0.0] * settings.vector_dimension for _ in texts]
            
        except Exception as e:
            logger.error(f"[BATCH-EMB] 배치 임베딩 생성 오류: {e}")
            # 오류 발생 시 더미 벡터들 반환
            return [[0.0] * settings.vector_dimension for _ in texts]
    
    async def _get_azure_openai_embeddings_batch(self, texts: List[str], batch_size: int) -> List[List[float]]:
        """Azure OpenAI 배치 임베딩 (최대 100개씩)"""
        all_embeddings: List[List[float]] = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            try:
                response = await self.azure_openai_client.embeddings.create(
                    model=settings.azure_openai_embedding_deployment,
                    input=batch  # 한 번에 여러 텍스트 전송
                )
                
                # 응답 데이터를 순서대로 추출
                batch_embeddings = []
                for text_value, data in zip(batch, response.data):
                    normalized = self._normalize_embedding_dimension(data.embedding)
                    batch_embeddings.append(normalized)
                    self._embedding_cache[text_value] = (time.time(), normalized)
                all_embeddings.extend(batch_embeddings)
                
                logger.debug(f"[BATCH-EMB][Azure] {i+1}~{i+len(batch)}/{len(texts)} 완료")
                
            except Exception as e:
                logger.error(f"[BATCH-EMB][Azure] 배치 {i}~{i+batch_size} 실패: {e}")
                # 실패한 배치는 더미 벡터로 채움
                all_embeddings.extend([[0.0] * settings.vector_dimension for _ in batch])
        
        return all_embeddings
    
    async def _get_openai_embeddings_batch(self, texts: List[str], batch_size: int) -> List[List[float]]:
        """OpenAI 배치 임베딩 (최대 100개씩)"""
        all_embeddings: List[List[float]] = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            try:
                response = await self.openai_client.embeddings.create(
                    model=settings.openai_embedding_model,
                    input=batch  # 한 번에 여러 텍스트 전송
                )
                
                # 응답 데이터를 순서대로 추출
                batch_embeddings = []
                for text_value, data in zip(batch, response.data):
                    normalized = self._normalize_embedding_dimension(data.embedding)
                    batch_embeddings.append(normalized)
                    self._embedding_cache[text_value] = (time.time(), normalized)
                all_embeddings.extend(batch_embeddings)
                
                logger.debug(f"[BATCH-EMB][OpenAI] {i+1}~{i+len(batch)}/{len(texts)} 완료")
                
            except Exception as e:
                logger.error(f"[BATCH-EMB][OpenAI] 배치 {i}~{i+batch_size} 실패: {e}")
                # 실패한 배치는 더미 벡터로 채움
                all_embeddings.extend([[0.0] * settings.vector_dimension for _ in batch])
        
        return all_embeddings
    
    def _normalize_embedding_dimension(self, embedding: List[float]) -> List[float]:
        """
        임베딩 벡터를 설정된 차원으로 정규화 (작은 차원은 제로 패딩, 큰 차원은 그대로 유지)
        """
        target_dimension = settings.vector_dimension
        current_dimension = len(embedding)
        
        if current_dimension == target_dimension:
            return embedding
        elif current_dimension < target_dimension:
            # 확장: 0으로 패딩 (성능 보존)
            logger.debug(f"임베딩 차원 확장 (제로 패딩): {current_dimension} -> {target_dimension}")
            return embedding + [0.0] * (target_dimension - current_dimension)
        else:
            # 큰 차원의 경우 설정 오류 방지를 위해 경고 후 그대로 반환
            logger.warning(f"임베딩 차원이 설정보다 큼: {current_dimension} > {target_dimension}. 원본 유지.")
            return embedding


# 전역 싱글톤 인스턴스 생성
embedding_service = EmbeddingService()
