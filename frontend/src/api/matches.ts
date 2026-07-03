import { apiFetch } from "./client";
import type { BulkImportResult, MatchCreateRequest, MatchOut, VoteOut } from "./types";

export function getMatches(tournamentId: string): Promise<MatchOut[]> {
  return apiFetch<MatchOut[]>(`/tournaments/${encodeURIComponent(tournamentId)}/matches`);
}

export function createMatch(
  tournamentId: string,
  body: MatchCreateRequest
): Promise<MatchOut> {
  return apiFetch<MatchOut>(`/tournaments/${encodeURIComponent(tournamentId)}/matches`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function bulkUploadMatches(
  tournamentId: string,
  file: File
): Promise<BulkImportResult> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<BulkImportResult>(
    `/tournaments/${encodeURIComponent(tournamentId)}/matches/bulk`,
    { method: "POST", body: form }
  );
}

export function deleteMatch(matchId: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/matches/${encodeURIComponent(matchId)}`, {
    method: "DELETE",
  });
}

export function getMatchVotes(matchId: string): Promise<VoteOut[]> {
  return apiFetch<VoteOut[]>(`/matches/${encodeURIComponent(matchId)}/votes`);
}

export function deleteMatchVote(
  matchId: string,
  userId: string
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(
    `/matches/${encodeURIComponent(matchId)}/votes/${encodeURIComponent(userId)}`,
    { method: "DELETE" }
  );
}
