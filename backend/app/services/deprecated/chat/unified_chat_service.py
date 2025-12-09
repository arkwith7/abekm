"""
💬 통합 채팅 및 RAG 서비스 (Unified Chat & RAG Service)
======================================================

🎯 목적:
- vs_doc_contents_index를 활용한 RAG 기반 질의응답
- tb_chat_history를 이용한 세션 기반 대화 관리
- 실시간 채팅 및 히스토리 관리 통합

📊 핵심 데이터 소스:
- vs_doc_contents_index: RAG 컨텍스트 검색의 메인 소스
- tb_file_bss_info: 문서 메타데이터 및 출처 정보
- tb_chat_history: 대화 이력 및 세션 관리

🔄 RAG 플로우:
1. 사용자 질문 → 임베딩 생성
2. vs_doc_contents_index에서 관련 문서 검색
3. 검색된 청크들로 컨텍스트 구성
4. LLM을 통한 답변 생성
5. tb_chat_history에 대화 저장
"""

import json
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_, func, desc

from app.core.database import get_async_session_local
from app.services.core.ai_service import ai_service
from app.services.search.search_service import search_service
from app.services.auth.permission_service import PermissionService
from app.models import TbChatHistory
from app.models import TbFileBssInfo, TbDocumentSearchIndex
from app.core.config import settings

logger = logging.getLogger(__name__)


