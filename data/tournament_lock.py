"""
data/tournament_lock.py — serializes tournament-scoped mutations.

Several independent operations mutate the same tournament-scoped
match_players/matches/points data via a delete-then-rebuild pattern:
recalculate_tournament, apply_match_result, quit_player, reinstate_player,
the standalone "Rebuild match_players" action, apply_miss_floor,
remove_miss_floor. Overlapping calls for the SAME tournament — e.g. two
admin actions fired in quick succession, or a double-click during a slow
request — can interleave their deletes/inserts and silently corrupt data.
This is exactly what caused a real incident: quitting a player, recalculating,
reinstating, and recalculating again left several unrelated matches
permanently stuck as "abandoned" (see data/points.py's _mark_abandoned and
git history for the full story).

Each top-level, directly admin/API-triggered entry point wraps its body in
tournament_lock() so only one such operation runs at a time per tournament;
a second concurrent call fails fast with RuntimeError (surfaced as HTTP 409
by the API) instead of racing.

Internal helper functions that these entry points call as a sub-step
(migrate_from_votes, rebuild_for_match) are intentionally left UNLOCKED,
since some of them are invoked from within an already-locked entry point
(e.g. reinstate_player calls migrate_from_votes) — locking those too would
either deadlock or falsely reject that legitimate nesting. Only the
outermost, user-facing actions are locked:
  data/points.py:        recalculate_tournament, apply_match_result
  data/match_players.py: quit_player, reinstate_player, rebuild_for_tournament
                          (the standalone-button entry point),
                          apply_miss_floor, remove_miss_floor
"""

import threading
from contextlib import contextmanager

_locks: dict[str, str] = {}
_guard = threading.Lock()


@contextmanager
def tournament_lock(tournament_id: str, operation: str):
    with _guard:
        existing = _locks.get(tournament_id)
        if existing:
            raise RuntimeError(
                f"Another operation ({existing}) is already in progress for "
                f"tournament {tournament_id} — please wait for it to finish "
                f"before trying {operation}."
            )
        _locks[tournament_id] = operation
    try:
        yield
    finally:
        with _guard:
            _locks.pop(tournament_id, None)
