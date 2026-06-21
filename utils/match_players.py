"""
data/match_players.py
━━━━━━━━━━━━━━━━━━━━
Single source of truth for building / rebuilding match_players.json.

Public API
──────────
rebuild_for_match(match_id, tournament_id)
    Rebuild match_player records for ONE match.
    Called by the admin dashboard when a single result is saved or corrected.

rebuild_for_tournament(tournament_id)
    Rebuild match_player records for ALL completed/abandoned matches in a
    tournament.  Called by "Recalculate Tournament" and by the migration
    script when seeding from scratch.

migrate_from_votes(gcs_fetch_fn, gcs_push_fn)
    One-time migration helper that back-fills match_players from votes.json
    without touching existing records.  Kept for the standalone migration
    script; prefer rebuild_for_tournament for admin-driven rebuilds.

Design notes
────────────
• All reads bypass the session / TTL caches — raw _fetch/_push so that points
  calculation always sees a fully consistent, freshly-written table.
• quit records are always preserved; they are managed separately by the admin.
• not_started players (first vote is after this match) are silently skipped —
  they produce no row in match_players.
• abandoned matches produce no rows at all.
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


# ── shared core ───────────────────────────────────────────────────────────────

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
    Build the full set of match_player records for a single match.

    Returns a list of dicts (voted | missed).
    not_started and quit players produce no record.
    If the match is abandoned, returns an empty list immediately.
    """
    if _is_abandoned(this_match):
        return []

    this_dt = _match_dt(this_match)

    # Build a date-time map for every non-abandoned tournament match
    match_dt_map: dict[str, str] = {
        m["match_id"]: _match_dt(m)
        for m in all_matches
        if m.get("tournament_id") == tournament_id
        and not _is_abandoned(m)
    }

    # Registered players for this tournament
    reg_users = [r["user_id"] for r in registrations
                 if r["tournament_id"] == tournament_id]

    # Votes for this specific match  {user_id: vote_string}
    vote_map: dict[str, str] = {
        v["user_id"]: v.get("vote", "")
        for v in all_votes
        if v.get("match_id") == match_id
        and v.get("tournament_id") == tournament_id
    }

    # First voted match datetime per player (across the whole tournament)
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
            continue  # quit records are preserved separately

        voted = uid in vote_map
        fvdt  = first_vote_dt.get(uid)

        if voted:
            status = "voted"
            vote   = vote_map[uid]
        elif fvdt is None or fvdt >= this_dt:
            # Player hadn't started yet — no record
            continue
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

def rebuild_for_match(match_id: str, tournament_id: str) -> int:
    """
    Rebuild match_players records for ONE match only.

    Replaces all existing records for that match_id (except quit records),
    then writes the updated table back to GCS.

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

    # Quit keys are global across all tournaments
    quit_keys = {
        (r["user_id"], r["match_id"])
        for r in existing_mp
        if r.get("status") == "quit"
    }

    new_records = _build_records_for_match(
        match_id, tournament_id,
        this_match, all_matches, all_votes, registrations, quit_keys,
    )

    # Keep every record that is NOT for this match
    other_records = [r for r in existing_mp if r["match_id"] != match_id]

    # Re-add quit records for this match from the existing set
    quit_this_match = [
        r for r in existing_mp
        if r["match_id"] == match_id and r.get("status") == "quit"
    ]

    _push("match_players", other_records + quit_this_match + new_records)
    return len(new_records)


def rebuild_for_tournament(tournament_id: str) -> int:
    """
    Rebuild match_players records for ALL completed / abandoned matches in a
    tournament from scratch.

    Existing quit records for this tournament are preserved.
    Records belonging to other tournaments are untouched.

    Returns the total number of active records written (voted + missed).
    """
    from data.gcs import _fetch, _push

    all_votes     = _fetch("votes")
    all_matches   = _fetch("matches")
    registrations = _fetch("registrations")
    existing_mp   = _fetch("match_players")

    # Preserve quit records for THIS tournament
    quit_records = [
        r for r in existing_mp
        if r.get("status") == "quit"
        and r.get("tournament_id") == tournament_id
    ]
    quit_keys = {(r["user_id"], r["match_id"]) for r in quit_records}

    # Tournament matches, sorted chronologically, with a result set
    t_matches = sorted(
        [
            m for m in all_matches
            if m.get("tournament_id") == tournament_id
            and m.get("status") in ("completed", "abandoned")
            and m.get("result") not in ("", None)
        ],
        key=_match_dt,
    )

    new_mp: list[dict] = []
    for m in t_matches:
        new_mp.extend(
            _build_records_for_match(
                m["match_id"], tournament_id,
                m, all_matches, all_votes, registrations, quit_keys,
            )
        )

    # Keep records from OTHER tournaments, then add this tournament's quit +
    # freshly-built records
    other_mp = [r for r in existing_mp
                if r.get("tournament_id") != tournament_id]

    _push("match_players", other_mp + quit_records + new_mp)
    return len(new_mp)


def migrate_from_votes(
    gcs_fetch_fn,
    gcs_push_fn,
) -> int:
    """
    One-time migration: back-fill match_players from votes.json without
    disturbing any existing records.

    gcs_fetch_fn: callable(table_name) -> list[dict]
    gcs_push_fn:  callable(table_name, records) -> None

    Returns the number of new records added.
    """
    print("Reading votes.json …")
    votes = gcs_fetch_fn("votes")
    print(f"  {len(votes)} votes found")

    print("Reading match_players.json (existing) …")
    existing_mp   = gcs_fetch_fn("match_players")
    existing_keys = {(r["user_id"], r["match_id"]) for r in existing_mp}
    print(f"  {len(existing_mp)} existing records")

    new_records: list[dict] = []
    for v in votes:
        key = (v["user_id"], v["match_id"])
        if key not in existing_keys:
            new_records.append({
                "mp_id"        : _uid(),
                "match_id"     : v["match_id"],
                "tournament_id": v.get("tournament_id", ""),
                "user_id"      : v["user_id"],
                "status"       : "active",      # migration sentinel
                "vote"         : v.get("vote", ""),
                "quit_at"      : "",
                "created_at"   : v.get("voted_at", _now()),
            })
            existing_keys.add(key)

    print(f"  {len(new_records)} new records to add")
    print(f"  {len(existing_mp) + len(new_records)} total records")

    print("Writing match_players.json …")
    gcs_push_fn("match_players", existing_mp + new_records)
    print("✅ Migration complete")
    return len(new_records)
