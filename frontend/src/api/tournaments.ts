import { apiFetch } from "./client";
import type { LeaderboardResponse, Tournament, TournamentCreateRequest } from "./types";

export function getTournaments(): Promise<Tournament[]> {
  return apiFetch<Tournament[]>("/tournaments");
}

export function getLeaderboard(tournamentId: string): Promise<LeaderboardResponse> {
  return apiFetch<LeaderboardResponse>(
    `/tournaments/${encodeURIComponent(tournamentId)}/leaderboard`
  );
}

export function createTournament(body: TournamentCreateRequest): Promise<Tournament> {
  return apiFetch<Tournament>("/tournaments", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateTournamentStatus(
  tournamentId: string,
  status: string
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(
    `/tournaments/${encodeURIComponent(tournamentId)}/status`,
    { method: "PATCH", body: JSON.stringify({ status }) }
  );
}

export function deleteTournament(tournamentId: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(
    `/tournaments/${encodeURIComponent(tournamentId)}`,
    { method: "DELETE" }
  );
}
