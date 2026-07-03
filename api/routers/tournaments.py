"""
api/routers/tournaments.py — tournament + leaderboard endpoints.

Leaderboard handler is a thin wrapper: data/leaderboard_builder.py's
build_lb_data() dict already matches LeaderboardResponse field-for-field.
"""

from fastapi import APIRouter, Depends, HTTPException

from data.db import get_tournament, get_tournaments
from data.leaderboard_builder import build_lb_data

from api.deps import get_current_user
from api.schemas import LeaderboardResponse, TournamentOut

router = APIRouter()


@router.get("", response_model=list[TournamentOut])
def list_tournaments(user: dict = Depends(get_current_user)):
    return get_tournaments()


@router.get("/{tournament_id}/leaderboard", response_model=LeaderboardResponse)
def leaderboard(tournament_id: str, user: dict = Depends(get_current_user)):
    if not get_tournament(tournament_id):
        raise HTTPException(status_code=404, detail="Tournament not found")
    return build_lb_data(tournament_id)
