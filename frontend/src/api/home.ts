import { apiFetch } from "./client";
import type { HomeResponse } from "./types";

export function getHome(tournamentId: string): Promise<HomeResponse> {
  return apiFetch<HomeResponse>(
    `/tournaments/${encodeURIComponent(tournamentId)}/home`
  );
}
