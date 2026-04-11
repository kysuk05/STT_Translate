import asyncio
import os
from typing import Optional

from fastapi import Request, UploadFile

from app.utils.lang_detect import detect_language_with_prob
from app_v2.core.config import settings
from app_v2.core.errors import AppError, timeout_error, unprocessable
from app_v2.services.stt_service import SttService
from app_v2.services.translation_service import TranslationService
from app_v2.services.upload_guard import (
    cleanup_file,
    sanitize_filename,
    save_upload_with_limit,
    validate_upload_meta,
)


class VoicePipelineService:
    def __init__(self, stt_service: SttService, translation_service: TranslationService) -> None:
        self.stt_service = stt_service
        self.translation_service = translation_service

    async def run(self, file: UploadFile, request: Optional[Request]) -> dict:
        validate_upload_meta(file, request)

        safe_name = sanitize_filename(file.filename or "upload_audio")
        audio_path = os.path.join(settings.upload_dir, safe_name)

        text = ""
        lang = None
        prompt = ""
        try:
            await save_upload_with_limit(file, audio_path)

            try:
                text = await asyncio.wait_for(
                    asyncio.to_thread(self.stt_service.transcribe, audio_path),
                    timeout=settings.max_transcribe_seconds,
                )
            except asyncio.TimeoutError:
                raise timeout_error(
                    code="STT_TIMEOUT",
                    message="STT 처리 시간이 초과되었습니다.",
                    detail=f"timeout={settings.max_transcribe_seconds}s",
                )

            if not text.strip():
                raise unprocessable(
                    code="EMPTY_STT_RESULT",
                    message="STT 결과가 비어 있습니다.",
                )

            try:
                lang = detect_language_with_prob(text)
            except Exception:
                lang = None

            translate_src = "auto" if lang is None else lang
            if lang == "en":
                prompt = text
            else:
                try:
                    prompt = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.translation_service.smart_translate,
                            text,
                            translate_src,
                            "en",
                        ),
                        timeout=settings.max_translate_seconds,
                    )
                except asyncio.TimeoutError:
                    raise timeout_error(
                        code="TRANSLATION_TIMEOUT",
                        message="번역 처리 시간이 초과되었습니다.",
                        detail=f"timeout={settings.max_translate_seconds}s",
                    )

            return {
                "detected_lang": lang,
                "stt_text": text,
                "prompt_en": prompt,
            }
        except AppError:
            raise
        finally:
            cleanup_file(audio_path)

