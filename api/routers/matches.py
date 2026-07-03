"""
api/routers/matches.py — match CRUD, votes, and CSV bulk upload.

GET endpoints are open to any authenticated user (reusable later by the
voting/home-page milestone); mutations are admin-only. The bulk-upload
endpoint mirrors admin/dashboard.py::_bulk_upload's validation/transform
logic exactly, using the shared utils/match_helpers.py functions.
"""

import io

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from data.db import (
    create_match,
    bulk_create_matches,
    delete_match,
    delete_vote,
    get_display_name,
    get_matches,
    get_votes,
    match_id_exists_in_tournament,
)
from utils.match_helpers import options_from_title, parse_time, validate_options
from utils.timezone import is_voting_open

from api.deps import get_current_user, require_admin
from api.schemas import BulkImportResult, MatchCreateRequest, MatchOut, VoteOut

router = APIRouter()

REQUIRED_CSV_COLUMNS = ["match_id", "title", "location", "match_date", "start_time", "timezone"]


@router.get("/tournaments/{tournament_id}/matches", response_model=list[MatchOut])
def list_matches(tournament_id: str, user: dict = Depends(get_current_user)):
    # is_voting_open is timezone-sensitive (per-match venue timezone) — computed
    # here rather than duplicating utils/timezone.py's logic in TypeScript.
    return [{**m, "is_voting_open": is_voting_open(m)} for m in get_matches(tournament_id=tournament_id)]


@router.post("/tournaments/{tournament_id}/matches", response_model=MatchOut)
def create_match_endpoint(
    tournament_id: str, body: MatchCreateRequest, admin: dict = Depends(require_admin)
):
    if not body.match_id.strip() or not body.title.strip():
        raise HTTPException(status_code=400, detail="ID and Title required.")

    options = body.options.strip() or options_from_title(body.title)
    valid, err = validate_options(options)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    if match_id_exists_in_tournament(body.match_id, tournament_id):
        raise HTTPException(
            status_code=409,
            detail=f"Match ID `{body.match_id}` already exists in this tournament.",
        )

    create_match({
        "match_id": body.match_id,
        "tournament_id": tournament_id,
        "title": body.title,
        "location": body.location,
        "match_date": body.match_date,
        "start_time": parse_time(body.start_time),
        "timezone": body.timezone,
        "options": options,
        "scoring_mode": body.scoring_mode,
        "fixed_odds": body.fixed_odds,
        "poll_mode": body.poll_mode,
        "created_by": admin["username"],
    })
    return next(m for m in get_matches(tournament_id=tournament_id) if m["match_id"] == body.match_id)


@router.post("/tournaments/{tournament_id}/matches/bulk", response_model=BulkImportResult)
async def bulk_upload(
    tournament_id: str, file: UploadFile, admin: dict = Depends(require_admin)
):
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str).fillna("")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV error: {e}")

    missing = [c for c in REQUIRED_CSV_COLUMNS if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {missing}")

    # All-or-nothing option validation, mirrors _bulk_upload exactly.
    errors = []
    for _, row in df.iterrows():
        opts = str(row.get("options", "")).strip() or options_from_title(str(row.get("title", "")))
        valid, err = validate_options(opts)
        if not valid:
            errors.append(f"`{row['match_id']}`: {err}")
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    rows = []
    skipped = []
    for _, row in df.iterrows():
        r = row.to_dict()
        if not r.get("options", "").strip():
            r["options"] = options_from_title(r.get("title", ""))
        if not r.get("scoring_mode", "").strip():
            r["scoring_mode"] = "ratio"
        if not r.get("poll_mode", "").strip():
            r["poll_mode"] = "closed"
        r["start_time"] = parse_time(r.get("start_time", "00:00"))

        if match_id_exists_in_tournament(r["match_id"], tournament_id):
            skipped.append({"match_id": r["match_id"], "reason": "ID already exists"})
            continue
        rows.append(r)

    if rows:
        bulk_create_matches(tournament_id, rows, admin["username"])

    return BulkImportResult(created=len(rows), skipped=skipped)


@router.delete("/matches/{match_id}")
def delete_match_endpoint(match_id: str, admin: dict = Depends(require_admin)):
    delete_match(match_id)
    return {"ok": True}


@router.get("/matches/{match_id}/votes", response_model=list[VoteOut])
def match_votes(match_id: str, admin: dict = Depends(require_admin)):
    votes = get_votes(match_id=match_id)
    return [{**v, "player_name": get_display_name(v["user_id"])} for v in votes]


@router.delete("/matches/{match_id}/votes/{user_id}")
def delete_match_vote(match_id: str, user_id: str, admin: dict = Depends(require_admin)):
    delete_vote(user_id, match_id)
    return {"ok": True}
