import logging

from faster_whisper import WhisperModel

from app_v2.core.config import settings
from app_v2.core.errors import internal_error


class SttService:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.model = WhisperModel(
            settings.whisper_model_size,
            device=settings.device,
            compute_type=settings.whisper_compute_type,
        )

    def transcribe(self, audio_path: str) -> str:
        try:
            segments, _ = self.model.transcribe(audio_path)
            return " ".join(segment.text for segment in segments).strip()
        except Exception as exc:
            self.logger.exception("STT failed for file: %s", audio_path)
            raise internal_error(
                code="STT_FAILED",
                message="STT 처리에 실패했습니다.",
                detail=str(exc),
            )

