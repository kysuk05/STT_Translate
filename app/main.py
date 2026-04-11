import asyncio
import os
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.stt.whisper_service import WhisperService
from app.translate.translate_util import TranslateUtil
from app.utils.lang_detect import detect_language_with_prob
from app.config import (
    UPLOAD_READ_CHUNK_BYTES,
    MAX_UPLOAD_BYTES,
    ALLOWED_AUDIO_FILE_EXTENSIONS,
    ALLOWED_AUDIO_MIME_TYPES,
    MAX_TRANSCRIBE_SECONDS,
    MAX_TRANSLATE_SECONDS,
)

app = FastAPI(title="STT → Translate → Prompt (GPU)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stt_service = WhisperService()
translate_util = TranslateUtil()

UPLOAD_DIR = "tmp"
os.makedirs(UPLOAD_DIR, exist_ok=True)


_SAFE_FILENAME_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "._-"
)


def _sanitize_filename(filename: str) -> str:
    """
    업로드 파일명을 안전하게 정규화.
    - 경로 탐색 방지: basename만 사용
    - 허용 문자만 남김
    """
    if not filename:
        return "upload_audio"

    filename = os.path.basename((filename or "").replace("\\", "/"))
    cleaned = "".join(c if c in _SAFE_FILENAME_CHARS else "_" for c in filename)
    cleaned = cleaned.strip("._-")
    return cleaned or "upload_audio"


def _get_audio_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    return ext.lower().lstrip(".")


def _validate_upload(file: UploadFile, request: Optional[Request] = None) -> None:
    # 선제 크기 체크(content-length가 있는 경우)
    if request is not None:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"업로드 파일이 너무 큽니다. 최대 {MAX_UPLOAD_BYTES} bytes 입니다.",
                    )
            except ValueError:
                # header가 이상하면 무시하고 실제 read에서 최종 차단
                pass

    mime = (file.content_type or "").lower()
    ext = _get_audio_extension(file.filename or "")

    if ext not in ALLOWED_AUDIO_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="허용되지 않은 오디오 확장자입니다.",
        )

    # mime 타입은 클라이언트마다 부정확할 수 있어, 확장자가 허용되는 경우엔
    # 애매한 MIME(application/octet-stream 등)는 허용하도록 완화합니다.
    if mime and mime not in ALLOWED_AUDIO_MIME_TYPES and mime != "application/octet-stream":
        raise HTTPException(
            status_code=415,
            detail="허용되지 않은 오디오 MIME 타입입니다.",
        )


@app.post("/voice-to-prompt")
async def voice_to_prompt(file: UploadFile = File(...), request: Request = None):
    cleaned_filename = _sanitize_filename(file.filename or "upload_audio")
    audio_path = os.path.join(UPLOAD_DIR, cleaned_filename)

    # 업로드 검증(형식/크기)
    _validate_upload(file, request=request)

    text: str = ""
    lang = None
    prompt: str = ""
    try:
        # 업로드 저장(읽는 중 크기 초과 시 즉시 중단)
        size_bytes = 0
        with open(audio_path, "wb") as buffer:
            while True:
                chunk = await file.read(UPLOAD_READ_CHUNK_BYTES)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"업로드 파일이 너무 큽니다. 최대 {MAX_UPLOAD_BYTES} bytes 입니다.",
                    )
                buffer.write(chunk)

        # STT 처리(타임아웃 + 예외)
        try:
            text = await asyncio.wait_for(
                asyncio.to_thread(stt_service.transcribe, audio_path),
                timeout=MAX_TRANSCRIBE_SECONDS,
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="STT 처리 시간이 초과되었습니다.")
        except Exception:
            raise HTTPException(status_code=500, detail="STT 처리에 실패했습니다.")

        if not text or not text.strip():
            raise HTTPException(status_code=422, detail="STT 결과가 비어 있습니다.")

        # 언어 감지(실패 시 None)
        try:
            lang = detect_language_with_prob(text)
        except Exception:
            lang = None

        # 번역 처리(타임아웃 + 예외)
        try:
            if lang is None:
                prompt = await asyncio.wait_for(
                    asyncio.to_thread(
                        translate_util.smart_translate,
                        text,
                        "auto",
                        "en",
                    ),
                    timeout=MAX_TRANSLATE_SECONDS,
                )
            elif lang == "en":
                prompt = text
            else:
                prompt = await asyncio.wait_for(
                    asyncio.to_thread(
                        translate_util.smart_translate,
                        text,
                        lang,
                        "en",
                    ),
                    timeout=MAX_TRANSLATE_SECONDS,
                )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="번역 처리 시간이 초과되었습니다.")
        except Exception:
            raise HTTPException(status_code=500, detail="번역 처리에 실패했습니다.")

        return {
            "detected_lang": lang,
            "stt_text": text,
            "prompt_en": prompt,
        }
    finally:
        # 업로드 임시 파일 정리(best-effort)
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass