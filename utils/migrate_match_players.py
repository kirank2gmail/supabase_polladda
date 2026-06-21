"""
migrate_match_players.py
━━━━━━━━━━━━━━━━━━━━━━━
One-time migration script to back-fill match_players.json from existing
votes.json data.

All rebuild logic now lives in data/match_players.py.
This file is a thin runner that calls the shared helpers.

Two modes
─────────
1. migrate_from_votes  — additive back-fill from votes (original migration).
   Safe to re-run: skips records that already exist.

2. rebuild_for_tournament  — full deterministic rebuild for one tournament.
   Use this when you want a clean, authoritative state (e.g. after adding
   registrations or correcting votes).

Run from repo root:
    python migrate_match_players.py                        # migrate mode
    python migrate_match_players.py --rebuild IPL2026      # rebuild mode
"""

import sys


# ── Streamlit admin runners ───────────────────────────────────────────────────

def run_migration_in_streamlit() -> int:
    """
    Additive back-fill from votes.json.
    Call from a Streamlit admin button:

        from migrate_match_players import run_migration_in_streamlit
        if st.button("🔄 Migrate match_players"):
            n = run_migration_in_streamlit()
            st.success(f"Migration complete — {n} new records created")
    """
    from data.gcs import _fetch, _push
    from data.match_players import migrate_from_votes
    return migrate_from_votes(_fetch, _push)


def run_rebuild_in_streamlit(tournament_id: str) -> int:
    """
    Full deterministic rebuild for one tournament.
    Call from a Streamlit admin button:

        from migrate_match_players import run_rebuild_in_streamlit
        if st.button("🔄 Rebuild match_players"):
            n = run_rebuild_in_streamlit("IPL2026")
            st.success(f"Rebuild complete — {n} records written")
    """
    from data.match_players import rebuild_for_tournament
    return rebuild_for_tournament(tournament_id)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.path.insert(0, ".")

    try:
        from data.gcs import _fetch, _push
    except ImportError:
        print("Run from repo root: python migrate_match_players.py")
        sys.exit(1)

    if "--rebuild" in sys.argv:
        idx = sys.argv.index("--rebuild")
        if idx + 1 >= len(sys.argv):
            print("Usage: python migrate_match_players.py --rebuild <tournament_id>")
            sys.exit(1)
        tid = sys.argv[idx + 1]
        print(f"Rebuilding match_players for tournament: {tid}")
        from data.match_players import rebuild_for_tournament
        n = rebuild_for_tournament(tid)
        print(f"Done — {n} records written")
    else:
        print("Running additive migration from votes.json …")
        from data.match_players import migrate_from_votes
        n = migrate_from_votes(_fetch, _push)
        print(f"Done — {n} new records added")
