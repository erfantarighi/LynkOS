import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import create_access_token, current_user, hash_password, verify_password
from app.config import Settings, get_settings
from app.credentials import current_admin_hash, set_admin_hash
from app.models import ChangePasswordRequest, OkResponse, Token
from app.ratelimit import login_limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])
_auth_log = logging.getLogger("lynkos.auth")


def _client_ip(request: Request) -> str:
    # Prefer X-Forwarded-For when we trust the proxy (nginx). For direct
    # uvicorn bind we fall back to the socket peer.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Token:
    ip = _client_ip(request)
    wait = login_limiter.remaining_lockout(ip)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {wait}s.",
        )
    if form.username != settings.admin_username or not verify_password(
        form.password, current_admin_hash()
    ):
        login_limiter.record_failure(ip)
        # Logged in a format fail2ban can parse: see deploy/fail2ban/filter.d/lynkos.conf
        _auth_log.warning("auth_failure ip=%s user=%s", ip, form.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    login_limiter.record_success(ip)
    return Token(access_token=create_access_token(form.username, settings))


@router.get("/me")
async def me(user: Annotated[str, Depends(current_user)]) -> dict[str, str]:
    return {"username": user}


@router.post("/change-password", response_model=OkResponse)
async def change_password(
    req: ChangePasswordRequest,
    user: Annotated[str, Depends(current_user)],
) -> OkResponse:
    if not verify_password(req.old_password, current_admin_hash()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    if req.new_password == req.old_password:
        raise HTTPException(status_code=400, detail="New password must differ from old one")
    set_admin_hash(hash_password(req.new_password))
    return OkResponse(detail="password changed")
