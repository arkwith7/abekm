import json
import boto3
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError, BotoCoreError
from loguru import logger
from app.core.config import settings

class BedrockService:
    """AWS Bedrock LLM 및 Embedding 서비스"""
    
    def __init__(self):
        self.region = settings.aws_region
        self.client = boto3.client(
            'bedrock-runtime',
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key
        )
        
        # 동적 모델 설정
        self.text_model_id = settings.get_current_llm_model()
        self.embedding_model_id = settings.get_current_embedding_model()
        self.alt_embedding_model_id = settings.bedrock_alt_embedding_model_id
        
        logger.info(f"Bedrock 서비스 초기화 완료 - Region: {self.region}")
        logger.info(f"Text Model: {self.text_model_id}")
        logger.info(f"Embedding Model: {self.embedding_model_id}")
    
    async def generate_text_claude(
        self, 
        prompt: str, 
        max_tokens: int = None,
        temperature: float = None,
        top_p: float = None,
        top_k: int = None,
        system_prompt: str = None
    ) -> str:
        """
        Claude 3.5 Sonnet v2를 사용한 텍스트 생성
        """
        try:
            # 파라미터 설정 - 동적 구성 사용
            max_tokens = max_tokens or settings.bedrock_max_tokens
            temperature = temperature or settings.bedrock_temperature
            top_p = top_p or settings.bedrock_top_p
            top_k = top_k or settings.bedrock_top_k
            
            # Claude 3.5 Sonnet v2 요청 형식
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "messages": messages
            }
            
            # 시스템 프롬프트가 있는 경우 추가
            if system_prompt:
                body["system"] = system_prompt
            
            logger.debug(f"Claude 요청: {json.dumps(body, ensure_ascii=False)}")
            
            response = self.client.invoke_model(
                modelId=self.text_model_id,
                body=json.dumps(body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            logger.debug(f"Claude 응답: {response_body}")
            
            # Claude 응답 형식에서 텍스트 추출
            if 'content' in response_body and response_body['content']:
                return response_body['content'][0]['text']
            else:
                logger.error(f"Unexpected Claude response format: {response_body}")
                return ""
                
        except ClientError as e:
            logger.error(f"Claude 텍스트 생성 중 AWS 클라이언트 오류: {e}")
            return ""
        except Exception as e:
            logger.error(f"Claude 텍스트 생성 중 오류: {e}")
            return ""
    
    async def get_embeddings_titan(self, texts: List[str]) -> List[List[float]]:
        """
        Amazon Titan Text Embeddings V2를 사용한 임베딩 생성
        """
        try:
            embeddings = []
            
            for i, text in enumerate(texts):
                # 토큰 수 계산 및 검증
                import tiktoken
                tokenizer = tiktoken.get_encoding("cl100k_base")
                token_count = len(tokenizer.encode(text))
                
                # Titan Embeddings V2 토큰 제한: 8,192
                max_tokens = 8000  # 안전 마진 포함
                
                if token_count > max_tokens:
                    logger.warning(f"텍스트 {i}가 토큰 제한 초과: {token_count} > {max_tokens}")
                    # 텍스트를 토큰 제한에 맞게 자르기
                    tokens = tokenizer.encode(text)
                    truncated_tokens = tokens[:max_tokens]
                    text = tokenizer.decode(truncated_tokens)
                    logger.info(f"텍스트 {i}를 {max_tokens} 토큰으로 자름")
                
                # Titan Embeddings V2 요청 형식
                body = {
                    "inputText": text,
                    "dimensions": settings.vector_dimension,
                    "normalize": True
                }
                
                logger.debug(f"Titan 임베딩 요청: {text[:100]}... (토큰: {token_count})")
                
                response = self.client.invoke_model(
                    modelId=self.embedding_model_id,
                    body=json.dumps(body),
                    contentType='application/json',
                    accept='application/json'
                )
                
                response_body = json.loads(response['body'].read())
                
                # Titan 응답에서 임베딩 벡터 추출
                if 'embedding' in response_body:
                    embeddings.append(response_body['embedding'])
                else:
                    logger.error(f"Unexpected Titan response format: {response_body}")
                    embeddings.append([0.0] * settings.vector_dimension)
            
            logger.info(f"Titan 임베딩 생성 완료: {len(embeddings)}개")
            return embeddings
            
        except ClientError as e:
            logger.error(f"Titan 임베딩 생성 중 AWS 클라이언트 오류: {e}")
            return [[0.0] * settings.vector_dimension for _ in texts]
        except Exception as e:
            logger.error(f"Titan 임베딩 생성 중 오류: {e}")
            return [[0.0] * settings.vector_dimension for _ in texts]
    
    async def get_embeddings_cohere(self, texts: List[str]) -> List[List[float]]:
        """
        Cohere Embed Multilingual v3 (Marengo Embed 2.7)를 사용한 임베딩 생성
        """
        try:
            embeddings = []
            
            for text in texts:
                # Cohere Embed 요청 형식
                body = {
                    "texts": [text],
                    "input_type": "search_document",  # 문서 검색용
                    "truncate": "END"
                }
                
                logger.debug(f"Cohere 임베딩 요청: {text[:100]}...")
                
                response = self.client.invoke_model(
                    modelId=self.alt_embedding_model_id,
                    body=json.dumps(body),
                    contentType='application/json',
                    accept='application/json'
                )
                
                response_body = json.loads(response['body'].read())
                
                # Cohere 응답에서 임베딩 벡터 추출
                if 'embeddings' in response_body and response_body['embeddings']:
                    embeddings.append(response_body['embeddings'][0])
                else:
                    logger.error(f"Unexpected Cohere response format: {response_body}")
                    embeddings.append([0.0] * settings.VECTOR_DIMENSION)
            
            logger.info(f"Cohere 임베딩 생성 완료: {len(embeddings)}개")
            return embeddings
            
        except ClientError as e:
            logger.error(f"Cohere 임베딩 생성 중 AWS 클라이언트 오류: {e}")
            return [[0.0] * settings.VECTOR_DIMENSION for _ in texts]
        except Exception as e:
            logger.error(f"Cohere 임베딩 생성 중 오류: {e}")
            return [[0.0] * settings.VECTOR_DIMENSION for _ in texts]
    
    async def check_model_access(self) -> Dict[str, bool]:
        """
        사용 가능한 모델들의 접근 권한 확인
        """
        try:
            bedrock_client = boto3.client(
                'bedrock',
                region_name=self.region,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            
            # 사용 가능한 기본 모델 목록 조회
            response = bedrock_client.list_foundation_models()
            available_models = [model['modelId'] for model in response['modelSummaries']]
            
            model_access = {
                'claude_3_5_sonnet': self.text_model_id in available_models,
                'titan_embeddings_v2': self.embedding_model_id in available_models,
                'cohere_embed_multilingual': self.alt_embedding_model_id in available_models
            }
            
            logger.info(f"모델 접근 권한 확인: {model_access}")
            return model_access
            
        except Exception as e:
            logger.error(f"모델 접근 권한 확인 중 오류: {e}")
            return {
                'claude_3_5_sonnet': False,
                'titan_embeddings_v2': False,
                'cohere_embed_multilingual': False
            }
    
    async def chat_with_context(
        self, 
        user_message: str, 
        context_documents: List[str],
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """
        컨텍스트와 대화 히스토리를 포함한 채팅
        """
        try:
            # 시스템 프롬프트 구성
            system_prompt = """당신은 WKMS(지식 관리 시스템)의 AI 어시스턴트입니다. 
제공된 문서 컨텍스트를 바탕으로 정확하고 도움이 되는 답변을 제공하세요.
한국어로 답변하며, 문서에 없는 내용은 추측하지 마세요."""
            
            # 컨텍스트 문서를 프롬프트에 포함
            context_text = ""
            if context_documents:
                context_text = "\n\n관련 문서:\n" + "\n".join([f"- {doc}" for doc in context_documents])
            
            # 대화 히스토리 포함
            history_text = ""
            if conversation_history:
                history_text = "\n\n이전 대화:\n"
                for item in conversation_history[-5:]:  # 최근 5개만
                    history_text += f"사용자: {item.get('user', '')}\n어시스턴트: {item.get('assistant', '')}\n"
            
            full_prompt = f"{context_text}{history_text}\n\n현재 질문: {user_message}"
            
            response = await self.generate_text_claude(
                prompt=full_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=2048
            )
            
            return response
            
        except Exception as e:
            logger.error(f"컨텍스트 채팅 중 오류: {e}")
            return "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다."

# 싱글톤 인스턴스
bedrock_service = BedrockService()
