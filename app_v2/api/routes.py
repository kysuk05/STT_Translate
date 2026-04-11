from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from app_v2.api.schemas import ErrorResponse, VoiceToPromptResponse
from app_v2.core.errors import AppError, internal_error
from app_v2.services.pipeline_service import VoicePipelineService


def build_router(pipeline_service: VoicePipelineService) -> APIRouter:
    router = APIRouter()

    @router.post("/voice-to-prompt", response_model=VoiceToPromptResponse)
    async def voice_to_prompt(file: UploadFile = File(...), request: Request = None):
        try:
            result = await pipeline_service.run(file=file, request=request)
            return VoiceToPromptResponse(**result)
        except AppError as err:
            payload = ErrorResponse(
                error_code=err.error_code,
                message=err.message,
                detail=err.detail,
            ).model_dump()
            return JSONResponse(status_code=err.status_code, content=payload)
        except Exception as exc:
            err = internal_error(
                code="INTERNAL_ERROR",
                message="서버 내부 오류가 발생했습니다.",
                detail=str(exc),
            )
            payload = ErrorResponse(
                error_code=err.error_code,
                message=err.message,
                detail=err.detail,
            ).model_dump()
            return JSONResponse(status_code=err.status_code, content=payload)

    return router

