from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

CORRELATION_ID_PATTERN = re.compile(r"^req-[0-9a-f]{8}$")

RESPONSE_TIME_MS_PRECISION = 3


def new_correlation_id() -> str:
    return f"req-{uuid.uuid4().hex[:8]}"


def resolve_correlation_id(request: Request) -> str:
    """Chỉ tin `x-request-id` khi nó đúng format `req-<8-hex>`.

    Header do client tự gửi có thể chứa PII hoặc chuỗi tùy ý, nên format sai
    bị bỏ qua và thay bằng ID sinh ra trong server.
    """
    supplied = request.headers.get("x-request-id", "").strip().lower()
    if CORRELATION_ID_PATTERN.match(supplied):
        return supplied
    return new_correlation_id()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Xóa context của request trước đó, nếu không structlog sẽ ghi
        # correlation_id của request cũ vào log của request mới.
        clear_contextvars()

        correlation_id = resolve_correlation_id(request)
        bind_contextvars(correlation_id=correlation_id)

        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = correlation_id
            response.headers["x-response-time-ms"] = format(
                (time.perf_counter() - start) * 1000,
                f".{RESPONSE_TIME_MS_PRECISION}f",
            )
            return response
        finally:
            # Dọn context để không rò sang request kế tiếp hoặc task nền.
            clear_contextvars()
