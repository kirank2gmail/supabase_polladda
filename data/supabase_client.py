"""
data/supabase_client.py — Supabase Postgres backend for the live app.

Framework-agnostic: safe to import from Streamlit (app.py, pages/*.py,
admin/dashboard.py) or from a stateless service like the FastAPI app under
api/ — nothing here requires a live Streamlit runtime.

Replaces data/gcs.py. data/gcs.py itself is kept, unmodified, purely as the
source reader for the one-time GCS -> Supabase migration script
(utils/migrate_to_supabase.py); nothing in the live app imports it.

Same three-tier caching design as the old gcs.py:
  1. SESSION CACHE (process-global dict) — users, tournaments, matches,
     registrations, points. Loaded once per process; invalidated on write.
     Was st.session_state-scoped (one copy per Streamlit browser tab); now a
     plain module-level dict (one shared copy per process) — safe because
     every write path already calls sess_clear(table) right after writing,
     and this app's scale means a single shared warm cache is strictly
     better than N per-session copies of the same data.
  2. VOTES — 30s TTL, in-process dict, write-through on this session's own
     write so the user sees their own vote instantly.
  3. SESSIONS — 60s st.cache_data TTL.
  penalties / activity_log are always fetched fresh (uncached), same as
  today. match_players is never routed through read_table() at all — every
  caller queries it directly, scoped by tournament_id/match_id, so it is
  always fully fresh (single source of truth for points calculation).

Config: reads [supabase].url/.key from st.secrets when Streamlit is
available (.streamlit/secrets.toml, unchanged for the Streamlit app), else
falls back to the SUPABASE_URL/SUPABASE_KEY environment variables (used by
the FastAPI service, which has no secrets.toml).
"""

import os
import time as _time
from functools import lru_cache
import streamlit as st

VOTES_TTL    = 30    # seconds — how stale other users' votes can be
SESSION_TBLS = {"users", "tournaments", "matches", "registrations", "points"}
PAGE_SIZE    = 1000  # PostgREST's default max rows per response — anything
                      # that can return more rows than this MUST paginate via
                      # select_all(), or results are silently truncated.


# ── Config ────────────────────────────────────────────────────────────────────

def _secret(section: str, key: str, env_var: str) -> str:
    """Try st.secrets first (keeps .streamlit/secrets.toml working unchanged
    for the Streamlit app); fall back to an env var (for the API process,
    which has no secrets.toml)."""
    try:
        val = st.secrets[section][key]
        if val:
            return val
    except Exception:
        pass
    val = os.environ.get(env_var)
    if not val:
        raise RuntimeError(
            f"Missing config: st.secrets['{section}']['{key}'] or ${env_var}"
        )
    return val


# ── Client ────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_client():
    from supabase import create_client
    url = _secret("supabase", "url", "SUPABASE_URL")
    key = _secret("supabase", "key", "SUPABASE_KEY")
    return create_client(url, key)


def select_all(build_query) -> list[dict]:
    """
    Run a Supabase select to completion, paginating via .range() so results
    are never silently capped by PostgREST's default max-rows limit
    (1000 by default on Supabase — any table/filter that can return more
    rows than that WILL be truncated by a bare .execute() otherwise).

    build_query: zero-arg callable returning a FRESH, filtered (not yet
    executed) query builder each time it's called, e.g.:
        select_all(lambda: get_client().table("votes").select("*").eq("tournament_id", tid))
    (query builders are single-use, so we need a fresh one per page.)
    """
    rows: list[dict] = []
    offset = 0
    while True:
        page = build_query().range(offset, offset + PAGE_SIZE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def _raw_fetch(table: str) -> list[dict]:
    """Synchronous full-table read, paginated."""
    rows = select_all(lambda: get_client().table(table).select("*"))
    if table == "matches":
        # Single normalization choke point: Postgres TIME columns come back
        # as "HH:MM:SS" from PostgREST; the rest of the app (utils/timezone.py
        # strptime calls, string-concat sorting, match_players._match_ist_label)
        # expects exactly "HH:MM".
        for m in rows:
            if m.get("start_time"):
                m["start_time"] = m["start_time"][:5]
    return rows


# ── Votes: 30s TTL + write-through ───────────────────────────────────────────

_votes_cache: dict = {"data": None, "ts": 0.0}


def _ttl_votes() -> list[dict]:
    if _votes_cache["data"] is None or _time.monotonic() - _votes_cache["ts"] > VOTES_TTL:
        _votes_cache["data"] = _raw_fetch("votes")
        _votes_cache["ts"]   = _time.monotonic()
    return _votes_cache["data"]


def ttl_votes_write_through(user_id: str, match_id: str, record: dict):
    """Patch the in-memory votes cache immediately after this session's own write."""
    data = [v for v in (_votes_cache["data"] or [])
            if not (v["user_id"] == user_id and v["match_id"] == match_id)]
    data.append(record)
    _votes_cache["data"] = data
    _votes_cache["ts"]   = _time.monotonic()


def ttl_votes_clear():
    """Force next read to re-fetch from Supabase."""
    _votes_cache["ts"] = 0.0


# ── Sessions: 60s TTL ─────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _ttl_sessions() -> list[dict]:
    return _raw_fetch("sessions")


def ttl_sessions_clear():
    _ttl_sessions.clear()


# ── Process-global full-table cache ──────────────────────────────────────────
# Was st.session_state-scoped (one copy per Streamlit browser tab); now a
# plain module-level dict — see the module docstring for why this is safe.

_process_cache: dict = {}


def _sess() -> dict:
    return _process_cache


def _sess_get(table: str) -> list[dict]:
    cache = _sess()
    if table not in cache:
        cache[table] = _raw_fetch(table)
    return cache[table]


def sess_clear(table: str):
    _sess().pop(table, None)


# ── Public read API ───────────────────────────────────────────────────────────

def read_table(table: str) -> list[dict]:
    """
    Read a table using the appropriate cache tier.

    votes    -> 30s TTL; cleared/write-through on write
    sessions -> 60s TTL (auth, rarely changes)
    users/tournaments/matches/registrations/points -> session cache
    penalties/activity_log -> always fresh, uncached
    """
    if table == "votes":      return _ttl_votes()
    if table == "sessions":   return _ttl_sessions()
    if table in SESSION_TBLS: return _sess_get(table)
    return _raw_fetch(table)
