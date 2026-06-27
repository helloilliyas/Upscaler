"""Error codes and the application exception type.

Every failure the API surfaces maps to one of these stable, machine-readable
codes (mirrored in the Android client). The HTTP status is derived from the
code so handlers stay consistent.
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    ACCOUNT_NOT_ALLOWED = "ACCOUNT_NOT_ALLOWED"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    INVALID_IMAGE = "INVALID_IMAGE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    PIXEL_LIMIT_EXCEEDED = "PIXEL_LIMIT_EXCEEDED"
    MASK_SIZE_MISMATCH = "MASK_SIZE_MISMATCH"
    GPU_OUT_OF_MEMORY = "GPU_OUT_OF_MEMORY"
    MODEL_ERROR = "MODEL_ERROR"
    RESULT_EXPIRED = "RESULT_EXPIRED"
    BUDGET_LIMIT = "BUDGET_LIMIT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # Supporting codes not in the blueprint table but needed by the API surface.
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"


# Default HTTP status for each code.
_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.ACCOUNT_NOT_ALLOWED: 403,
    ErrorCode.UNSUPPORTED_FORMAT: 415,
    ErrorCode.INVALID_IMAGE: 422,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.PIXEL_LIMIT_EXCEEDED: 422,
    ErrorCode.MASK_SIZE_MISMATCH: 422,
    ErrorCode.GPU_OUT_OF_MEMORY: 500,
    ErrorCode.MODEL_ERROR: 500,
    ErrorCode.RESULT_EXPIRED: 410,
    ErrorCode.BUDGET_LIMIT: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.NOT_FOUND: 404,
}


def http_status_for(code: ErrorCode) -> int:
    return _HTTP_STATUS.get(code, 500)


class ApiError(Exception):
    """An error with a stable code and a derived HTTP status.

    The ``message`` is safe to show a developer/client; it must never contain
    private image bytes, raw tokens, or full emails.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        *,
        http_status: int | None = None,
    ) -> None:
        self.code = code
        self.message = message or code.value.replace("_", " ").title()
        self.http_status = http_status if http_status is not None else http_status_for(code)
        super().__init__(self.message)

    def to_dict(self) -> dict[str, object]:
        return {"error": {"code": self.code.value, "message": self.message}}
