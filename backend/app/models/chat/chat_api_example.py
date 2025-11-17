"""
WKMS Redis 기반 실시간 채팅 API 예제
FastAPI에서 Redis 채팅 기능을 사용하는 방법을 보여주는 예제
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer
from typing import List, Optional
from datetime import datetime
import json

from app.models.chat import (
    RedisChatManager, 
    get_redis_client,
    RedisChatSession,
    RedisChatMessage,
    ChatSessionStatus,
    MessageType
)

# 라우터 설정
chat_router = APIRouter(prefix="/api/v1/chat", tags=["실시간 채팅"])
security = HTTPBearer()

# Redis 채팅 매니저 의존성
def get_chat_manager() -> RedisChatManager:
    """Redis 채팅 매니저 의존성 주입"""
    redis_client = get_redis_client()
    return RedisChatManager(redis_client)


# === REST API 엔드포인트 ===

@chat_router.post("/sessions", response_model=dict)
async def create_chat_session(
    user_emp_no: str,
    user_name: str,
    department: str,
    knowledge_container_id: Optional[str] = None,
    chat_manager: RedisChatManager = Depends(get_chat_manager)
):
    """새 채팅 세션 생성"""
    try:
        session = await chat_manager.create_chat_session(
            user_emp_no=user_emp_no,
            user_name=user_name,
            department=department,
            knowledge_container_id=knowledge_container_id
        )
        
        return {
            "success": True,
            "session_id": session.session_id,
            "message": "채팅 세션이 생성되었습니다."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 생성 실패: {str(e)}")


@chat_router.get("/sessions/{session_id}", response_model=dict)
async def get_chat_session(
    session_id: str,
    chat_manager: RedisChatManager = Depends(get_chat_manager)
):
    """채팅 세션 조회"""
    session = await chat_manager.get_chat_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    return {
        "session_id": session.session_id,
        "user_emp_no": session.user_emp_no,
        "user_name": session.user_name,
        "status": session.status.value,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat()
    }


@chat_router.get("/sessions/{session_id}/messages", response_model=List[dict])
async def get_recent_messages(
    session_id: str,
    limit: int = 20,
    chat_manager: RedisChatManager = Depends(get_chat_manager)
):
    """최근 메시지 조회"""
    messages = await chat_manager.get_recent_messages(session_id, limit)
    
    return [
        {
            "message_id": msg.message_id,
            "message_type": msg.message_type.value,
            "content": msg.content,
            "user_name": msg.user_name,
            "timestamp": msg.timestamp.isoformat(),
            "sequence_number": msg.sequence_number,
            "model_used": msg.model_used,
            "response_time_ms": msg.response_time_ms
        }
        for msg in messages
    ]


@chat_router.post("/sessions/{session_id}/messages", response_model=dict)
async def send_message(
    session_id: str,
    content: str,
    user_emp_no: str,
    user_name: str,
    message_type: str = "user",
    chat_manager: RedisChatManager = Depends(get_chat_manager)
):
    """메시지 전송"""
    try:
        # 세션 존재 확인
        session = await chat_manager.get_chat_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        # 메시지 추가
        message = await chat_manager.add_message(
            session_id=session_id,
            content=content,
            message_type=MessageType(message_type),
            user_emp_no=user_emp_no,
            user_name=user_name
        )
        
        return {
            "success": True,
            "message_id": message.message_id,
            "sequence_number": message.sequence_number,
            "timestamp": message.timestamp.isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메시지 전송 실패: {str(e)}")


@chat_router.post("/sessions/{session_id}/typing", response_model=dict)
async def set_typing_indicator(
    session_id: str,
    user_emp_no: str,
    user_name: str,
    is_typing: bool = True,
    chat_manager: RedisChatManager = Depends(get_chat_manager)
):
    """타이핑 표시기 설정"""
    try:
        await chat_manager.set_typing_indicator(
            session_id=session_id,
            user_emp_no=user_emp_no,
            user_name=user_name,
            is_typing=is_typing
        )
        
        return {
            "success": True,
            "message": f"타이핑 표시기가 {'설정' if is_typing else '해제'}되었습니다."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"타이핑 표시기 설정 실패: {str(e)}")


@chat_router.get("/sessions/{session_id}/typing", response_model=List[dict])
async def get_typing_users(
    session_id: str,
    chat_manager: RedisChatManager = Depends(get_chat_manager)
):
    """타이핑 중인 사용자 조회"""
    typing_users = await chat_manager.get_typing_users(session_id)
    
    return [
        {
            "user_emp_no": user.user_emp_no,
            "user_name": user.user_name,
            "started_at": user.started_at.isoformat()
        }
        for user in typing_users
    ]


@chat_router.delete("/sessions/{session_id}", response_model=dict)
async def close_chat_session(
    session_id: str,
    chat_manager: RedisChatManager = Depends(get_chat_manager)
):
    """채팅 세션 종료"""
    success = await chat_manager.close_chat_session(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    return {
        "success": True,
        "message": "채팅 세션이 종료되었습니다."
    }


# === WebSocket 엔드포인트 ===

@chat_router.websocket("/ws/{session_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_emp_no: str,
    user_name: str
):
    """WebSocket 채팅 연결"""
    chat_manager = get_chat_manager()
    
    await websocket.accept()
    
    try:
        # 세션 존재 확인
        session = await chat_manager.get_chat_session(session_id)
        if not session:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "세션을 찾을 수 없습니다."
            }))
            await websocket.close()
            return
        
        # WebSocket 연결 등록
        await chat_manager.register_websocket(session_id, user_emp_no, websocket)
        
        # 연결 성공 메시지
        await websocket.send_text(json.dumps({
            "type": "connected",
            "session_id": session_id,
            "message": "채팅에 연결되었습니다."
        }))
        
        # 최근 메시지 전송
        recent_messages = await chat_manager.get_recent_messages(session_id, 10)
        for message in recent_messages:
            await websocket.send_text(json.dumps({
                "type": "message",
                "message_id": message.message_id,
                "content": message.content,
                "user_name": message.user_name,
                "message_type": message.message_type.value,
                "timestamp": message.timestamp.isoformat()
            }))
        
        # 메시지 수신 루프
        while True:
            try:
                # 클라이언트로부터 메시지 수신
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                message_type = message_data.get("type")
                
                if message_type == "message":
                    # 채팅 메시지 처리
                    content = message_data.get("content", "")
                    
                    # Redis에 메시지 저장
                    new_message = await chat_manager.add_message(
                        session_id=session_id,
                        content=content,
                        message_type=MessageType.USER,
                        user_emp_no=user_emp_no,
                        user_name=user_name
                    )
                    
                    # 모든 연결된 클라이언트에게 브로드캐스트
                    broadcast_data = {
                        "type": "message",
                        "message_id": new_message.message_id,
                        "content": new_message.content,
                        "user_name": new_message.user_name,
                        "message_type": new_message.message_type.value,
                        "timestamp": new_message.timestamp.isoformat(),
                        "sequence_number": new_message.sequence_number
                    }
                    
                    # 현재는 발신자에게만 에코
                    await websocket.send_text(json.dumps(broadcast_data))
                
                elif message_type == "typing":
                    # 타이핑 표시기 처리
                    is_typing = message_data.get("is_typing", False)
                    
                    await chat_manager.set_typing_indicator(
                        session_id=session_id,
                        user_emp_no=user_emp_no,
                        user_name=user_name,
                        is_typing=is_typing
                    )
                    
                    # 타이핑 상태 브로드캐스트 (현재는 발신자에게만)
                    await websocket.send_text(json.dumps({
                        "type": "typing",
                        "user_name": user_name,
                        "is_typing": is_typing
                    }))
                
                elif message_type == "ping":
                    # 연결 상태 확인
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
            
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "잘못된 메시지 형식입니다."
                }))
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"메시지 처리 중 오류가 발생했습니다: {str(e)}"
                }))
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"연결 중 오류가 발생했습니다: {str(e)}"
            }))
        except:
            pass
    
    finally:
        # WebSocket 연결 해제
        try:
            await chat_manager.unregister_websocket("", user_emp_no)
        except:
            pass


# === 관리자 API ===

@chat_router.get("/admin/stats", response_model=dict)
async def get_chat_stats(
    chat_manager: RedisChatManager = Depends(get_chat_manager)
):
    """채팅 통계 조회"""
    active_sessions = await chat_manager.get_active_sessions_count()
    
    return {
        "active_sessions": active_sessions,
        "timestamp": datetime.now().isoformat()
    }


@chat_router.post("/admin/cleanup", response_model=dict)
async def cleanup_expired_sessions(
    chat_manager: RedisChatManager = Depends(get_chat_manager)
):
    """만료된 세션 정리"""
    expired_count = await chat_manager.cleanup_expired_sessions()
    
    return {
        "success": True,
        "expired_sessions_cleaned": expired_count,
        "message": f"{expired_count}개의 만료된 세션이 정리되었습니다."
    }
