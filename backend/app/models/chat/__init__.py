"""
WKMS 채팅 및 대화 관리 모델 패키지
"""
from .chat_models import (
    TbChatHistory,
    TbChatSessions,
    TbChatFeedback
)

# Redis 기반 실시간 채팅 스키마
from .redis_schemas import (
    RedisChatSession,
    RedisChatMessage,
    RedisTypingIndicator,
    RedisChatRoomInfo,
    ChatSessionStatus,
    MessageType,
    RedisKeyPatterns,
    RedisChatTTL
)

# Redis 연결 및 관리
from .redis_config import (
    RedisConfig,
    RedisClientInterface,
    DummyRedisClient,
    get_redis_config,
    get_redis_client,
    set_redis_client
)

# Redis 채팅 매니저
from .redis_chat_manager import RedisChatManager

__all__ = [
    # PostgreSQL 채팅 모델
    "TbChatHistory",
    "TbChatSessions", 
    "TbChatFeedback",
    
    # Redis 실시간 채팅 스키마
    "RedisChatSession",
    "RedisChatMessage", 
    "RedisTypingIndicator",
    "RedisChatRoomInfo",
    "ChatSessionStatus",
    "MessageType",
    "RedisKeyPatterns",
    "RedisChatTTL",
    
    # Redis 연결 및 설정
    "RedisConfig",
    "RedisClientInterface",
    "DummyRedisClient",
    "get_redis_config",
    "get_redis_client",
    "set_redis_client",
    
    # Redis 채팅 매니저
    "RedisChatManager",
]
