import os
from typing import Optional

from fastapi import Request, UploadFile

from app_v2.core.config import settings
from app_v2.core.errors import payload_too_large, unsupported_media


SAFE_FILENAME_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "._-"
)


def sanitize_filename(filename: str) -> str:
    if not filename:
        return "upload_audio"
    basename = os.path.basename(filename.replace("\\", "/"))
    cleaned = "".join(c if c in SAFE_FILENAME_CHARS else "_" for c in basename).strip("._-")
    return cleaned or "upload_audio"


def get_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    return ext.lower().lstrip(".")


def validate_upload_meta(file: UploadFile, request: Optional[Request]) -> None:
    if request is not None:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_upload_bytes:
                    raise payload_too_large(
                        code="FILE_TOO_LARGE",
                        message="업로드 파일이 너무 큽니다.",
                        detail=f"max_bytes={settings.max_upload_bytes}",
                    )
            except ValueError:
                pass

    ext = get_extension(file.filename or "")
    if ext not in settings.allowed_audio_extensions:
        raise unsupported_media(
            code="UNSUPPORTED_EXTENSION",
            message="허용되지 않은 오디오 확장자입니다.",
            detail=f"ext={ext}",
        )

    mime = (file.content_type or "").lower()
    if mime and mime not in settings.allowed_audio_mime_types and mime != "application/octet-stream":
        raise unsupported_media(
            code="UNSUPPORTED_MIME",
            message="허용되지 않은 오디오 MIME 타입입니다.",
            detail=f"mime={mime}",
        )


async def save_upload_with_limit(file: UploadFile, target_path: str) -> int:
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    total_bytes = 0
    with open(target_path, "wb") as buffer:
        while True:
            chunk = await file.read(settings.upload_read_chunk_bytes)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > settings.max_upload_bytes:
                raise payload_too_large(
                    code="FILE_TOO_LARGE",
                    message="업로드 파일이 너무 큽니다.",
                    detail=f"max_bytes={settings.max_upload_bytes}",
                )
            buffer.write(chunk)
    return total_bytes


def cleanup_file(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

