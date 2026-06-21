"""
migrate_match_players.py
━━━━━━━━━━━━━━━━━━━━━━━
CLI and Streamlit runners for rebuilding match_players.json.

All logic lives in data/match_players.migrate_from_votes().
This file is a thin entry-point only.

Usage (CLI)
───────────
Rebuild all tournaments:
    python migrate_match_players.py

Rebuild one tournament:
    python migrate_match_players.py --tournament IPL2026
"""

import sys


# ── Streamlit admin runner ────────────────────────────────────────────────────

def run_migration_in_streamlit(tournament_id: str | None = None) -> int:
    """
    Full rebuild of match_players for one or all tournaments.

    Produces voted + missed records; preserves quit records.
    Safe to re-run at any time — always writes a clean, complete table.

    Example usage in dashboard.py:
        from migrate_match_players import run_migration_in_streamlit
        if st.button("🗂️ Run Migration"):
            n = run_migration_in_streamlit(sel_tid)
            st.success(f"Done — {n} record(s) written")
    """
    from data.match_players import migrate_from_votes
    return migrate_from_votes(tournament_id=tournament_id)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.path.insert(0, ".")

    try:
        from data.gcs import _fetch, _push
    except ImportError:
        print("Run from repo root: python migrate_match_players.py")
        sys.exit(1)

    from data.match_players import migrate_from_votes

    tid = None
    if "--tournament" in sys.argv:
        idx = sys.argv.index("--tournament")
        if idx + 1 >= len(sys.argv):
            print("Usage: python migrate_match_players.py --tournament <tournament_id>")
            sys.exit(1)
        tid = sys.argv[idx + 1]
        print(f"Rebuilding match_players for tournament: {tid}")
    else:
        print("Rebuilding match_players for ALL tournaments …")

    n = migrate_from_votes(tournament_id=tid, gcs_fetch_fn=_fetch, gcs_push_fn=_push)
    print(f"Done — {n} record(s) written")
