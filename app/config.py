import torch


# =========================
# DEVICE
# =========================

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# =========================
# WHISPER
# =========================

WHISPER_MODEL_SIZE = "base"

# int8 = 메모리 절약
# float16 = GPU 빠름
WHISPER_COMPUTE_TYPE = "int8"


# =========================
# TRANSLATE MODELS
# =========================

TRANSLATE_MODELS = {
    "m2m100": "facebook/m2m100_418M",
    "nllb": "facebook/nllb-200-distilled-600M",
}

DEFAULT_MODEL = "m2m100"


# =========================
# LANGUAGE GROUP
# =========================

ASIA_LANGS = {
    "ko",
    "ja",
    "zh",
}

EURO_LANGS = {
    "en",
    "fr",
    "de",
    "es",
    "it",
    "pt",
}


# =========================
# SCORE CHECK
# =========================

SCORE_THRESHOLD = 0.7


# =========================
# EMBEDDING MODEL
# =========================

EMBEDDING_MODEL = "sentence-transformers/LaBSE"


# =========================
# TARGET LANGS
# =========================

TARGET_LANGS = {
    "ko",
    "en",
    "ja",
    "zh",
    "es",
    "fr",
    "de",
    "it",
    "pt",
}


# =========================
# DEBUG
# =========================

DEBUG = True


# =========================
# UPLOAD LIMITS / TIMEOUTS
# =========================

# 업로드 파일 크기 제한 (MB)
# 실제 환경에 맞게 조정하세요.
MAX_UPLOAD_SIZE_MB = 25
MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# 파일 읽기 청크 크기(바이트)
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024  # 1MB

# 모델 처리 타임아웃(초)
# asyncio.wait_for로 API 레벨에서 제한을 걸며,
# 타임아웃이 걸리면 해당 요청은 에러로 응답합니다.
MAX_TRANSCRIBE_SECONDS = 120
MAX_TRANSLATE_SECONDS = 120

# 허용 MIME 타입/확장자(기본값)
# content_type 은 브라우저/클라이언트마다 다를 수 있으므로,
# 확장자 검사도 함께 사용합니다.
ALLOWED_AUDIO_MIME_TYPES = {
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

ALLOWED_AUDIO_FILE_EXTENSIONS = {
    "wav",
    "mp3",
    "m4a",
    "mp4",
    "webm",
    "ogg",
    "aac",
}