"""
utils/cookie_auth.py
Persistent login cookie using extra-streamlit-components CookieManager.

Secrets required:
    [cookie]
    encryption_key = "any-long-random-string"
"""

import json
import hashlib
import base64
import streamlit as st
from datetime import datetime, timedelta, timezone

COOKIE_NAME  = "sportspoll_session"
COOKIE_DAYS  = 7


def _fernet():
    from cryptography.fernet import Fernet
    raw = st.secrets.get("cookie", {}).get("encryption_key", "changeme")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def _get_manager():
    if "_cookie_mgr" not in st.session_state:
        from extra_streamlit_components import CookieManager
        st.session_state["_cookie_mgr"] = CookieManager(prefix="ssp_")
    return st.session_state["_cookie_mgr"]


def save_session_cookie(user_id: str):
    try:
        expires = (datetime.now(timezone.utc) + timedelta(days=COOKIE_DAYS)).isoformat()
        payload = json.dumps({"user_id": user_id, "expires": expires})
        token   = _fernet().encrypt(payload.encode()).decode()
        mgr     = _get_manager()
        mgr.set(COOKIE_NAME, token,
                expires_at=datetime.now() + timedelta(days=COOKIE_DAYS),
                key=f"set_{COOKIE_NAME}")
    except Exception:
        pass


def load_session_cookie() -> str | None:
    try:
        mgr   = _get_manager()
        token = mgr.get(COOKIE_NAME)
        if not token:
            return None
        payload = json.loads(_fernet().decrypt(token.encode()).decode())
        expires = datetime.fromisoformat(payload["expires"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            clear_session_cookie()
            return None
        return payload.get("user_id")
    except Exception:
        return None


def clear_session_cookie():
    try:
        mgr = _get_manager()
        mgr.delete(COOKIE_NAME, key=f"del_{COOKIE_NAME}")
    except Exception:
        pass
