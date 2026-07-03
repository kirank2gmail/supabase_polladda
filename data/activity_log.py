"""
data/activity_log.py
User activity logging to the Supabase activity_log table.

Framework-agnostic: the batching queue is a plain process-global list, not
st.session_state, so this works the same whether called from Streamlit or
from the FastAPI service under api/.

Logged events:
  login         — user signed in
  logout        — user signed out (with session duration)
  vote_cast     — user voted on a match
  vote_changed  — user changed their vote

Each record:
  event_id, user_id, user_name, event, timestamp, details (dict, JSONB)
"""

import uuid
from datetime import datetime, timezone
from data.supabase_client import get_client

_activity_queue: list[dict] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())[:8]


def _get_name(user_id: str) -> str:
    try:
        from data.db import get_display_name
        return get_display_name(user_id)
    except Exception:
        return user_id


def _log(user_id: str, event: str, details: dict = None):
    """
    Queue activity record in a process-global list.
    Writes to Supabase only when the queue reaches 5 events or on flush.
    This avoids a write on every vote action.
    """
    try:
        record = {
            "event_id"  : _uid(),
            "user_id"   : user_id,
            "user_name" : _get_name(user_id),
            "event"     : event,
            "timestamp" : _now(),
            "details"   : details or {},
        }
        _activity_queue.append(record)

        # Flush to Supabase when queue has 5+ records, or for login events
        if len(_activity_queue) >= 5 or event == "login":
            _flush()
    except Exception:
        pass


def _flush():
    """Write queued activity records to Supabase in one batch insert."""
    try:
        if not _activity_queue:
            return
        get_client().table("activity_log").insert(_activity_queue).execute()
        _activity_queue.clear()
    except Exception:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def log_login(user_id: str):
    """Call immediately after successful login."""
    _log(user_id, "login", {})


def log_vote_cast(user_id: str, match_id: str, match_title: str,
                  tournament_id: str, vote: str):
    _log(user_id, "vote_cast", {
        "match_id"      : match_id,
        "match_title"   : match_title,
        "tournament_id" : tournament_id,
        "vote"          : vote,
    })


def log_vote_changed(user_id: str, match_id: str, match_title: str,
                     tournament_id: str, old_vote: str, new_vote: str):
    _log(user_id, "vote_changed", {
        "match_id"      : match_id,
        "match_title"   : match_title,
        "tournament_id" : tournament_id,
        "old_vote"      : old_vote,
        "new_vote"      : new_vote,
    })
