"""
data/db.py — Data access layer (Supabase Postgres backend).

Every public function keeps the exact signature it had under the old
GCS-JSON backend, so pages/*.py, admin/dashboard.py and app.py did not need
to change except for the users.name -> username and
registrations.reg_id -> registration_id field renames (see admin/dashboard.py).

  - No registration required: users can vote in any tournament directly
  - Tournament ID uniqueness enforced
  - Match ID uniqueness enforced within tournament
  - delete_tournament / delete_match / delete_user rely on ON DELETE CASCADE
    in the Supabase schema — a single DELETE on the parent row cleans up
    every dependent row (votes, points, match_players, registrations,
    sessions, penalties).
  - nickname defaults to first name
  - register_user kept for compatibility but auto-called on first vote
"""

import hashlib
import uuid
from datetime import datetime, timezone
from data.supabase_client import (
    read_table, get_client, sess_clear,
    ttl_votes_clear, ttl_votes_write_through, ttl_sessions_clear,
)


def _now():          return datetime.now(timezone.utc).isoformat()
def _uid():           return str(uuid.uuid4())[:8]
def _hash(pw: str):  return hashlib.sha256(pw.encode()).hexdigest()   # legacy SHA-256
def _sb():            return get_client()

def _hash_bcrypt(pw: str) -> str:
    import bcrypt
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def _is_bcrypt(h: str) -> bool:
    return h.startswith("$2b$") or h.startswith("$2a$")


# ── Users ─────────────────────────────────────────────────────────────────────

def get_all_users() -> list[dict]:
    return read_table("users")

def get_user_by_id(user_id: str) -> dict | None:
    return next((u for u in read_table("users") if u["user_id"] == user_id), None)

def get_user_by_name(name: str) -> dict | None:
    return next((u for u in read_table("users")
                 if u["username"].lower() == name.lower()), None)

def get_display_name(user_id: str) -> str:
    u    = get_user_by_id(user_id)
    if not u: return user_id
    nick = (u.get("nickname") or "").strip()
    return nick if nick else u["user_id"]

def admin_exists() -> bool:
    return any(u.get("role") == "admin" for u in read_table("users"))

def _first_name(name: str) -> str:
    parts = name.strip().split()
    return parts[0].capitalize() if parts else name.strip()

def create_user(name: str, password: str, role: str = "user",
                created_by: str = "admin") -> dict:
    uid  = _uid()
    user = {
        "user_id"             : uid,
        "username"            : name,
        "nickname"            : _first_name(name),   # first name, not user_id
        "role"                : role,
        "password_hash"       : _hash(password),
        "must_change_password": True,
        "timezone"            : "Asia/Kolkata",
        "created_by"          : created_by,
        "created_at"          : _now(),
    }
    _sb().table("users").insert(user).execute()
    sess_clear("users")
    return user

def verify_password(user_id: str, password: str) -> bool:
    """Supports both bcrypt (new) and SHA-256 (legacy)."""
    import bcrypt
    u = get_user_by_id(user_id)
    if not u: return False
    h = u.get("password_hash", "")
    if _is_bcrypt(h):
        return bcrypt.checkpw(password.encode(), h.encode())
    return h == _hash(password)   # legacy SHA-256

def is_legacy_password(user_id: str) -> bool:
    """True if user still has a SHA-256 password hash."""
    u = get_user_by_id(user_id)
    return bool(u and not _is_bcrypt(u.get("password_hash", "")))

def change_password(user_id: str, new_password: str):
    """Always stores new passwords as bcrypt."""
    _sb().table("users").update({
        "password_hash"       : _hash_bcrypt(new_password),
        "must_change_password": False,
    }).eq("user_id", user_id).execute()
    sess_clear("users")

def update_nickname(user_id: str, nickname: str):
    _sb().table("users").update({"nickname": nickname.strip()}) \
        .eq("user_id", user_id).execute()
    sess_clear("users")

def update_user_timezone(user_id: str, tz: str):
    _sb().table("users").update({"timezone": tz}).eq("user_id", user_id).execute()
    sess_clear("users")

def set_user_role(user_id: str, role: str):
    _sb().table("users").update({"role": role}).eq("user_id", user_id).execute()
    sess_clear("users")

def force_password_change(user_id: str):
    """Force must_change_password=True — used by admin password resets."""
    _sb().table("users").update({"must_change_password": True}) \
        .eq("user_id", user_id).execute()
    sess_clear("users")

