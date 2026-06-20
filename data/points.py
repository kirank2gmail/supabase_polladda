"""
data/points.py — Points calculation engine.

Exact rules:

  FREE MISS (within allowed_misses):
    pts = 0. Nothing goes anywhere.

  PENALISED MISS (beyond allowed_misses):
    pts = -penalty_pts (configurable, default 1.0)
    RATIO mode → goes to winner pool
    FIXED mode → goes to bank

  LOSER (voted wrong):
    pts = -1 always (both modes)
    RATIO mode → -1 goes to winner pool
    FIXED mode → -1 goes to bank

  WINNER:
    RATIO mode → pool (all loser pts + all penalised miss pts) / n_winners
    FIXED mode → fixed_odds (flat). Everything else goes to bank.
"""

from data.gcs import read_table, write_table

ABANDONED = "abandoned"   # sentinel returned when match has no voters


def _get_tournament(tid):
    return next((t for t in read_table("tournaments")
                 if t["tournament_id"] == tid), None)

def _get_match(mid):
    return next((m for m in read_table("matches")
                 if m["match_id"] == mid), None)

def _get_registrations(tid):
    return [r for r in read_table("registrations")
            if r["tournament_id"] == tid]

def _get_votes(match_id=None, tournament_id=None):
    vs = read_table("votes")
    if match_id:      vs = [v for v in vs if v["match_id"] == match_id]
    if tournament_id: vs = [v for v in vs if v["tournament_id"] == tournament_id]
    return vs

def _get_matches(tournament_id=None, status=None):
    ms = read_table("matches")
    if tournament_id: ms = [m for m in ms if m["tournament_id"] == tournament_id]
    if status:        ms = [m for m in ms if m.get("status") == status]
    return ms

def _uid():
    import uuid; return str(uuid.uuid4())[:8]

def _now():
    from datetime import datetime; return datetime.utcnow().isoformat()


def _count_prior_misses(user_id: str, match_id: str,
                         tournament_id: str,
                         quit_map: dict = None) -> int:
    """
    Count matches this user missed BEFORE match_id in this tournament.

    Key fix: counts ALL tournament matches (any status) before this match,
    not just completed ones. This ensures accuracy when results are entered
    out of chronological order — earlier missed matches are still counted
    even if their results haven't been entered yet.

    Abandoned matches excluded. Counts only from player's first voted match.
    """
    # All non-abandoned matches in tournament regardless of status
    all_matches = [m for m in _get_matches(tournament_id=tournament_id)
                   if m.get("result") != "abandoned"
                   and m.get("status") != "abandoned"]

    this_match = next((m for m in all_matches
                       if m["match_id"] == match_id), None)
    if not this_match:
        return 0

    this_dt    = f"{this_match['match_date']} {this_match['start_time']}"
    all_votes  = _get_votes(tournament_id=tournament_id)
    user_votes = [v for v in all_votes if v["user_id"] == user_id]
    voted_ids  = {v["match_id"] for v in user_votes}

    if not voted_ids:
        return 0   # never voted — no misses

    # Find the player's first voted match date+time
    voted_match_dts = [
        f"{m['match_date']} {m['start_time']}"
        for m in all_matches if m["match_id"] in voted_ids
    ]
    if not voted_match_dts:
        return 0

    first_vote_dt = min(voted_match_dts)

    # Use passed quit_map if available (avoids extra GCS read),
    # otherwise fetch fresh. Quit matches excluded from miss counting.
    effective_quit_map = quit_map if quit_map is not None else _get_quit_players(tournament_id)

    # Count matches that:
    #   1. Started strictly AFTER the player's first voted match
    #   2. Started strictly BEFORE this match
    #   3. Player did not vote in
    #   4. Player was NOT quit at that match's time
    return sum(
        1 for m in all_matches
        if m["match_id"] != match_id
        and f"{m['match_date']} {m['start_time']}" > first_vote_dt
        and f"{m['match_date']} {m['start_time']}" < this_dt
        and m["match_id"] not in voted_ids
        and not _player_quit_before(user_id, m, effective_quit_map)
    )
def _get_quit_players(tournament_id: str) -> dict:
    """
    Return {user_id: quit_at_iso} for players who quit this tournament.
    Always reads fresh from GCS — bypasses session cache — so that quit
    status set immediately before a recalculation is always visible.
    """
    return {
        r["user_id"]: r["quit_at"]
        for r in read_table("registrations", force_fresh=True)
        if r.get("tournament_id") == tournament_id
        and r.get("quit_at")
    }


