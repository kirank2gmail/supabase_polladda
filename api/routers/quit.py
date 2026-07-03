"""
api/routers/quit.py — player quit/reinstate and miss-floor management.

All admin-only. Composes existing data.match_players functions exactly as
admin/dashboard.py::_quit_tab does today — no new business logic.
"""

from datetime import datetime as _dt

import pytz
from fastapi import APIRouter, Depends, HTTPException

from data.db import get_display_name, get_matches
from data.match_players import (
    _match_ist_label,
    apply_miss_floor,
    get_miss_floor_status,
    get_player_quit_status,
    quit_player,
    reinstate_player,
    remove_miss_floor,
)

from api.deps import require_admin
from api.schemas import (
    MatchLabelOut,
    MissFloorApplyRequest,
    MissFloorStatus,
    PlayerStatusOut,
    QuitRequest,
    QuitStatusResponse,
)

router = APIRouter()


def _sorted_matches_with_labels(tournament_id: str) -> list[dict]:
    """Chronological match order + IST label, same sort key as _quit_tab."""
    all_ms = get_matches(tournament_id=tournament_id)

    def _sort_key(m):
        local_tz = pytz.timezone(m.get("timezone", "Asia/Kolkata"))
        local_dt = _dt.strptime(f"{m['match_date']} {m['start_time']}", "%Y-%m-%d %H:%M")
        return local_tz.localize(local_dt)

    sorted_ms = sorted(all_ms, key=_sort_key)
    return [{"match_id": m["match_id"], "match": m} for m in sorted_ms]


@router.get("/tournaments/{tournament_id}/quit-status", response_model=QuitStatusResponse)
def quit_status(tournament_id: str, admin: dict = Depends(require_admin)):
    player_status = get_player_quit_status(tournament_id)
    sorted_matches = _sorted_matches_with_labels(tournament_id)

    players = [
        PlayerStatusOut(
            user_id=uid,
            name=get_display_name(uid),
            has_quit_records=s["has_quit_records"],
            quit_from_match_id=s["quit_from_match_id"],
            quit_since_label=s["quit_since_label"],
            active_matches=s["active_matches"],
            quit_matches=s["quit_matches"],
        )
        for uid, s in player_status.items()
    ]
    matches = [
        MatchLabelOut(match_id=sm["match_id"], label=_match_ist_label(sm["match"]))
        for sm in sorted_matches
    ]
    return QuitStatusResponse(players=players, matches=matches)


@router.post("/tournaments/{tournament_id}/quit")
def mark_quit(tournament_id: str, body: QuitRequest, admin: dict = Depends(require_admin)):
    n = quit_player(body.user_id, tournament_id, body.from_match_id)
    return {"updated": n}


@router.post("/tournaments/{tournament_id}/reinstate")
def reinstate(tournament_id: str, body: QuitRequest, admin: dict = Depends(require_admin)):
    n = reinstate_player(body.user_id, tournament_id, body.from_match_id)
    return {"removed": n}


@router.get("/tournaments/{tournament_id}/miss-floor", response_model=MissFloorStatus | None)
def miss_floor_status(tournament_id: str, admin: dict = Depends(require_admin)):
    status = get_miss_floor_status(tournament_id)
    if not status:
        return None
    match = next(
        (m for m in get_matches(tournament_id=tournament_id)
         if m["match_id"] == status["from_match_id"]),
        None,
    )
    label = _match_ist_label(match) if match else status["from_match_id"]
    return MissFloorStatus(**status, label=label)


@router.post("/tournaments/{tournament_id}/miss-floor")
def apply_floor(
    tournament_id: str, body: MissFloorApplyRequest, admin: dict = Depends(require_admin)
):
    n = apply_miss_floor(tournament_id, body.from_match_id)
    return {"written": n}


@router.delete("/tournaments/{tournament_id}/miss-floor")
def remove_floor(tournament_id: str, admin: dict = Depends(require_admin)):
    n = remove_miss_floor(tournament_id)
    return {"removed": n}
