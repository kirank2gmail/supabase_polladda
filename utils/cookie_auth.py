"""
utils/cookie_auth.py
Persistent login using browser localStorage via a custom Streamlit component.

localStorage survives tab close/reopen and browser restart on same device.
The component is an invisible iframe (height=0) using declare_component.

File layout required in repo:
  utils/
    cookie_auth.py          ← this file
    session_component/
      index.html            ← the iframe component

Secrets required:
    [cookie]
    encryption_key = "any-long-random-string"
"""

import os
import json
import hashlib
import base64
import streamlit as st
import streamlit.components.v1 as stc
from datetime import datetime, timedelta, timezone

COOKIE_DAYS   = 7
_COMP_DIR     = os.path.join(os.path.dirname(__file__), "session_component")
_COMP_KEY     = "__sportspoll_sess__"


# ── Encryption ────────────────────────────────────────────────────────────────

def _fernet():
    from cryptography.fernet import Fernet
    raw = st.secrets.get("cookie", {}).get("encryption_key", "changeme-please")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def _encrypt(data: str) -> str:
    return _fernet().encrypt(data.encode()).decode()


def _decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


# ── Component (declared once per process) ─────────────────────────────────────

@st.cache_resource
def _declare():
    return stc.declare_component("sportspoll_session", path=_COMP_DIR)


# ── Public API ────────────────────────────────────────────────────────────────

def load_session_cookie() -> str | None:
    """
    Render the component once per run (read mode).
    Result cached in session_state so save/clear don't re-render it.
    Returns user_id if valid session exists, else None.
    """
    # Only render the read component once per script run
    if "_sess_raw" not in st.session_state:
        comp = _declare()
        raw  = comp(cmd="read", value="", key="sess_read", default=None)
        st.session_state["_sess_raw"] = raw or ""
    else:
        raw = st.session_state["_sess_raw"]

    if not raw:
        return None
    try:
        payload = json.loads(_decrypt(raw))
        expires = datetime.fromisoformat(payload["expires"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            clear_session_cookie()
            return None
        return payload.get("user_id")
    except Exception:
        return None


def save_session_cookie(user_id: str):
    """Write encrypted session to localStorage after successful login."""
    expires = (datetime.now(timezone.utc) + timedelta(days=COOKIE_DAYS)).isoformat()
    payload = json.dumps({"user_id": user_id, "expires": expires})
    token   = _encrypt(payload)
    comp    = _declare()
    comp(cmd="set", value=token, key="sess_set", default=None)
    # Cache the new value so subsequent reads in same run are consistent
    st.session_state["_sess_raw"] = token


def clear_session_cookie():
    """Clear localStorage session on sign-out."""
    comp = _declare()
    comp(cmd="clear", value="", key="sess_clear", default=None)
    st.session_state.pop("_sess_raw", None)
