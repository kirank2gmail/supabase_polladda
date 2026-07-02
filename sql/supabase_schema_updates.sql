-- SportsPoll — Supabase schema updates
-- Run once in the Supabase SQL editor before deploying the Supabase-backed app
-- or running utils/migrate_to_supabase.py. Safe to re-run (idempotent).

-- ── 1. New columns needed by the app ────────────────────────────────────────
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS sport       TEXT;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS start_date  DATE;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS created_by  TEXT;
ALTER TABLE matches     ADD COLUMN IF NOT EXISTS created_by  TEXT;

-- ── 2. ON DELETE CASCADE on every FK ────────────────────────────────────────
-- (default auto-generated constraint name convention: <table>_<column>_fkey)

ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_tournament_id_fkey;
ALTER TABLE matches ADD  CONSTRAINT matches_tournament_id_fkey
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE;

ALTER TABLE votes DROP CONSTRAINT IF EXISTS votes_user_id_fkey;
ALTER TABLE votes ADD  CONSTRAINT votes_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE votes DROP CONSTRAINT IF EXISTS votes_match_id_fkey;
ALTER TABLE votes ADD  CONSTRAINT votes_match_id_fkey
    FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE;

ALTER TABLE points DROP CONSTRAINT IF EXISTS points_user_id_fkey;
ALTER TABLE points ADD  CONSTRAINT points_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE points DROP CONSTRAINT IF EXISTS points_match_id_fkey;
ALTER TABLE points ADD  CONSTRAINT points_match_id_fkey
    FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE;

ALTER TABLE registrations DROP CONSTRAINT IF EXISTS registrations_user_id_fkey;
ALTER TABLE registrations ADD  CONSTRAINT registrations_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE registrations DROP CONSTRAINT IF EXISTS registrations_tournament_id_fkey;
ALTER TABLE registrations ADD  CONSTRAINT registrations_tournament_id_fkey
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE;

ALTER TABLE match_players DROP CONSTRAINT IF EXISTS match_players_match_id_fkey;
ALTER TABLE match_players ADD  CONSTRAINT match_players_match_id_fkey
    FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE;

ALTER TABLE match_players DROP CONSTRAINT IF EXISTS match_players_user_id_fkey;
ALTER TABLE match_players ADD  CONSTRAINT match_players_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_user_id_fkey;
ALTER TABLE sessions ADD  CONSTRAINT sessions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE penalties DROP CONSTRAINT IF EXISTS penalties_tournament_id_fkey;
ALTER TABLE penalties ADD  CONSTRAINT penalties_tournament_id_fkey
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id) ON DELETE CASCADE;

ALTER TABLE penalties DROP CONSTRAINT IF EXISTS penalties_user_id_fkey;
ALTER TABLE penalties ADD  CONSTRAINT penalties_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- ── 3. Unique constraints needed for upsert-based writes ────────────────────
-- votes: exactly one vote row per (user, match) — lets cast_vote/update_vote
-- use a single .upsert(on_conflict="user_id,match_id").
DO $$ BEGIN
    ALTER TABLE votes ADD CONSTRAINT votes_user_match_uniq UNIQUE (user_id, match_id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- match_players: exactly one status row per (user, match).
DO $$ BEGIN
    ALTER TABLE match_players ADD CONSTRAINT match_players_user_match_uniq UNIQUE (user_id, match_id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- (registrations already has UNIQUE(user_id, tournament_id) per the existing DDL.)

-- ── 4. Recommended indexes on frequently-filtered columns ───────────────────
CREATE INDEX IF NOT EXISTS idx_matches_tournament_id      ON matches(tournament_id);
CREATE INDEX IF NOT EXISTS idx_votes_match_id              ON votes(match_id);
CREATE INDEX IF NOT EXISTS idx_votes_tournament_id         ON votes(tournament_id);
CREATE INDEX IF NOT EXISTS idx_points_match_id             ON points(match_id);
CREATE INDEX IF NOT EXISTS idx_points_tournament_id        ON points(tournament_id);
CREATE INDEX IF NOT EXISTS idx_match_players_match_id      ON match_players(match_id);
CREATE INDEX IF NOT EXISTS idx_match_players_tournament_id ON match_players(tournament_id);
CREATE INDEX IF NOT EXISTS idx_registrations_tournament_id ON registrations(tournament_id);
CREATE INDEX IF NOT EXISTS idx_penalties_tournament_id     ON penalties(tournament_id);
