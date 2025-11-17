"""
🔔 알림 서비스
=============

문서 업로드 및 처리 완료 시 관련 팀원들에게 알림을 전송하는 서비스
- 실시간 알림 (WebSocket)
- 이메일 알림
- 팀 내 알림
- 알림 히스토리 관리
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    """알림 유형"""
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_FAILED = "document_failed"
    TEAM_MENTION = "team_mention"
    SYSTEM_ALERT = "system_alert"

class NotificationPriority(Enum):
    """알림 우선순위"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class NotificationService:
    """알림 관리 서비스"""
    
    def __init__(self):
        self.enabled = True
        self.websocket_enabled = True
        self.email_enabled = False  # 개발 단계에서는 비활성화
        
    async def send_document_upload_notification(
        self,
        document_info: Dict[str, Any],
        uploader_info: Dict[str, Any],
        container_id: str
    ) -> Dict[str, Any]:
        """
        문서 업로드 완료 알림 전송
        
        Args:
            document_info: 업로드된 문서 정보
            uploader_info: 업로더 정보
            container_id: 컨테이너 ID
            
        Returns:
            Dict containing notification results
        """
        try:
            notification_data = {
                "type": NotificationType.DOCUMENT_UPLOADED.value,
                "priority": NotificationPriority.NORMAL.value,
                "title": "📄 새 문서가 업로드되었습니다",
                "message": f"{uploader_info.get('username', '사용자')}님이 '{document_info.get('filename', '문서')}'를 업로드했습니다.",
                "document_id": document_info.get("id"),
                "document_name": document_info.get("filename"),
                "uploader": uploader_info.get("username"),
                "container_id": container_id,
                "timestamp": datetime.now().isoformat(),
                "action_url": f"/documents/{document_info.get('id')}",
                "metadata": {
                    "file_size": document_info.get("file_size"),
                    "file_type": document_info.get("file_extension"),
                    "upload_time": document_info.get("created_at")
                }
            }
            
            # 알림 전송
            results = await self._send_notification(notification_data, container_id)
            
            logger.info(f"문서 업로드 알림 전송 완료 - 문서 ID: {document_info.get('id')}")
            return results
            
        except Exception as e:
            logger.error(f"문서 업로드 알림 전송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_document_processing_complete_notification(
        self,
        document_info: Dict[str, Any],
        processing_results: Dict[str, Any],
        container_id: str
    ) -> Dict[str, Any]:
        """
        문서 처리 완료 알림 전송
        
        Args:
            document_info: 문서 정보
            processing_results: 처리 결과
            container_id: 컨테이너 ID
            
        Returns:
            Dict containing notification results
        """
        try:
            # 처리 결과에 따른 메시지 생성
            success_count = sum(1 for result in processing_results.values() if result.get('success', False))
            total_count = len(processing_results)
            
            if success_count == total_count:
                status_emoji = "✅"
                status_message = "모든 처리가 완료되었습니다"
                priority = NotificationPriority.NORMAL
            elif success_count > 0:
                status_emoji = "⚠️"
                status_message = f"일부 처리가 완료되었습니다 ({success_count}/{total_count})"
                priority = NotificationPriority.HIGH
            else:
                status_emoji = "❌"
                status_message = "처리에 실패했습니다"
                priority = NotificationPriority.HIGH
            
            notification_data = {
                "type": NotificationType.DOCUMENT_PROCESSED.value,
                "priority": priority.value,
                "title": f"{status_emoji} 문서 처리 완료",
                "message": f"'{document_info.get('filename', '문서')}' {status_message}",
                "document_id": document_info.get("id"),
                "document_name": document_info.get("filename"),
                "container_id": container_id,
                "timestamp": datetime.now().isoformat(),
                "action_url": f"/documents/{document_info.get('id')}",
                "metadata": {
                    "processing_results": processing_results,
                    "success_count": success_count,
                    "total_count": total_count,
                    "processing_time": processing_results.get("processing_time")
                }
            }
            
            # 알림 전송
            results = await self._send_notification(notification_data, container_id)
            
            logger.info(f"문서 처리 완료 알림 전송 완료 - 문서 ID: {document_info.get('id')}")
            return results
            
        except Exception as e:
            logger.error(f"문서 처리 완료 알림 전송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_team_notification(
        self,
        message: str,
        container_id: str,
        user_ids: Optional[List[str]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        팀 내 일반 알림 전송
        
        Args:
            message: 알림 메시지
            container_id: 컨테이너 ID
            user_ids: 특정 사용자 ID 목록 (None이면 전체 팀)
            priority: 알림 우선순위
            
        Returns:
            Dict containing notification results
        """
        try:
            notification_data = {
                "type": NotificationType.TEAM_MENTION.value,
                "priority": priority.value,
                "title": "📢 팀 알림",
                "message": message,
                "container_id": container_id,
                "timestamp": datetime.now().isoformat(),
                "target_users": user_ids,
                "metadata": {
                    "is_broadcast": user_ids is None,
                    "target_count": len(user_ids) if user_ids else None
                }
            }
            
            # 알림 전송
            results = await self._send_notification(notification_data, container_id)
            
            logger.info(f"팀 알림 전송 완료 - 컨테이너: {container_id}")
            return results
            
        except Exception as e:
            logger.error(f"팀 알림 전송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_notification(
        self, 
        notification_data: Dict[str, Any], 
        container_id: str
    ) -> Dict[str, Any]:
        """
        실제 알림 전송 처리
        
        Args:
            notification_data: 알림 데이터
            container_id: 컨테이너 ID
            
        Returns:
            Dict containing send results
        """
        results = {
            "success": True,
            "notification_id": f"notif_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "sent_channels": [],
            "failed_channels": [],
            "recipient_count": 0
        }
        
        try:
            # 1. WebSocket 실시간 알림
            if self.websocket_enabled:
                websocket_result = await self._send_websocket_notification(
                    notification_data, container_id
                )
                if websocket_result["success"]:
                    results["sent_channels"].append("websocket")
                    results["recipient_count"] += websocket_result.get("recipient_count", 0)
                else:
                    results["failed_channels"].append("websocket")
            
            # 2. 이메일 알림 (현재는 비활성화)
            if self.email_enabled:
                email_result = await self._send_email_notification(
                    notification_data, container_id
                )
                if email_result["success"]:
                    results["sent_channels"].append("email")
                else:
                    results["failed_channels"].append("email")
            
            # 3. 알림 히스토리 저장
            await self._save_notification_history(notification_data, results)
            
            results["success"] = len(results["sent_channels"]) > 0
            
        except Exception as e:
            logger.error(f"알림 전송 처리 실패: {e}")
            results["success"] = False
            results["error"] = str(e)
        
        return results
    
    async def _send_websocket_notification(
        self, 
        notification_data: Dict[str, Any], 
        container_id: str
    ) -> Dict[str, Any]:
        """
        WebSocket을 통한 실시간 알림 전송 (시뮬레이션)
        TODO: 실제 WebSocket 구현
        """
        try:
            # TODO: 실제 WebSocket 연결 및 전송
            # 현재는 로그로 시뮬레이션
            logger.info(f"WebSocket 알림 전송 시뮬레이션:")
            logger.info(f"  - 컨테이너: {container_id}")
            logger.info(f"  - 제목: {notification_data['title']}")
            logger.info(f"  - 메시지: {notification_data['message']}")
            
            # 컨테이너별 모의 사용자 수
            mock_user_counts = {
                "WJ_HR": 15,
                "WJ_FIN": 12,
                "WJ_IT": 8,
                "WJ_MKT": 10
            }
            
            recipient_count = mock_user_counts.get(container_id, 5)
            
            return {
                "success": True,
                "channel": "websocket",
                "recipient_count": recipient_count,
                "delivery_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"WebSocket 알림 전송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_email_notification(
        self, 
        notification_data: Dict[str, Any], 
        container_id: str
    ) -> Dict[str, Any]:
        """
        이메일 알림 전송 (시뮬레이션)
        TODO: 실제 이메일 서비스 구현
        """
        try:
            # TODO: 실제 이메일 발송 로직
            logger.info(f"이메일 알림 전송 시뮬레이션:")
            logger.info(f"  - 컨테이너: {container_id}")
            logger.info(f"  - 제목: {notification_data['title']}")
            
            return {
                "success": True,
                "channel": "email",
                "recipient_count": 3,  # 모의 이메일 수신자 수
                "delivery_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"이메일 알림 전송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def _save_notification_history(
        self, 
        notification_data: Dict[str, Any], 
        send_results: Dict[str, Any]
    ) -> bool:
        """
        알림 히스토리 저장
        TODO: 데이터베이스 테이블에 저장
        """
        try:
            # TODO: tb_notification_history 테이블에 저장
            logger.debug(f"알림 히스토리 저장 시뮬레이션:")
            logger.debug(f"  - 알림 ID: {send_results.get('notification_id')}")
            logger.debug(f"  - 타입: {notification_data['type']}")
            logger.debug(f"  - 성공 채널: {send_results.get('sent_channels', [])}")
            
            return True
            
        except Exception as e:
            logger.error(f"알림 히스토리 저장 실패: {e}")
            return False
    
    async def get_user_notifications(
        self, 
        user_id: str, 
        container_id: Optional[str] = None,
        limit: int = 20,
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        사용자의 알림 목록 조회
        TODO: 실제 데이터베이스 조회
        """
        try:
            # TODO: 실제 알림 조회 로직
            logger.info(f"사용자 알림 조회 시뮬레이션 - 사용자: {user_id}")
            
            # 모의 알림 데이터
            mock_notifications = [
                {
                    "id": "notif_20241201_143000",
                    "type": NotificationType.DOCUMENT_UPLOADED.value,
                    "title": "📄 새 문서가 업로드되었습니다",
                    "message": "HR001님이 '인사정책_2024.pdf'를 업로드했습니다.",
                    "timestamp": "2024-12-01T14:30:00",
                    "read": False,
                    "container_id": container_id or "WJ_HR"
                }
            ]
            
            return mock_notifications
            
        except Exception as e:
            logger.error(f"사용자 알림 조회 실패: {e}")
            return []

# 전역 인스턴스
notification_service = NotificationService()
