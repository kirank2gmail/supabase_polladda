"""
api/routers/auth.py — auth endpoints.

Calls the exact same functions the Streamlit app uses (data/db.py,
utils/session_manager.py, data/activity_log.py) — a token created here is
valid on the Streamlit side too, and vice versa, since both read/write the
same Supabase "sessions" table.
"""

import pytz
from fastapi import APIRouter, Depends, Header, HTTPException

from data.activity_log import log_login
from data.db import (
    admin_exists,
    change_password,
    create_user,
    get_user_by_name,
    is_legacy_password,
    update_nickname,
    update_user_timezone,
    verify_password,
)
from utils.session_manager import create_session, delete_session
from utils.timezone import COMMON_TIMEZONES

from api.deps import get_current_user
from api.schemas import (
    BootstrapAdminRequest,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    NicknameUpdateRequest,
    TimezoneListResponse,
    TimezoneUpdateRequest,
    UserOut,
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    user = get_user_by_name(body.username.strip())
    if not user or not verify_password(user["user_id"], body.password):
        raise HTTPException(status_code=401, detail="Username or password is incorrect.")

    token = create_session(user["user_id"])
    log_login(user["user_id"])

    return LoginResponse(
        token=token,
        user=UserOut(**user),
        must_change_password=bool(user.get("must_change_password")),
        is_legacy_password=is_legacy_password(user["user_id"]),
    )


@router.post("/bootstrap-admin", response_model=LoginResponse)
def bootstrap_admin(body: BootstrapAdminRequest):
    """Only works once — before any admin exists. Mirrors app.py's
    show_login first-run 'create the first admin' path, for API-only local
    dev/testing without needing to run Streamlit first."""
    if admin_exists():
        raise HTTPException(status_code=409, detail="An admin already exists.")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    user = create_user(body.username.strip(), body.password, role="admin", created_by="system")
    change_password(user["user_id"], body.password)
    user = get_user_by_name(body.username.strip())  # re-fetch: must_change_password now False

    token = create_session(user["user_id"])
    log_login(user["user_id"])

    return LoginResponse(
        token=token,
        user=UserOut(**user),
        must_change_password=bool(user.get("must_change_password")),
        is_legacy_password=is_legacy_password(user["user_id"]),
    )


@router.post("/change-password")
def change_password_endpoint(
    body: ChangePasswordRequest, user: dict = Depends(get_current_user)
):
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if body.current_password is not None:
        if not verify_password(user["user_id"], body.current_password):
            raise HTTPException(status_code=403, detail="Current password is incorrect.")
    change_password(user["user_id"], body.new_password)
    return {"ok": True}


@router.post("/logout")
def logout(authorization: str = Header(default="")):
    """Token read directly (not via get_current_user) so an already-invalid
    or expired token still 'succeeds' at logging out."""
    if authorization.startswith("Bearer "):
        delete_session(authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(**user)


@router.patch("/me/nickname")
def update_nickname_endpoint(
    body: NicknameUpdateRequest, user: dict = Depends(get_current_user)
):
    if not body.nickname.strip():
        raise HTTPException(status_code=400, detail="Nickname cannot be empty.")
    update_nickname(user["user_id"], body.nickname.strip())
    return {"ok": True}


@router.patch("/me/timezone")
def update_timezone_endpoint(
    body: TimezoneUpdateRequest, user: dict = Depends(get_current_user)
):
    update_user_timezone(user["user_id"], body.timezone)
    return {"ok": True}


@router.get("/timezones", response_model=TimezoneListResponse)
def list_timezones(user: dict = Depends(get_current_user)):
    all_tz = COMMON_TIMEZONES + [t for t in pytz.all_timezones if t not in COMMON_TIMEZONES]
    return TimezoneListResponse(common=COMMON_TIMEZONES, all=all_tz)
