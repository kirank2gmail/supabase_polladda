"""
data/match_players.py (Supabase Postgres backend)
━━━━━━━━━━━━━━━━━━━━
Single source of truth for building / rebuilding the match_players table.

Public API
──────────
migrate_from_votes(tournament_id, gcs_fetch_fn, gcs_push_fn)
    Full deterministic rebuild of match_players for one or all tournaments.
    This is THE core logic: voted + missed records, quit records preserved,
    abandoned matches skipped, not_started players omitted.

    gcs_fetch_fn/gcs_push_fn are kept only for backward-compatible signature
    injection (e.g. tests) — when omitted (the normal path) the function
    reads/writes Supabase directly, scoped to the tournament(s) being
    rebuilt, rather than replacing the entire table.

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
• matches/registrations/tournaments reads go through the session cache
  (data.supabase_client.read_table) — fine here since same-session writes
  already invalidate that cache before any rebuild button is clicked.
• votes and match_players reads/writes always go straight to Supabase,
  scoped by tournament_id/match_id — these must stay maximally fresh.
• quit records are always preserved; they are managed separately by admin.
• not_started players (first vote is after this match) produce no row.
• abandoned matches produce no rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from data.supabase_client import read_table, get_client, sess_clear, select_all


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
    quit_boundaries: dict[str, str],
    existing_mp: list[dict] | None = None,
) -> list[dict]:
    """
    Build voted / missed / quit records for a single match.

    quit_boundaries: {user_id: from_match_id} — the match_id from which the
        player quit.  Any match whose _match_dt() is >= that boundary's
        _match_dt() gets status="quit".  quit_at on written records stores
        the same from_match_id so boundary-building on future reads is
        consistent and unambiguous.

    Returns [] for abandoned matches.
    not_started players produce no record.
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

    # miss_floor records are synthetic — protect them from rebuild
    floor_keys = {
        (r["user_id"], r["match_id"])
        for r in existing_mp
        if r.get("note") == "miss_floor"
        and r.get("tournament_id") == tournament_id
    } if existing_mp else set()

    records: list[dict] = []
    for uid in reg_users:
        if (uid, match_id) in floor_keys:
            continue  # miss_floor record already exists — leave it untouched

        # Check quit boundary — applies to ALL matches on/after the boundary,
        # including new matches that have no existing quit record yet.
        # quit_boundaries stores from_match_id; convert to _match_dt for comparison.
        from_mid = quit_boundaries.get(uid)
        if from_mid:
            from_dt = match_dt_map.get(from_mid)
            if from_dt and this_dt >= from_dt:
                records.append({
                    "mp_id"        : _uid(),
                    "match_id"     : match_id,
                    "tournament_id": tournament_id,
                    "user_id"      : uid,
                    "status"       : "quit",
                    "vote"         : "",
                    "quit_at"      : from_mid,   # always store match_id, never datetime
                    "created_at"   : _now(),
                })
                continue

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


def _build_quit_boundaries(tid: str, t_match_map: dict, existing_mp: list[dict]) -> dict[str, str]:
    """
    Build {user_id: earliest quit boundary match_id} for one tournament from
    existing quit records. quit_at holds the from_match_id passed to
    quit_player().
    """
    quit_boundaries: dict[str, str] = {}
    for r in existing_mp:
        if r.get("tournament_id") != tid:
            continue
        if r.get("status") != "quit":
            continue
        uid          = r["user_id"]
        boundary_mid = r.get("quit_at") or r["match_id"]
        bm = t_match_map.get(boundary_mid)
        if not bm:
            # Fall back to the record's own match_id as the boundary
            boundary_mid = r["match_id"]
            bm = t_match_map.get(boundary_mid)
        if not bm:
            continue
        boundary_dt = _match_dt(bm)
        if uid not in quit_boundaries or boundary_dt < _match_dt(t_match_map[quit_boundaries[uid]]):
            quit_boundaries[uid] = boundary_mid
    return quit_boundaries


# ── Public API ────────────────────────────────────────────────────────────────

