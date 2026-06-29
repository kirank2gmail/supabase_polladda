"""
data/db.py — Data access layer.
Changes:
  - No registration required: users can vote in any tournament directly
  - Tournament ID uniqueness enforced
  - Match ID uniqueness enforced within tournament
  - delete_tournament deletes all related data
  - nickname defaults to first name
  - register_user kept for compatibility but auto-called on first vote
"""

import hashlib
import uuid
from datetime import datetime
from data.gcs import read_table, write_table


def _now():          return datetime.utcnow().isoformat()
def _uid():          return str(uuid.uuid4())[:8]
def _hash(pw: str):  return hashlib.sha256(pw.encode()).hexdigest()   # legacy SHA-256

def _hash_bcrypt(pw: str) -> str:
    import bcrypt
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def _is_bcrypt(h: str) -> bool:
    return h.startswith("$2b$") or h.startswith("$2a$")

def _insert(table: str, record: dict):
    rows = read_table(table); rows.append(record); write_table(table, rows)

def _update_where(table: str, match_fn, update_fn):
    rows = read_table(table)
    for r in rows:
        if match_fn(r): update_fn(r)
    write_table(table, rows)

def _delete_where(table: str, match_fn):
    write_table(table, [r for r in read_table(table) if not match_fn(r)])


# ── Users ─────────────────────────────────────────────────────────────────────

def get_all_users() -> list[dict]:
    return read_table("users")

def get_user_by_id(user_id: str) -> dict | None:
    return next((u for u in read_table("users") if u["user_id"] == user_id), None)

def get_user_by_name(name: str) -> dict | None:
    return next((u for u in read_table("users")
                 if u["name"].lower() == name.lower()), None)

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
        "name"                : name,
        "nickname"            : _first_name(name),   # first name, not user_id
        "role"                : role,
        "password_hash"       : _hash(password),
        "must_change_password": True,
        "timezone"            : "Asia/Kolkata",
        "created_by"          : created_by,
        "created_at"          : _now(),
    }
    _insert("users", user)
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
    new_hash = _hash_bcrypt(new_password)
    _update_where("users",
        lambda r: r["user_id"] == user_id,
        lambda r: r.update({"password_hash"       : new_hash,
                             "must_change_password": False}))

def update_nickname(user_id: str, nickname: str):
    _update_where("users",
        lambda r: r["user_id"] == user_id,
        lambda r: r.update({"nickname": nickname.strip()}))

def update_user_timezone(user_id: str, tz: str):
    _update_where("users",
        lambda r: r["user_id"] == user_id,
        lambda r: r.update({"timezone": tz}))

def set_user_role(user_id: str, role: str):
    _update_where("users",
        lambda r: r["user_id"] == user_id,
        lambda r: r.update({"role": role}))

def delete_user(user_id: str):
    _delete_where("users", lambda r: r["user_id"] == user_id)


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
    _insert("tournaments", {
        "tournament_id" : data["tournament_id"],
        "name"          : data["name"],
        "sport"         : data["sport"],
        "start_date"    : data["start_date"],
        "status"        : "upcoming",
        "allowed_misses": int(data["allowed_misses"]),
        "penalty_points": float(data["penalty_points"]),
        "created_by"    : data.get("created_by", "admin"),
        "created_at"    : _now(),
    })

def update_tournament_status(tid: str, status: str):
    _update_where("tournaments",
        lambda r: r["tournament_id"] == tid,
        lambda r: r.update({"status": status}))

def delete_tournament(tid: str):
    """Delete tournament and ALL related data."""
    _delete_where("tournaments",   lambda r: r["tournament_id"] == tid)
    _delete_where("registrations", lambda r: r["tournament_id"] == tid)
    _delete_where("matches",       lambda r: r["tournament_id"] == tid)
    _delete_where("votes",         lambda r: r["tournament_id"] == tid)
    _delete_where("points",        lambda r: r["tournament_id"] == tid)


# ── Registrations (auto — no user action needed) ──────────────────────────────

def get_registrations(tid: str) -> list[dict]:
    return [r for r in read_table("registrations") if r["tournament_id"] == tid]

def is_registered(user_id: str, tid: str) -> bool:
    return any(r["user_id"] == user_id and r["tournament_id"] == tid
               for r in read_table("registrations"))

def ensure_registered(user_id: str, tid: str):
    """Auto-register user when they first vote in a tournament."""
    if not is_registered(user_id, tid):
        _insert("registrations", {
            "reg_id"       : _uid(),
            "user_id"      : user_id,
            "tournament_id": tid,
            "registered_at": _now(),
        })

# Keep for compatibility
def register_user(user_id: str, tid: str):
    ensure_registered(user_id, tid)


# ── match_players ─────────────────────────────────────────────────────────────
# match_players.json — one record per (player, match).
# status: "voted" | "missed" | "quit" | "not_started"
#   voted       — player cast a vote before cutoff
#   missed      — player was active but did not vote
#   quit        — player quit before this match start
#   not_started — match was before player's first vote (excluded from misses)
#
# vote field stores the actual vote string when status="voted", else "".
# This is the single source of truth for points calculation.
# All reads/writes bypass the GCS cache (_fetch/_push directly).

def _mp_fetch() -> list[dict]:
    from data.gcs import _fetch
    return _fetch("match_players")

def _mp_push(rows: list[dict]):
    from data.gcs import _push
    _push("match_players", rows)

def get_match_players(match_id: str = None, tournament_id: str = None,
                       user_id: str = None) -> list[dict]:
    """Read match_players fresh from GCS. Filter by any combination of keys."""
    rows = _mp_fetch()
    if match_id:      rows = [r for r in rows if r["match_id"] == match_id]
    if tournament_id: rows = [r for r in rows if r["tournament_id"] == tournament_id]
    if user_id:       rows = [r for r in rows if r["user_id"] == user_id]
    return rows

