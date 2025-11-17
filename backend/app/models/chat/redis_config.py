"""
WKMS Redis 연결 설정 및 관리
실시간 채팅을 위한 Redis 클라이언트 설정
"""
import os
from typing import Optional
from functools import lru_cache

# Redis 설정
class RedisConfig:
    """Redis 연결 설정"""
    
    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.password = os.getenv("REDIS_PASSWORD", None)
        self.db = int(os.getenv("REDIS_DB", 0))
        self.decode_responses = True
        self.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", 20))
        
        # SSL 설정 (선택적)
        self.ssl = os.getenv("REDIS_SSL", "false").lower() == "true"
        self.ssl_cert_reqs = None
        
        # 연결 타임아웃
        self.socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT", 5.0))
        self.socket_connect_timeout = float(os.getenv("REDIS_CONNECT_TIMEOUT", 5.0))
    
    @property
    def url(self) -> str:
        """Redis 연결 URL 생성"""
        protocol = "rediss" if self.ssl else "redis"
        auth = f":{self.password}@" if self.password else ""
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"


@lru_cache()
def get_redis_config() -> RedisConfig:
    """Redis 설정 싱글톤"""
    return RedisConfig()


# Redis 클라이언트 인터페이스 (의존성 주입용)
class RedisClientInterface:
    """Redis 클라이언트 인터페이스 (타입 힌트용)"""
    
    async def get(self, key: str) -> Optional[str]:
        """키 값 조회"""
        pass
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """키 값 설정"""
        pass
    
    async def setex(self, key: str, time: int, value: str) -> bool:
        """TTL과 함께 키 값 설정"""
        pass
    
    async def delete(self, *keys: str) -> int:
        """키 삭제"""
        pass
    
    async def exists(self, key: str) -> bool:
        """키 존재 확인"""
        pass
    
    async def expire(self, key: str, time: int) -> bool:
        """키 TTL 설정"""
        pass
    
    async def incr(self, key: str) -> int:
        """숫자 값 증가"""
        pass
    
    async def sadd(self, key: str, *values: str) -> int:
        """Set에 값 추가"""
        pass
    
    async def srem(self, key: str, *values: str) -> int:
        """Set에서 값 제거"""
        pass
    
    async def smembers(self, key: str) -> set:
        """Set 멤버 조회"""
        pass
    
    async def scard(self, key: str) -> int:
        """Set 크기 조회"""
        pass
    
    async def zadd(self, key: str, mapping: dict) -> int:
        """Sorted Set에 값 추가"""
        pass
    
    async def zrangebyscore(self, key: str, min_score: float, max_score: float) -> list:
        """Sorted Set 점수 범위로 조회"""
        pass
    
    async def lpush(self, key: str, *values: str) -> int:
        """List 앞에 값 추가"""
        pass
    
    async def lrange(self, key: str, start: int, end: int) -> list:
        """List 범위 조회"""
        pass
    
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """List 범위 외 제거"""
        pass
    
    async def keys(self, pattern: str) -> list:
        """패턴으로 키 검색"""
        pass


# 더미 Redis 클라이언트 (개발용)
class DummyRedisClient(RedisClientInterface):
    """Redis가 없을 때 사용하는 더미 클라이언트"""
    
    def __init__(self):
        self._data = {}
        self._sets = {}
        self._lists = {}
        self._sorted_sets = {}
    
    async def get(self, key: str) -> Optional[str]:
        return self._data.get(key)
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self._data[key] = value
        return True
    
    async def setex(self, key: str, time: int, value: str) -> bool:
        self._data[key] = value
        return True
    
    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
        return count
    
    async def exists(self, key: str) -> bool:
        return key in self._data
    
    async def expire(self, key: str, time: int) -> bool:
        return True
    
    async def incr(self, key: str) -> int:
        current = int(self._data.get(key, 0))
        current += 1
        self._data[key] = str(current)
        return current
    
    async def sadd(self, key: str, *values: str) -> int:
        if key not in self._sets:
            self._sets[key] = set()
        count = 0
        for value in values:
            if value not in self._sets[key]:
                self._sets[key].add(value)
                count += 1
        return count
    
    async def srem(self, key: str, *values: str) -> int:
        if key not in self._sets:
            return 0
        count = 0
        for value in values:
            if value in self._sets[key]:
                self._sets[key].remove(value)
                count += 1
        return count
    
    async def smembers(self, key: str) -> set:
        return self._sets.get(key, set())
    
    async def scard(self, key: str) -> int:
        return len(self._sets.get(key, set()))
    
    async def zadd(self, key: str, mapping: dict) -> int:
        if key not in self._sorted_sets:
            self._sorted_sets[key] = {}
        count = 0
        for member, score in mapping.items():
            if member not in self._sorted_sets[key]:
                count += 1
            self._sorted_sets[key][member] = score
        return count
    
    async def zrangebyscore(self, key: str, min_score: float, max_score: float) -> list:
        if key not in self._sorted_sets:
            return []
        
        result = []
        for member, score in self._sorted_sets[key].items():
            if min_score <= score <= max_score:
                result.append(member)
        
        # 점수 순으로 정렬
        return sorted(result, key=lambda x: self._sorted_sets[key][x])
    
    async def lpush(self, key: str, *values: str) -> int:
        if key not in self._lists:
            self._lists[key] = []
        
        for value in reversed(values):
            self._lists[key].insert(0, value)
        
        return len(self._lists[key])
    
    async def lrange(self, key: str, start: int, end: int) -> list:
        if key not in self._lists:
            return []
        
        return self._lists[key][start:end+1 if end != -1 else None]
    
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        if key not in self._lists:
            return False
        
        self._lists[key] = self._lists[key][start:end+1 if end != -1 else None]
        return True
    
    async def keys(self, pattern: str) -> list:
        # 간단한 패턴 매칭 (와일드카드 * 지원)
        import fnmatch
        all_keys = list(self._data.keys()) + list(self._sets.keys()) + \
                  list(self._lists.keys()) + list(self._sorted_sets.keys())
        
        return [key for key in all_keys if fnmatch.fnmatch(key, pattern)]


