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

def _get_match_players_for_match(match_id: str, tournament_id: str) -> list[dict]:
    """
    Read match_players for this specific match directly from GCS.
    Returns all records: voted, missed, quit, not_started.
    No cache — always fresh.
    """
    from data.gcs import _fetch
    return [r for r in _fetch("match_players")
            if r["match_id"] == match_id
            and r["tournament_id"] == tournament_id]

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
                         all_mp: list = None) -> int:
    """
    Count how many 'missed' records this player has BEFORE match_id
    in match_players.json.

    match_players.json is the single source of truth — it already contains
    explicit 'missed' records written when results are saved or when
    recalculate tournament runs. No date comparison or votes.json needed.

    all_mp: pre-fetched match_players for the tournament (avoids repeated
            GCS reads when called in a loop).
    """
    from data.gcs import _fetch

    if all_mp is None:
        all_mp = _fetch("match_players")

    # Get this match's date+time for "before" comparison
    all_matches = _get_matches(tournament_id=tournament_id)
    this_match  = next((m for m in all_matches if m["match_id"] == match_id), None)
    if not this_match:
        return 0
    this_dt = f"{this_match['match_date']} {this_match['start_time']}"

    # Build match_id → date+time lookup
    match_dt_map = {
        m["match_id"]: f"{m['match_date']} {m['start_time']}"
        for m in all_matches
    }

    # Count real missed records strictly before this match (exclude miss_floor)
    real_count = sum(
        1 for r in all_mp
        if r["user_id"] == user_id
        and r["tournament_id"] == tournament_id
        and r["status"] == "missed"
        and r.get("note") != "miss_floor"
        and match_dt_map.get(r["match_id"], "") < this_dt
        and r["match_id"] != match_id
    )

    # If a miss floor is active and its boundary is at or before this match,
    # the player's effective prior miss count is at least allowed_misses.
    floor_records = [r for r in all_mp
                     if r["tournament_id"] == tournament_id
                     and r.get("note") == "miss_floor"]
    if floor_records:
        floor_match_ids = {r["match_id"] for r in floor_records}
        # Use the earliest floor boundary
        floor_dt = min(
            match_dt_map.get(mid, "")
            for mid in floor_match_ids
            if mid in match_dt_map
        )
        if floor_dt and floor_dt <= this_dt:
            t_obj = next((t for t in read_table("tournaments")
                          if t["tournament_id"] == tournament_id), None)
            allowed = int((t_obj or {}).get("allowed_misses", 3))
            real_count = max(real_count, allowed)

    return real_count
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

    # Read match_players fresh from GCS — single source of truth, no cache
    from data.gcs import _fetch as _gcs_fetch
    all_mp   = _gcs_fetch("match_players")
    mp_match = [r for r in all_mp
                if r["match_id"] == match_id
                and r["tournament_id"] == tournament_id]

    # Split by status — match_players has all records pre-computed
    voted_records  = [r for r in mp_match if r["status"] == "voted"]
    missed_records = [r for r in mp_match if r["status"] == "missed" and r.get("note") != "miss_floor"]
    quit_records   = [r for r in mp_match if r["status"] == "quit"]
    # not_started records are ignored — player wasn't participating yet

    winner_votes = [r for r in voted_records if r["vote"] == winning_option]
    loser_votes  = [r for r in voted_records if r["vote"] != winning_option]
    n_winners    = len(winner_votes)

    results    = []
    ratio_pool = 0.0   # accumulates only in ratio mode

    # ── Missed voters ─────────────────────────────────────────────────────────
    for r in missed_records:
        user_id = r["user_id"]
        prior = _count_prior_misses(user_id, match_id, tournament_id, all_mp)
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
    for r in loser_votes:
        dest = "winner pool" if scoring_mode == "ratio" else "bank"
        if scoring_mode == "ratio":
            ratio_pool += 1.0
        results.append({
            "user_id": r["user_id"], "match_id": match_id,
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

    for r in winner_votes:
        results.append({
            "user_id": r["user_id"], "match_id": match_id,
            "tournament_id": tournament_id,
            "base_points": total_win, "penalty_points": 0,
            "bonus_points": 0, "total_points": total_win,
            "note": note_win,
        })

    # ── Quit players — 0 points, excluded from pool ───────────────────────────
    for r in quit_records:
        results.append({
            "user_id": r["user_id"], "match_id": match_id,
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


def _mark_abandoned(match_id: str):
    """Delete points and mark match as abandoned."""
    delete_match_points(match_id)
    matches = read_table("matches")
    for m in matches:
        if m["match_id"] == match_id:
            m["result"] = "abandoned"
            m["status"] = "abandoned"
    write_table("matches", matches)


def run_points_calculation(match_id: str, tournament_id: str,
                            winning_option: str):
    """
    Dedup votes → check active (non-quit) voters → calculate → save.
    Returns ABANDONED (sentinel string) when the match has no valid contest.
    Returns list[dict] of point records on success.

    Abandon conditions (evaluated against non-quit voted records only):
      - No votes at all from active players
      - Nobody voted for the winning option
      - All active voters picked the same option (no contest)

    Quit players are excluded from abandon checks — their historical votes
    in votes.json are irrelevant once they have quit status in match_players.
    """
    _deduplicate_votes(match_id)

    # Use match_players as the source of truth for who is active.
    # Quit players may still have votes in votes.json — ignore them here.
    from data.gcs import _fetch as _gcs_fetch
    all_mp   = _gcs_fetch("match_players")
    mp_match = [r for r in all_mp
                if r["match_id"] == match_id
                and r["tournament_id"] == tournament_id]

    active_voted = [r for r in mp_match if r["status"] == "voted"]

    if not active_voted:
        _mark_abandoned(match_id)
        return ABANDONED

    # ── Abandon if no winners or no meaningful contest ────────────────────────
    # Evaluated only on active (non-quit) voted records.
    winner_active  = [r for r in active_voted if r.get("vote") == winning_option]
    unique_options = {r.get("vote") for r in active_voted}
    if not winner_active or len(unique_options) == 1:
        _mark_abandoned(match_id)
        return ABANDONED

    delete_match_points(match_id)
    records = calculate_match_points(match_id, tournament_id, winning_option)
    if records:
        save_points_batch(records)
    return records