def _player_quit_before(user_id: str, match: dict,
                         quit_map: dict) -> bool:
    """
    True if this player quit at or before the match start time.
    Both quit_at (stored as UTC ISO) and match start time are converted
    to UTC for accurate cross-timezone comparison.
    """
    quit_at = quit_map.get(user_id, "")
    if not quit_at:
        return False
    try:
        from datetime import datetime, timezone
        import pytz

        # Parse quit time (stored as UTC ISO)
        quit_dt = datetime.fromisoformat(quit_at)
        if quit_dt.tzinfo is None:
            quit_dt = quit_dt.replace(tzinfo=timezone.utc)
        quit_utc = quit_dt.astimezone(timezone.utc)

        # Convert match start time to UTC using match's own timezone
        tz_name  = match.get("timezone") or "Asia/Kolkata"
        match_tz = pytz.timezone(tz_name)
        naive_dt = datetime.strptime(
            f"{match['match_date']} {match['start_time']}", "%Y-%m-%d %H:%M"
        )
        match_utc = match_tz.localize(naive_dt).astimezone(timezone.utc)

        return quit_utc <= match_utc
    except Exception:
        # Fallback: compare as ISO strings (less accurate but safe)
        try:
            return quit_at[:16] <= f"{match['match_date']} {match['start_time']}"
        except Exception:
            return False


def calculate_match_points(match_id: str, tournament_id: str,
                            winning_option: str) -> list[dict]:
    tournament = _get_tournament(tournament_id)
    if not tournament:
        raise ValueError(f"Tournament {tournament_id} not found")

    match          = _get_match(match_id) or {}
    scoring_mode   = match.get("scoring_mode", "ratio")
    fixed_odds     = float(match.get("fixed_odds", 1.0))
    allowed_misses = int(tournament.get("allowed_misses", 3))
    penalty_pts    = float(tournament.get("penalty_points", 1.0))

    # Players who quit — always reads fresh from GCS via _get_quit_players
    quit_map = _get_quit_players(tournament_id)

    registered   = [r["user_id"] for r in _get_registrations(tournament_id)]
    votes        = _get_votes(match_id=match_id)

    # Exclude quit players from votes and missed calculation
    # Quit players get 0 points for all matches after their quit time
    active_registered = [
        u for u in registered
        if not _player_quit_before(u, match, quit_map)
    ]
    quit_in_match = [
        u for u in registered
        if _player_quit_before(u, match, quit_map)
    ]

    voted_users  = {v["user_id"] for v in votes if v["user_id"] in active_registered}
    missed_users = [u for u in active_registered if u not in voted_users]

    winner_votes = [v for v in votes
                    if v["vote"] == winning_option
                    and v["user_id"] in active_registered]
    loser_votes  = [v for v in votes
                    if v["vote"] != winning_option
                    and v["user_id"] in active_registered]
    n_winners    = len(winner_votes)

    results    = []
    ratio_pool = 0.0   # accumulates only in ratio mode

    # ── Missed voters ─────────────────────────────────────────────────────────
    for user_id in missed_users:
        prior = _count_prior_misses(user_id, match_id, tournament_id, quit_map)
        if prior >= allowed_misses:
            dest = "winner pool" if scoring_mode == "ratio" else "bank"
            if scoring_mode == "ratio":
                ratio_pool += penalty_pts
            results.append({
                "user_id": user_id, "match_id": match_id,
                "tournament_id": tournament_id,
                "base_points": 0, "penalty_points": -penalty_pts,
                "bonus_points": 0, "total_points": -penalty_pts,
                "note": f"penalty (-{penalty_pts} → {dest})",
            })
        else:
            results.append({
                "user_id": user_id, "match_id": match_id,
                "tournament_id": tournament_id,
                "base_points": 0, "penalty_points": 0,
                "bonus_points": 0, "total_points": 0,
                "note": f"free miss ({prior+1}/{allowed_misses})",
            })

    # ── Losers — always -1 ────────────────────────────────────────────────────
    for v in loser_votes:
        dest = "winner pool" if scoring_mode == "ratio" else "bank"
        if scoring_mode == "ratio":
            ratio_pool += 1.0
        results.append({
            "user_id": v["user_id"], "match_id": match_id,
            "tournament_id": tournament_id,
            "base_points": -1, "penalty_points": 0,
            "bonus_points": 0, "total_points": -1,
            "note": f"wrong (-1 → {dest})",
        })

    # ── Winners ───────────────────────────────────────────────────────────────
    if scoring_mode == "fixed":
        total_win = fixed_odds
        note_win  = f"correct fixed=+{fixed_odds}"
    else:
        per_winner = round(ratio_pool / n_winners, 4) if n_winners > 0 else 1.0
        total_win  = per_winner
        note_win   = (f"correct ratio "
                      f"(pool={round(ratio_pool,3)} ÷ {n_winners} winners = +{per_winner})")

    for v in winner_votes:
        results.append({
            "user_id": v["user_id"], "match_id": match_id,
            "tournament_id": tournament_id,
            "base_points": total_win, "penalty_points": 0,
            "bonus_points": 0, "total_points": total_win,
            "note": note_win,
        })

    # ── Quit players — 0 points, excluded from pool ──────────────────────────
    for user_id in quit_in_match:
        results.append({
            "user_id": user_id, "match_id": match_id,
            "tournament_id": tournament_id,
            "base_points": 0, "penalty_points": 0,
            "bonus_points": 0, "total_points": 0,
            "note": "quit",
        })

    return results


