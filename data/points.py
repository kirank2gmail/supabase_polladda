"""
data/points.py — Points calculation engine (Supabase Postgres backend).

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

from data.supabase_client import read_table, get_client, sess_clear, ttl_votes_clear, select_all

ABANDONED = "abandoned"   # sentinel returned when match has no voters


def _get_tournament(tid):
    return next((t for t in read_table("tournaments")
                 if t["tournament_id"] == tid), None)

def _get_match(mid):
    return next((m for m in read_table("matches")
                 if m["match_id"] == mid), None)

def _get_match_players_for_match(match_id: str, tournament_id: str) -> list[dict]:
    """
    Read match_players for this specific match directly from Supabase.
    Returns all records: voted, missed, quit, not_started.
    No cache — always fresh.
    """
    return select_all(lambda: get_client().table("match_players").select("*")
                       .eq("match_id", match_id).eq("tournament_id", tournament_id))

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
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _count_prior_misses(user_id: str, match_id: str,
                         tournament_id: str,
                         all_mp: list = None) -> int:
    """
    Count how many 'missed' records this player has BEFORE match_id
    in match_players.

    match_players is the single source of truth — it already contains
    explicit 'missed' records written when results are saved or when
    recalculate tournament runs. No date comparison or votes table needed.

    all_mp: pre-fetched match_players for the tournament (avoids repeated
            reads when called in a loop).
    """
    if all_mp is None:
        all_mp = select_all(lambda: get_client().table("match_players").select("*")
                             .eq("tournament_id", tournament_id))

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
            t_obj = _get_tournament(tournament_id)
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

    # Read match_players fresh, tournament-scoped — single source of truth, no cache
    all_mp   = select_all(lambda: get_client().table("match_players").select("*")
                           .eq("tournament_id", tournament_id))
    mp_match = [r for r in all_mp if r["match_id"] == match_id]

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
    get_client().table("points").delete().eq("match_id", match_id).execute()
    sess_clear("points")


def save_points_batch(records: list[dict]):
    now = _now()
    payload = [{
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
    } for r in records]
    sb = get_client()
    for i in range(0, len(payload), 500):
        sb.table("points").insert(payload[i:i + 500]).execute()
    sess_clear("points")


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

    drop_ids = set()

    for uid, uvotes in by_user.items():
        if len(uvotes) <= 1:
            continue
        # Sort newest first
        uvotes.sort(
            key=lambda v: v.get("updated_at") or v.get("voted_at") or "",
            reverse=True
        )
        for v in uvotes[1:]:
            drop_ids.add(v["vote_id"])

    if drop_ids:
        get_client().table("votes").delete().in_("vote_id", list(drop_ids)).execute()
        ttl_votes_clear()


def _mark_abandoned(match_id: str):
    """Delete points and mark match as abandoned."""
    delete_match_points(match_id)
    get_client().table("matches").update({
        "result": "abandoned", "status": "abandoned",
    }).eq("match_id", match_id).execute()
    sess_clear("matches"); sess_clear("points")


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
    in the votes table are irrelevant once they have quit status in
    match_players.
    """
    _deduplicate_votes(match_id)

    # Use match_players as the source of truth for who is active.
    # Quit players may still have votes on record — ignore them here.
    mp_match = select_all(lambda: get_client().table("match_players").select("*")
                           .eq("match_id", match_id).eq("tournament_id", tournament_id))

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


def recalculate_tournament(tournament_id: str) -> tuple[int, int, int]:
    """
    Rebuild match_players then recalculate points for all completed matches
    in chronological order. Use after correcting votes or when a new player
    joins mid-tournament.

    Returns (recalculated_count, abandoned_count, error_count).
    """
    from data.match_players import rebuild_for_tournament
    from data.db import get_matches

    rebuild_for_tournament(tournament_id)

    all_ms = get_matches(tournament_id)
    done = sorted(
        [m for m in all_ms
         if m.get("tournament_id") == tournament_id
         and m["status"] in ("completed", "abandoned")
         and m.get("result") not in ("", None)],
        key=lambda m: m["match_date"] + " " + m["start_time"]
    )
    recalc = abandoned = errors = 0
    for m in done:
        if m.get("status") == "abandoned" and m.get("result") == "abandoned":
            delete_match_points(m["match_id"])
            abandoned += 1
            continue
        try:
            result = run_points_calculation(m["match_id"], tournament_id, m.get("result", ""))
            if result is ABANDONED:
                abandoned += 1
            else:
                recalc += 1
        except Exception:
            errors += 1
    return recalc, abandoned, errors


def apply_match_result(match_id: str, tournament_id: str, winner: str) -> dict:
    """
    Shared logic for saving/correcting a match result: rebuild match_players
    for this match, calculate points, and persist (or mark abandoned if
    there's no valid contest).

    Returns {"abandoned": bool, "records": list[dict] | None,
             "correct_voters": int | None} — callers decide their own
    UI/response feedback and whether to trigger emails.
    """
    from data.match_players import rebuild_for_match
    from data.db import mark_match_abandoned, update_match_result

    rebuild_for_match(match_id, tournament_id)
    records = run_points_calculation(match_id, tournament_id, winner)

    if records is ABANDONED:
        mark_match_abandoned(match_id)
        return {"abandoned": True, "records": None, "correct_voters": None}

    update_match_result(match_id, winner)
    correct = sum(1 for r in records if r.get("total_points", 0) > 0)
    return {"abandoned": False, "records": records, "correct_voters": correct}
