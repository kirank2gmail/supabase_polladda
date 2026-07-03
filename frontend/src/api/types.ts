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
  is_voting_open: boolean;
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

// ── Results ───────────────────────────────────────────────────────────────────

export interface RecalculateResult {
  recalculated: number;
  abandoned: number;
  errors: number;
}

export interface RebuildResult {
  written: number;
}

export interface MatchResultResponse {
  abandoned: boolean;
  correct_voters: number | null;
  email_sent: boolean;
  email_error: string | null;
}

// ── Player quit / miss floor ─────────────────────────────────────────────────

export interface PlayerStatusOut {
  user_id: string;
  name: string;
  has_quit_records: boolean;
  quit_from_match_id: string | null;
  quit_since_label: string | null;
  active_matches: number;
  quit_matches: number;
}

export interface MatchLabelOut {
  match_id: string;
  label: string;
}

export interface QuitStatusResponse {
  players: PlayerStatusOut[];
  matches: MatchLabelOut[];
}

export interface MissFloorStatus {
  from_match_id: string;
  player_count: number;
  record_count: number;
  label: string;
}

// ── Profile ───────────────────────────────────────────────────────────────────

export interface TimezoneListResponse {
  common: string[];
  all: string[];
}

// ── Home page ─────────────────────────────────────────────────────────────────

export interface MatchTimesOut {
  local: string;
  utc: string;
  user: string | null;
  tz: string;
}

export interface CountdownOut {
  message: string;
  severity: "success" | "warning" | "error";
}

export interface HomeMatchOut {
  match: MatchOut;
  times: MatchTimesOut;
  countdown: CountdownOut | null;
  my_vote: string | null;
  my_points: number | null;
  correct: boolean | null;
}

export interface HomeResponse {
  upcoming: HomeMatchOut[];
  in_progress: HomeMatchOut[];
  completed: HomeMatchOut[];
}

// ── Match detail / voting / poll / result ────────────────────────────────────

export interface VoteSelfOut {
  vote: string;
  voted_at: string | null;
  updated_at: string | null;
  update_count: number;
}

export interface MatchDetailResponse {
  match: MatchOut;
  times: MatchTimesOut;
  countdown: CountdownOut;
  my_vote: VoteSelfOut | null;
}

export interface PollVoterOut {
  user_id: string;
  name: string;
  voted_at: string | null;
}

export interface PollOptionOut {
  option: string;
  count: number;
  pct: number;
  voters: PollVoterOut[] | null;
}

export interface PollSummaryResponse {
  total: number;
  hidden: boolean;
  options: PollOptionOut[];
}

export interface ResultVoterOut {
  user_id: string;
  name: string;
  voted_at: string | null;
  points: number;
}

export interface ResultOptionOut {
  option: string;
  is_win: boolean;
  pts_label: string;
  voters: ResultVoterOut[];
}

export interface MissedPenalizedOut {
  user_id: string;
  name: string;
  note: string;
  points: number;
}

export interface ResultBreakdownResponse {
  result: string;
  winner_points: number;
  options: ResultOptionOut[];
  missed: MissedPenalizedOut[];
}
