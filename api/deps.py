"""
api/deps.py — FastAPI auth dependencies.

Reuses the exact same session store as the Streamlit app
(utils/session_manager.py's create_session/validate_session/delete_session,
backed by the Supabase "sessions" table) — a token created via Streamlit's
login form or the API's /auth/login is valid on either surface.
"""

from fastapi import Depends, Header, HTTPException

from data.db import get_user_by_id
from utils.session_manager import validate_session


def get_bearer_token(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(authorization: str = Header(default="")) -> dict:
    token = get_bearer_token(authorization)
    user_id = validate_session(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    return user
