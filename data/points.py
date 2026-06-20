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

def _get_match_players(match_id: str, tournament_id: str) -> list[dict]:
    """
    Read match_players for this specific match directly from GCS.
    No cache — always fresh. Returns list of {user_id, status, ...}.
    Only active players are considered for miss/winner/loser logic.
    Quit players get 0 points and are excluded from the pool.
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
                         tournament_id: str) -> int:
    """
    Count matches this user missed BEFORE match_id in this tournament.

    Uses match_players.json (read fresh from GCS) — no registrations needed.
    A "miss" is a match where the player has an "active" record in match_players
    but no vote in votes.json.
    Only counts from the player's first match_player record onwards.
    Abandoned matches are excluded (they have no match_player records).
    """
    from data.gcs import _fetch

    # All non-abandoned matches in this tournament
    all_matches = [m for m in _get_matches(tournament_id=tournament_id)
                   if m.get("result") != "abandoned"
                   and m.get("status") != "abandoned"]

    this_match = next((m for m in all_matches
                       if m["match_id"] == match_id), None)
    if not this_match:
        return 0

    this_dt = f"{this_match['match_date']} {this_match['start_time']}"

    # Get this player's match_player records (active + quit) for this tournament
    all_mp = _fetch("match_players")
    player_mp = [r for r in all_mp
                 if r["user_id"] == user_id
                 and r["tournament_id"] == tournament_id]

    if not player_mp:
        return 0  # no match_player records — player hasn't started yet

    # Build set of match IDs where player has a vote
    all_votes  = _get_votes(tournament_id=tournament_id)
    voted_ids  = {v["match_id"] for v in all_votes if v["user_id"] == user_id}

    # Player's first active match (by match date+time)
    active_mp_ids = {r["match_id"] for r in player_mp if r["status"] == "active"}
    if not active_mp_ids:
        return 0

    active_match_dts = [
        f"{m['match_date']} {m['start_time']}"
        for m in all_matches if m["match_id"] in active_mp_ids
    ]
    if not active_match_dts:
        return 0

    first_active_dt = min(active_match_dts)

    # Count matches where:
    #   1. Started strictly AFTER player's first active match
    #   2. Started strictly BEFORE this match
    #   3. Player has an active match_player record (not quit, not before joining)
    #   4. Player did NOT vote
    active_mp_id_set = {r["match_id"] for r in player_mp if r["status"] == "active"}

    return sum(
        1 for m in all_matches
        if m["match_id"] != match_id
        and f"{m['match_date']} {m['start_time']}" > first_active_dt
        and f"{m['match_date']} {m['start_time']}" < this_dt
        and m["match_id"] in active_mp_id_set
        and m["match_id"] not in voted_ids
    )
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

    # Read match_players fresh from GCS — no cache
    mp_records   = _get_match_players(match_id, tournament_id)
    active_users = {r["user_id"] for r in mp_records if r["status"] == "active"}
    quit_users   = {r["user_id"] for r in mp_records if r["status"] == "quit"}

    votes        = _get_votes(match_id=match_id)
    voted_users  = {v["user_id"] for v in votes if v["user_id"] in active_users}
    missed_users = [u for u in active_users if u not in voted_users]

    winner_votes = [v for v in votes
                    if v["vote"] == winning_option and v["user_id"] in active_users]
    loser_votes  = [v for v in votes
                    if v["vote"] != winning_option and v["user_id"] in active_users]
    n_winners    = len(winner_votes)

    results    = []
    ratio_pool = 0.0   # accumulates only in ratio mode

    # ── Missed voters ─────────────────────────────────────────────────────────
    for user_id in missed_users:
        prior = _count_prior_misses(user_id, match_id, tournament_id)
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

    # ── Quit players — 0 points, excluded from pool ─────────────────────────
    for user_id in quit_users:
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
