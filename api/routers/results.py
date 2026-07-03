"""
api/routers/results.py — recalculate/rebuild, match results, manual penalties.

All admin-only. Result-saving and email-sending logic is shared with
Streamlit via data/points.py::apply_match_result and
utils/email_sender.py::send_result_emails — no scoring logic lives here.
"""

from fastapi import APIRouter, Depends, HTTPException

from data.db import (
    add_penalty,
    delete_penalty,
    get_display_name,
    get_match,
    get_penalties,
)
from data.match_players import migrate_from_votes
from data.points import apply_match_result, recalculate_tournament
from utils.email_sender import email_configured, send_result_emails

from api.deps import require_admin
from api.schemas import (
    MatchResultRequest,
    MatchResultResponse,
    PenaltyCreateRequest,
    PenaltyOut,
    RebuildResult,
    RecalculateResult,
)

router = APIRouter()


@router.post("/tournaments/{tournament_id}/recalculate", response_model=RecalculateResult)
def recalculate(tournament_id: str, admin: dict = Depends(require_admin)):
    try:
        recalc, abandoned, errors = recalculate_tournament(tournament_id)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return RecalculateResult(recalculated=recalc, abandoned=abandoned, errors=errors)


@router.post(
    "/tournaments/{tournament_id}/rebuild-match-players", response_model=RebuildResult
)
def rebuild_match_players(tournament_id: str, admin: dict = Depends(require_admin)):
    n = migrate_from_votes(tournament_id=tournament_id)
    return RebuildResult(written=n)


@router.post("/matches/{match_id}/result", response_model=MatchResultResponse)
def save_result(
    match_id: str, body: MatchResultRequest, admin: dict = Depends(require_admin)
):
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    outcome = apply_match_result(match_id, body.tournament_id, body.winner)

    email_sent = False
    email_error = None
    if not outcome["abandoned"] and email_configured():
        try:
            send_result_emails(match, body.winner, body.tournament_id, outcome["records"])
            email_sent = True
        except Exception as e:
            email_error = str(e)

    return MatchResultResponse(
        abandoned=outcome["abandoned"],
        correct_voters=outcome["correct_voters"],
        email_sent=email_sent,
        email_error=email_error,
    )


@router.get("/tournaments/{tournament_id}/penalties", response_model=list[PenaltyOut])
def list_penalties(tournament_id: str, admin: dict = Depends(require_admin)):
    penalties = get_penalties(tournament_id)
    return [{**p, "player_name": get_display_name(p["user_id"])} for p in penalties]


@router.post("/tournaments/{tournament_id}/penalties", response_model=PenaltyOut)
def create_penalty(
    tournament_id: str, body: PenaltyCreateRequest, admin: dict = Depends(require_admin)
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required.")
    record = add_penalty(tournament_id, body.user_id, body.points, body.reason)
    return {**record, "player_name": get_display_name(body.user_id)}


@router.delete("/penalties/{penalty_id}")
def delete_penalty_endpoint(penalty_id: str, admin: dict = Depends(require_admin)):
    delete_penalty(penalty_id)
    return {"ok": True}
