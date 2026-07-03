import { apiFetch } from "./client";
import type { LoginResponse, TimezoneListResponse, User } from "./types";

export function login(username: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function me(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

export function logout(): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/auth/logout", { method: "POST" });
}

export function changePassword(
  newPassword: string,
  currentPassword?: string
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      new_password: newPassword,
      current_password: currentPassword ?? null,
    }),
  });
}

export function updateNickname(nickname: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/auth/me/nickname", {
    method: "PATCH",
    body: JSON.stringify({ nickname }),
  });
}

export function updateTimezone(timezone: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/auth/me/timezone", {
    method: "PATCH",
    body: JSON.stringify({ timezone }),
  });
}

export function getTimezones(): Promise<TimezoneListResponse> {
  return apiFetch<TimezoneListResponse>("/auth/timezones");
}
