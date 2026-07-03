"""
api/routers/tournaments.py — tournament + leaderboard endpoints.

Leaderboard handler is a thin wrapper: data/leaderboard_builder.py's
build_lb_data() dict already matches LeaderboardResponse field-for-field.
GET endpoints are open to any authenticated user; mutations are admin-only.
"""

from fastapi import APIRouter, Depends, HTTPException

from data.db import (
    create_tournament,
    delete_tournament,
    get_tournament,
    get_tournaments,
    tournament_id_exists,
    update_tournament_status,
)
from data.leaderboard_builder import build_lb_data

from api.deps import get_current_user, require_admin
from api.schemas import (
    LeaderboardResponse,
    TournamentCreateRequest,
    TournamentOut,
    TournamentStatusRequest,
)

router = APIRouter()


@router.get("", response_model=list[TournamentOut])
def list_tournaments(user: dict = Depends(get_current_user)):
    return get_tournaments()


@router.get("/{tournament_id}/leaderboard", response_model=LeaderboardResponse)
def leaderboard(tournament_id: str, user: dict = Depends(get_current_user)):
    if not get_tournament(tournament_id):
        raise HTTPException(status_code=404, detail="Tournament not found")
    return build_lb_data(tournament_id)


@router.post("", response_model=TournamentOut)
def create_tournament_endpoint(
    body: TournamentCreateRequest, admin: dict = Depends(require_admin)
):
    if not body.tournament_id.strip() or not body.name.strip():
        raise HTTPException(status_code=400, detail="ID and Name required.")
    if tournament_id_exists(body.tournament_id):
        raise HTTPException(
            status_code=409,
            detail=f"Tournament ID `{body.tournament_id}` already exists. Choose a unique ID.",
        )
    create_tournament({
        "tournament_id": body.tournament_id,
        "name": body.name,
        "sport": body.sport,
        "start_date": body.start_date,
        "allowed_misses": body.allowed_misses,
        "penalty_points": body.penalty_points,
        "created_by": admin["username"],
    })
    return get_tournament(body.tournament_id)


@router.patch("/{tournament_id}/status")
def update_status(
    tournament_id: str, body: TournamentStatusRequest, admin: dict = Depends(require_admin)
):
    if not get_tournament(tournament_id):
        raise HTTPException(status_code=404, detail="Tournament not found")
    update_tournament_status(tournament_id, body.status)
    return {"ok": True}


@router.delete("/{tournament_id}")
def delete_tournament_endpoint(tournament_id: str, admin: dict = Depends(require_admin)):
    delete_tournament(tournament_id)
    return {"ok": True}
