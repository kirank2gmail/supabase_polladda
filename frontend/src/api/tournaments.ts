import { apiFetch } from "./client";
import type { LeaderboardResponse, Tournament } from "./types";

export function getTournaments(): Promise<Tournament[]> {
  return apiFetch<Tournament[]>("/tournaments");
}

export function getLeaderboard(tournamentId: string): Promise<LeaderboardResponse> {
  return apiFetch<LeaderboardResponse>(
    `/tournaments/${encodeURIComponent(tournamentId)}/leaderboard`
  );
}
