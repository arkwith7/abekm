import logging
import time
import uuid
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    """AWS Transcribe 기반 음성 텍스트 변환 서비스
    
    배치 변환 방식:
    1. S3에 오디오 파일 업로드
    2. StartTranscriptionJob API 호출
    3. 폴링으로 완료 대기
    4. 결과 JSON 다운로드 및 텍스트 추출
    """
    
    def __init__(self):
        self._transcribe_client = None
        self._s3_client = None
        self._enabled = False
        self._init_clients()

    def _init_clients(self):
        """AWS Transcribe 및 S3 클라이언트 초기화"""
        if not settings.enable_audio_transcription:
            logger.info("Audio transcription disabled via configuration flag.")
            return

        # AWS 자격 증명 확인
        if not (settings.aws_access_key_id and settings.aws_secret_access_key):
            logger.warning("Audio transcription is enabled but AWS credentials are missing.")
            return

        # S3 버킷 확인
        if not settings.aws_s3_bucket:
            logger.warning("Audio transcription is enabled but AWS S3 bucket is not configured.")
            return

        try:
            # Transcribe 클라이언트 초기화
            self._transcribe_client = boto3.client(
                'transcribe',
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )
            
            # S3 클라이언트 초기화
            self._s3_client = boto3.client(
                's3',
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )
            
            self._enabled = True
            logger.info(
                "✅ AudioTranscriptionService initialized with AWS Transcribe (region: %s, bucket: %s)",
                settings.aws_region,
                settings.aws_s3_bucket
            )
        except Exception as exc:
            self._transcribe_client = None
            self._s3_client = None
            self._enabled = False
            logger.error("❌ Failed to initialize AWS Transcribe client: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._enabled and self._transcribe_client is not None

    def transcribe(self, audio_path: Path, language_code: str = "ko-KR") -> str:
        """오디오 파일을 텍스트로 변환
        
        Args:
            audio_path: 오디오 파일 경로
            language_code: 언어 코드 (ko-KR, en-US, ja-JP, zh-CN 등)
        
        Returns:
            변환된 텍스트
        """
        if not self.enabled or not self._transcribe_client or not self._s3_client:
            raise RuntimeError("Audio transcription service is not configured.")

        logger.info("🎤 [AWS-TRANSCRIBE] 음성 변환 시작 - file: %s, language: %s", audio_path, language_code)
        
        # 고유 작업 ID 생성
        job_name = f"transcribe-{uuid.uuid4()}"
        s3_key = f"transcribe-temp/{job_name}{audio_path.suffix}"
        
        try:
            # 1. S3에 오디오 파일 업로드
            logger.info("📤 [AWS-TRANSCRIBE] S3 업로드 시작 - key: %s", s3_key)
            with audio_path.open("rb") as audio_file:
                self._s3_client.upload_fileobj(
                    audio_file,
                    settings.aws_s3_bucket,
                    s3_key
                )
            logger.info("✅ [AWS-TRANSCRIBE] S3 업로드 완료")
            
            # 2. Transcribe 작업 시작
            s3_uri = f"s3://{settings.aws_s3_bucket}/{s3_key}"
            logger.info("🚀 [AWS-TRANSCRIBE] 변환 작업 시작 - job: %s", job_name)
            
            self._transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': s3_uri},
                MediaFormat=self._get_media_format(audio_path.suffix),
                LanguageCode=language_code,
                Settings={
                    'ShowSpeakerLabels': False,
                    'MaxSpeakerLabels': 1
                }
            )
            
            # 3. 작업 완료 대기 (폴링)
            max_wait_time = 300  # 5분
            poll_interval = 2  # 2초
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                status = self._transcribe_client.get_transcription_job(
                    TranscriptionJobName=job_name
                )
                job_status = status['TranscriptionJob']['TranscriptionJobStatus']
                
                if job_status == 'COMPLETED':
                    logger.info("✅ [AWS-TRANSCRIBE] 변환 완료 - elapsed: %ds", elapsed_time)
                    
                    # 4. 결과 다운로드
                    transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                    text = self._download_transcript(transcript_uri)
                    
                    return text
                
                elif job_status == 'FAILED':
                    failure_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown')
                    logger.error("❌ [AWS-TRANSCRIBE] 변환 실패 - reason: %s", failure_reason)
                    raise RuntimeError(f"Transcription job failed: {failure_reason}")
                
                # 진행 중
                logger.debug("⏳ [AWS-TRANSCRIBE] 변환 중... status: %s (elapsed: %ds)", job_status, elapsed_time)
                time.sleep(poll_interval)
                elapsed_time += poll_interval
            
            # 타임아웃
            logger.error("⏰ [AWS-TRANSCRIBE] 타임아웃 - max_wait: %ds", max_wait_time)
            raise RuntimeError(f"Transcription job timed out after {max_wait_time}s")
            
        except ClientError as exc:
            logger.error("❌ [AWS-TRANSCRIBE] AWS 클라이언트 오류: %s", exc)
            raise RuntimeError(f"AWS Transcribe error: {exc}")
        
        finally:
            # 정리: S3에서 임시 파일 삭제
            try:
                self._s3_client.delete_object(
                    Bucket=settings.aws_s3_bucket,
                    Key=s3_key
                )
                logger.info("🗑️ [AWS-TRANSCRIBE] S3 임시 파일 삭제 완료")
            except Exception as cleanup_exc:
                logger.warning("⚠️ [AWS-TRANSCRIBE] S3 정리 실패: %s", cleanup_exc)
            
            # Transcribe 작업 삭제 (선택사항)
            try:
                self._transcribe_client.delete_transcription_job(
                    TranscriptionJobName=job_name
                )
                logger.info("🗑️ [AWS-TRANSCRIBE] 변환 작업 삭제 완료")
            except Exception as cleanup_exc:
                logger.warning("⚠️ [AWS-TRANSCRIBE] 작업 삭제 실패: %s", cleanup_exc)

    def _get_media_format(self, suffix: str) -> str:
        """파일 확장자에서 미디어 포맷 추출"""
        format_map = {
            '.mp3': 'mp3',
            '.mp4': 'mp4',
            '.wav': 'wav',
            '.flac': 'flac',
            '.ogg': 'ogg',
            '.amr': 'amr',
            '.webm': 'webm',
            '.m4a': 'mp4'
        }
        return format_map.get(suffix.lower(), 'mp4')

    def _download_transcript(self, transcript_uri: str) -> str:
        """Transcribe 결과 JSON 다운로드 및 텍스트 추출"""
        import json
        import urllib.request
        
        try:
            with urllib.request.urlopen(transcript_uri) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            # 전체 텍스트 추출
            transcripts = data.get('results', {}).get('transcripts', [])
            if transcripts:
                text = transcripts[0].get('transcript', '')
                logger.info("📝 [AWS-TRANSCRIBE] 텍스트 추출 완료 - length: %d", len(text))
                return text
            
            logger.warning("⚠️ [AWS-TRANSCRIBE] 변환 결과가 비어있습니다")
            return ""
            
        except Exception as exc:
            logger.error("❌ [AWS-TRANSCRIBE] 결과 다운로드 실패: %s", exc)
            raise RuntimeError(f"Failed to download transcript: {exc}")


audio_transcription_service = AudioTranscriptionService()

