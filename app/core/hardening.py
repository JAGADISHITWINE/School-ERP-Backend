from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.ENVIRONMENT.lower() == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        path = request.url.path
        is_auth_path = path.endswith("/auth/login") or path.endswith("/auth/refresh") or path.endswith("/auth/reset-password")
        limit = settings.AUTH_RATE_LIMIT_PER_MINUTE if is_auth_path else settings.RATE_LIMIT_PER_MINUTE
        key = (client, "auth" if is_auth_path else "global")
        bucket = self._hits[key]

        while bucket and now - bucket[0] > 60:
            bucket.popleft()

        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={"success": False, "data": None, "message": "Too many requests. Try again later."},
            )

        bucket.append(now)
        return await call_next(request)


def allowed_origins() -> list[str]:
    return [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]


def assert_secure_runtime_config() -> None:
    if settings.ENVIRONMENT.lower() != "production":
        return
    weak_secrets = {
        "change-me",
        "change-me-to-a-secure-random-64-char-string",
        "secret",
        "dev-secret",
    }
    if settings.SECRET_KEY.strip() in weak_secrets or len(settings.SECRET_KEY.strip()) < 48:
        raise RuntimeError("Production SECRET_KEY must be a strong random value of at least 48 characters.")
    if "*" in allowed_origins():
        raise RuntimeError("Production ALLOWED_ORIGINS cannot contain '*'.")
