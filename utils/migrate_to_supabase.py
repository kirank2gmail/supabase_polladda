"""
utils/migrate_to_supabase.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
One-time migration: GCS JSON blobs (data/gcs.py._fetch) -> Supabase Postgres.

Safe to re-run — all writes are idempotent upserts keyed on each table's
primary key. Requires BOTH the [gcp_service_account]/[gcs] secrets (source)
and the [supabase] secret (destination) to be configured simultaneously —
this is a migration-time-only requirement; the live app only needs
[supabase] afterwards.

Run the SQL in sql/supabase_schema_updates.sql against your Supabase project
BEFORE running this script — it adds the columns/constraints this migration
and the live app depend on.

Usage (CLI)
───────────
Migrate everything:
    python utils/migrate_to_supabase.py

Migrate one table only:
    python utils/migrate_to_supabase.py --table votes

Preview only, no writes:
    python utils/migrate_to_supabase.py --dry-run

Usage (Streamlit / admin panel, optional)
──────────────────────────────────────────
    from utils.migrate_to_supabase import run_migration_in_streamlit
    if st.button("Migrate JSON -> Supabase"):
        run_migration_in_streamlit(dry_run=True)
"""

import sys
import argparse

# FK-safe dependency order: parents before children.
TABLE_ORDER = [
    "users", "tournaments", "matches",
    "registrations", "votes", "match_players", "points", "penalties",
    "sessions", "activity_log",
]

PK_COL = {
    "users"        : "user_id",
    "tournaments"  : "tournament_id",
    "matches"      : "match_id",
    "registrations": "registration_id",
    "votes"        : "vote_id",
    "match_players": "mp_id",
    "points"       : "point_id",
    "penalties"    : "penalty_id",
    "sessions"     : "token",
    "activity_log" : "event_id",
}

# Old JSON field name -> new Supabase column name.
RENAME_MAP = {
    "users"        : {"name": "username"},
    "registrations": {"reg_id": "registration_id"},
}

# Columns that are TIMESTAMPTZ in Supabase but may be "" (never NULL) in the
# old JSON — Postgres can't store "" in a timestamptz column.
TIMESTAMP_FIELDS = {
    "users"        : ["created_at"],
    "tournaments"  : ["created_at"],
    "matches"      : ["created_at"],
    "votes"        : ["voted_at", "updated_at"],
    "points"       : ["calculated_at"],
    "registrations": ["registered_at"],
    "match_players": ["created_at"],
    "sessions"     : ["created_at", "expires"],
    "penalties"    : ["created_at"],
    "activity_log" : ["timestamp"],
}

# FK columns that must resolve to an already-migrated parent row.
# Required because pre-existing bugs in the old delete_tournament/delete_match
# (no match_players/penalties cleanup) mean production GCS data may contain
# rows whose FK target no longer exists — inserting them would violate the
# new FK constraints.
FK_MAP = {
    "matches"      : {"tournament_id": "tournaments"},
    "registrations": {"user_id": "users", "tournament_id": "tournaments"},
    "votes"        : {"user_id": "users", "match_id": "matches"},
    "match_players": {"match_id": "matches", "user_id": "users"},
    "points"       : {"user_id": "users", "match_id": "matches"},
    "penalties"    : {"tournament_id": "tournaments", "user_id": "users"},
    "sessions"     : {"user_id": "users"},
}

CHUNK_SIZE = 500


def _transform(table: str, record: dict) -> dict:
    rec = dict(record)
    for old, new in RENAME_MAP.get(table, {}).items():
        if old in rec:
            rec[new] = rec.pop(old)
    for field in TIMESTAMP_FIELDS.get(table, []):
        if rec.get(field) == "":
            rec[field] = None
    return rec


def _parent_keys(parent_table: str, sb, valid_keys: dict) -> set:
    """
    Keys for a parent table this run either already migrated (present in
    valid_keys) or that already exist in Supabase from a previous run
    (e.g. when migrating with --table to scope to a single child table).
    """
    if parent_table not in valid_keys:
        pk   = PK_COL[parent_table]
        rows = sb.table(parent_table).select(pk).execute().data or []
        valid_keys[parent_table] = {r[pk] for r in rows}
    return valid_keys[parent_table]