# Redis 클라이언트 팩토리
redis_client: Optional[RedisClientInterface] = None

def get_redis_client() -> RedisClientInterface:
    """Redis 클라이언트 반환 (의존성 주입용)"""
    global redis_client
    
    if redis_client is None:
        # 실제 환경에서는 Redis 연결을 시도하고, 실패하면 더미 클라이언트 사용
        try:
            # 실제 Redis 연결 시도
            config = get_redis_config()
            print(f"🔍 Redis 연결 시도: {config.url}")
            
            # redis 라이브러리 사용 (aioredis 대신)
            import redis
            sync_client = redis.from_url(
                config.url,
                decode_responses=True,
                socket_timeout=config.socket_timeout,
                socket_connect_timeout=config.socket_connect_timeout
            )
            # 연결 테스트
            sync_client.ping()
            print("✅ Redis 연결 성공")
            
            # 비동기 래퍼 생성
            class AsyncRedisWrapper(RedisClientInterface):
                def __init__(self, sync_client):
                    self._client = sync_client
                
                async def get(self, key: str) -> Optional[str]:
                    return self._client.get(key)
                
                async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
                    return self._client.set(key, value, ex=ex)
                
                async def setex(self, key: str, time: int, value: str) -> bool:
                    return self._client.setex(key, time, value)
                
                async def delete(self, *keys: str) -> int:
                    return self._client.delete(*keys)
                
                async def exists(self, key: str) -> bool:
                    return bool(self._client.exists(key))
                
                async def expire(self, key: str, time: int) -> bool:
                    return bool(self._client.expire(key, time))
                
                async def incr(self, key: str) -> int:
                    return self._client.incr(key)
                
                async def sadd(self, key: str, *values: str) -> int:
                    return self._client.sadd(key, *values)
                
                async def srem(self, key: str, *values: str) -> int:
                    return self._client.srem(key, *values)
                
                async def smembers(self, key: str) -> set:
                    return self._client.smembers(key)
                
                async def scard(self, key: str) -> int:
                    return self._client.scard(key)
                
                async def zadd(self, key: str, mapping: dict) -> int:
                    return self._client.zadd(key, mapping)
                
                async def zrangebyscore(self, key: str, min_score: float, max_score: float) -> list:
                    return self._client.zrangebyscore(key, min_score, max_score)
                
                async def lpush(self, key: str, *values: str) -> int:
                    return self._client.lpush(key, *values)
                
                async def lrange(self, key: str, start: int, end: int) -> list:
                    return self._client.lrange(key, start, end)
                
                async def ltrim(self, key: str, start: int, end: int) -> bool:
                    return self._client.ltrim(key, start, end)
                
                async def keys(self, pattern: str) -> list:
                    return self._client.keys(pattern)
            
            redis_client = AsyncRedisWrapper(sync_client)
        except Exception as e:
            print(f"⚠️ Redis 연결 실패, 더미 클라이언트 사용: {e}")
            print(f"🔍 오류 타입: {type(e)}")
            import traceback
            print(f"🔍 스택 트레이스: {traceback.format_exc()}")
            redis_client = DummyRedisClient()
    
    return redis_client

def set_redis_client(client: RedisClientInterface) -> None:
    """Redis 클라이언트 설정 (테스트용)"""
    global redis_client
    redis_client = client
