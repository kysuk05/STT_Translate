from typing import Optional

from pydantic import BaseModel


class VoiceToPromptResponse(BaseModel):
    detected_lang: Optional[str]
    stt_text: str
    prompt_en: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: Optional[str] = None