def delete_user(user_id: str):
    """ON DELETE CASCADE removes votes/points/registrations/match_players/
    sessions/penalties for this user automatically."""
    _sb().table("users").delete().eq("user_id", user_id).execute()
    sess_clear("users"); sess_clear("registrations"); sess_clear("points")
    ttl_votes_clear(); ttl_sessions_clear()


# ── Tournaments ───────────────────────────────────────────────────────────────

def get_tournaments(status: str = None) -> list[dict]:
    ts = read_table("tournaments")
    return [t for t in ts if t.get("status") == status] if status else ts

def get_tournament(tid: str) -> dict | None:
    return next((t for t in read_table("tournaments")
                 if t["tournament_id"] == tid), None)

def tournament_id_exists(tid: str) -> bool:
    return get_tournament(tid) is not None

def create_tournament(data: dict):
    _sb().table("tournaments").insert({
        "tournament_id" : data["tournament_id"],
        "name"          : data["name"],
        "sport"         : data["sport"],
        "start_date"    : data["start_date"],
        "status"        : "upcoming",
        "allowed_misses": int(data["allowed_misses"]),
        "penalty_points": float(data["penalty_points"]),
        "created_by"    : data.get("created_by", "admin"),
        "created_at"    : _now(),
    }).execute()
    sess_clear("tournaments")

def update_tournament_status(tid: str, status: str):
    _sb().table("tournaments").update({"status": status}) \
        .eq("tournament_id", tid).execute()
    sess_clear("tournaments")

def delete_tournament(tid: str):
    """Delete tournament — ON DELETE CASCADE removes matches (which in turn
    cascades to votes/points/match_players), registrations and penalties."""
    _sb().table("tournaments").delete().eq("tournament_id", tid).execute()
    sess_clear("tournaments"); sess_clear("matches")
    sess_clear("registrations"); sess_clear("points")
    ttl_votes_clear()


# ── Registrations (auto — no user action needed) ──────────────────────────────

def get_registrations(tid: str) -> list[dict]:
    return [r for r in read_table("registrations") if r["tournament_id"] == tid]

def is_registered(user_id: str, tid: str) -> bool:
    return any(r["user_id"] == user_id and r["tournament_id"] == tid
               for r in read_table("registrations"))

def ensure_registered(user_id: str, tid: str):
    """Auto-register user when they first vote in a tournament."""
    if not is_registered(user_id, tid):
        _sb().table("registrations").insert({
            "registration_id": _uid(),
            "user_id"        : user_id,
            "tournament_id"  : tid,
            "registered_at"  : _now(),
        }).execute()
        sess_clear("registrations")

# Keep for compatibility
def register_user(user_id: str, tid: str):
    ensure_registered(user_id, tid)


# ── match_players ─────────────────────────────────────────────────────────────
# match_players — one record per (player, match).
# status: "voted" | "missed" | "quit" | "not_started"
#   voted       — player cast a vote before cutoff
#   missed      — player was active but did not vote
#   quit        — player quit before this match start
#   not_started — match was before player's first vote (excluded from misses)
#
# vote field stores the actual vote string when status="voted", else "".
# This is the single source of truth for points calculation.
# All reads/writes go straight to Supabase, scoped by match_id/tournament_id
# — never routed through the session cache — so points calculation always
# sees a fully fresh, consistent table.

def get_match_players(match_id: str = None, tournament_id: str = None,
                       user_id: str = None) -> list[dict]:
    """Read match_players fresh from Supabase. Filter by any combination of keys."""
    q = get_client().table("match_players").select("*")
    if match_id:      q = q.eq("match_id", match_id)
    if tournament_id: q = q.eq("tournament_id", tournament_id)
    if user_id:       q = q.eq("user_id", user_id)
    return q.execute().data or []

def upsert_match_player(match_id: str, tournament_id: str,
                         user_id: str, status: str,
                         vote: str = "", quit_at: str = ""):
    """
    Insert or update a match_player record.
    Explicit select-then-branch (not a blind upsert) so mp_id/created_at
    stay stable across re-votes.
    """
    sb = get_client()
    existing = sb.table("match_players").select("mp_id") \
        .eq("user_id", user_id).eq("match_id", match_id) \
        .limit(1).execute().data
    if existing:
        sb.table("match_players").update({
            "status": status, "vote": vote, "quit_at": quit_at,
        }).eq("mp_id", existing[0]["mp_id"]).execute()
    else:
        sb.table("match_players").insert({
            "mp_id"        : _uid(),
            "match_id"     : match_id,
            "tournament_id": tournament_id,
            "user_id"      : user_id,
            "status"       : status,
            "vote"         : vote,
            "quit_at"      : quit_at,
            "created_at"   : _now(),
        }).execute()