class UnifiedChatService:
    """통합 채팅 및 RAG 서비스"""
    
    def __init__(self):
        self.async_session_local = get_async_session_local()
        
        # RAG 설정
        self.max_context_chunks = 8      # 컨텍스트로 사용할 최대 청크 수
        self.max_context_length = 4000   # 최대 컨텍스트 길이
        self.similarity_threshold = 0.6   # RAG용 유사도 임계값
        
        # 세션 설정
        self.session_timeout_hours = 24   # 세션 타임아웃 (시간)
        self.max_history_per_session = 50 # 세션당 최대 히스토리 수
        
        logger.info("💬 통합 채팅 및 RAG 서비스 초기화 완료")

    # =========================================================================
    # 💬 1. 메인 채팅 인터페이스
    # =========================================================================
    
    async def chat(
        self,
        message: str,
        user_emp_no: str,
        session_id: Optional[str] = None,
        container_ids: Optional[List[str]] = None,
        use_rag: bool = True,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        통합 채팅 메인 엔트리포인트
        
        Args:
            message: 사용자 메시지
            user_emp_no: 사용자 사번
            session_id: 채팅 세션 ID (없으면 새로 생성)
            container_ids: RAG 검색 대상 컨테이너
            use_rag: RAG 사용 여부
            provider: AI 공급자 선택
        """
        try:
            async with self.async_session_local() as session:
                start_time = datetime.now()
                
                # 1. 세션 관리
                if not session_id:
                    session_id = await self._create_new_session(session, user_emp_no)
                
                session_valid = await self._validate_session(session, session_id, user_emp_no)
                if not session_valid:
                    session_id = await self._create_new_session(session, user_emp_no)
                
                # 2. 대화 이력 조회 (컨텍스트용)
                chat_history = await self._get_chat_history(session, session_id, limit=5)
                
                # 3. RAG 기반 답변 생성
                if use_rag:
                    response_data = await self._generate_rag_response(
                        session, message, user_emp_no, container_ids, chat_history, provider
                    )
                else:
                    response_data = await self._generate_simple_response(
                        message, chat_history, provider
                    )
                
                # 4. 대화 저장
                await self._save_chat_exchange(
                    session, session_id, user_emp_no, message, response_data
                )
                
                # 5. 세션 정리 (오래된 메시지 제거)
                await self._cleanup_session_history(session, session_id)
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                return {
                    "response": response_data["response"],
                    "session_id": session_id,
                    "use_rag": use_rag,
                    "references": response_data.get("references", []),
                    "context_info": response_data.get("context_info", {}),
                    "provider": response_data.get("provider", "default"),
                    "execution_time": execution_time,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"채팅 처리 실패: {str(e)}")
            raise

    # =========================================================================
    # 🤖 2. RAG 기반 답변 생성
    # =========================================================================
    
    async def _generate_rag_response(
        self,
        session: AsyncSession,
        message: str,
        user_emp_no: str,
        container_ids: Optional[List[str]],
        chat_history: List[Dict[str, Any]],
        provider: Optional[str]
    ) -> Dict[str, Any]:
        """
        RAG 기반 답변 생성
        vs_doc_contents_index를 검색하여 컨텍스트 구성 후 답변 생성
        """
        try:
            # 1. 관련 문서 검색 (vs_doc_contents_index 활용)
            search_results = await search_service.search(
                query=message,
                user_emp_no=user_emp_no,
                container_ids=container_ids,
                max_results=self.max_context_chunks,
                search_type="vector",
                similarity_threshold=self.similarity_threshold
            )
            
            relevant_chunks = search_results.get("results", [])
            
            if not relevant_chunks:
                # 관련 문서가 없으면 일반 답변
                return await self._generate_simple_response(message, chat_history, provider)
            
            # 2. 컨텍스트 구성
            context_text, references = self._build_rag_context(relevant_chunks)
            
            # 3. 대화 이력 포함 프롬프트 구성
            prompt = self._build_rag_prompt(message, context_text, chat_history)
            
            # 4. AI 서비스를 통한 답변 생성
            ai_response = await ai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                provider=provider
            )
            
            response_text = ai_response.get("response", "죄송합니다. 답변을 생성할 수 없습니다.")
            
            # 5. 컨텍스트 정보 구성
            context_info = {
                "chunks_used": len(relevant_chunks),
                "total_context_length": len(context_text),
                "avg_similarity": sum(chunk["similarity_score"] for chunk in relevant_chunks) / len(relevant_chunks),
                "search_containers": list(set(chunk["container_id"] for chunk in relevant_chunks)),
                "search_execution_time": search_results.get("execution_time", 0)
            }
            
            return {
                "response": response_text,
                "references": references,
                "context_info": context_info,
                "provider": ai_response.get("provider", provider or "default"),
                "context_text": context_text[:500] + "..." if len(context_text) > 500 else context_text  # 디버그용
            }
            
        except Exception as e:
            logger.error(f"RAG 답변 생성 실패: {str(e)}")
            # 실패 시 일반 답변으로 폴백
            return await self._generate_simple_response(message, chat_history, provider)

    def _build_rag_context(self, relevant_chunks: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        """검색된 청크들로부터 RAG 컨텍스트 구성"""
        try:
            context_parts = []
            references = []
            current_length = 0
            
            for i, chunk in enumerate(relevant_chunks):
                chunk_text = chunk.get("content", "")
                chunk_length = len(chunk_text)
                
                # 최대 길이 초과 시 중단
                if current_length + chunk_length > self.max_context_length:
                    break
                
                # 컨텍스트에 추가
                context_parts.append(f"[문서 {i+1}]\n{chunk_text}")
                current_length += chunk_length
                
                # 참조 정보 구성
                references.append({
                    "document_id": chunk.get("document_id"),
                    "title": chunk.get("title"),
                    "file_path": chunk.get("file_path"),
                    "chunk_index": chunk.get("chunk_index"),
                    "similarity_score": chunk.get("similarity_score"),
                    "container_id": chunk.get("container_id"),
                    "content_preview": chunk.get("content_preview", "")
                })
            
            context_text = "\n\n".join(context_parts)
            
            logger.debug(f"RAG 컨텍스트 구성: {len(context_parts)}개 청크, {len(context_text)}자")
            return context_text, references
            
        except Exception as e:
            logger.error(f"RAG 컨텍스트 구성 실패: {str(e)}")
            return "", []

    def _build_rag_prompt(
        self, 
        user_message: str, 
        context_text: str, 
        chat_history: List[Dict[str, Any]]
    ) -> str:
        """RAG용 프롬프트 구성"""
        try:
            # 대화 이력 텍스트 구성
            history_text = ""
            if chat_history:
                history_parts = []
                for exchange in chat_history[-3:]:  # 최근 3개 대화만 포함
                    history_parts.append(f"사용자: {exchange['user_message']}")
                    history_parts.append(f"AI: {exchange['ai_response']}")
                history_text = "\n".join(history_parts)
            
            prompt = f"""다음 문서들을 참고하여 사용자의 질문에 정확하고 도움이 되는 답변을 제공해주세요.

=== 참고 문서 ===
{context_text}

=== 대화 이력 ===
{history_text}

=== 현재 질문 ===
{user_message}

=== 답변 지침 ===
1. 제공된 문서 내용을 기반으로 정확한 답변을 제공하세요
2. 문서에 없는 내용은 추측하지 마세요
3. 답변 시 어떤 문서를 참고했는지 언급해주세요
4. 한국어로 자연스럽고 친근하게 답변해주세요
5. 이전 대화 맥락을 고려하여 일관성 있는 답변을 제공하세요

답변:"""
            
            return prompt
            
        except Exception as e:
            logger.error(f"RAG 프롬프트 구성 실패: {str(e)}")
            return f"다음 질문에 답변해주세요: {user_message}"

    # =========================================================================
    # 📝 3. 세션 및 히스토리 관리
    # =========================================================================
    
    async def _create_new_session(self, session: AsyncSession, user_emp_no: str) -> str:
        """새로운 채팅 세션 생성"""
        try:
            session_id = f"chat_{uuid.uuid4().hex[:16]}"
            
            # 세션 시작 메시지 저장
            query = text("""
                INSERT INTO tb_chat_history (
                    session_id, user_emp_no, user_message, ai_response,
                    response_type, created_at
                ) VALUES (
                    :session_id, :user_emp_no, '[세션 시작]', '안녕하세요! 무엇을 도와드릴까요?',
                    'session_start', NOW()
                )
            """)
            
            await session.execute(query, {
                "session_id": session_id,
                "user_emp_no": user_emp_no
            })
            
            logger.info(f"새 채팅 세션 생성: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"채팅 세션 생성 실패: {str(e)}")
            return f"chat_{uuid.uuid4().hex[:16]}"  # 폴백

    async def _validate_session(
        self, 
        session: AsyncSession, 
        session_id: str, 
        user_emp_no: str
    ) -> bool:
        """채팅 세션 유효성 검증"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.session_timeout_hours)
            
            query = text("""
                SELECT COUNT(*) as count
                FROM tb_chat_history
                WHERE session_id = :session_id 
                    AND user_emp_no = :user_emp_no
                    AND created_at >= :cutoff_time
            """)
            
            result = await session.execute(query, {
                "session_id": session_id,
                "user_emp_no": user_emp_no,
                "cutoff_time": cutoff_time
            })
            
            count = result.scalar()
            return count > 0
            
        except Exception as e:
            logger.error(f"세션 유효성 검증 실패: {str(e)}")
            return False

    async def _get_chat_history(
        self, 
        session: AsyncSession, 
        session_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """채팅 이력 조회"""
        try:
            query = text("""
                SELECT user_message, ai_response, created_at, response_type
                FROM tb_chat_history
                WHERE session_id = :session_id
                    AND response_type != 'session_start'
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            
            result = await session.execute(query, {
                "session_id": session_id,
                "limit": limit
            })
            
            history = []
            for row in result.fetchall():
                history.append({
                    "user_message": row.user_message,
                    "ai_response": row.ai_response,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "response_type": row.response_type
                })
            
            # 시간순으로 정렬 (오래된 것부터)
            history.reverse()
            return history
            
        except Exception as e:
            logger.error(f"채팅 이력 조회 실패: {str(e)}")
            return []

    async def _save_chat_exchange(
        self,
        session: AsyncSession,
        session_id: str,
        user_emp_no: str,
        user_message: str,
        response_data: Dict[str, Any]
    ) -> bool:
        """채팅 대화 저장"""
        try:
            # 참조 정보가 있으면 JSON으로 저장
            references_json = None
            if response_data.get("references"):
                references_json = json.dumps(response_data["references"])
            
            # 컨텍스트 정보 JSON으로 저장
            context_json = None
            if response_data.get("context_info"):
                context_json = json.dumps(response_data["context_info"])
            
            query = text("""
                INSERT INTO tb_chat_history (
                    session_id, user_emp_no, user_message, ai_response,
                    response_type, references_json, context_json, 
                    ai_provider, created_at
                ) VALUES (
                    :session_id, :user_emp_no, :user_message, :ai_response,
                    :response_type, :references_json, :context_json,
                    :ai_provider, NOW()
                )
            """)
            
            await session.execute(query, {
                "session_id": session_id,
                "user_emp_no": user_emp_no,
                "user_message": user_message,
                "ai_response": response_data["response"],
                "response_type": "rag" if response_data.get("references") else "general",
                "references_json": references_json,
                "context_json": context_json,
                "ai_provider": response_data.get("provider", "default")
            })
            
            return True
            
        except Exception as e:
            logger.error(f"채팅 대화 저장 실패: {str(e)}")
            return False

    async def _cleanup_session_history(self, session: AsyncSession, session_id: str):
        """세션 히스토리 정리 (오래된 메시지 제거)"""
        try:
            # 세션당 최대 메시지 수 초과 시 오래된 메시지 삭제
            query = text("""
                DELETE FROM tb_chat_history
                WHERE session_id = :session_id
                    AND id NOT IN (
                        SELECT id FROM tb_chat_history
                        WHERE session_id = :session_id
                        ORDER BY created_at DESC
                        LIMIT :max_messages
                    )
            """)
            
            await session.execute(query, {
                "session_id": session_id,
                "max_messages": self.max_history_per_session
            })
            
        except Exception as e:
            logger.error(f"세션 히스토리 정리 실패: {str(e)}")

    # =========================================================================
    # 💭 4. 일반 답변 생성 (RAG 없이)
    # =========================================================================
    
    async def _generate_simple_response(
        self,
        message: str,
        chat_history: List[Dict[str, Any]],
        provider: Optional[str]
    ) -> Dict[str, Any]:
        """일반 답변 생성 (RAG 없이)"""
        try:
            # 대화 이력 포함 프롬프트 구성
            history_text = ""
            if chat_history:
                history_parts = []
                for exchange in chat_history[-3:]:
                    history_parts.append(f"사용자: {exchange['user_message']}")
                    history_parts.append(f"AI: {exchange['ai_response']}")
                history_text = "\n".join(history_parts)
            
            prompt = f"""이전 대화를 참고하여 사용자의 질문에 도움이 되는 답변을 제공해주세요.

=== 대화 이력 ===
{history_text}

=== 현재 질문 ===
{message}

한국어로 자연스럽고 친근하게 답변해주세요. 이전 대화 맥락을 고려하여 일관성 있는 답변을 제공하세요.

답변:"""
            
            # AI 서비스를 통한 답변 생성
            ai_response = await ai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                provider=provider
            )
            
            return {
                "response": ai_response.get("response", "죄송합니다. 답변을 생성할 수 없습니다."),
                "provider": ai_response.get("provider", provider or "default"),
                "references": [],
                "context_info": {"type": "general", "use_rag": False}
            }
            
        except Exception as e:
            logger.error(f"일반 답변 생성 실패: {str(e)}")
            return {
                "response": "죄송합니다. 현재 답변을 생성할 수 없습니다. 잠시 후 다시 시도해주세요.",
                "provider": "fallback",
                "references": [],
                "context_info": {"type": "error", "error": str(e)}
            }

    # =========================================================================
    # 📊 5. 세션 관리 API
    # =========================================================================
    
    async def get_session_history(
        self,
        session_id: str,
        user_emp_no: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """세션 히스토리 전체 조회"""
        try:
            async with self.async_session_local() as session:
                # 세션 유효성 확인
                if not await self._validate_session(session, session_id, user_emp_no):
                    return {
                        "session_id": session_id,
                        "messages": [],
                        "message": "유효하지 않은 세션입니다"
                    }
                
                # 전체 히스토리 조회
                history = await self._get_chat_history(session, session_id, limit)
                
                return {
                    "session_id": session_id,
                    "messages": history,
                    "total_count": len(history)
                }
                
        except Exception as e:
            logger.error(f"세션 히스토리 조회 실패: {str(e)}")
            raise

    async def clear_session(self, session_id: str, user_emp_no: str) -> bool:
        """세션 초기화"""
        try:
            async with self.async_session_local() as session:
                query = text("""
                    DELETE FROM tb_chat_history
                    WHERE session_id = :session_id AND user_emp_no = :user_emp_no
                """)
                
                await session.execute(query, {
                    "session_id": session_id,
                    "user_emp_no": user_emp_no
                })
                
                logger.info(f"세션 초기화 완료: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"세션 초기화 실패: {str(e)}")
            return False


# 싱글톤 인스턴스 생성
unified_chat_service = UnifiedChatService()
