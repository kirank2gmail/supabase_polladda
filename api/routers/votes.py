"""
api/routers/votes.py — voting, poll summary, and result breakdown for a
single match. Mirrors pages/match.py's _voting_section/_poll_summary/
_result_section exactly, including the poll-visibility rules, split into
separate GET/POST endpoints so the frontend can refresh each section
independently after casting a vote (rather than one large page payload).
"""

from fastapi import APIRouter, Depends, HTTPException

from data.db import (
    cast_vote,
    get_display_name,
    get_match,
    get_points,
    get_user_vote,
    get_votes,
    update_vote,
)
from utils.timezone import format_countdown, format_match_times, is_voting_open

from api.deps import get_current_user
from api.schemas import (
    CountdownOut,
    MatchDetailResponse,
    MatchOut,
    MatchTimesOut,
    MissedPenalizedOut,
    PollOptionOut,
    PollSummaryResponse,
    PollVoterOut,
    ResultBreakdownResponse,
    ResultOptionOut,
    ResultVoterOut,
    VoteCastRequest,
    VoteSelfOut,
)

router = APIRouter()


def _options(match: dict) -> list[str]:
    return [o.strip() for o in match.get("options", "").split("|") if o.strip()]


def _get_match_or_404(match_id: str) -> dict:
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.get("/matches/{match_id}/detail", response_model=MatchDetailResponse)
def match_detail(match_id: str, user: dict = Depends(get_current_user)):
    match   = _get_match_or_404(match_id)
    user_tz = user.get("timezone") or "Asia/Kolkata"
    v       = get_user_vote(user["user_id"], match_id)
    message, severity = format_countdown(match)

    return MatchDetailResponse(
        match=MatchOut(**{**match, "is_voting_open": is_voting_open(match)}),
        times=MatchTimesOut(**format_match_times(match, user_tz)),
        countdown=CountdownOut(message=message, severity=severity),
        my_vote=VoteSelfOut(**v) if v else None,
    )


@router.post("/matches/{match_id}/vote", response_model=VoteSelfOut)
def cast_or_update_vote(
    match_id: str, body: VoteCastRequest, user: dict = Depends(get_current_user)
):
    match = _get_match_or_404(match_id)
    if not is_voting_open(match):
        raise HTTPException(status_code=409, detail="Voting has closed.")
    if body.vote not in _options(match):
        raise HTTPException(status_code=400, detail="Invalid option.")

    existing = get_user_vote(user["user_id"], match_id)
    if existing:
        if existing["vote"] == body.vote:
            raise HTTPException(status_code=409, detail=f"Already voted for {body.vote}.")
        update_vote(user["user_id"], match_id, body.vote)
    else:
        cast_vote(user["user_id"], match_id, match["tournament_id"], body.vote)

    return VoteSelfOut(**get_user_vote(user["user_id"], match_id))


@router.get("/matches/{match_id}/poll", response_model=PollSummaryResponse)
def poll_summary(match_id: str, user: dict = Depends(get_current_user)):
    match       = _get_match_or_404(match_id)
    is_admin    = user.get("role") == "admin"
    voting_open = is_voting_open(match)
    poll_mode   = match.get("poll_mode", "closed")

    votes = get_votes(match_id=match_id)
    total = len(votes)

    # Votes hidden from regular users ONLY while poll is still open AND
    # mode=closed. Once poll closes, all votes visible to everyone.
    hide = voting_open and not is_admin and poll_mode == "closed"
    if hide:
        return PollSummaryResponse(total=total, hidden=True, options=[])

    # Individual voters shown when poll is closed, or when admin views.
    show_voters = (not voting_open) or is_admin

    options_out = []
    for opt in _options(match):
        opt_votes = [v for v in votes if v["vote"] == opt]
        count     = len(opt_votes)
        pct       = round(count / total * 100) if total else 0
        voters    = None
        if show_voters and opt_votes:
            voters = [
                PollVoterOut(
                    user_id=v["user_id"],
                    name=get_display_name(v["user_id"]),
                    voted_at=v.get("voted_at"),
                )
                for v in opt_votes
            ]
        options_out.append(PollOptionOut(option=opt, count=count, pct=pct, voters=voters))

    return PollSummaryResponse(total=total, hidden=False, options=options_out)


@router.get("/matches/{match_id}/result", response_model=ResultBreakdownResponse)
def result_breakdown(match_id: str, user: dict = Depends(get_current_user)):
    match = _get_match_or_404(match_id)
    if match.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Match has no result yet.")

    result   = match.get("result", "")
    votes    = get_votes(match_id=match_id)
    pts_list = get_points()   # unfiltered, mirrors pages/match.py's _result_section exactly

    winner_pts = next(
        (float(p["total_points"]) for p in pts_list
         if p["match_id"] == match_id and float(p.get("total_points", 0)) > 0),
        0.0,
    )

    options_out = []
    for opt in _options(match):
        opt_votes = [v for v in votes if v["vote"] == opt]
        is_win    = opt == result
        voters = []
        for v in opt_votes:
            u_pts = next(
                (float(p["total_points"]) for p in pts_list
                 if p["user_id"] == v["user_id"] and p["match_id"] == match_id),
                0.0,
            )
            voters.append(ResultVoterOut(
                user_id=v["user_id"], name=get_display_name(v["user_id"]),
                voted_at=v.get("voted_at"), points=u_pts,
            ))
        pts_label = f"+{winner_pts} pts each" if is_win and winner_pts else "−1 pt each"
        options_out.append(ResultOptionOut(
            option=opt, is_win=is_win, pts_label=pts_label, voters=voters,
        ))

    missed_out = [
        MissedPenalizedOut(
            user_id=p["user_id"], name=get_display_name(p["user_id"]),
            note=p["note"], points=float(p["total_points"]),
        )
        for p in pts_list
        if p["match_id"] == match_id
        and ("miss" in p.get("note", "") or "penalty" in p.get("note", ""))
    ]

    return ResultBreakdownResponse(
        result=result, winner_points=winner_pts, options=options_out, missed=missed_out,
    )
