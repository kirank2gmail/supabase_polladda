"""
api/schemas.py — Pydantic request/response models.

Field names verified against the actual dicts returned by data/db.py and
data/leaderboard_builder.py::build_lb_data() as of this milestone.
"""

from typing import Any
from pydantic import BaseModel


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    user_id: str
    username: str
    nickname: str
    role: str
    must_change_password: bool
    timezone: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut
    must_change_password: bool
    is_legacy_password: bool


class ChangePasswordRequest(BaseModel):
    new_password: str
    # Required only for the normal profile-change flow (verified against the
    # current password first); omitted for the forced-reset flow, mirroring
    # app.py's show_change_password (no old-password check) vs show_profile's
    # pw_form (checks verify_password(uid, old) first).
    current_password: str | None = None


class BootstrapAdminRequest(BaseModel):
    username: str
    password: str


# ── Tournaments / leaderboard ────────────────────────────────────────────────

class TournamentOut(BaseModel):
    tournament_id: str
    name: str
    sport: str | None = None
    start_date: str | None = None
    status: str
    allowed_misses: int
    penalty_points: float


class HeroStat(BaseModel):
    names: str
    value: int


class PenaltyOut(BaseModel):
    penalty_id: str
    tournament_id: str
    user_id: str
    points: float
    reason: str
    created_at: str
    player_name: str


class LeaderboardResponse(BaseModel):
    # rows carry fixed keys (user_id, name, total_points, win_pct, missed,
    # rank, curr_win_streak, curr_loss_streak, max_win_streak, max_loss_streak)
    # PLUS one dynamic key per match_id (cell value: float | str | None) — use
    # col_match_ids to know which keys are match columns.
    rows: list[dict[str, Any]]
    matches_asc: list[dict[str, Any]]
    match_ids_desc: list[str]
    col_match_ids: list[str]
    labels: dict[str, str]
    col_totals: dict[str, float]
    grand_total: float
    bank: float
    penalty_total: float
    penalties: list[PenaltyOut]
    heroes: dict[str, HeroStat]


# ── Admin: users ──────────────────────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class RoleUpdateRequest(BaseModel):
    role: str


class PasswordResetRequest(BaseModel):
    new_password: str


# ── Admin: tournaments ────────────────────────────────────────────────────────

class TournamentCreateRequest(BaseModel):
    tournament_id: str
    name: str
    sport: str
    start_date: str
    allowed_misses: int = 3
    penalty_points: float = 1.0


class TournamentStatusRequest(BaseModel):
    status: str


# ── Admin: matches ────────────────────────────────────────────────────────────

class MatchCreateRequest(BaseModel):
    match_id: str
    title: str
    location: str
    match_date: str
    start_time: str
    timezone: str
    options: str = ""
    scoring_mode: str = "ratio"
    fixed_odds: float = 1.0
    poll_mode: str = "closed"


class MatchOut(BaseModel):
    match_id: str
    tournament_id: str
    title: str
    location: str
    match_date: str
    start_time: str
    timezone: str
    options: str
    scoring_mode: str
    fixed_odds: float
    poll_mode: str
    status: str
    result: str
    created_by: str | None = None
    created_at: str | None = None


class VoteOut(BaseModel):
    vote_id: str
    user_id: str
    match_id: str
    tournament_id: str
    vote: str
    voted_at: str | None = None
    updated_at: str | None = None
    update_count: int
    player_name: str


class BulkImportSkip(BaseModel):
    match_id: str
    reason: str


class BulkImportResult(BaseModel):
    created: int
    skipped: list[BulkImportSkip]
