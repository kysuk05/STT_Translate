from faster_whisper import WhisperModel
from app.config import DEVICE, WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE

class WhisperService:
    def __init__(self):
        self.model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE
        )

    def transcribe(self, audio_path: str) -> str:
        segments, _ = self.model.transcribe(audio_path)
        return " ".join(segment.text for segment in segments)
