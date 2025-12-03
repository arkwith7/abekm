from typing import List, Optional, Dict, Any
import time
from langchain.llms.base import BaseLLM
from langchain.embeddings.base import Embeddings
from langchain_aws import ChatBedrock, ChatBedrockConverse, BedrockEmbeddings
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings, ChatOpenAI, OpenAIEmbeddings
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from loguru import logger
import os
from app.core.config import settings


class MultiVendorAIService:
    """멀티 벤더 AI 서비스 - AWS Bedrock, Azure OpenAI, OpenAI 지원"""
    
    # 추론 모델 목록 (temperature 미지원)
    REASONING_MODELS = ["o1", "o3", "gpt-5"]
    
    def __init__(self):
        # Provider 별 LLM / Embedding 인스턴스
        self.llm_providers: Dict[str, BaseLLM] = {}
        self.embedding_providers: Dict[str, Embeddings] = {}

        # 기본 제공자 및 간단 메트릭 구조
        self.default_provider: str = settings.get_current_llm_provider()
        self._stats: Dict[str, Dict[str, Any]] = {}
        self._last_switch_time: Optional[str] = None
        self._init_errors: Dict[str, str] = {}

        # 각 AI 제공자 초기화 (실패는 기록)
        self._init_azure_openai()
        self._init_bedrock()
        self._init_openai()
    
    def _is_reasoning_model(self, model_name: str) -> bool:
        """추론 모델 여부 확인 (temperature 미지원 모델)"""
        model_lower = model_name.lower()
        return any(reasoning_model in model_lower for reasoning_model in self.REASONING_MODELS)
        
    def _init_azure_openai(self):
        """Azure OpenAI 초기화"""
        try:
            if settings.azure_openai_api_key and settings.azure_openai_endpoint:
                # LLM 초기화 - 동적 모델 사용
                deployment = settings.get_current_llm_model() if settings.get_current_llm_provider() == "azure_openai" else settings.azure_openai_llm_deployment

                llm_kwargs: Dict[str, Any] = {
                    "azure_endpoint": settings.azure_openai_endpoint,
                    "api_key": settings.azure_openai_api_key,
                    "api_version": settings.azure_openai_api_version,
                    "deployment_name": deployment,
                }
                
                # 추론 모델 여부 확인
                is_reasoning = self._is_reasoning_model(deployment)
                
                if is_reasoning:
                    # 추론 모델: temperature 제거, max_completion_tokens 사용
                    llm_kwargs["model_kwargs"] = {"max_completion_tokens": settings.max_tokens}
                    logger.info(f"🧠 추론 모델 감지: {deployment} (temperature 미지원)")
                else:
                    # 일반 모델: temperature 사용
                    llm_kwargs["temperature"] = settings.temperature
                    llm_kwargs["max_tokens"] = settings.max_tokens
                    logger.info(f"💬 일반 모델: {deployment} (temperature={settings.temperature})")
                
                self.llm_providers["azure_openai"] = AzureChatOpenAI(**llm_kwargs)
                
                # 임베딩 초기화 - 동적 모델 사용
                self.embedding_providers["azure_openai"] = AzureOpenAIEmbeddings(
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_api_key,
                    api_version=settings.azure_openai_api_version,
                    deployment=settings.get_current_embedding_model() if settings.get_current_embedding_provider() == "azure_openai" else settings.azure_openai_embedding_deployment,
                )
                
                logger.info("Azure OpenAI 초기화 완료")
        except Exception as e:
            logger.error(f"Azure OpenAI 초기화 실패: {e}")
    
    def _init_bedrock(self):
        """AWS Bedrock 초기화"""
        try:
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                # 환경 변수 설정
                os.environ["AWS_ACCESS_KEY_ID"] = settings.aws_access_key_id
                os.environ["AWS_SECRET_ACCESS_KEY"] = settings.aws_secret_access_key
                os.environ["AWS_DEFAULT_REGION"] = settings.aws_region
                
                # LLM 초기화 - 동적 모델 사용
                model_id = settings.get_current_llm_model() if settings.get_current_llm_provider() == "bedrock" else settings.bedrock_llm_model_id
                
                # 교차 리전 추론 모델 감지 (us., eu., apac. 등 프리픽스)
                is_cross_region = any(model_id.startswith(prefix) for prefix in ["us.", "eu.", "apac.", "global."])
                
                if is_cross_region:
                    # 교차 리전 추론: ChatBedrockConverse 사용 (Converse API)
                    logger.info(f"🌐 교차 리전 추론 모델 감지: {model_id} → ChatBedrockConverse 사용")
                    self.llm_providers["bedrock"] = ChatBedrockConverse(
                        model=model_id,
                        region_name=settings.aws_region,
                        max_tokens=settings.max_tokens,
                        temperature=settings.temperature,
                    )
                else:
                    # 단일 리전: ChatBedrock 사용 (InvokeModel API)
                    logger.info(f"📍 단일 리전 모델: {model_id} → ChatBedrock 사용")
                    self.llm_providers["bedrock"] = ChatBedrock(
                        model_id=model_id,
                        region_name=settings.aws_region,
                        model_kwargs={
                            "max_tokens": settings.max_tokens,
                            "temperature": settings.temperature,
                            "top_p": settings.top_p,
                        }
                    )
                
                # 임베딩 초기화 - 동적 모델 사용
                self.embedding_providers["bedrock"] = BedrockEmbeddings(
                    model_id=settings.get_current_embedding_model() if settings.get_current_embedding_provider() == "bedrock" else settings.bedrock_embedding_model_id,
                    region_name=settings.aws_region,
                )
                
                logger.info("AWS Bedrock 초기화 완료")
        except Exception as e:
            logger.error(f"AWS Bedrock 초기화 실패: {e}")
    
    def _init_openai(self):
        """OpenAI 초기화"""
        try:
            if settings.openai_api_key:
                # LLM 초기화 - 동적 모델 사용
                model_name = settings.get_current_llm_model() if settings.get_current_llm_provider() == "openai" else settings.openai_llm_model
                
                llm_kwargs: Dict[str, Any] = {
                    "api_key": settings.openai_api_key,
                    "model": model_name,
                }
                
                # 추론 모델 여부 확인
                is_reasoning = self._is_reasoning_model(model_name)
                
                if is_reasoning:
                    # 추론 모델: temperature 제거, max_completion_tokens 사용
                    llm_kwargs["model_kwargs"] = {"max_completion_tokens": settings.max_tokens}
                    logger.info(f"🧠 추론 모델 감지: {model_name} (temperature 미지원)")
                else:
                    # 일반 모델: temperature 사용
                    llm_kwargs["temperature"] = settings.temperature
                    llm_kwargs["max_tokens"] = settings.max_tokens
                    logger.info(f"💬 일반 모델: {model_name} (temperature={settings.temperature})")
                
                self.llm_providers["openai"] = ChatOpenAI(**llm_kwargs)
                
                # 임베딩 초기화 - 동적 모델 사용
                self.embedding_providers["openai"] = OpenAIEmbeddings(
                    api_key=settings.openai_api_key,
                    model=settings.get_current_embedding_model() if settings.get_current_embedding_provider() == "openai" else settings.openai_embedding_model,
                )
                
                logger.info("OpenAI 초기화 완료")
        except Exception as e:
            logger.error(f"OpenAI 초기화 실패: {e}")
    
    def get_llm(self, provider: Optional[str] = None) -> Optional[BaseLLM]:
        """LLM 인스턴스 반환"""
        provider = provider or self.default_provider
        
        if provider in self.llm_providers:
            return self.llm_providers[provider]
        
        # 기본 제공자가 실패하면 사용 가능한 다른 제공자 시도
        for fallback_provider in settings.llm_providers:
            if fallback_provider in self.llm_providers:
                logger.warning(f"기본 제공자 {provider} 실패, {fallback_provider}로 폴백")
                return self.llm_providers[fallback_provider]
        
        logger.error("사용 가능한 LLM 제공자가 없습니다")
        return None
    
    def get_embeddings(self, provider: Optional[str] = None) -> Optional[Embeddings]:
        """임베딩 인스턴스 반환"""
        provider = provider or self.default_provider
        
        if provider in self.embedding_providers:
            return self.embedding_providers[provider]
        
        # 기본 제공자가 실패하면 사용 가능한 다른 제공자 시도
        for fallback_provider in settings.llm_providers:
            if fallback_provider in self.embedding_providers:
                logger.warning(f"기본 임베딩 제공자 {provider} 실패, {fallback_provider}로 폴백")
                return self.embedding_providers[fallback_provider]
        
        logger.error("사용 가능한 임베딩 제공자가 없습니다")
        return None
    
    async def chat(self, message: str, provider: Optional[str] = None) -> str:
        """단일 사용자 입력 문자열에 대한 LLM 응답 (단순 문자열 반환).
        NOTE: 다중 turn 및 기록 포함 응답은 chat_completion() 사용 권장.
        """
        try:
            llm = self.get_llm(provider)
            if not llm:
                raise ValueError("사용 가능한 LLM이 없습니다")

            messages = [HumanMessage(content=message)]
            start = time.time()
            response = await llm.ainvoke(messages)
            elapsed = int((time.time() - start) * 1000)
            used_provider = provider or self.default_provider
            if used_provider not in self._stats:
                self._stats[used_provider] = {"requests": 0, "errors": 0, "last_error": None, "latencies_ms": []}
            self._stats[used_provider]["requests"] += 1
            self._stats[used_provider]["latencies_ms"].append(elapsed)
            # 일부 LLM 구현은 객체/문자열 모두 가능
            if hasattr(response, 'content'):
                return getattr(response, 'content')  # type: ignore[attr-defined]
            return str(response)
        except Exception as e:
            used_provider = provider or self.default_provider
            if used_provider not in self._stats:
                self._stats[used_provider] = {"requests": 0, "errors": 0, "last_error": None, "latencies_ms": []}
            self._stats[used_provider]["errors"] += 1
            self._stats[used_provider]["last_error"] = str(e)
            logger.error(f"채팅 처리 중 오류: {e}")
            raise

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """다중 메시지(chat history) 입력을 받아 표준 dict 반환.
        messages 예시: [{"role": "user"|"assistant"|"system", "content": "..."}, ...]
        반환: {"response": str, "provider": str, "raw": Any}
        """
        if not messages:
            raise ValueError("messages 리스트가 비어 있습니다.")
        llm = self.get_llm(provider)
        if not llm:
            raise ValueError("사용 가능한 LLM이 없습니다")
        
        # 파라미터 적용 (reasoning 모델은 temperature 미지원)
        # gpt-5-nano는 reasoning 모델이므로 temperature 제거
        used_provider = provider or self.default_provider
        model_name = getattr(llm, "deployment_name", "") or getattr(llm, "model_id", "")
        is_reasoning = self._is_reasoning_model(model_name)
        
        if not is_reasoning:
            if max_tokens:
                llm = llm.bind(max_tokens=max_tokens)
            if temperature is not None:
                llm = llm.bind(temperature=temperature)

        lc_messages: List[HumanMessage | AIMessage] = []
        for m in messages:
            role = (m.get("role") or "user").lower()
            content = m.get("content") or ""
            if role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                # system / user 둘 다 HumanMessage 로 처리 (간단화)
                lc_messages.append(HumanMessage(content=content))

        start = time.time()
        used_provider = provider or self.default_provider
        try:
            result = await llm.ainvoke(lc_messages)
            elapsed = int((time.time() - start) * 1000)
            if used_provider not in self._stats:
                self._stats[used_provider] = {"requests": 0, "errors": 0, "last_error": None, "latencies_ms": []}
            self._stats[used_provider]["requests"] += 1
            self._stats[used_provider]["latencies_ms"].append(elapsed)
            if hasattr(result, "content"):
                text = getattr(result, "content")  # type: ignore[attr-defined]
            else:
                text = str(result)
            return {"response": text, "provider": used_provider, "raw": result}
        except Exception as e:
            if used_provider not in self._stats:
                self._stats[used_provider] = {"requests": 0, "errors": 0, "last_error": None, "latencies_ms": []}
            self._stats[used_provider]["errors"] += 1
            self._stats[used_provider]["last_error"] = str(e)
            logger.error(f"chat_completion 처리 중 오류: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ):
        """스트리밍 채팅 메시지 처리. 메시지 목록을 직접 받습니다."""
        try:
            current_provider = provider or self.default_provider
            llm = self.get_llm(current_provider)
            if not llm:
                raise ValueError("사용 가능한 LLM이 없습니다")

            # 현재 모델명 추적 (reasoning 모델 여부 판단용)
            current_model = None
            if current_provider == "azure_openai":
                current_model = settings.azure_openai_llm_deployment
            elif current_provider == "bedrock":
                current_model = settings.bedrock_llm_model_id
            elif current_provider == "openai":
                current_model = settings.openai_llm_model

            is_reasoning = self._is_reasoning_model(current_model or "")

            # 요청 단위 LLM 파라미터 적용 (reasoning 모델은 temperature 미지원)
            bind_kwargs: Dict[str, Any] = {}
            if max_tokens:
                if is_reasoning:
                    bind_kwargs["max_completion_tokens"] = max_tokens
                else:
                    bind_kwargs["max_tokens"] = max_tokens
            if temperature is not None:
                if is_reasoning:
                    logger.info(
                        f"⚠️ reasoning 모델({current_model})은 temperature를 지원하지 않아 무시합니다"
                    )
                else:
                    bind_kwargs["temperature"] = temperature
            if bind_kwargs:
                llm = llm.bind(**bind_kwargs)
                logger.info(f"🔧 LLM 파라미터 바인딩: provider={current_provider}, params={bind_kwargs}")

            # LangChain 메시지 형식으로 변환
            lc_messages: List[HumanMessage | AIMessage | SystemMessage] = []
            for m in messages:
                role = (m.get("role") or "user").lower()
                content = m.get("content") or ""
                if not content:
                    continue
                if role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                elif role == "system":
                    lc_messages.append(SystemMessage(content=content))
                else:  # "user"
                    lc_messages.append(HumanMessage(content=content))

            logger.info(f"🔍 AI 스트리밍 시작 - 제공자: {current_provider}, 메시지 수: {len(lc_messages)}")

            # 스트리밍 LLM 호출
            chunk_count = 0
            async for chunk in llm.astream(lc_messages):
                chunk_count += 1
                # 초기 몇 개 청크는 디버그로 남겨 스트리밍 건강상태 확인
                if chunk_count <= 3:
                    try:
                        logger.debug(f"🔹 스트림 청크#{chunk_count} 수신: {str(chunk)[:120]}...")
                    except Exception:
                        pass
                content = None

                # content 속성이 있는 경우
                if hasattr(chunk, 'content') and getattr(chunk, 'content'):
                    content = getattr(chunk, 'content')
                # text 속성이 있는 경우 (메서드가 아닌 실제 텍스트)
                elif hasattr(chunk, 'text'):
                    chunk_text_attr = getattr(chunk, 'text')
                    if callable(chunk_text_attr):
                        try:
                            content = chunk_text_attr()
                        except Exception as e:
                            logger.error(f"🔍 청크 #{chunk_count} - text() 호출 실패: {e}")
                            content = str(chunk)
                    else:
                        content = chunk_text_attr
                # 기타 경우 문자열로 변환
                elif str(chunk).strip():
                    content = str(chunk)

                # 유효한 내용이 있는 경우만 yield
                if content:
                    content_str = str(content)
                    if content_str.strip():
                        yield content_str

        except Exception as e:
            logger.error(f"스트리밍 채팅 처리 중 오류: {e}")
            raise
    
    async def get_text_embeddings(self, texts: List[str], provider: Optional[str] = None) -> List[List[float]]:
        """텍스트 임베딩 생성"""
        try:
            embeddings = self.get_embeddings(provider)
            if not embeddings:
                raise ValueError("사용 가능한 임베딩 제공자가 없습니다")
            
            # 임베딩 생성
            embedding_vectors = await embeddings.aembed_documents(texts)
            return embedding_vectors
            
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류: {e}")
            raise
    
    async def search_documents(self, query: str, provider: Optional[str] = None) -> List[float]:
        """문서 검색용 단일 쿼리 임베딩 벡터 생성 (단일 벡터 List[float] 반환)"""
        try:
            embeddings = self.get_embeddings(provider)
            if not embeddings:
                raise ValueError("사용 가능한 임베딩 제공자가 없습니다")
            
            # 쿼리 임베딩 생성
            query_embedding = await embeddings.aembed_query(query)
            return query_embedding
            
        except Exception as e:
            logger.error(f"쿼리 임베딩 생성 중 오류: {e}")
            raise
    
    def get_available_providers(self) -> Dict[str, Any]:
        """사용 가능한 제공자 목록 및 기본 제공자 반환"""
        return {
            "llm_providers": list(self.llm_providers.keys()),
            "embedding_providers": list(self.embedding_providers.keys()),
            "default_provider": self.default_provider,
        }


# 전역 인스턴스
ai_service = MultiVendorAIService()