def migrate_from_votes(
    tournament_id: str | None = None,
    gcs_fetch_fn=None,
    gcs_push_fn=None,
) -> int:
    """
    Full deterministic rebuild of match_players.

    Reads votes, registrations, and matches to produce complete voted +
    missed records for every completed match. Quit records are preserved.
    Abandoned matches produce no rows.

    Parameters
    ──────────
    tournament_id
        Scope the rebuild to one tournament.  Pass None to rebuild ALL
        tournaments (useful for the initial one-time migration).
    gcs_fetch_fn / gcs_push_fn
        Legacy injectable primitives, kept only for backward-compatible
        signature/tests. When provided, the function operates on the old
        "read everything, replace the entire table" contract. When omitted
        (the normal path), reads/writes are scoped to the tournament(s)
        being rebuilt via targeted Supabase queries.

    Returns
    ───────
    Number of new (voted + missed + quit) records written for the tournament(s).
    """
    if gcs_fetch_fn or gcs_push_fn:
        # Legacy whole-table-replace path (tests / injected primitives only).
        fetch = gcs_fetch_fn or read_table
        all_votes     = fetch("votes")
        all_matches   = fetch("matches")
        registrations = fetch("registrations")
        existing_mp   = fetch("match_players")

        tids = [tournament_id] if tournament_id else list(
            {m["tournament_id"] for m in all_matches if m.get("tournament_id")})

        other_mp = [r for r in existing_mp if r.get("tournament_id") not in tids]
        new_mp: list[dict] = []
        for tid in tids:
            t_match_map = {m["match_id"]: m for m in all_matches
                           if m.get("tournament_id") == tid}
            quit_boundaries = _build_quit_boundaries(tid, t_match_map, existing_mp)
            t_matches = sorted(
                [m for m in all_matches
                 if m.get("tournament_id") == tid
                 and m.get("status") in ("completed", "abandoned")
                 and m.get("result") not in ("", None)],
                key=_match_dt,
            )
            for m in t_matches:
                new_mp.extend(_build_records_for_match(
                    m["match_id"], tid, m, all_matches, all_votes,
                    registrations, quit_boundaries, existing_mp,
                ))

        if gcs_push_fn:
            gcs_push_fn("match_players", other_mp + new_mp)
        return len(new_mp)

    # ── Normal path: targeted, tournament-scoped Supabase queries ────────────
    sb = get_client()
    all_matches   = read_table("matches")
    registrations = read_table("registrations")

    tids = [tournament_id] if tournament_id else list(
        {m["tournament_id"] for m in all_matches if m.get("tournament_id")})
    if not tids:
        return 0

    all_votes   = select_all(lambda: sb.table("votes").select("*").in_("tournament_id", tids))
    existing_mp = select_all(lambda: sb.table("match_players").select("*").in_("tournament_id", tids))

    new_mp: list[dict] = []
    for tid in tids:
        t_match_map = {m["match_id"]: m for m in all_matches
                       if m.get("tournament_id") == tid}
        quit_boundaries = _build_quit_boundaries(tid, t_match_map, existing_mp)
        t_matches = sorted(
            [m for m in all_matches
             if m.get("tournament_id") == tid
             and m.get("status") in ("completed", "abandoned")
             and m.get("result") not in ("", None)],
            key=_match_dt,
        )
        for m in t_matches:
            new_mp.extend(_build_records_for_match(
                m["match_id"], tid, m, all_matches, all_votes,
                registrations, quit_boundaries, existing_mp,
            ))

    sb.table("match_players").delete().in_("tournament_id", tids).execute()
    for i in range(0, len(new_mp), 500):
        sb.table("match_players").insert(new_mp[i:i + 500]).execute()

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
    sb = get_client()

    all_matches   = read_table("matches")
    registrations = read_table("registrations")
    existing_mp   = select_all(lambda: sb.table("match_players").select("*")
                                .eq("tournament_id", tournament_id))

    this_match = next(
        (m for m in all_matches if m["match_id"] == match_id), None
    )
    if not this_match:
        return 0

    t_match_map = {m["match_id"]: m for m in all_matches
                   if m.get("tournament_id") == tournament_id}
    quit_boundaries = _build_quit_boundaries(tournament_id, t_match_map, existing_mp)

    all_votes = select_all(lambda: sb.table("votes").select("*")
                            .eq("match_id", match_id).eq("tournament_id", tournament_id))

    new_records = _build_records_for_match(
        match_id, tournament_id,
        this_match, all_matches, all_votes, registrations, quit_boundaries,
        existing_mp,
    )

    sb.table("match_players").delete().eq("match_id", match_id).execute()
    if new_records:
        sb.table("match_players").insert(new_records).execute()
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
    all_matches = read_table("matches")

    t_matches = sorted(
        [m for m in all_matches if m.get("tournament_id") == tournament_id],
        key=_match_dt,
    )
    match_ids = [m["match_id"] for m in t_matches]

    if from_match_id not in match_ids:
        return 0

    from_idx       = match_ids.index(from_match_id)
    quit_match_ids = match_ids[from_idx:]

    resp = get_client().table("match_players").update({
        "status": "quit", "quit_at": from_match_id,
    }).eq("user_id", user_id).eq("tournament_id", tournament_id) \
        .in_("match_id", quit_match_ids).execute()

    return len(resp.data) if resp.data is not None else 0


