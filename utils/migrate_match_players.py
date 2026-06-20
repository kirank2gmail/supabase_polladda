"""
migrate_match_players.py
━━━━━━━━━━━━━━━━━━━━━━━
One-time migration script to build match_players.json from existing
votes.json and registrations.json data.

Run this ONCE from Streamlit admin or via a standalone script before
switching points calculation to use match_players.

Logic:
  - For every vote in votes.json, create an "active" match_player record
  - Players with quit_at in registrations.json are not handled here
    (quit will be applied via the new admin UI after migration)
  - Abandoned matches have no voters, so no match_player records

After running, verify by checking that points recalculation gives same results.
"""

import json
import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uid():
    return str(uuid.uuid4())[:8]


def migrate(gcs_fetch_fn, gcs_push_fn):
    """
    gcs_fetch_fn: callable(table_name) -> list[dict]
    gcs_push_fn:  callable(table_name, records) -> None
    """
    print("Reading votes.json...")
    votes = gcs_fetch_fn("votes")
    print(f"  {len(votes)} votes found")

    print("Reading match_players.json (existing)...")
    existing_mp = gcs_fetch_fn("match_players")
    existing_keys = {(r["user_id"], r["match_id"]) for r in existing_mp}
    print(f"  {len(existing_mp)} existing records")

    new_records = []
    for v in votes:
        key = (v["user_id"], v["match_id"])
        if key not in existing_keys:
            new_records.append({
                "mp_id"        : _uid(),
                "match_id"     : v["match_id"],
                "tournament_id": v.get("tournament_id", ""),
                "user_id"      : v["user_id"],
                "status"       : "active",
                "joined_at"    : v.get("voted_at", _now()),
                "quit_at"      : "",
            })
            existing_keys.add(key)

    all_records = existing_mp + new_records
    print(f"  {len(new_records)} new records to add")
    print(f"  {len(all_records)} total records")

    print("Writing match_players.json...")
    gcs_push_fn("match_players", all_records)
    print("✅ Migration complete")
    return len(new_records)


# ── Streamlit admin runner ────────────────────────────────────────────────────

def run_migration_in_streamlit():
    """
    Call this from a Streamlit button in the admin dashboard.
    Example usage in dashboard.py:
        from migrate_match_players import run_migration_in_streamlit
        if st.button("🔄 Migrate match_players"):
            n = run_migration_in_streamlit()
            st.success(f"Migration complete — {n} new records created")
    """
    import streamlit as st
    from data.gcs import _fetch, _push
    return migrate(_fetch, _push)


if __name__ == "__main__":
    # Run standalone (for local testing)
    import sys
    sys.path.insert(0, ".")
    try:
        from data.gcs import _fetch, _push
        n = migrate(_fetch, _push)
        print(f"Added {n} records")
    except ImportError:
        print("Run from repo root: python migrate_match_players.py")
