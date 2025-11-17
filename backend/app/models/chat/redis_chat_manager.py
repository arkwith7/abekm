"""
WKMS Redis 기반 실시간 채팅 매니저
채팅 세션, 메시지, 타이핑 표시기 등 실시간 채팅 기능 관리
"""
import json
import asyncio
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from .redis_config import RedisClientInterface
from .redis_schemas import (
    RedisChatSession, RedisChatMessage, RedisTypingIndicator, RedisChatRoomInfo,
    ChatSessionStatus, MessageType, RedisKeyPatterns, RedisChatTTL
)

logger = logging.getLogger(__name__)


class RedisChatManager:
    """Redis 기반 실시간 채팅 매니저"""
    
    def __init__(self, redis_client: RedisClientInterface):
        self.redis = redis_client
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_sessions: Dict[str, Set[str]] = {}  # user_emp_no -> session_ids
        
    # === 채팅 세션 관리 ===
    
    async def create_chat_session(
        self,
        user_emp_no: str,
        user_name: str,
        department: str,
        knowledge_container_id: Optional[str] = None,
        accessible_containers: Optional[List[str]] = None,
        websocket_id: Optional[str] = None,
        session_id: Optional[str] = None  # 기존 세션 ID 유지 옵션
    ) -> RedisChatSession:
        """새 채팅 세션 생성"""
        session_id = session_id or f"chat_{uuid.uuid4().hex[:12]}"
        now = datetime.now()
        
        session = RedisChatSession(
            session_id=session_id,
            user_emp_no=user_emp_no,
            user_name=user_name,
            department=department,
            status=ChatSessionStatus.ACTIVE,
            last_activity=now,
            created_at=now,
            expires_at=now + timedelta(hours=24),
            user_permission_level="internal",  # DB에서 조회해서 설정
            knowledge_container_id=knowledge_container_id,
            accessible_containers=accessible_containers or [],
            websocket_id=websocket_id
        )
        
        # Redis에 세션 저장
        session_key = RedisKeyPatterns.CHAT_SESSION.format(session_id=session_id)
        await self.redis.setex(
            session_key,
            RedisChatTTL.CHAT_SESSION,
            json.dumps(session.to_dict())
        )
        
        # 사용자별 세션 목록에 추가
        user_sessions_key = RedisKeyPatterns.USER_SESSIONS.format(user_emp_no=user_emp_no)
        await self.redis.sadd(user_sessions_key, session_id)
        await self.redis.expire(user_sessions_key, RedisChatTTL.CHAT_SESSION)
        
        # 활성 세션 목록에 추가
        await self.redis.sadd(RedisKeyPatterns.ACTIVE_SESSIONS, session_id)
        
        # 메시지 시퀀스 번호 초기화
        sequence_key = RedisKeyPatterns.MESSAGE_SEQUENCE.format(session_id=session_id)
        await self.redis.set(sequence_key, 0, ex=RedisChatTTL.CHAT_SESSION)
        
        return session
    
    async def get_chat_session(self, session_id: str) -> Optional[RedisChatSession]:
        """채팅 세션 조회"""
        session_key = RedisKeyPatterns.CHAT_SESSION.format(session_id=session_id)
        session_data = await self.redis.get(session_key)
        
        if session_data:
            data = json.loads(session_data)
            return RedisChatSession.from_dict(data)
        return None
    
    async def update_session_activity(self, session_id: str) -> bool:
        """세션 마지막 활동 시간 업데이트"""
        session = await self.get_chat_session(session_id)
        if not session:
            return False
        
        session.last_activity = datetime.now()
        session.status = ChatSessionStatus.ACTIVE
        
        session_key = RedisKeyPatterns.CHAT_SESSION.format(session_id=session_id)
        await self.redis.setex(
            session_key,
            RedisChatTTL.CHAT_SESSION,
            json.dumps(session.to_dict())
        )
        return True
    
    async def close_chat_session(self, session_id: str) -> bool:
        """채팅 세션 완전 종료 및 정리"""
        session = await self.get_chat_session(session_id)
        if not session:
            logger.warning(f"⚠️ 종료할 세션을 찾을 수 없음: {session_id}")
            return False
        
        try:
            # 1. 메시지 목록 완전 삭제
            messages_key = RedisKeyPatterns.RECENT_MESSAGES.format(session_id=session_id)
            await self.redis.delete(messages_key)
            logger.info(f"✅ 메시지 목록 삭제: {messages_key}")
            
            # 2. 세션 정보 삭제
            session_key = RedisKeyPatterns.CHAT_SESSION.format(session_id=session_id)
            await self.redis.delete(session_key)
            logger.info(f"✅ 세션 정보 삭제: {session_key}")
            
            # 3. 활성 세션 목록에서 제거
            await self.redis.srem(RedisKeyPatterns.ACTIVE_SESSIONS, session_id)
            logger.info(f"✅ 활성 세션 목록에서 제거: {session_id}")
            
            # 4. 타이핑 표시기 정리
            await self.clear_typing_indicators(session_id)
            
            # 5. 기타 관련 키들 정리
            context_key = RedisKeyPatterns.CONVERSATION_CONTEXT.format(session_id=session_id)
            await self.redis.delete(context_key)
            
            logger.info(f"✅ 세션 완전 삭제 완료: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 세션 삭제 중 오류: {e}")
            return False
    
    # === 메시지 관리 ===
    
    async def add_message(
        self,
        session_id: str,
        content: str,
        message_type: MessageType,
        user_emp_no: str,
        user_name: str,
        model_used: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        search_context: Optional[Dict[str, Any]] = None,
        referenced_documents: Optional[List[int]] = None
    ) -> RedisChatMessage:
        """채팅 메시지 추가"""
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        # 시퀀스 번호 증가
        sequence_key = RedisKeyPatterns.MESSAGE_SEQUENCE.format(session_id=session_id)
        sequence_number = await self.redis.incr(sequence_key)
        
        message = RedisChatMessage(
            message_id=message_id,
            session_id=session_id,
            message_type=message_type,
            content=content,
            user_emp_no=user_emp_no,
            user_name=user_name,
            timestamp=datetime.now(),
            sequence_number=sequence_number,
            model_used=model_used,
            response_time_ms=response_time_ms,
            search_context=search_context,
            referenced_documents=referenced_documents
        )
        
        # 세션 메시지 리스트에 추가 (Sorted Set 사용, 시퀀스 번호로 정렬)
        messages_key = RedisKeyPatterns.CHAT_MESSAGES.format(session_id=session_id)
        await self.redis.zadd(
            messages_key,
            {json.dumps(message.to_dict()): sequence_number}
        )
        await self.redis.expire(messages_key, RedisChatTTL.CHAT_SESSION)
        
        # 최근 메시지 캐시 (빠른 조회용)
        recent_key = RedisKeyPatterns.RECENT_MESSAGES.format(session_id=session_id)
        await self.redis.lpush(recent_key, json.dumps(message.to_dict()))
        await self.redis.ltrim(recent_key, 0, 50)  # 최근 50개만 유지
        await self.redis.expire(recent_key, RedisChatTTL.RECENT_MESSAGES)
        
        # 세션 활동 시간 업데이트
        await self.update_session_activity(session_id)
        
        return message
    
    async def get_recent_messages(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[RedisChatMessage]:
        """최근 메시지 조회"""
        recent_key = RedisKeyPatterns.RECENT_MESSAGES.format(session_id=session_id)
        message_data_list = await self.redis.lrange(recent_key, 0, limit - 1)
        
        messages = []
        for message_data in reversed(message_data_list):  # 시간순 정렬
            data = json.loads(message_data)
            messages.append(RedisChatMessage.from_dict(data))
        
        return messages
    
    async def get_messages_range(
        self,
        session_id: str,
        start_sequence: int = 0,
        end_sequence: int = -1
    ) -> List[RedisChatMessage]:
        """시퀀스 범위로 메시지 조회"""
        messages_key = RedisKeyPatterns.CHAT_MESSAGES.format(session_id=session_id)
        message_data_list = await self.redis.zrangebyscore(
            messages_key, start_sequence, end_sequence
        )
        
        messages = []
        for message_data in message_data_list:
            data = json.loads(message_data)
            messages.append(RedisChatMessage.from_dict(data))
        
        return messages
    
    # === 타이핑 표시기 관리 ===
    
    async def set_typing_indicator(
        self,
        session_id: str,
        user_emp_no: str,
        user_name: str,
        is_typing: bool = True
    ) -> None:
        """타이핑 표시기 설정"""
        now = datetime.now()
        indicator = RedisTypingIndicator(
            session_id=session_id,
            user_emp_no=user_emp_no,
            user_name=user_name,
            is_typing=is_typing,
            started_at=now,
            expires_at=now + timedelta(seconds=RedisChatTTL.TYPING_INDICATOR)
        )
        
        typing_key = RedisKeyPatterns.TYPING_INDICATOR.format(
            session_id=session_id,
            user_emp_no=user_emp_no
        )
        
        if is_typing:
            await self.redis.setex(
                typing_key,
                RedisChatTTL.TYPING_INDICATOR,
                json.dumps(indicator.to_dict())
            )
        else:
            await self.redis.delete(typing_key)
    
    async def get_typing_users(self, session_id: str) -> List[RedisTypingIndicator]:
        """세션의 타이핑 중인 사용자 조회"""
        pattern = RedisKeyPatterns.TYPING_INDICATOR.format(
            session_id=session_id,
            user_emp_no="*"
        )
        
        keys = await self.redis.keys(pattern)
        typing_users = []
        
        for key in keys:
            data = await self.redis.get(key)
            if data:
                indicator_data = json.loads(data)
                typing_users.append(RedisTypingIndicator.from_dict(indicator_data))
        
        return typing_users
    
    async def clear_typing_indicators(self, session_id: str) -> None:
        """세션의 모든 타이핑 표시기 제거"""
        pattern = RedisKeyPatterns.TYPING_INDICATOR.format(
            session_id=session_id,
            user_emp_no="*"
        )
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
    
    # === 검색 컨텍스트 관리 ===
    
    async def set_search_context(
        self,
        session_id: str,
        search_results: List[Dict[str, Any]],
        search_query: str,
        total_results: int
    ) -> None:
        """검색 컨텍스트 임시 저장"""
        context = {
            "search_query": search_query,
            "search_results": search_results,
            "total_results": total_results,
            "timestamp": datetime.now().isoformat()
        }
        
        context_key = RedisKeyPatterns.TEMP_SEARCH_CONTEXT.format(session_id=session_id)
        await self.redis.setex(
            context_key,
            RedisChatTTL.SEARCH_CONTEXT,
            json.dumps(context)
        )
    
    async def get_search_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """검색 컨텍스트 조회"""
        context_key = RedisKeyPatterns.TEMP_SEARCH_CONTEXT.format(session_id=session_id)
        context_data = await self.redis.get(context_key)
        
        if context_data:
            return json.loads(context_data)
        return None
    
    # === 대화 컨텍스트 관리 ===
    
    async def update_conversation_context(
        self,
        session_id: str,
        context_summary: str,
        relevant_documents: List[int],
        conversation_depth: int
    ) -> None:
        """대화 컨텍스트 업데이트"""
        context = {
            "context_summary": context_summary,
            "relevant_documents": relevant_documents,
            "conversation_depth": conversation_depth,
            "last_updated": datetime.now().isoformat()
        }
        
        context_key = RedisKeyPatterns.CONVERSATION_CONTEXT.format(session_id=session_id)
        await self.redis.setex(
            context_key,
            RedisChatTTL.CONVERSATION_CONTEXT,
            json.dumps(context)
        )
    
    async def get_conversation_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """대화 컨텍스트 조회"""
        context_key = RedisKeyPatterns.CONVERSATION_CONTEXT.format(session_id=session_id)
        context_data = await self.redis.get(context_key)
        
        if context_data:
            return json.loads(context_data)
        return None
    
    # === WebSocket 연결 관리 ===
    
    async def register_websocket(
        self,
        session_id: str,
        user_emp_no: str,
        websocket: WebSocket
    ) -> None:
        """WebSocket 연결 등록"""
        connection_id = f"ws_{uuid.uuid4().hex[:8]}"
        self.active_connections[connection_id] = websocket
        
        # 사용자별 연결 정보 저장
        user_conn_key = RedisKeyPatterns.USER_CONNECTIONS.format(user_emp_no=user_emp_no)
        connection_info = {
            "connection_id": connection_id,
            "session_id": session_id,
            "connected_at": datetime.now().isoformat()
        }
        await self.redis.setex(
            user_conn_key,
            RedisChatTTL.WEBSOCKET_CONNECTION,
            json.dumps(connection_info)
        )
    
    async def unregister_websocket(self, connection_id: str, user_emp_no: str) -> None:
        """WebSocket 연결 해제"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        # Redis에서 연결 정보 제거
        user_conn_key = RedisKeyPatterns.USER_CONNECTIONS.format(user_emp_no=user_emp_no)
        await self.redis.delete(user_conn_key)
    
    async def broadcast_to_session(
        self,
        session_id: str,
        message: Dict[str, Any],
        exclude_user: Optional[str] = None
    ) -> None:
        """세션의 모든 연결된 사용자에게 메시지 브로드캐스트"""
        # 실제 구현에서는 Redis Pub/Sub이나 WebSocket 매니저를 통해 처리
        pass
    
    # === 통계 및 모니터링 ===
    
    async def get_active_sessions_count(self) -> int:
        """활성 세션 수 조회"""
        return await self.redis.scard(RedisKeyPatterns.ACTIVE_SESSIONS)
    
    async def get_user_active_sessions(self, user_emp_no: str) -> List[str]:
        """사용자의 활성 세션 목록 조회"""
        user_sessions_key = RedisKeyPatterns.USER_SESSIONS.format(user_emp_no=user_emp_no)
        return await self.redis.smembers(user_sessions_key)
    
    async def cleanup_expired_sessions(self) -> int:
        """만료된 세션 정리"""
        try:
            # 활성 세션 목록 조회
            active_sessions = await self.redis.smembers(RedisKeyPatterns.ACTIVE_SESSIONS)
            cleaned_count = 0
            
            for session_id in active_sessions:
                session = await self.get_chat_session(session_id)
                if session and session.expires_at < datetime.now():
                    await self.close_chat_session(session_id)
                    cleaned_count += 1
            
            return cleaned_count
        except Exception as e:
            logger.error(f"만료된 세션 정리 실패: {e}")
            return 0

    # === Redis → RDB 영구 저장 ===
    
    async def archive_session_to_rdb(
        self, 
        session_id: str, 
        db: AsyncSession
    ) -> bool:
        """Redis 세션을 RDB에 영구 저장"""
        try:
            logger.info(f"🔍 RDB 아카이브 시작: 세션 {session_id}")
            
            # Redis에서 세션 정보 조회
            try:
                session = await self.get_chat_session(session_id)
                if not session:
                    logger.warning(f"⚠️ 세션을 찾을 수 없음: {session_id}")
                    return False
                
                logger.info(f"✅ 세션 조회 성공: {session.session_id}, 사용자: {session.user_emp_no}")
            except Exception as session_error:
                logger.warning(f"⚠️ 세션 조회 실패: {session_error}")
                return False
            
            # Redis에서 메시지 목록 조회
            try:
                messages = await self.get_recent_messages(session_id, limit=1000)
                if not messages:
                    logger.warning(f"⚠️ 메시지를 찾을 수 없음: {session_id}")
                    return False
                
                logger.info(f"✅ 메시지 조회 성공: {len(messages)}개 메시지")
            except Exception as message_error:
                logger.warning(f"⚠️ 메시지 조회 실패: {message_error}")
                return False
            
            # RDB에 세션 저장
            try:
                session_query = text("""
                    INSERT INTO tb_chat_sessions (
                        session_id, user_emp_no, session_name, message_count,
                        max_messages, session_timeout_minutes, is_active, last_activity, 
                        created_date, last_modified_date
                    ) VALUES (
                        :session_id, :user_emp_no, :session_name, :message_count,
                        :max_messages, :session_timeout_minutes, false, :last_activity, 
                        :created_at, :last_activity
                    ) ON CONFLICT (session_id) DO UPDATE SET
                        message_count = :message_count,
                        last_activity = :last_activity,
                        last_modified_date = :last_activity,
                        is_active = false
                """)
                
                # 세션 제목 생성 (첫 번째 사용자 메시지에서)
                session_title = "대화"
                for msg in messages:
                    if msg.message_type == MessageType.USER:
                        session_title = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                        break
                
                await db.execute(session_query, {
                    "session_id": session.session_id,
                    "user_emp_no": session.user_emp_no,
                    "session_name": session_title,
                    "message_count": len(messages),
                    "max_messages": 1000,  # 기본값
                    "session_timeout_minutes": 60,  # 기본값
                    "last_activity": session.last_activity,
                    "created_at": session.created_at
                })
                
                logger.info(f"✅ 세션 RDB 저장 완료: {session_id}")
            except Exception as session_save_error:
                logger.error(f"❌ 세션 RDB 저장 실패: {session_save_error}")
                await db.rollback()
                return False
            
            # RDB에 메시지 저장
            try:
                for msg in messages:
                    if msg.message_type in [MessageType.USER, MessageType.ASSISTANT]:
                        # 사용자 메시지와 AI 응답을 적절한 기본값과 함께 저장
                        if msg.message_type == MessageType.USER:
                            message_query = text("""
                                INSERT INTO tb_chat_history (
                                    session_id, user_emp_no, user_message, assistant_response,
                                    model_used, created_date, search_results, referenced_documents
                                ) VALUES (
                                    :session_id, :user_emp_no, :user_message, '',
                                    :model_used, :created_date, :search_results, :referenced_documents
                                )
                            """)
                        elif msg.message_type == MessageType.ASSISTANT:
                            message_query = text("""
                                INSERT INTO tb_chat_history (
                                    session_id, user_emp_no, user_message, assistant_response,
                                    model_used, created_date, search_results, referenced_documents
                                ) VALUES (
                                    :session_id, :user_emp_no, '', :assistant_response,
                                    :model_used, :created_date, :search_results, :referenced_documents
                                )
                            """)
                        else:
                            continue  # 다른 타입의 메시지는 건너뛰기
                        

                        
                        # 메시지 타입에 따라 올바른 파라미터 설정
                        if msg.message_type == MessageType.USER:
                            await db.execute(message_query, {
                                "session_id": msg.session_id,
                                "user_emp_no": msg.user_emp_no,
                                "user_message": msg.content,
                                "model_used": msg.model_used or "default",
                                "created_date": msg.timestamp,
                                "search_results": None,
                                "referenced_documents": None
                            })
                        elif msg.message_type == MessageType.ASSISTANT:
                            # 참고자료 정보 추출
                            search_results = None
                            referenced_documents = None
                            if hasattr(msg, 'search_context') and msg.search_context:
                                search_results = msg.search_context.get('search_results')
                                referenced_documents = msg.search_context.get('referenced_documents')
                            
                            await db.execute(message_query, {
                                "session_id": msg.session_id,
                                "user_emp_no": msg.user_emp_no,
                                "assistant_response": msg.content,
                                "model_used": msg.model_used or "default",
                                "created_date": msg.timestamp,
                                "search_results": search_results,
                                "referenced_documents": referenced_documents
                            })
                
                logger.info(f"✅ 메시지 RDB 저장 완료: {session_id}")
            except Exception as message_save_error:
                logger.error(f"❌ 메시지 RDB 저장 실패: {message_save_error}")
                await db.rollback()
                return False
            
            await db.commit()
            logger.info(f"✅ RDB 저장 완료: 세션 {session_id}")
            
            # Redis에서 세션 삭제 (선택적)
            try:
                await self.close_chat_session(session_id)
                logger.info(f"✅ Redis 세션 삭제 완료: {session_id}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Redis 세션 삭제 실패 (무시): {cleanup_error}")
            
            return True
            
        except Exception as e:
            try:
                await db.rollback()
            except:
                pass
            logger.error(f"❌ 세션 RDB 저장 실패: {e}")
            return False

    async def get_session_for_rdb_archive(self, session_id: str) -> Optional[Dict[str, Any]]:
        """RDB 저장용 세션 데이터 조회"""
        try:
            session = await self.get_chat_session(session_id)
            if not session:
                return None
            
            messages = await self.get_recent_messages(session_id, limit=1000)
            
            return {
                "session": session,
                "messages": messages
            }
        except Exception as e:
            logger.error(f"세션 데이터 조회 실패: {e}")
            return None