def delete_match_points(match_id: str):
    existing = read_table("points")
    write_table("points", [p for p in existing if p["match_id"] != match_id])


def save_points_batch(records: list[dict]):
    existing = read_table("points")
    now = _now()
    for r in records:
        existing.append({
            "point_id"      : _uid(),
            "user_id"       : r["user_id"],
            "match_id"      : r["match_id"],
            "tournament_id" : r["tournament_id"],
            "base_points"   : r.get("base_points",    0),
            "penalty_points": r.get("penalty_points", 0),
            "bonus_points"  : r.get("bonus_points",   0),
            "total_points"  : r.get("total_points",   0),
            "note"          : r.get("note",           ""),
            "calculated_at" : now,
        })
    write_table("points", existing)


def _deduplicate_votes(match_id: str):
    """
    Keep only the most recent vote per user per match.
    Sorts by updated_at then voted_at, keeps latest, deletes rest.
    """
    from collections import defaultdict
    votes  = read_table("votes")
    by_user: dict = defaultdict(list)
    for v in votes:
        if v.get("match_id") == match_id:
            by_user[v["user_id"]].append(v)

    changed  = False
    keep_ids = set()
    drop_ids = set()

    for uid, uvotes in by_user.items():
        if len(uvotes) <= 1:
            if uvotes:
                keep_ids.add(uvotes[0]["vote_id"])
            continue
        # Sort newest first
        uvotes.sort(
            key=lambda v: v.get("updated_at") or v.get("voted_at") or "",
            reverse=True
        )
        keep_ids.add(uvotes[0]["vote_id"])
        for v in uvotes[1:]:
            drop_ids.add(v["vote_id"])
        changed = True

    if changed and drop_ids:
        cleaned = [v for v in votes if v.get("vote_id") not in drop_ids]
        write_table("votes", cleaned)


def run_points_calculation(match_id: str, tournament_id: str,
                            winning_option: str):
    """
    Dedup votes → check voters → calculate → save.
    Returns ABANDONED sentinel when no votes exist.
    """
    """
    Dedup votes → check voters → calculate → save.
    Returns ABANDONED (sentinel string) when no votes exist.
    Returns list[dict] of point records on success.

    When abandoned:
      - All point records for the match are deleted (clears stale misses)
      - Match status set to "abandoned" so future miss calculations skip it
    """
    _deduplicate_votes(match_id)

    match_votes = [v for v in read_table("votes")
                   if v.get("match_id") == match_id]

    if not match_votes:
        # Delete all point records (winners, losers, misses) for this match
        delete_match_points(match_id)
        # Mark match abandoned so _count_prior_misses skips it
        matches = read_table("matches")
        for m in matches:
            if m["match_id"] == match_id:
                m["result"] = "abandoned"
                m["status"] = "abandoned"
        write_table("matches", matches)
        return ABANDONED

    # ── Abandon if no winners ─────────────────────────────────────────────────
    # Case 1: nobody voted for the winning option.
    # Case 2: all votes are for the same option (no meaningful contest).
    # In both cases — clear points, mark abandoned, skip miss counting.
    winner_votes   = [v for v in match_votes if v.get("vote") == winning_option]
    unique_options = {v.get("vote") for v in match_votes}
    if not winner_votes or len(unique_options) == 1:
        delete_match_points(match_id)
        matches = read_table("matches")
        for m in matches:
            if m["match_id"] == match_id:
                m["result"] = "abandoned"
                m["status"] = "abandoned"
        write_table("matches", matches)
        return ABANDONED

    delete_match_points(match_id)
    records = calculate_match_points(match_id, tournament_id, winning_option)
    if records:
        save_points_batch(records)
    return records
