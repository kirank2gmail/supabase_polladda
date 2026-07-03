"""
api/routers/home.py — Home page: upcoming / in-progress / completed match
cards for the current user, scoped to one tournament.

Mirrors pages/home.py's three-section layout (_card_upcoming/
_card_in_progress/_card_completed) as a single request, so the page doesn't
need N+1 calls per match — same reasoning as the leaderboard endpoint.
Countdown/local-time formatting is computed here (utils/timezone.py) rather
than duplicated in TypeScript, same precedent as MatchOut.is_voting_open in
api/routers/matches.py.
"""

from fastapi import APIRouter, Depends

from data.db import get_matches, get_points, get_votes
from utils.timezone import format_countdown, format_match_times, is_voting_open

from api.deps import get_current_user
from api.schemas import CountdownOut, HomeMatchOut, HomeResponse, MatchOut, MatchTimesOut

router = APIRouter()


def _times_out(m: dict, user_tz: str) -> MatchTimesOut:
    return MatchTimesOut(**format_match_times(m, user_tz))


def _countdown_out(m: dict) -> CountdownOut:
    message, severity = format_countdown(m)
    return CountdownOut(message=message, severity=severity)


@router.get("/tournaments/{tournament_id}/home", response_model=HomeResponse)
def home(tournament_id: str, user: dict = Depends(get_current_user)):
    user_tz = user.get("timezone") or "Asia/Kolkata"
    user_id = user["user_id"]

    all_matches = get_matches(tournament_id=tournament_id)
    upcoming    = [m for m in all_matches if m["status"] == "upcoming" and is_voting_open(m)]
    in_progress = [m for m in all_matches if m["status"] == "upcoming" and not is_voting_open(m)]
    completed   = [m for m in all_matches if m["status"] == "completed"]

    # Fetch votes/points ONCE for the whole tournament — not per card,
    # mirrors pages/home.py's own "fetch once" comment for the same reason.
    votes_all = get_votes(tournament_id=tournament_id)
    pts_all   = get_points(tournament_id=tournament_id, user_id=user_id)

    def vote_for(match_id: str) -> dict | None:
        return next(
            (v for v in votes_all if v["user_id"] == user_id and v["match_id"] == match_id),
            None,
        )

    def points_for(match_id: str) -> float:
        return next(
            (float(p.get("total_points", 0)) for p in pts_all if p["match_id"] == match_id),
            0.0,
        )

    up_cards = [
        HomeMatchOut(
            match=MatchOut(**{**m, "is_voting_open": True}),
            times=_times_out(m, user_tz),
            countdown=_countdown_out(m),
            my_vote=(vote_for(m["match_id"]) or {}).get("vote"),
        )
        for m in upcoming
    ]

    ip_cards = [
        HomeMatchOut(
            match=MatchOut(**{**m, "is_voting_open": False}),
            times=_times_out(m, user_tz),
            my_vote=(vote_for(m["match_id"]) or {}).get("vote"),
        )
        for m in in_progress
    ]

    done_cards = []
    for m in reversed(completed):   # newest first, same as pages/home.py
        v = vote_for(m["match_id"])
        done_cards.append(HomeMatchOut(
            match=MatchOut(**{**m, "is_voting_open": False}),
            times=_times_out(m, user_tz),
            my_vote=v.get("vote") if v else None,
            my_points=points_for(m["match_id"]),
            correct=(v.get("vote") == m.get("result")) if v else None,
        ))

    return HomeResponse(upcoming=up_cards, in_progress=ip_cards, completed=done_cards)
