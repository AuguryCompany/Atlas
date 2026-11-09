"""AUGURY IDENTITY (minimal): API-key based principals and role checks."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

# Higher rank includes every permission of lower ranks.
ROLE_RANK = {"viewer": 0, "analyst": 1, "admin": 2}


@dataclass(frozen=True)
class Principal:
    name: str
    role: str

    def has(self, role: str) -> bool:
        return ROLE_RANK.get(self.role, -1) >= ROLE_RANK[role]


ANONYMOUS_DEV = Principal(name="dev-anonymous", role="admin")


def resolve_principal(request: Request) -> Principal:
    """Resolve the caller. Cached on request.state so audit can read it too."""
    cached = getattr(request.state, "principal", None)
    if cached is not None:
        return cached
    settings = request.app.state.settings
    if not settings.auth_enabled:
        principal = ANONYMOUS_DEV
    else:
        key = request.headers.get("x-api-key") or ""
        role = settings.api_keys.get(key)
        if role not in ROLE_RANK:
            principal = Principal(name="unauthenticated", role="none")
        else:
            principal = Principal(name=f"key:{key[:4]}…", role=role)
    request.state.principal = principal
    return principal


def require(role: str):
    """FastAPI dependency factory enforcing a minimum role."""

    def checker(principal: Principal = Depends(resolve_principal)) -> Principal:
        if principal.role == "none":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid X-API-Key")
        if not principal.has(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role '{role}'")
        return principal

    return checker
