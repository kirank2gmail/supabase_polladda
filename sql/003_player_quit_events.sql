-- SportsPoll — durable quit/reinstate event log
--
-- Previously, a player's quit status (whether they've quit a tournament,
-- and from which match_id onward) lived only as rows inside match_players
-- (status="quit", quit_at=<from_match_id>). match_players is otherwise a
-- fully derived/regenerable table — migrate_from_votes()/rebuild_for_match()
-- delete-and-reinsert it from votes+matches+registrations on every
-- recalculate_tournament run. Quit rows were the one exception, since
-- _build_quit_boundaries() determined who's quit by reading match_players'
-- OWN current rows before rebuilding it — no other source of truth existed
-- anywhere. Truncating match_players (as happened during a real GCS/Supabase
-- data resync) silently destroyed quit history with no way to recover it.
--
-- This table is the new, durable source of truth: an append-only log of
-- every quit/reinstate action. "Current" status for a user = their latest
-- event by event_id (not created_at, to avoid timestamp-tie ambiguity).
--
-- Run this once in the Supabase SQL editor.

CREATE TABLE IF NOT EXISTS player_quit_events (
    event_id      BIGSERIAL PRIMARY KEY,
    tournament_id TEXT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    action        TEXT NOT NULL CHECK (action IN ('quit', 'reinstate')),
    from_match_id TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_player_quit_events_tournament_user
    ON player_quit_events(tournament_id, user_id);
