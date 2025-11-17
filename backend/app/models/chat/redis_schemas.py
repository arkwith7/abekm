"""
WKMS Redis 기반 실시간 채팅 스키마
채팅 세션 관리, 임시 메시지 캐싱, 실시간 상태 관리용
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid


class ChatSessionStatus(Enum):
    """채팅 세션 상태"""
    ACTIVE = "active"
    IDLE = "idle"
    TYPING = "typing"
    DISCONNECTED = "disconnected"
    ARCHIVED = "archived"


class MessageType(Enum):
    """메시지 타입"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TYPING_INDICATOR = "typing"
    ERROR = "error"


@dataclass
class RedisChatSession:
    """Redis 채팅 세션 스키마"""
    session_id: str
    user_emp_no: str
    user_name: str
    department: str
    
    # 세션 상태
    status: ChatSessionStatus
    last_activity: datetime
    created_at: datetime
    expires_at: datetime
    
    # 권한 컨텍스트
    user_permission_level: str
    knowledge_container_id: Optional[str] = None
    accessible_containers: List[str] = None
    
    # 채팅 설정
    max_messages: int = 100
    message_retention_hours: int = 24
    auto_archive_hours: int = 72
    
    # 연결 정보
    websocket_id: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Redis 저장용 딕셔너리 변환"""
        data = asdict(self)
        # datetime 객체를 ISO 문자열로 변환
        data['last_activity'] = self.last_activity.isoformat()
        data['created_at'] = self.created_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat()
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RedisChatSession':
        """Redis에서 딕셔너리로부터 객체 생성"""
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        data['status'] = ChatSessionStatus(data['status'])
        return cls(**data)


@dataclass
class RedisChatMessage:
    """Redis 채팅 메시지 스키마"""
    message_id: str
    session_id: str
    message_type: MessageType
    content: str
    
    # 사용자 정보
    user_emp_no: str
    user_name: str
    
    # 메시지 메타데이터
    timestamp: datetime
    sequence_number: int
    
    # AI 응답 관련 (assistant 메시지용)
    model_used: Optional[str] = None
    response_time_ms: Optional[int] = None
    search_context: Optional[Dict[str, Any]] = None
    referenced_documents: Optional[List[int]] = None
    
    # 시스템 메시지 관련
    system_event: Optional[str] = None
    
    # 상태 정보
    is_delivered: bool = True
    is_read: bool = False
    read_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Redis 저장용 딕셔너리 변환"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['message_type'] = self.message_type.value
        if self.read_at:
            data['read_at'] = self.read_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RedisChatMessage':
        """Redis에서 딕셔너리로부터 객체 생성"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['message_type'] = MessageType(data['message_type'])
        if data.get('read_at'):
            data['read_at'] = datetime.fromisoformat(data['read_at'])
        return cls(**data)


@dataclass
class RedisTypingIndicator:
    """Redis 타이핑 표시기 스키마"""
    session_id: str
    user_emp_no: str
    user_name: str
    is_typing: bool
    started_at: datetime
    expires_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Redis 저장용 딕셔너리 변환"""
        return {
            'session_id': self.session_id,
            'user_emp_no': self.user_emp_no,
            'user_name': self.user_name,
            'is_typing': self.is_typing,
            'started_at': self.started_at.isoformat(),
            'expires_at': self.expires_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RedisTypingIndicator':
        """Redis에서 딕셔너리로부터 객체 생성"""
        data['started_at'] = datetime.fromisoformat(data['started_at'])
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        return cls(**data)


@dataclass
class RedisChatRoomInfo:
    """Redis 채팅방 정보 스키마 (다중 사용자 채팅용)"""
    room_id: str
    room_name: str
    room_type: str  # "private", "group", "support"
    
    # 참여자 정보
    participants: List[str]  # user_emp_no 목록
    moderators: List[str]    # 관리자 목록
    
    # 권한 설정
    knowledge_container_id: Optional[str] = None
    access_level: str = "internal"
    
    # 방 설정
    max_participants: int = 10
    message_retention_days: int = 30
    is_archived: bool = False
    
    # 시간 정보
    created_at: datetime = None
    last_activity: datetime = None
    archived_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Redis 저장용 딕셔너리 변환"""
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.last_activity:
            data['last_activity'] = self.last_activity.isoformat()
        if self.archived_at:
            data['archived_at'] = self.archived_at.isoformat()
        return data


class RedisKeyPatterns:
    """Redis 키 패턴 정의"""
    
    # 채팅 세션
    CHAT_SESSION = "wkms:chat:session:{session_id}"
    USER_SESSIONS = "wkms:chat:user:{user_emp_no}:sessions"
    ACTIVE_SESSIONS = "wkms:chat:active_sessions"
    
    # 채팅 메시지
    CHAT_MESSAGES = "wkms:chat:messages:{session_id}"
    MESSAGE_SEQUENCE = "wkms:chat:sequence:{session_id}"
    RECENT_MESSAGES = "wkms:chat:recent:{session_id}"
    
    # 타이핑 표시기
    TYPING_INDICATOR = "wkms:chat:typing:{session_id}:{user_emp_no}"
    SESSION_TYPING = "wkms:chat:typing:{session_id}"
    
    # 채팅방 (다중 사용자)
    CHAT_ROOM = "wkms:chat:room:{room_id}"
    USER_ROOMS = "wkms:chat:user:{user_emp_no}:rooms"
    ROOM_PARTICIPANTS = "wkms:chat:room:{room_id}:participants"
    
    # 연결 관리
    WEBSOCKET_SESSIONS = "wkms:websocket:sessions"
    USER_CONNECTIONS = "wkms:websocket:user:{user_emp_no}"
    
    # 임시 데이터
    TEMP_SEARCH_CONTEXT = "wkms:chat:temp_search:{session_id}"
    CONVERSATION_CONTEXT = "wkms:chat:context:{session_id}"
    
    # 통계 및 모니터링
    CHAT_STATS_DAILY = "wkms:stats:chat:daily:{date}"
    ACTIVE_USERS_COUNT = "wkms:stats:active_users"
    MESSAGE_RATE_LIMIT = "wkms:rate_limit:message:{user_emp_no}"


class RedisChatTTL:
    """Redis TTL 설정"""
    
    # 세션 관련
    CHAT_SESSION = 24 * 60 * 60  # 24시간
    IDLE_SESSION = 2 * 60 * 60   # 2시간
    
    # 메시지 관련
    RECENT_MESSAGES = 6 * 60 * 60  # 6시간
    TEMP_MESSAGES = 30 * 60        # 30분
    
    # 타이핑 표시기
    TYPING_INDICATOR = 10  # 10초
    
    # 검색 컨텍스트
    SEARCH_CONTEXT = 30 * 60  # 30분
    CONVERSATION_CONTEXT = 60 * 60  # 1시간
    
    # 연결 관리
    WEBSOCKET_CONNECTION = 60  # 1분 (heartbeat으로 갱신)
    
    # 통계
    DAILY_STATS = 7 * 24 * 60 * 60  # 7일
    RATE_LIMIT = 60  # 1분
