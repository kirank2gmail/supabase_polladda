import { apiFetch } from "./client";
import type { MissFloorStatus, QuitStatusResponse } from "./types";

export function getQuitStatus(tournamentId: string): Promise<QuitStatusResponse> {
  return apiFetch<QuitStatusResponse>(
    `/tournaments/${encodeURIComponent(tournamentId)}/quit-status`
  );
}

export function quitPlayer(
  tournamentId: string,
  userId: string,
  fromMatchId: string
): Promise<{ updated: number }> {
  return apiFetch<{ updated: number }>(
    `/tournaments/${encodeURIComponent(tournamentId)}/quit`,
    { method: "POST", body: JSON.stringify({ user_id: userId, from_match_id: fromMatchId }) }
  );
}

export function reinstatePlayer(
  tournamentId: string,
  userId: string,
  fromMatchId: string
): Promise<{ removed: number }> {
  return apiFetch<{ removed: number }>(
    `/tournaments/${encodeURIComponent(tournamentId)}/reinstate`,
    { method: "POST", body: JSON.stringify({ user_id: userId, from_match_id: fromMatchId }) }
  );
}

export function getMissFloorStatus(tournamentId: string): Promise<MissFloorStatus | null> {
  return apiFetch<MissFloorStatus | null>(
    `/tournaments/${encodeURIComponent(tournamentId)}/miss-floor`
  );
}

export function applyMissFloor(
  tournamentId: string,
  fromMatchId: string
): Promise<{ written: number }> {
  return apiFetch<{ written: number }>(
    `/tournaments/${encodeURIComponent(tournamentId)}/miss-floor`,
    { method: "POST", body: JSON.stringify({ from_match_id: fromMatchId }) }
  );
}

export function removeMissFloor(tournamentId: string): Promise<{ removed: number }> {
  return apiFetch<{ removed: number }>(
    `/tournaments/${encodeURIComponent(tournamentId)}/miss-floor`,
    { method: "DELETE" }
  );
}
