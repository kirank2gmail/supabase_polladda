"""
utils/session_manager.py
Server-side session tokens stored in Supabase.

Session token is placed in the URL as ?s=TOKEN.
URL params persist as long as the browser tab is open or the URL is bookmarked.
Closing a tab and reopening the base URL loses the token — but browsers that
restore previous sessions (Chrome, Edge, Firefox) will restore the URL including
the token, giving silent login.

For guaranteed persistence across tab close: user ticks "Keep me signed in"
on the login form, which sets the token in the URL. Browsers that restore
sessions pick this up automatically.

Sessions expire after SESSION_DAYS. Expired sessions are cleaned up
opportunistically on read.
"""

import uuid
import streamlit as st
from datetime import datetime, timedelta, timezone
from data.supabase_client import read_table, get_client, ttl_sessions_clear

SESSION_DAYS  = 365    # 1 year
SESSION_PARAM = "s"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_valid() -> list[dict]:
    """Read sessions table (60s TTL cache), dropping expired entries."""
    sessions = read_table("sessions")
    now      = datetime.now(timezone.utc)
    valid, expired_tokens = [], []
    for s in sessions:
        try:
            exp = datetime.fromisoformat(s["expires"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now:
                valid.append(s)
            else:
                expired_tokens.append(s["token"])
        except Exception:
            if s.get("token"):
                expired_tokens.append(s["token"])
    if expired_tokens:
        get_client().table("sessions").delete().in_("token", expired_tokens).execute()
        ttl_sessions_clear()
    return valid


def create_session(user_id: str) -> str:
    """Create a server-side session, return the token."""
    sb      = get_client()
    token   = str(uuid.uuid4()).replace("-", "")
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    # One session per user — remove any existing one(s) first
    sb.table("sessions").delete().eq("user_id", user_id).execute()
    sb.table("sessions").insert({
        "token"      : token,
        "user_id"    : user_id,
        "created_at" : _now(),
        "expires"    : expires,
    }).execute()
    ttl_sessions_clear()
    return token


def validate_session(token: str) -> str | None:
    """
    Validate token, return user_id if valid else None.
    Targeted single-row lookup — this runs on every page rerun, so an
    indexed .eq() lookup is simpler and cheaper than scanning a cached
    full table.
    """
    if not token:
        return None
    resp = get_client().table("sessions").select("user_id,expires") \
        .eq("token", token).limit(1).execute()
    rows = resp.data or []
    if not rows:
        return None
    row = rows[0]
    try:
        exp = datetime.fromisoformat(row["expires"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= datetime.now(timezone.utc):
            return None
    except Exception:
        return None
    return row["user_id"]


def delete_session(token: str):
    """Delete a session (sign out)."""
    if not token:
        return
    try:
        get_client().table("sessions").delete().eq("token", token).execute()
        ttl_sessions_clear()
    except Exception:
        pass


def get_session_token() -> str | None:
    """Read session token from URL query params."""
    return st.query_params.get(SESSION_PARAM)


def set_session_token(token: str):
    """Write session token to URL query params."""
    st.query_params[SESSION_PARAM] = token


def clear_session_token():
    """Remove session token from URL."""
    if SESSION_PARAM in st.query_params:
        del st.query_params[SESSION_PARAM]