def migrate_table(table: str, sb, valid_keys: dict, dry_run: bool = False):
    from data.gcs import _fetch

    raw         = _fetch(table)
    transformed = [_transform(table, r) for r in raw]

    # Filter rows whose FK target hasn't been migrated (orphans).
    parent_keys = {parent: _parent_keys(parent, sb, valid_keys)
                   for parent in set(FK_MAP.get(table, {}).values())}
    kept, orphans = [], []
    for rec in transformed:
        ok = True
        for fk_col, parent_table in FK_MAP.get(table, {}).items():
            if rec.get(fk_col) not in parent_keys[parent_table]:
                ok = False
                break
        (kept if ok else orphans).append(rec)

    if orphans:
        sample = [r.get(PK_COL[table]) for r in orphans[:10]]
        print(f"[{table}] SKIPPING {len(orphans)} orphaned row(s) "
              f"(dangling FK — pre-existing data-integrity gap): {sample}"
              f"{' ...' if len(orphans) > 10 else ''}")

    print(f"[{table}] {len(raw)} read, {len(kept)} valid, {len(orphans)} orphaned")

    if not dry_run and kept:
        pk = PK_COL[table]
        for i in range(0, len(kept), CHUNK_SIZE):
            sb.table(table).upsert(kept[i:i + CHUNK_SIZE], on_conflict=pk).execute()

    valid_keys[table] = {r[PK_COL[table]] for r in kept}
    return len(raw), len(kept), len(orphans)


def run(tables: list[str], dry_run: bool = False):
    from data.supabase_client import get_client
    sb = get_client()

    valid_keys: dict[str, set] = {}
    report = []
    for t in tables:
        try:
            src, kept, orphaned = migrate_table(t, sb, valid_keys, dry_run=dry_run)
            report.append((t, src, kept, orphaned, None))
        except Exception as e:
            print(f"[{t}] ERROR: {e}")
            report.append((t, None, None, None, str(e)))
            valid_keys.setdefault(t, set())
            continue   # report-and-continue: one bad table shouldn't block the rest

    print("\n=== Migration report ===")
    for t, src, kept, orphaned, err in report:
        if err:
            print(f"  {t:15s} ERROR: {err}")
        else:
            print(f"  {t:15s} {src} read, {kept} migrated, {orphaned} orphaned/skipped")

    if not dry_run:
        print("\n=== Post-migration row-count verification ===")
        from data.gcs import _fetch
        for t, _, _, orphaned, err in report:
            if err:
                print(f"  {t:15s} SKIPPED (migration errored)")
                continue
            src_count = len(_fetch(t))
            resp      = sb.table(t).select("*", count="exact").limit(1).execute()
            dst_count = resp.count if resp.count is not None else -1
            expected  = src_count - (orphaned or 0)
            flag      = "OK" if dst_count == expected else "MISMATCH"
            print(f"  {t:15s} source={src_count:5d}  supabase={dst_count:5d}  "
                  f"expected={expected:5d}  [{flag}]")


def run_migration_in_streamlit(table: str | None = None, dry_run: bool = False):
    run([table] if table else TABLE_ORDER, dry_run=dry_run)


if __name__ == "__main__":
    sys.path.insert(0, ".")

    try:
        import data.gcs  # noqa: F401 — sanity check source backend is importable
    except ImportError:
        print("Run from repo root: python utils/migrate_to_supabase.py")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Migrate SportsPoll data from GCS JSON to Supabase Postgres.")
    parser.add_argument("--table", choices=TABLE_ORDER,
                         help="Migrate a single table instead of everything.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Preview counts/orphans without writing anything.")
    args = parser.parse_args()

    run([args.table] if args.table else TABLE_ORDER, dry_run=args.dry_run)
