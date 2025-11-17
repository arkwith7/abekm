import logging
from pathlib import Path
from typing import Optional

from openai import AzureOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    def __init__(self):
        self._client: Optional[AzureOpenAI] = None
        self._enabled = False
        self._init_client()

    def _init_client(self):
        if not settings.enable_audio_transcription:
            logger.info("Audio transcription disabled via configuration flag.")
            return

        if not (settings.azure_openai_api_key and settings.azure_openai_endpoint and settings.azure_openai_audio_deployment):
            logger.warning("Audio transcription is enabled but Azure OpenAI audio deployment settings are missing.")
            return

        try:
            self._client = AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_audio_api_version or settings.azure_openai_api_version
            )
            self._enabled = True
            logger.info("AudioTranscriptionService initialized with Azure OpenAI deployment '%s'.", settings.azure_openai_audio_deployment)
        except Exception as exc:
            self._client = None
            self._enabled = False
            logger.error("Failed to initialize Azure OpenAI audio client: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def transcribe(self, audio_path: Path, mime_type: Optional[str] = None) -> str:
        if not self.enabled or not self._client:
            raise RuntimeError("Audio transcription service is not configured.")

        logger.info("Transcribing audio file: %s", audio_path)
        with audio_path.open("rb") as audio_file:
            result = self._client.audio.transcriptions.create(
                model=settings.azure_openai_audio_deployment,
                file=audio_file,
                response_format="verbose_json"
            )

        text = getattr(result, "text", None)
        if not text and isinstance(result, dict):
            text = result.get("text") or result.get("combined_text")

        return text or ""


audio_transcription_service = AudioTranscriptionService()

