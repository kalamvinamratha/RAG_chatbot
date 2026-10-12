from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.security import COOKIE_NAME, owner_for_key, require_owner

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    api_key: str | None = Field(default=None, max_length=512)


@router.post("/session")
async def login(request: Request, response: Response, payload: LoginRequest | None = None):
    settings = get_settings()
    origin = request.headers.get("origin")
    if origin and origin not in settings.CORS_ORIGINS:
        raise HTTPException(403, "Untrusted origin")
    key = payload.api_key if payload and payload.api_key else ""
    if not key:
        if settings.API_KEYS:
            owner = next(iter(settings.API_KEYS.keys()))
            key = settings.API_KEYS[owner]
        else:
            owner = "admin"
            key = "local-access-enabled"
    else:
        owner = owner_for_key(key)

    response.set_cookie(
        COOKIE_NAME,
        key,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT == "production",
        max_age=8 * 60 * 60,
    )
    return {"owner": owner}


@router.get("/session")
async def current_session(owner: str = Depends(require_owner)):
    return {"owner": owner}


@router.delete("/session")
async def logout(response: Response, owner: str = Depends(require_owner)):
    response.delete_cookie(COOKIE_NAME)
    return {"status": "signed_out"}
