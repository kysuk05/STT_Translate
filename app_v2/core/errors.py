from dataclasses import dataclass
from typing import Optional


@dataclass
class AppError(Exception):
    error_code: str
    message: str
    status_code: int
    detail: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.error_code}: {self.message}"


def bad_request(code: str, message: str, detail: Optional[str] = None) -> AppError:
    return AppError(error_code=code, message=message, status_code=400, detail=detail)


def unsupported_media(code: str, message: str, detail: Optional[str] = None) -> AppError:
    return AppError(error_code=code, message=message, status_code=415, detail=detail)


def payload_too_large(code: str, message: str, detail: Optional[str] = None) -> AppError:
    return AppError(error_code=code, message=message, status_code=413, detail=detail)


def unprocessable(code: str, message: str, detail: Optional[str] = None) -> AppError:
    return AppError(error_code=code, message=message, status_code=422, detail=detail)


def timeout_error(code: str, message: str, detail: Optional[str] = None) -> AppError:
    return AppError(error_code=code, message=message, status_code=504, detail=detail)


def internal_error(code: str, message: str, detail: Optional[str] = None) -> AppError:
    return AppError(error_code=code, message=message, status_code=500, detail=detail)

