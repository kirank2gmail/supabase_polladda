"""
data/gcs.py
Optimised caching for SportsPoll usage pattern:
  - Users view leaderboard, past matches, vote for upcoming matches
  - Only votes change data during normal usage
  - Admin writes (results, new matches) are infrequent

THREE TIERS:

  1. SESSION CACHE (st.session_state["_gcs"])
     Loaded once per session per user. Never hits GCS again.
     Tables: users, tournaments, matches, registrations, points
     Invalidation: on explicit admin write to that table

  2. VOTE WRITE-THROUGH + ASYNC GCS
     When user casts/changes vote:
       a. Update local session cache immediately → UI is instant
       b. Write to GCS in background thread → non-blocking
     Other users get the updated votes within 30s (their TTL)

  3. SHORT TTL (30s) for votes
     Votes may be written by other users concurrently.
     30s TTL balances freshness vs GCS round-trips.
     A user's own vote is always fresh (write-through to session).
"""

import json
import threading
import streamlit as st
from pathlib import Path

SESSION_KEY  = "_gcs"
VOTES_TTL    = 30    # seconds — how stale other users' votes can be
SESSION_TBLS = {"users", "tournaments", "matches", "registrations", "points"}


# ── GCS primitives ────────────────────────────────────────────────────────────

def _gcs_configured() -> bool:
    try:
        return bool(st.secrets.get("gcs", {}).get("bucket_name"))
    except Exception:
        return False


@st.cache_resource
def _get_bucket():
    from google.cloud import storage
    from google.oauth2.service_account import Credentials
    sa    = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(dict(sa))
    client = storage.Client(credentials=creds, project=sa["project_id"])
    return client.bucket(st.secrets["gcs"]["bucket_name"])


def _blob(table: str):
    prefix = st.secrets.get("gcs", {}).get("prefix", "sportspoll/")
    return _get_bucket().blob(f"{prefix}{table}.json")


def _fetch(table: str) -> list[dict]:
    """Synchronous GCS read."""
    if _gcs_configured():
        try:
            b = _blob(table)
            return json.loads(b.download_as_text(encoding="utf-8")) if b.exists() else []
        except Exception as e:
            st.warning(f"GCS read error ({table}): {e}")
            return []
    else:
        p = Path(__file__).parent / "store" / f"{table}.json"
        return json.loads(p.read_text()) if p.exists() else []


def _push(table: str, records: list[dict]):
    """Synchronous GCS write."""
    data = json.dumps(records, indent=2, default=str)
    if _gcs_configured():
        try:
            _blob(table).upload_from_string(data, content_type="application/json")
        except Exception as e:
            st.error(f"GCS write error ({table}): {e}")
    else:
        local = Path(__file__).parent / "store"
        local.mkdir(parents=True, exist_ok=True)
        (local / f"{table}.json").write_text(data)


def _push_async(table: str, records: list[dict]):
    """
    Fire-and-forget GCS write in a background thread.
    Returns immediately — does not block Streamlit rendering.
    Safe because GCS writes are atomic (full blob replace).
    """
    # Pass a copy so the list can't be mutated while thread is writing
    data_copy = list(records)
    t = threading.Thread(target=_push, args=(table, data_copy), daemon=True)
    t.start()
    return t   # caller can .join() if they need to wait


# ── Manual TTL cache for votes ───────────────────────────────────────────────
# Unlike @st.cache_data, this lets us inject fresh records immediately after
# a write — so reruns see the new vote with zero lag and no GCS round-trip.
# Other users see the update when their TTL expires (same as before).

import time as _time

_votes_cache: dict = {"data": None, "ts": 0.0}


def _ttl_votes() -> list[dict]:
    """Return cached votes, fetching from GCS if the TTL has expired."""
    if _time.monotonic() - _votes_cache["ts"] > VOTES_TTL or _votes_cache["data"] is None:
        _votes_cache["data"] = _fetch("votes")
        _votes_cache["ts"]   = _time.monotonic()
    return _votes_cache["data"]


def _ttl_votes_set(records: list[dict]):
    """Inject new records into the votes cache — used after a write."""
    _votes_cache["data"] = records
    _votes_cache["ts"]   = _time.monotonic()


def _ttl_votes_clear():
    """Force next read to re-fetch from GCS."""
    _votes_cache["ts"] = 0.0

@st.cache_data(ttl=60, show_spinner=False)
def _ttl_sessions() -> list[dict]:
    return _fetch("sessions")


# ── Session cache helpers ─────────────────────────────────────────────────────

def _sess() -> dict:
    return st.session_state.setdefault(SESSION_KEY, {})


def _sess_get(table: str) -> list[dict]:
    cache = _sess()
    if table not in cache:
        cache[table] = _fetch(table)
    return cache[table]


def _sess_set(table: str, records: list[dict]):
    _sess()[table] = records


def _sess_clear(table: str):
    _sess().pop(table, None)


# ── Public API ────────────────────────────────────────────────────────────────

def read_table(table: str) -> list[dict]:
    """
    Read a table using the appropriate cache tier.

    votes    → 30s TTL; cleared after each vote write once GCS confirms
    sessions → 60s TTL (auth, rarely changes)
    others   → session cache (loaded once, stays for session)
    """
    if table == "votes":    return _ttl_votes()
    if table == "sessions": return _ttl_sessions()
    if table in SESSION_TBLS: return _sess_get(table)
    return _fetch(table)


def write_table(table: str, records: list[dict], async_write: bool = False):
    """
    Write a table to GCS and update the appropriate cache.

    async_write=True  → update local cache instantly, write GCS in background.
                        Use for votes: user sees their vote immediately.

    async_write=False → synchronous write (default).
                        Use for admin operations where consistency matters.

    Cache invalidation:
      votes    → update local session votes + clear TTL cache
                 (so other users see the update within 30s)
      sessions → clear TTL cache
      others   → clear from session cache (reloads on next read)
    """
    if async_write:
        # Inject the new records into the in-process votes cache immediately —
        # all reads on this rerun and the next see the new vote with zero lag.
        # GCS write happens in the background; no join needed.
        if table == "votes":
            _ttl_votes_set(records)
        _push_async(table, records)
    else:
        # Synchronous write — wait for GCS confirmation
        _push(table, records)
        # Invalidate caches
        if table == "votes":
            _ttl_votes_set(records)
            _ttl_votes_clear()   # force re-fetch on next read (sync write = GCS already updated)
        elif table == "sessions":
            _ttl_sessions.clear()
        elif table in SESSION_TBLS:
            _sess_set(table, records)
