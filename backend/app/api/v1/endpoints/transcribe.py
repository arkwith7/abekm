"""
실시간 음성→텍스트 변환 API (AWS Transcribe Streaming)

WebSocket 기반 실시간 STT 서비스 - amazon-transcribe 라이브러리 사용
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import asyncio
import json
import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError

# AWS Transcribe Streaming 라이브러리
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

from app.core.database import get_db
from app.models import User


from app.utils.stt_post_processor import post_process_transcript, should_post_process

logger = logging.getLogger(__name__)
router = APIRouter()


# WebSocket 인증 헬퍼 (선택적)
async def get_current_user_ws_optional(token: Optional[str]) -> Optional[User]:
    """
    WebSocket 연결용 사용자 인증 (선택적)
    
    인증 실패 시 None 반환 (예외 발생 안 함)
    
    Note: DB 세션을 별도로 생성하여 사용 (WebSocket 수명과 독립적)
    """
    logger.debug(f"🔐 [STT-AUTH] 토큰 인증 시작 - token={'있음' if token else '없음'}")
    
    if not token:
        logger.warning("⚠️ [STT-AUTH] 토큰 없음 - 익명 사용자로 진행")
        return None
    
    try:
        from app.core.security import AuthUtils
        from sqlalchemy import select
        
        logger.debug(f"🔍 [STT-AUTH] 토큰 검증 중... (token length: {len(token)})")
        
        # 토큰 검증
        token_data = AuthUtils.verify_token(token)
        logger.debug(f"✅ [STT-AUTH] 토큰 검증 성공 - emp_no: {token_data.emp_no}")
        
        # 별도 DB 세션 생성하여 사용자 조회 (동기 방식)
        # WebSocket은 비동기이지만, DB 조회는 선택적이므로 동기 세션 사용
        from app.core.database import get_sync_session_local
        
        SyncSessionLocal = get_sync_session_local()
        db = SyncSessionLocal()
        try:
            user = db.query(User).filter(User.emp_no == token_data.emp_no).first()
            
            if user:
                logger.info(f"✅ [STT-AUTH] 사용자 인증 완료 - user_id: {user.id}, username: {user.username}")
            else:
                logger.warning(f"⚠️ [STT-AUTH] 사용자 DB 조회 실패 - emp_no: {token_data.emp_no}")
            
            return user
        finally:
            db.close()
        
    except Exception as e:
        logger.warning(f"⚠️ [STT-AUTH] 인증 실패 (계속 진행) - error: {str(e)}, type: {type(e).__name__}")
        import traceback
        logger.debug(f"🐛 [STT-AUTH] 스택 트레이스:\n{traceback.format_exc()}")
        return None


class WebSocketTranscriptHandler(TranscriptResultStreamHandler):
    """WebSocket으로 변환 결과를 전송하는 핸들러"""
    
    def __init__(self, output_stream, websocket: WebSocket):
        super().__init__(output_stream)
        self.websocket = websocket
        self.transcript_count = 0
        
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        """변환 결과 이벤트 처리"""
        results = transcript_event.transcript.results

        if not results:
            logger.debug("📭 [AWS-STT] 빈 transcript 이벤트 수신 (results=0)")
            return

        for result in results:
            if not result.alternatives:
                logger.debug("📭 [AWS-STT] 결과는 있으나 대안(alternatives)이 없음")
                continue

            for alt in result.alternatives:
                self.transcript_count += 1

                text = alt.transcript or ""
                
                # 🆕 후처리: 확정 결과(is_partial=False)만 오인식 보정
                if should_post_process(text, result.is_partial):
                    original_text = text
                    text = post_process_transcript(text)
                    if text != original_text:
                        logger.info(
                            "🔧 [STT-POSTPROCESS] 오인식 보정 - before='%s', after='%s'",
                            original_text[:30],
                            text[:30]
                        )
                
                response = {
                    'type': 'transcript',
                    'text': text,
                    'is_partial': result.is_partial,
                    'confidence': getattr(alt, 'confidence', None)
                }

                logger.info(
                    "📤 [AWS-STT] 변환 결과 전송 #%s - len=%s, partial=%s, text_preview='%s'",
                    self.transcript_count,
                    len(text),
                    result.is_partial,
                    text[:50] + ("..." if len(text) > 50 else ""),
                )

                try:
                    await self.websocket.send_json(response)
                except Exception as e:
                    logger.error(f"❌ [AWS-STT] WebSocket 전송 실패: {e}")


class TranscribeStreamingSession:
    """AWS Transcribe Streaming 세션 관리"""
    
    def __init__(self, region: str = "ap-northeast-2"):
        self.region = region
        self.client = None
        self.stream = None
        self.handler = None
        self.handler_task = None
        
    async def start_stream(
        self,
        websocket: WebSocket,
        language_code: str = "ko-KR",
        sample_rate: int = 16000
    ):
        """스트리밍 세션 시작"""
        # auto를 ko-KR로 변환 (amazon-transcribe 라이브러리는 자동 언어 감지 미지원)
        if language_code == "auto":
            language_code = "ko-KR"
            logger.info("🌐 [AWS-STT] 자동 언어 감지 요청 -> 한국어(ko-KR)로 설정 (라이브러리 제한)")
        
        logger.info(f"🚀 [AWS-STT] 스트리밍 세션 시작 - language: {language_code}, sample_rate: {sample_rate}, region: {self.region}")
        
        try:
            # AWS Transcribe Streaming 클라이언트 생성
            logger.debug("🔧 [AWS-STT] TranscribeStreamingClient 생성 중...")
            self.client = TranscribeStreamingClient(region=self.region)
            logger.debug("✅ [AWS-STT] 클라이언트 생성 완료")
            
            # 스트리밍 세션 시작 (인식 정확도 최적화 설정)
            logger.debug("📡 [AWS-STT] start_stream_transcription 호출 중...")
            self.stream = await self.client.start_stream_transcription(
                language_code=language_code,
                media_sample_rate_hz=sample_rate,
                media_encoding="pcm",
                # 부분 결과 안정화 - 인식 정확도 향상
                enable_partial_results_stabilization=True,
                partial_results_stability="high",  # medium → high (더 정확한 인식)
            )
            logger.info("✅ [AWS-STT] 스트리밍 세션 시작 성공 (고정확도 모드)")
            
            # 이벤트 핸들러 생성 및 시작
            self.handler = WebSocketTranscriptHandler(self.stream.output_stream, websocket)
            self.handler_task = asyncio.create_task(self.handler.handle_events())
            logger.debug("✅ [AWS-STT] 이벤트 핸들러 시작")
            
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"❌ [AWS-STT] AWS Transcribe 시작 실패 - error_code: {error_code}, message: {error_msg}")
            logger.error(f"💡 [AWS-STT] 힌트: IAM 권한 확인 필요 (transcribe:StartStreamTranscription)")
            return False
        except Exception as e:
            logger.error(f"❌ [AWS-STT] 스트리밍 세션 시작 오류 - error: {str(e)}, type: {type(e).__name__}")
            import traceback
            logger.error(f"📋 [AWS-STT] 스택 트레이스:\n{traceback.format_exc()}")
            return False
    
    async def send_audio(self, audio_chunk: bytes):
        """오디오 청크 전송"""
        if not self.stream:
            logger.warning("⚠️ [AWS-STT] 스트림 없음 - 오디오 전송 불가")
            return False
        
        try:
            if not hasattr(self, "_audio_bytes_total"):
                self._audio_bytes_total = 0
                self._audio_chunk_count = 0

            chunk_size = len(audio_chunk)
            self._audio_bytes_total += chunk_size
            self._audio_chunk_count += 1

            logger.debug(
                "🎤 [AWS-STT] 오디오 청크 전송 중 #%s - size=%s bytes, total_bytes=%s",
                self._audio_chunk_count,
                chunk_size,
                self._audio_bytes_total,
            )

            await self.stream.input_stream.send_audio_event(audio_chunk=audio_chunk)
            logger.debug("✅ [AWS-STT] 오디오 청크 전송 완료 - size=%s bytes", chunk_size)
            return True
        except Exception as e:
            logger.error(f"❌ [AWS-STT] 오디오 전송 오류 - error: {str(e)}, type: {type(e).__name__}")
            return False
    
    async def close(self):
        """스트리밍 세션 종료 (Graceful Shutdown)"""
        try:
            if self.stream:
                logger.debug("🛑 [AWS-STT] 스트림 종료 신호 전송 중...")
                await self.stream.input_stream.end_stream()
                logger.debug("✅ [AWS-STT] 스트림 종료 신호 전송 완료")
                
            if self.handler_task:
                logger.debug("⏳ [AWS-STT] 핸들러 태스크 완료 대기 중 (최대 2초)...")
                try:
                    # 최대 2초 대기 (AWS가 마지막 결과 전송 완료할 시간 제공)
                    await asyncio.wait_for(self.handler_task, timeout=2.0)
                    logger.debug("✅ [AWS-STT] 핸들러 태스크 완료")
                except asyncio.TimeoutError:
                    # 타임아웃은 정상 동작 (클라이언트가 먼저 종료한 경우)
                    logger.debug("⏳ [AWS-STT] 핸들러 태스크 타임아웃 (2초, 정상)")
                    # 타임아웃 후에도 태스크 취소 시도
                    if not self.handler_task.done():
                        self.handler_task.cancel()
                        try:
                            await self.handler_task
                        except asyncio.CancelledError:
                            logger.debug("✅ [AWS-STT] 핸들러 태스크 강제 취소됨")
                
            logger.info("✅ Transcribe 스트리밍 세션 종료")
        except Exception as e:
            logger.error(f"❌ 세션 종료 오류: {e}")


@router.websocket("/stream")
async def transcribe_stream(
    websocket: WebSocket
):
    """
    실시간 음성→텍스트 변환 WebSocket
    
    프론트엔드에서 오디오 청크를 전송하면 실시간으로 텍스트 반환
    
    **메시지 형식:**
    
    클라이언트 → 서버:
    - 바이너리: 오디오 청크 (PCM 16kHz 16bit)
    - JSON: {"action": "start", "language": "ko-KR", "sample_rate": 16000}
    - JSON: {"action": "stop"}
    
    서버 → 클라이언트:
    - {"type": "transcript", "text": "변환된 텍스트", "is_partial": true/false}
    - {"type": "error", "message": "오류 메시지"}
    - {"type": "started", "session_id": "..."}
    - {"type": "stopped"}
    """
    client_host = websocket.client.host if websocket.client else 'unknown'
    logger.info(f"🔌 [WS-CONNECT] WebSocket 연결 요청 - client: {client_host}")
    
    await websocket.accept()
    logger.info(f"✅ [WS-CONNECT] WebSocket 연결 수락 완료")
    
    # 사용자 인증 (선택사항)
    token = websocket.query_params.get('token')
    logger.debug(f"🔐 [WS-CONNECT] 쿼리 파라미터 - token={'있음' if token else '없음'}")
    
    user = await get_current_user_ws_optional(token)
    
    session = TranscribeStreamingSession()
    session_id = f"transcribe_{asyncio.current_task().get_name()}"
    
    logger.info(f"🔌 [WS-SESSION] WebSocket 세션 생성 - session_id: {session_id}, user: {user.username if user else 'Anonymous'}, user_id: {user.id if user else None}")
    
    try:
        # 초기 시작 메시지 대기
        logger.debug(f"⏳ [WS-SESSION] 초기 시작 메시지 대기 중... - session_id: {session_id}")
        data = await websocket.receive()
        logger.debug(f"📨 [WS-SESSION] 메시지 수신 - keys: {list(data.keys())}")
        
        if 'text' in data:
            logger.debug(f"📄 [WS-SESSION] 텍스트 메시지 - content: {data['text'][:200]}")
            config = json.loads(data['text'])
            logger.info(f"⚙️ [WS-SESSION] 설정 파싱 완료 - config: {config}")
            
            if config.get('action') == 'start':
                language = config.get('language', 'ko-KR')
                sample_rate = config.get('sample_rate', 16000)
                logger.info(f"🚀 [WS-SESSION] STT 시작 요청 - language: {language}, sample_rate: {sample_rate}")
                
                # Transcribe 스트리밍 시작
                success = await session.start_stream(
                    websocket=websocket,
                    language_code=language,
                    sample_rate=sample_rate
                )
                
                if success:
                    response = {
                        'type': 'started',
                        'session_id': session_id,
                        'language': language,
                        'sample_rate': sample_rate
                    }
                    logger.info(f"✅ [WS-SESSION] STT 시작 성공 응답 전송 - response: {response}")
                    await websocket.send_json(response)
                else:
                    error_response = {
                        'type': 'error',
                        'message': 'AWS Transcribe 시작 실패 - IAM 권한 또는 네트워크를 확인하세요'
                    }
                    logger.error(f"❌ [WS-SESSION] STT 시작 실패 - response: {error_response}")
                    await websocket.send_json(error_response)
                    await websocket.close()
                    return
            else:
                logger.warning(f"⚠️ [WS-SESSION] 잘못된 action - action: {config.get('action')}")
        else:
            logger.warning(f"⚠️ [WS-SESSION] 텍스트 메시지 없음 - data_keys: {list(data.keys())}")
        
        # 오디오 수신 루프
        chunk_count = 0
        while True:
            try:
                logger.debug("⏳ [WS-RECV] 메시지 대기 중...")
                data = await websocket.receive()
                
                # 바이너리 오디오 데이터
                if 'bytes' in data:
                    chunk_count += 1
                    audio_chunk = data['bytes']
                    logger.debug(f"🎤 [WS-RECV] 오디오 청크 수신 #{chunk_count} - size: {len(audio_chunk)} bytes")
                    await session.send_audio(audio_chunk)
                
                # JSON 제어 메시지
                elif 'text' in data:
                    message = json.loads(data['text'])
                    logger.info(f"📨 [WS-RECV] 제어 메시지 수신 - message: {message}")
                    
                    if message.get('action') == 'stop':
                        logger.info(f"🛑 [WS-RECV] 클라이언트 중지 요청 - 총 {chunk_count}개 청크 처리됨")
                        
                        # 클라이언트에 종료 확인 전송 (WebSocket 상태 확인)
                        try:
                            from starlette.websockets import WebSocketState
                            if websocket.client_state == WebSocketState.CONNECTED:
                                await websocket.send_json({'type': 'stopped'})
                                logger.debug("✅ [WS-RECV] 종료 확인 메시지 전송 완료")
                            else:
                                logger.warning(f"⚠️ [WS-RECV] WebSocket 이미 종료됨 - 상태: {websocket.client_state}")
                        except Exception as send_error:
                            logger.warning(f"⚠️ [WS-RECV] 종료 확인 메시지 전송 실패: {send_error}")
                        
                        break
                else:
                    logger.warning(f"⚠️ [WS-RECV] 알 수 없는 메시지 타입 - keys: {list(data.keys())}")
            
            except WebSocketDisconnect:
                logger.info(f"🔌 [WS-RECV] 클라이언트 연결 종료 - 총 {chunk_count}개 청크 처리됨")
                break
            except Exception as e:
                logger.error(f"❌ [WS-RECV] 오디오 수신 오류 - error: {str(e)}, chunk_count: {chunk_count}")
                break
        
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket 정상 종료: {session_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket 오류: {session_id}, {e}")
        import traceback
        logger.error(f"📋 스택 트레이스:\n{traceback.format_exc()}")
        try:
            await websocket.send_json({
                'type': 'error',
                'message': str(e)
            })
        except:
            pass
    finally:
        await session.close()
        try:
            await websocket.close()
        except:
            pass
        logger.info(f"🔌 WebSocket 종료 완료: {session_id}")


@router.post("/test")
async def test_transcribe_setup():
    """
    AWS Transcribe 설정 테스트
    
    IAM 권한 및 연결 확인
    """
    try:
        client = boto3.client('transcribe', region_name='ap-northeast-2')
        
        # 간단한 API 호출로 권한 확인
        # list_transcription_jobs는 읽기 권한만 필요
        response = client.list_transcription_jobs(MaxResults=1)
        
        # amazon-transcribe 라이브러리로 스트리밍 클라이언트 테스트
        streaming_client = TranscribeStreamingClient(region='ap-northeast-2')
        
        return {
            'success': True,
            'message': 'AWS Transcribe 연결 및 권한 확인 성공',
            'region': 'ap-northeast-2',
            'service': 'transcribe',
            'streaming_client': 'TranscribeStreamingClient 생성 성공',
            'note': 'StartStreamTranscription 권한은 실제 스트리밍 시 확인됩니다'
        }
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        return {
            'success': False,
            'error_code': error_code,
            'message': error_message,
            'hint': '💡 IAM 권한 확인: transcribe:StartStreamTranscription'
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': str(e),
            'hint': '💡 AWS 자격증명 확인: ~/.aws/credentials 또는 환경변수'
        }