def write_match_players_batch(records: list[dict]):
    """
    Write multiple match_player records at once. Upserts by (user_id, match_id).
    Used by recalculate_tournament and migration.
    """
    sb = get_client()
    match_ids = list({r["match_id"] for r in records})
    existing  = (sb.table("match_players").select("mp_id,user_id,match_id")
                 .in_("match_id", match_ids).execute().data
                 if match_ids else [])
    key_map = {(r["user_id"], r["match_id"]): r["mp_id"] for r in existing}

    updates, inserts = [], []
    for rec in records:
        key = (rec["user_id"], rec["match_id"])
        if key in key_map:
            row = {k: v for k, v in rec.items() if k not in ("mp_id", "created_at")}
            updates.append((key_map[key], row))
        else:
            rec = dict(rec)
            rec.setdefault("mp_id", _uid())
            rec.setdefault("created_at", _now())
            inserts.append(rec)

    for mp_id, row in updates:
        sb.table("match_players").update(row).eq("mp_id", mp_id).execute()
    for i in range(0, len(inserts), 500):
        sb.table("match_players").insert(inserts[i:i + 500]).execute()

def delete_match_players_for_match(match_id: str):
    """Remove all match_player records for a match (used when rebuilding)."""
    get_client().table("match_players").delete().eq("match_id", match_id).execute()


# ── Matches ───────────────────────────────────────────────────────────────────

def get_matches(tournament_id: str = None, status: str = None) -> list[dict]:
    ms = read_table("matches")
    if tournament_id: ms = [m for m in ms if m["tournament_id"] == tournament_id]
    if status:        ms = [m for m in ms if m.get("status") == status]
    # Sort by date + time
    ms.sort(key=lambda m: m.get("match_date","") + " " + m.get("start_time",""))
    return ms

def get_match(match_id: str) -> dict | None:
    return next((m for m in read_table("matches") if m["match_id"] == match_id), None)

def match_id_exists_in_tournament(match_id: str, tournament_id: str) -> bool:
    return any(m["match_id"] == match_id and m["tournament_id"] == tournament_id
               for m in read_table("matches"))

def create_match(data: dict):
    _sb().table("matches").insert({
        "match_id"     : data["match_id"],
        "tournament_id": data["tournament_id"],
        "title"        : data["title"],
        "location"     : data["location"],
        "match_date"   : data["match_date"],
        "start_time"   : data["start_time"],
        "timezone"     : data["timezone"],
        "options"      : data["options"],
        "scoring_mode" : data.get("scoring_mode", "ratio"),
        "fixed_odds"   : float(data.get("fixed_odds", 1.0)),
        "poll_mode"    : data.get("poll_mode", "closed"),
        "status"       : "upcoming",
        "result"       : "",
        "created_by"   : data.get("created_by", "admin"),
        "created_at"   : _now(),
    }).execute()
    sess_clear("matches")

def bulk_create_matches(tid: str, rows: list[dict], created_by: str):
    payload = [{
        "match_id"     : r["match_id"],
        "tournament_id": tid,
        "title"        : r["title"],
        "location"     : r["location"],
        "match_date"   : r["match_date"],
        "start_time"   : r["start_time"],
        "timezone"     : r["timezone"],
        "options"      : r["options"],
        "scoring_mode" : r.get("scoring_mode", "ratio"),
        "fixed_odds"   : float(r.get("fixed_odds", 1.0)),
        "poll_mode"    : r.get("poll_mode", "closed"),
        "status"       : "upcoming",
        "result"       : "",
        "created_by"   : created_by,
        "created_at"   : _now(),
    } for r in rows]
    if payload:
        _sb().table("matches").insert(payload).execute()
    sess_clear("matches")

def update_match_result(match_id: str, result: str):
    _sb().table("matches").update({"result": result, "status": "completed"}) \
        .eq("match_id", match_id).execute()
    sess_clear("matches")

def mark_match_abandoned(match_id: str):
    """No voters — mark as abandoned. No points calculated, misses not counted."""
    _sb().table("matches").update({"result": "abandoned", "status": "abandoned"}) \
        .eq("match_id", match_id).execute()
    sess_clear("matches")
    # Clear any previously calculated points for this match
    _sb().table("points").delete().eq("match_id", match_id).execute()
    sess_clear("points")

