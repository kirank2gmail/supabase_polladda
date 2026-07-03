import { apiFetch } from "./client";
import type { User } from "./types";

export function getUsers(): Promise<User[]> {
  return apiFetch<User[]>("/users");
}

export function createUser(
  username: string,
  password: string,
  role: string
): Promise<User> {
  return apiFetch<User>("/users", {
    method: "POST",
    body: JSON.stringify({ username, password, role }),
  });
}

export function updateRole(userId: string, role: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/users/${encodeURIComponent(userId)}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export function resetPassword(
  userId: string,
  newPassword: string
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(
    `/users/${encodeURIComponent(userId)}/reset-password`,
    { method: "POST", body: JSON.stringify({ new_password: newPassword }) }
  );
}

export function deleteUser(userId: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/users/${encodeURIComponent(userId)}`, {
    method: "DELETE",
  });
}
