import { apiFetch } from "./client";
import type { LoginResponse, User } from "./types";

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
