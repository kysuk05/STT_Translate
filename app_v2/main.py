from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app_v2.api.routes import build_router
from app_v2.core.config import settings
from app_v2.services.pipeline_service import VoicePipelineService
from app_v2.services.stt_service import SttService
from app_v2.services.translation_service import TranslationService


stt_service = SttService()
translation_service = TranslationService()
pipeline_service = VoicePipelineService(
    stt_service=stt_service,
    translation_service=translation_service,
)

app = FastAPI(title=settings.app_title)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(build_router(pipeline_service))