def reinstate_player(user_id: str, tournament_id: str, from_match_id: str) -> int:
    """
    Reinstate a player from from_match_id onwards (inclusive).

    Removes quit records whose match_id falls on or after from_match_id
    in chronological order, then calls migrate_from_votes to rebuild
    those matches as voted / missed from votes and registrations.

    Quit records for matches before from_match_id are preserved
    (supports partial quit history: quit, rejoin, quit again).

    Returns the number of quit records removed before the rebuild.
    """
    all_matches = read_table("matches")

    t_matches = sorted(
        [m for m in all_matches if m.get("tournament_id") == tournament_id],
        key=_match_dt,
    )
    match_ids = [m["match_id"] for m in t_matches]

    if from_match_id not in match_ids:
        return 0

    from_idx            = match_ids.index(from_match_id)
    reinstate_match_ids = match_ids[from_idx:]

    resp = get_client().table("match_players").delete() \
        .eq("user_id", user_id).eq("tournament_id", tournament_id) \
        .eq("status", "quit").in_("match_id", reinstate_match_ids).execute()
    removed = len(resp.data) if resp.data is not None else 0

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
    t_mp = select_all(lambda: get_client().table("match_players").select("*")
                       .eq("tournament_id", tournament_id))
    all_matches = read_table("matches")

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

def apply_miss_floor(tournament_id: str, from_match_id: str) -> int:
    """
    Max out the free-miss allowance for all active players from
    from_match_id onwards.

    Writes `allowed_misses` synthetic match_players records per player,
    all with:
      status = "missed"
      note   = "miss_floor"
      match_id = from_match_id   (sorts before the knockout stage)

    _count_prior_misses counts these normally, so the very first real
    miss in the knockout stage is already beyond the threshold and is
    penalised.  _build_records_for_match skips (uid, from_match_id)
    pairs that already have a miss_floor record, so rebuild is safe.

    Returns the number of synthetic records written.
    """
    sb = get_client()

    tournament     = next((t for t in read_table("tournaments")
                           if t["tournament_id"] == tournament_id), None)
    allowed_misses = int((tournament or {}).get("allowed_misses", 3))

    existing_mp = select_all(lambda: sb.table("match_players").select("*")
                              .eq("tournament_id", tournament_id))

    # Active players = those with any non-quit record in this tournament
    active_uids = {
        r["user_id"] for r in existing_mp
        if r.get("status") != "quit"
        and r.get("note") != "miss_floor"
    }

    # Remove any existing floor records for this tournament (idempotent)
    sb.table("match_players").delete() \
        .eq("tournament_id", tournament_id).eq("note", "miss_floor").execute()

    new_records: list[dict] = []
    for uid in active_uids:
        for _ in range(allowed_misses):
            new_records.append({
                "mp_id"        : _uid(),
                "match_id"     : from_match_id,
                "tournament_id": tournament_id,
                "user_id"      : uid,
                "status"       : "missed",
                "vote"         : "",
                "quit_at"      : "",
                "note"         : "miss_floor",
                "created_at"   : _now(),
            })

    for i in range(0, len(new_records), 500):
        sb.table("match_players").insert(new_records[i:i + 500]).execute()
    return len(new_records)


def remove_miss_floor(tournament_id: str) -> int:
    """
    Remove all miss_floor records for a tournament (undo apply_miss_floor).
    Returns the number of records removed.
    """
    resp = get_client().table("match_players").delete() \
        .eq("tournament_id", tournament_id).eq("note", "miss_floor").execute()
    return len(resp.data) if resp.data is not None else 0


def get_miss_floor_status(tournament_id: str) -> dict | None:
    """
    Return info about the current miss floor for a tournament, or None
    if no floor is set.

    Returns:
      {
        "from_match_id": str,
        "player_count":  int,
        "record_count":  int,
      }
    """
    floor_records = select_all(lambda: get_client().table("match_players").select("*")
                                .eq("tournament_id", tournament_id).eq("note", "miss_floor"))
    if not floor_records:
        return None

    match_ids     = {r["match_id"] for r in floor_records}
    from_match_id = min(match_ids)   # earliest boundary match
    return {
        "from_match_id": from_match_id,
        "player_count" : len({r["user_id"] for r in floor_records}),
        "record_count" : len(floor_records),
    }
