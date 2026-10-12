import secrets

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

COOKIE_NAME = "healthcare_session"


def owner_for_key(key: str) -> str:
    settings = get_settings()
    if not settings.API_KEYS:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Configure API_KEYS to enable access"
        )
    for owner, expected in settings.API_KEYS.items():
        if expected and secrets.compare_digest(key.encode(), expected.encode()):
            return owner
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")


async def require_owner(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(HTTPBearer(auto_error=False)),
) -> str:
    key = credentials.credentials if credentials else ""
    if not key:
        key = request.cookies.get(COOKIE_NAME, "")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin not in get_settings().CORS_ORIGINS:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Untrusted origin")
    if not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return owner_for_key(key)
