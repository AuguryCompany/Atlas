"""AUGURY AUDIT: every API call is recorded with principal, role and outcome."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .identity import resolve_principal

log = logging.getLogger("atlas.audit")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            principal = resolve_principal(request)
            try:
                request.app.state.db.write_audit(
                    principal=principal.name,
                    role=principal.role,
                    method=request.method,
                    path=request.url.path,
                    query=str(request.url.query) or None,
                    status=status_code,
                    duration_ms=round((time.perf_counter() - start) * 1000, 2),
                )
            except Exception:  # auditing must never break the request path
                log.exception("failed to write audit record")