def delete_match(match_id: str):
    """ON DELETE CASCADE removes votes/points/match_players for this match."""
    _sb().table("matches").delete().eq("match_id", match_id).execute()
    sess_clear("matches"); sess_clear("points")
    ttl_votes_clear()


# ── Votes ─────────────────────────────────────────────────────────────────────

def get_votes(match_id: str = None, tournament_id: str = None) -> list[dict]:
    vs = read_table("votes")
    if match_id:      vs = [v for v in vs if v["match_id"] == match_id]
    if tournament_id: vs = [v for v in vs if v["tournament_id"] == tournament_id]
    return vs

def get_user_vote(user_id: str, match_id: str) -> dict | None:
    return next((v for v in read_table("votes")
                 if v["user_id"] == user_id and v["match_id"] == match_id), None)

def cast_vote(user_id: str, match_id: str, tid: str, vote: str):
    ensure_registered(user_id, tid)   # auto-register on first vote
    upsert_match_player(match_id, tid, user_id, status="voted", vote=vote)
    record = {
        "vote_id"      : _uid(), "user_id": user_id,
        "match_id"     : match_id, "tournament_id": tid,
        "vote"         : vote, "voted_at": _now(),
        "updated_at"   : None, "update_count": 0,
    }
    get_client().table("votes").upsert(record, on_conflict="user_id,match_id").execute()
    ttl_votes_write_through(user_id, match_id, record)

def update_vote(user_id: str, match_id: str, new_vote: str):
    existing  = get_user_vote(user_id, match_id) or {}
    cur_count = int(existing.get("update_count", 0))
    voted_at  = existing.get("voted_at") or _now()
    tid       = existing.get("tournament_id", "")

    sb = get_client()
    sb.table("match_players").update({"vote": new_vote}) \
        .eq("user_id", user_id).eq("match_id", match_id).execute()

    record = {
        "vote_id"      : existing.get("vote_id") or _uid(),
        "user_id"      : user_id, "match_id": match_id, "tournament_id": tid,
        "vote"         : new_vote, "voted_at": voted_at,
        "updated_at"   : _now(), "update_count": cur_count + 1,
    }
    sb.table("votes").upsert(record, on_conflict="user_id,match_id").execute()
    ttl_votes_write_through(user_id, match_id, record)

def delete_vote(user_id: str, match_id: str):
    get_client().table("votes").delete() \
        .eq("user_id", user_id).eq("match_id", match_id).execute()
    ttl_votes_clear()


# ── Points ────────────────────────────────────────────────────────────────────

def get_points(tournament_id: str = None, user_id: str = None) -> list[dict]:
    ps = read_table("points")
    if tournament_id: ps = [p for p in ps if p["tournament_id"] == tournament_id]
    if user_id:       ps = [p for p in ps if p["user_id"] == user_id]
    return ps

def save_points_batch(records: list[dict]):
    now = _now()
    payload = [{
        "point_id"      : _uid(),
        "user_id"       : r["user_id"],
        "match_id"      : r["match_id"],
        "tournament_id" : r["tournament_id"],
        "base_points"   : r.get("base_points",    0),
        "penalty_points": r.get("penalty_points", 0),
        "bonus_points"  : r.get("bonus_points",   0),
        "total_points"  : r.get("total_points",   0),
        "note"          : r.get("note",           ""),
        "calculated_at" : now,
    } for r in records]
    sb = get_client()
    for i in range(0, len(payload), 500):
        sb.table("points").insert(payload[i:i + 500]).execute()
    sess_clear("points")

def delete_match_points(match_id: str):
    get_client().table("points").delete().eq("match_id", match_id).execute()
    sess_clear("points")


# ── Penalties ─────────────────────────────────────────────────────────────────

def get_penalties(tournament_id: str) -> list[dict]:
    """Return all manual penalties for a tournament, newest first."""
    return get_client().table("penalties").select("*") \
        .eq("tournament_id", tournament_id) \
        .order("created_at", desc=True).execute().data or []


def add_penalty(tournament_id: str, user_id: str,
                points: float, reason: str) -> dict:
    """
    Add a manual penalty.
    points is stored as a positive number — it flows to the bank.
    """
    record = {
        "penalty_id"   : _uid(),
        "tournament_id": tournament_id,
        "user_id"      : user_id,
        "points"       : abs(float(points)),   # always stored positive
        "reason"       : reason.strip(),
        "created_at"   : _now(),
    }
    get_client().table("penalties").insert(record).execute()
    return record


def delete_penalty(penalty_id: str):
    get_client().table("penalties").delete().eq("penalty_id", penalty_id).execute()
