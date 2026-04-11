import os
from dataclasses import dataclass, field
from typing import Set

import torch


@dataclass(frozen=True)
class Settings:
    app_title: str = "STT -> Translate -> Prompt (GPU) v2"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    whisper_model_size: str = "base"
    whisper_compute_type: str = "int8"

    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
    upload_read_chunk_bytes: int = int(os.getenv("UPLOAD_READ_CHUNK_BYTES", str(1024 * 1024)))
    max_transcribe_seconds: int = int(os.getenv("MAX_TRANSCRIBE_SECONDS", "120"))
    max_translate_seconds: int = int(os.getenv("MAX_TRANSLATE_SECONDS", "120"))

    upload_dir: str = os.getenv("UPLOAD_DIR", "tmp")

    allowed_audio_mime_types: Set[str] = field(
        default_factory=lambda: {
            "audio/wav",
            "audio/x-wav",
            "audio/mpeg",
            "audio/mp3",
            "audio/mp4",
            "audio/aac",
            "audio/webm",
            "audio/ogg",
            "audio/x-m4a",
        }
    )
    allowed_audio_extensions: Set[str] = field(
        default_factory=lambda: {"wav", "mp3", "m4a", "mp4", "webm", "ogg", "aac"}
    )

    translate_models: dict = field(
        default_factory=lambda: {
            "m2m100": "facebook/m2m100_418M",
            "nllb": "facebook/nllb-200-distilled-600M",
        }
    )
    score_threshold: float = float(os.getenv("SCORE_THRESHOLD", "0.7"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/LaBSE")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()

