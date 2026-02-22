from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os

from app.stt.whisper_service import WhisperService
from app.translate.translate_util import TranslateUtil
from app.utils.lang_detect import is_korean

app = FastAPI(title="STT → Translate → Prompt (GPU)")

# 🔥 CORS 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stt_service = WhisperService()
translate_util = TranslateUtil()

UPLOAD_DIR = "tmp"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/voice-to-prompt")
async def voice_to_prompt(file: UploadFile = File(...)):
    audio_path = f"{UPLOAD_DIR}/{file.filename}"

    with open(audio_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    text = stt_service.transcribe(audio_path)

    if is_korean(text):
        prompt = translate_util.translate(text)
    else:
        prompt = text

    return {
        "stt_text": text,
        "prompt_en": prompt
    }