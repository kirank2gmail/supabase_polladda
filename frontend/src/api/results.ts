import { apiFetch } from "./client";
import type {
  MatchResultResponse,
  PenaltyOut,
  RebuildResult,
  RecalculateResult,
} from "./types";

export function recalculateTournament(tournamentId: string): Promise<RecalculateResult> {
  return apiFetch<RecalculateResult>(
    `/tournaments/${encodeURIComponent(tournamentId)}/recalculate`,
    { method: "POST" }
  );
}

export function rebuildMatchPlayers(tournamentId: string): Promise<RebuildResult> {
  return apiFetch<RebuildResult>(
    `/tournaments/${encodeURIComponent(tournamentId)}/rebuild-match-players`,
    { method: "POST" }
  );
}

export function saveMatchResult(
  matchId: string,
  tournamentId: string,
  winner: string
): Promise<MatchResultResponse> {
  return apiFetch<MatchResultResponse>(`/matches/${encodeURIComponent(matchId)}/result`, {
    method: "POST",
    body: JSON.stringify({ tournament_id: tournamentId, winner }),
  });
}

export function getPenalties(tournamentId: string): Promise<PenaltyOut[]> {
  return apiFetch<PenaltyOut[]>(`/tournaments/${encodeURIComponent(tournamentId)}/penalties`);
}

export function addPenalty(
  tournamentId: string,
  userId: string,
  points: number,
  reason: string
): Promise<PenaltyOut> {
  return apiFetch<PenaltyOut>(`/tournaments/${encodeURIComponent(tournamentId)}/penalties`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, points, reason }),
  });
}

export function deletePenalty(penaltyId: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/penalties/${encodeURIComponent(penaltyId)}`, {
    method: "DELETE",
  });
}