def upsert_match_player(match_id: str, tournament_id: str,
                         user_id: str, status: str,
                         vote: str = "", quit_at: str = ""):
    """
    Insert or update a match_player record.
    Uses _fetch/_push to bypass cache entirely.
    """
    rows = _mp_fetch()
    existing = next((r for r in rows
                     if r["user_id"] == user_id and r["match_id"] == match_id), None)
    if existing:
        existing["status"]  = status
        existing["vote"]    = vote
        existing["quit_at"] = quit_at
    else:
        rows.append({
            "mp_id"        : _uid(),
            "match_id"     : match_id,
            "tournament_id": tournament_id,
            "user_id"      : user_id,
            "status"       : status,
            "vote"         : vote,
            "quit_at"      : quit_at,
            "created_at"   : _now(),
        })
    _mp_push(rows)

def write_match_players_batch(records: list[dict]):
    """
    Write multiple match_player records at once (single GCS write).
    Upserts by (user_id, match_id). Used by recalculate_tournament and migration.
    """
    rows = _mp_fetch()
    key_map = {(r["user_id"], r["match_id"]): r for r in rows}
    for rec in records:
        key = (rec["user_id"], rec["match_id"])
        if key in key_map:
            key_map[key].update(rec)
        else:
            if "mp_id" not in rec:
                rec["mp_id"] = _uid()
            if "created_at" not in rec:
                rec["created_at"] = _now()
            key_map[key] = rec
    _mp_push(list(key_map.values()))

def delete_match_players_for_match(match_id: str):
    """Remove all match_player records for a match (used when rebuilding)."""
    rows = [r for r in _mp_fetch() if r["match_id"] != match_id]
    _mp_push(rows)


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
    _insert("matches", {
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
    })

def bulk_create_matches(tid: str, rows: list[dict], created_by: str):
    for row in rows:
        row["tournament_id"] = tid
        row["created_by"]    = created_by
        create_match(row)

def update_match_result(match_id: str, result: str):
    _update_where("matches",
        lambda r: r["match_id"] == match_id,
        lambda r: r.update({"result": result, "status": "completed"}))

def mark_match_abandoned(match_id: str):
    """No voters — mark as abandoned. No points calculated, misses not counted."""
    _update_where("matches",
        lambda r: r["match_id"] == match_id,
        lambda r: r.update({"result": "abandoned", "status": "abandoned"}))
    # Clear any previously calculated points for this match
    _delete_where("points", lambda r: r["match_id"] == match_id)

def delete_match(match_id: str):
    for table in ("matches", "votes", "points"):
        _delete_where(table, lambda r, m=match_id: r["match_id"] == m)


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
    # Write match_player record (voted status) — bypasses cache
    upsert_match_player(match_id, tid, user_id, status="voted", vote=vote)
    # Build new votes list locally, write async to GCS
    from data.gcs import read_table as _rt, write_table as _wt
    votes = [v for v in _rt("votes")
             if not (v["user_id"] == user_id and v["match_id"] == match_id)]
    votes.append({
        "vote_id"      : _uid(), "user_id": user_id,
        "match_id"     : match_id, "tournament_id": tid,
        "vote"         : vote, "voted_at": _now(),
        "updated_at"   : "", "update_count": 0})
    _wt("votes", votes, async_write=True)   # instant local update, async GCS

def update_vote(user_id: str, match_id: str, new_vote: str):
    # Update match_player record with new vote
    rows = _mp_fetch()
    for r in rows:
        if r["user_id"] == user_id and r["match_id"] == match_id:
            r["vote"] = new_vote
            break
    _mp_push(rows)
    from data.gcs import read_table as _rt, write_table as _wt
    existing  = get_user_vote(user_id, match_id)
    cur_count = int((existing or {}).get("update_count", 0))
    voted_at  = (existing or {}).get("voted_at", _now())
    tid       = (existing or {}).get("tournament_id", "")
    votes     = [v for v in _rt("votes")
                 if not (v["user_id"] == user_id and v["match_id"] == match_id)]
    votes.append({
        "vote_id"      : _uid(), "user_id": user_id,
        "match_id"     : match_id, "tournament_id": tid,
        "vote"         : new_vote, "voted_at": voted_at,
        "updated_at"   : _now(), "update_count": cur_count + 1})
    _wt("votes", votes, async_write=True)   # instant local update, async GCS

def delete_vote(user_id: str, match_id: str):
    _delete_where("votes",
        lambda r: r["user_id"] == user_id and r["match_id"] == match_id)


# ── Points ────────────────────────────────────────────────────────────────────

def get_points(tournament_id: str = None, user_id: str = None) -> list[dict]:
    ps = read_table("points")
    if tournament_id: ps = [p for p in ps if p["tournament_id"] == tournament_id]
    if user_id:       ps = [p for p in ps if p["user_id"] == user_id]
    return ps

def save_points_batch(records: list[dict]):
    existing = read_table("points")
    now = _now()
    for r in records:
        existing.append({
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
        })
    write_table("points", existing)

def delete_match_points(match_id: str):
    _delete_where("points", lambda r: r["match_id"] == match_id)


# ── Penalties ─────────────────────────────────────────────────────────────────

def get_penalties(tournament_id: str) -> list[dict]:
    """Return all manual penalties for a tournament, newest first."""
    ps = [p for p in read_table("penalties")
          if p["tournament_id"] == tournament_id]
    return sorted(ps, key=lambda p: p.get("created_at", ""), reverse=True)


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
    _insert("penalties", record)
    return record


def delete_penalty(penalty_id: str):
    _delete_where("penalties", lambda r: r.get("penalty_id") == penalty_id)
