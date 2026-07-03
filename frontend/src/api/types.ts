// TS mirrors of api/schemas.py — keep field names in sync with that file.

export interface User {
  user_id: string;
  username: string;
  nickname: string;
  role: string;
  must_change_password: boolean;
  timezone: string;
}

export interface LoginResponse {
  token: string;
  user: User;
  must_change_password: boolean;
  is_legacy_password: boolean;
}

export interface Tournament {
  tournament_id: string;
  name: string;
  sport: string | null;
  start_date: string | null;
  status: string;
  allowed_misses: number;
  penalty_points: number;
}

export interface TournamentCreateRequest {
  tournament_id: string;
  name: string;
  sport: string;
  start_date: string;
  allowed_misses: number;
  penalty_points: number;
}

export interface HeroStat {
  names: string;
  value: number;
}

export interface PenaltyOut {
  penalty_id: string;
  tournament_id: string;
  user_id: string;
  points: number;
  reason: string;
  created_at: string;
  player_name: string;
}

export type CellValue = number | string | null;

// LeaderboardRow has fixed keys below PLUS one dynamic key per match_id
// (a CellValue) — use LeaderboardResponse.col_match_ids to know which extra
// keys are match columns.
export interface LeaderboardRow {
  user_id: string;
  name: string;
  total_points: number;
  win_pct: number;
  missed: number;
  rank: number;
  curr_win_streak: number;
  curr_loss_streak: number;
  max_win_streak: number;
  max_loss_streak: number;
  [matchId: string]: CellValue | string | number;
}

export interface MatchOut {
  match_id: string;
  tournament_id: string;
  title: string;
  location: string;
  match_date: string;
  start_time: string;
  timezone: string;
  options: string;
  scoring_mode: string;
  fixed_odds: number;
  poll_mode: string;
  status: string;
  result: string;
  created_by: string | null;
  created_at: string | null;
}

export interface LeaderboardResponse {
  rows: LeaderboardRow[];
  matches_asc: MatchOut[];
  match_ids_desc: string[];
  col_match_ids: string[];
  labels: Record<string, string>;
  col_totals: Record<string, number>;
  grand_total: number;
  bank: number;
  penalty_total: number;
  penalties: PenaltyOut[];
  heroes: Record<string, HeroStat>;
}

export interface VoteOut {
  vote_id: string;
  user_id: string;
  match_id: string;
  tournament_id: string;
  vote: string;
  voted_at: string | null;
  updated_at: string | null;
  update_count: number;
  player_name: string;
}

export interface BulkImportSkip {
  match_id: string;
  reason: string;
}

export interface BulkImportResult {
  created: number;
  skipped: BulkImportSkip[];
}

export interface MatchCreateRequest {
  match_id: string;
  title: string;
  location: string;
  match_date: string;
  start_time: string;
  timezone: string;
  options?: string;
  scoring_mode?: string;
  fixed_odds?: number;
  poll_mode?: string;
}
