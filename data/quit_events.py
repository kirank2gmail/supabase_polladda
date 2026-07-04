"""
data/quit_events.py — durable, append-only quit/reinstate event log.

The single source of truth for "is this player currently quit, and from
which match onward" — see sql/003_player_quit_events.sql for why this
exists (match_players is a fully derived/regenerable table; quit status
used to live only inside it, with no other record, which made a routine
truncate-and-rebuild silently destroy quit history).

Deliberately isolated from data/match_players.py (which is already large)
and must never import it — the dependency only goes the other way:
match_players.py calls into this module, not vice versa.
"""

from __future__ import annotations

from datetime import datetime, timezone

from data.supabase_client import get_client, select_all


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_quit_event(user_id: str, tournament_id: str, from_match_id: str, action: str):
    """
    Append one event. action must be "quit" or "reinstate".

    Raises on failure rather than swallowing — a lost write here must be
    loud, not silently invisible (that silence is exactly what turned a
    routine rebuild into a real scoring bug last time).
    """
    get_client().table("player_quit_events").insert({
        "tournament_id": tournament_id,
        "user_id": user_id,
        "action": action,
        "from_match_id": from_match_id,
        "created_at": _now(),
    }).execute()


def get_current_quit_boundaries(tournament_id: str) -> dict[str, str]:
    """
    Return {user_id: from_match_id} for every player whose MOST RECENT event
    (by event_id, not created_at, to avoid timestamp-tie ambiguity) is a
    "quit" rather than a "reinstate" — i.e. "are they currently quit, and
    since when." Players with no events, or whose latest event is a
    "reinstate", are omitted (currently active).

    This answers a display question ("is this player currently off, since
    when") — it collapses a user to a single boundary and is NOT sufficient
    for rebuilding match_players, since it can't represent a past quit
    window that a later reinstate+quit-again left untouched (see
    get_quit_status_map for that). Used only by get_player_quit_status's
    summary fields.
    """
    events = select_all(lambda: get_client().table("player_quit_events").select("*")
                         .eq("tournament_id", tournament_id))

    latest: dict[str, dict] = {}
    for e in events:
        uid = e["user_id"]
        if uid not in latest or e["event_id"] > latest[uid]["event_id"]:
            latest[uid] = e

    return {
        uid: e["from_match_id"]
        for uid, e in latest.items()
        if e["action"] == "quit"
    }


def _match_pos(match_id: str) -> str:
    """Sortable position key — same numeric-aware convention as
    data/match_players.py's _match_dt, duplicated here to avoid importing
    match_players.py (this module must stay a one-way dependency)."""
    return f"0{int(match_id):010d}" if match_id.isdigit() else f"1{match_id}"


def get_quit_status_map(tournament_id: str, all_matches: list[dict]) -> dict[tuple[str, str], str]:
    """
    Return {(user_id, match_id): from_match_id} for every (user, match) pair
    that should currently show as quit — correctly handling multi-cycle
    history (quit, reinstate, quit again) by simulating events in
    chronological order (event_id) for each match position: a later event
    always overrides an earlier one, but only for matches at or after ITS
    OWN boundary, so a quit window that ended at an earlier reinstate stays
    intact even after a later quit-again with a different boundary.

    (get_current_quit_boundaries collapses to a single "latest event"
    boundary instead, which is right for a display summary but wrong here —
    it would either drop an earlier quit window entirely or, with the old
    match_players-scanning logic this replaces, re-quit an already-
    reinstated window by taking the earliest boundary across all quit rows.)
    """
    events = select_all(lambda: get_client().table("player_quit_events").select("*")
                         .eq("tournament_id", tournament_id))
    if not events:
        return {}

    match_pos = {
        m["match_id"]: _match_pos(m["match_id"])
        for m in all_matches
        if m.get("tournament_id") == tournament_id
    }

    by_user: dict[str, list[dict]] = {}
    for e in events:
        by_user.setdefault(e["user_id"], []).append(e)

    result: dict[tuple[str, str], str] = {}
    for uid, user_events in by_user.items():
        user_events.sort(key=lambda e: e["event_id"])  # chronological order
        for mid, mpos in match_pos.items():
            applicable = [e for e in user_events
                          if match_pos.get(e["from_match_id"], "") <= mpos]
            if not applicable:
                continue
            last = max(applicable, key=lambda e: e["event_id"])
            if last["action"] == "quit":
                result[(uid, mid)] = last["from_match_id"]
    return result
