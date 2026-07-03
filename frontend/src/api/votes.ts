import { apiFetch } from "./client";
import type {
  MatchDetailResponse,
  PollSummaryResponse,
  ResultBreakdownResponse,
  VoteSelfOut,
} from "./types";

export function getMatchDetail(matchId: string): Promise<MatchDetailResponse> {
  return apiFetch<MatchDetailResponse>(`/matches/${encodeURIComponent(matchId)}/detail`);
}

export function castVote(matchId: string, vote: string): Promise<VoteSelfOut> {
  return apiFetch<VoteSelfOut>(`/matches/${encodeURIComponent(matchId)}/vote`, {
    method: "POST",
    body: JSON.stringify({ vote }),
  });
}

export function getPollSummary(matchId: string): Promise<PollSummaryResponse> {
  return apiFetch<PollSummaryResponse>(`/matches/${encodeURIComponent(matchId)}/poll`);
}

export function getResultBreakdown(matchId: string): Promise<ResultBreakdownResponse> {
  return apiFetch<ResultBreakdownResponse>(`/matches/${encodeURIComponent(matchId)}/result`);
}
