"""
data/match_players.py
━━━━━━━━━━━━━━━━━━━━
Single source of truth for building / rebuilding match_players.json.

Public API
──────────
migrate_from_votes(tournament_id, gcs_fetch_fn, gcs_push_fn)
    Full deterministic rebuild of match_players for one or all tournaments.
    This is THE core logic: voted + missed records, quit records preserved,
    abandoned matches skipped, not_started players omitted.

    Called by:
      • Dashboard "Run Migration" button  — to inspect match_players without
        touching points
      • rebuild_for_tournament()          — before recalculating points
      • migrate_match_players.py CLI      — standalone seeding / repair

rebuild_for_match(match_id, tournament_id)
    Rebuild match_player records for ONE match only.
    Called when admin saves or corrects a single match result.

rebuild_for_tournament(tournament_id)
    Thin wrapper: calls migrate_from_votes then returns the record count.
    Called by "Recalculate Tournament" (which also recalculates points
    afterwards).

Design notes
────────────
• All reads bypass the session / TTL caches — raw _fetch/_push so that
  points calculation always sees a fully consistent, freshly-written table.
• quit records are always preserved; they are managed separately by admin.
• not_started players (first vote is after this match) produce no row.
• abandoned matches produce no rows.
• migrate_from_votes accepts optional gcs_fetch_fn / gcs_push_fn so the
  CLI and Streamlit callers can pass in the same _fetch/_push primitives
  without importing from data.gcs at module level.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


# ── helpers ───────────────────────────────────────────────────────────────────

def _uid() -> str:
    return str(uuid.uuid4())[:8]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _match_dt(m: dict) -> str:
    """Sortable 'YYYY-MM-DD HH:MM' string from a match record."""
    return f"{m['match_date']} {m['start_time']}"


def _is_abandoned(m: dict) -> bool:
    return (m.get("status") == "abandoned"
            or m.get("result") == "abandoned")


# ── per-match record builder (shared by both single-match and full rebuild) ───

def _build_records_for_match(
    match_id: str,
    tournament_id: str,
    this_match: dict,
    all_matches: list[dict],
    all_votes: list[dict],
    registrations: list[dict],
    quit_keys: set[tuple],
) -> list[dict]:
    """
    Build voted + missed records for a single match.

    Returns [] for abandoned matches.
    not_started and quit players are silently omitted.
    """
    if _is_abandoned(this_match):
        return []

    this_dt = _match_dt(this_match)

    # Date-time map for every non-abandoned match in this tournament
    match_dt_map: dict[str, str] = {
        m["match_id"]: _match_dt(m)
        for m in all_matches
        if m.get("tournament_id") == tournament_id
        and not _is_abandoned(m)
    }

    # Players registered for this tournament
    reg_users = [r["user_id"] for r in registrations
                 if r["tournament_id"] == tournament_id]

    # Votes cast for this specific match  {user_id: vote_string}
    vote_map: dict[str, str] = {
        v["user_id"]: v.get("vote", "")
        for v in all_votes
        if v.get("match_id") == match_id
        and v.get("tournament_id") == tournament_id
    }

    # Each player's first voted match datetime across the whole tournament
    # (used to distinguish "missed" from "not started yet")
    first_vote_dt: dict[str, str] = {}
    for uid in reg_users:
        voted_dts = [
            match_dt_map[v["match_id"]]
            for v in all_votes
            if v.get("user_id") == uid
            and v.get("tournament_id") == tournament_id
            and v.get("match_id") in match_dt_map
        ]
        if voted_dts:
            first_vote_dt[uid] = min(voted_dts)

    records: list[dict] = []
    for uid in reg_users:
        if (uid, match_id) in quit_keys:
            continue  # preserved separately

        voted = uid in vote_map
        fvdt  = first_vote_dt.get(uid)

        if voted:
            status = "voted"
            vote   = vote_map[uid]
        elif fvdt is None or fvdt >= this_dt:
            continue  # not started yet — no record
        else:
            status = "missed"
            vote   = ""

        records.append({
            "mp_id"        : _uid(),
            "match_id"     : match_id,
            "tournament_id": tournament_id,
            "user_id"      : uid,
            "status"       : status,
            "vote"         : vote,
            "quit_at"      : "",
            "created_at"   : _now(),
        })

    return records


# ── Public API ────────────────────────────────────────────────────────────────

def migrate_from_votes(
    tournament_id: str | None = None,
    gcs_fetch_fn=None,
    gcs_push_fn=None,
) -> int:
    """
    Full deterministic rebuild of match_players.json.

    Reads votes.json, registrations.json, and matches.json to produce
    complete voted + missed records for every completed match.
    Quit records are preserved. Abandoned matches produce no rows.

    Parameters
    ──────────
    tournament_id
        Scope the rebuild to one tournament.  Pass None to rebuild ALL
        tournaments (useful for the initial one-time migration).
    gcs_fetch_fn / gcs_push_fn
        Injectable GCS primitives.  When None, defaults to data.gcs._fetch
        and data.gcs._push so Streamlit callers don't need to import them.

    Returns
    ───────
    Number of new (voted + missed) records written for the tournament(s).
    """
    if gcs_fetch_fn is None or gcs_push_fn is None:
        from data.gcs import _fetch, _push
        gcs_fetch_fn = gcs_fetch_fn or _fetch
        gcs_push_fn  = gcs_push_fn  or _push

    all_votes     = gcs_fetch_fn("votes")
    all_matches   = gcs_fetch_fn("matches")
    registrations = gcs_fetch_fn("registrations")
    existing_mp   = gcs_fetch_fn("match_players")

    # Determine which tournament IDs to rebuild
    if tournament_id:
        tids = [tournament_id]
    else:
        tids = list({m["tournament_id"] for m in all_matches
                     if m.get("tournament_id")})

    # Preserve ALL quit records up front (across every tournament)
    quit_records = [r for r in existing_mp if r.get("status") == "quit"]
    quit_keys    = {(r["user_id"], r["match_id"]) for r in quit_records}

    # Keep records that belong to tournaments we are NOT rebuilding
    other_mp = [r for r in existing_mp
                if r.get("tournament_id") not in tids
                and r.get("status") != "quit"]

    new_mp: list[dict] = []
    for tid in tids:
        # Completed (non-abandoned) matches for this tournament, oldest first
        t_matches = sorted(
            [
                m for m in all_matches
                if m.get("tournament_id") == tid
                and m.get("status") in ("completed", "abandoned")
                and m.get("result") not in ("", None)
            ],
            key=_match_dt,
        )
        for m in t_matches:
            new_mp.extend(
                _build_records_for_match(
                    m["match_id"], tid,
                    m, all_matches, all_votes, registrations, quit_keys,
                )
            )

    gcs_push_fn("match_players", other_mp + quit_records + new_mp)
    return len(new_mp)


def rebuild_for_tournament(tournament_id: str) -> int:
    """
    Thin wrapper: rebuild match_players for one tournament via
    migrate_from_votes, then return the record count.

    Called by _recalculate_tournament in dashboard.py before points are
    recalculated, so match_players is always fresh and complete.
    """
    return migrate_from_votes(tournament_id=tournament_id)


def rebuild_for_match(match_id: str, tournament_id: str) -> int:
    """
    Rebuild match_players records for ONE match only.

    Replaces all non-quit records for that match, preserves quit records,
    leaves all other matches untouched.

    Returns the number of new records written.
    """
    from data.gcs import _fetch, _push

    all_votes     = _fetch("votes")
    all_matches   = _fetch("matches")
    registrations = _fetch("registrations")
    existing_mp   = _fetch("match_players")

    this_match = next(
        (m for m in all_matches if m["match_id"] == match_id), None
    )
    if not this_match:
        return 0

    quit_keys = {
        (r["user_id"], r["match_id"])
        for r in existing_mp
        if r.get("status") == "quit"
    }

    new_records = _build_records_for_match(
        match_id, tournament_id,
        this_match, all_matches, all_votes, registrations, quit_keys,
    )

    # All records except this match's non-quit rows
    other_records   = [r for r in existing_mp if r["match_id"] != match_id]
    quit_this_match = [r for r in existing_mp
                       if r["match_id"] == match_id
                       and r.get("status") == "quit"]

    _push("match_players", other_records + quit_this_match + new_records)
    return len(new_records)


def _match_ist_label(m: dict) -> str:
    """
    Human-readable IST label for a match dropdown:
    'M5 · CSK vs MI · 15 Apr 2025 07:30 PM IST'
    """
    import pytz
    from datetime import datetime as _dt
    local_tz = pytz.timezone(m.get("timezone", "Asia/Kolkata"))
    local_dt = _dt.strptime(
        f"{m['match_date']} {m['start_time']}", "%Y-%m-%d %H:%M"
    )
    ist_dt = local_tz.localize(local_dt).astimezone(pytz.timezone("Asia/Kolkata"))
    return f"{m['match_id']} · {m['title']} · {ist_dt.strftime('%d %b %Y %I:%M %p IST')}"


def quit_player(user_id: str, tournament_id: str, from_match_id: str) -> int:
    """
    Mark a player as quit from from_match_id onwards (inclusive).

    Determines which match_ids come on or after from_match_id by sorting
    the tournament's matches chronologically and taking the tail from
    from_match_id.  No datetime arithmetic needed — match_id membership
    in that set is sufficient.

    quit_at stores the from_match_id so reinstate and status display
    can look up the label without re-sorting.

    Returns the number of records updated.
    """
    from data.gcs import _fetch, _push

    all_mp      = _fetch("match_players")
    all_matches = _fetch("matches")

    # Sort this tournament's matches chronologically → get IDs from from_match_id onwards
    t_matches = sorted(
        [m for m in all_matches if m.get("tournament_id") == tournament_id],
        key=_match_dt,
    )
    match_ids = [m["match_id"] for m in t_matches]

    if from_match_id not in match_ids:
        return 0

    from_idx     = match_ids.index(from_match_id)
    quit_match_ids = set(match_ids[from_idx:])

    updated = 0
    for r in all_mp:
        if r.get("user_id") != user_id:
            continue
        if r.get("tournament_id") != tournament_id:
            continue
        if r["match_id"] in quit_match_ids:
            r["status"]  = "quit"
            r["quit_at"] = from_match_id
            updated += 1

    _push("match_players", all_mp)
    return updated


def reinstate_player(user_id: str, tournament_id: str, from_match_id: str) -> int:
    """
    Reinstate a player from from_match_id onwards (inclusive).

    Removes quit records whose match_id falls on or after from_match_id
    in chronological order, then calls migrate_from_votes to rebuild
    those matches as voted / missed from votes.json and registrations.json.

    Quit records for matches before from_match_id are preserved
    (supports partial quit history: quit, rejoin, quit again).

    Returns the number of quit records removed before the rebuild.
    """
    from data.gcs import _fetch, _push

    all_mp      = _fetch("match_players")
    all_matches = _fetch("matches")

    t_matches = sorted(
        [m for m in all_matches if m.get("tournament_id") == tournament_id],
        key=_match_dt,
    )
    match_ids = [m["match_id"] for m in t_matches]

    if from_match_id not in match_ids:
        return 0

    from_idx          = match_ids.index(from_match_id)
    reinstate_match_ids = set(match_ids[from_idx:])

    def _keep(r: dict) -> bool:
        if r.get("user_id") != user_id:
            return True
        if r.get("tournament_id") != tournament_id:
            return True
        if r.get("status") != "quit":
            return True
        return r["match_id"] not in reinstate_match_ids

    removed = sum(1 for r in all_mp if not _keep(r))
    _push("match_players", [r for r in all_mp if _keep(r)])

    migrate_from_votes(tournament_id=tournament_id)
    return removed


def get_player_quit_status(tournament_id: str) -> dict[str, dict]:
    """
    Return quit status for every player who has any match_players record
    in this tournament.

    Returns dict keyed by user_id:
      {
        "has_quit_records"  : bool,
        "quit_from_match_id": match_id stored in quit_at of the earliest
                              quit record (str | None),
        "quit_since_label"  : IST label string for that match (str | None),
        "active_matches"    : count of voted/missed records,
        "quit_matches"      : count of quit records,
      }

    quit_at on each record holds the from_match_id passed to quit_player,
    so finding the earliest quit boundary is a simple string comparison
    using the chronological sort key (_match_dt).
    """
    from data.gcs import _fetch

    all_mp      = _fetch("match_players")
    all_matches = _fetch("matches")
    t_mp        = [r for r in all_mp if r.get("tournament_id") == tournament_id]

    # match_id → match dict (for label generation and sort key)
    match_map = {
        m["match_id"]: m
        for m in all_matches
        if m.get("tournament_id") == tournament_id
    }

    # Chronological sort key per match_id (reuses existing _match_dt helper)
    def _sort_key(mid: str) -> str:
        m = match_map.get(mid)
        return _match_dt(m) if m else ""

    status: dict[str, dict] = {}
    for r in t_mp:
        uid = r["user_id"]
        if uid not in status:
            status[uid] = {
                "has_quit_records"  : False,
                "quit_from_match_id": None,
                "quit_since_label"  : None,
                "active_matches"    : 0,
                "quit_matches"      : 0,
            }
        s = status[uid]
        if r.get("status") == "quit":
            s["has_quit_records"] = True
            s["quit_matches"]    += 1
            # quit_at holds the from_match_id used when quitting
            boundary_mid = r.get("quit_at") or r["match_id"]
            cur_boundary = s["quit_from_match_id"]
            if (cur_boundary is None
                    or _sort_key(boundary_mid) < _sort_key(cur_boundary)):
                s["quit_from_match_id"] = boundary_mid
                m = match_map.get(boundary_mid)
                s["quit_since_label"] = _match_ist_label(m) if m else boundary_mid
        else:
            s["active_matches"] += 1

    return status
