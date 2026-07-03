import { useEffect, useState } from "react";
import * as usersApi from "../../api/users";
import { ApiError } from "../../api/client";
import type { User } from "../../api/types";
import { useAuth } from "../../context/AuthContext";

export function AdminUsersTab() {
  const { user: admin } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  const [username, setUsername] = useState("");
  const [role, setRole] = useState("user");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);

  const [resetTarget, setResetTarget] = useState<string | null>(null);
  const [resetPw, setResetPw] = useState("");
  const [resetError, setResetError] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const reload = () => {
    setLoading(true);
    usersApi
      .getUsers()
      .then(setUsers)
      .finally(() => setLoading(false));
  };

  useEffect(reload, []);

  const handleCreate = async () => {
    setCreateError(null);
    setCreateSuccess(null);
    if (!username.trim()) return setCreateError("Username required.");
    if (pw.length < 6) return setCreateError("Password must be at least 6 characters.");
    if (pw !== pw2) return setCreateError("Passwords do not match.");
    try {
      const newUser = await usersApi.createUser(username.trim(), pw, role);
      setCreateSuccess(
        `User ${username} created. Nickname: ${newUser.nickname}. ID: ${newUser.user_id}`
      );
      setUsername("");
      setPw("");
      setPw2("");
      reload();
    } catch (e) {
      setCreateError(e instanceof ApiError ? e.message : "Could not create user.");
    }
  };

  const handleRoleUpdate = async (userId: string, newRole: string) => {
    await usersApi.updateRole(userId, newRole);
    reload();
  };

  const handleResetPassword = async (userId: string) => {
    setResetError(null);
    if (resetPw.length < 6) return setResetError("Min 6 chars.");
    await usersApi.resetPassword(userId, resetPw);
    setResetTarget(null);
    setResetPw("");
    reload();
  };

  const handleDelete = async (userId: string) => {
    await usersApi.deleteUser(userId);
    setDeleteTarget(null);
    reload();
  };

  return (
    <div>
      <h2 className="mb-1 text-lg font-bold">Create New User</h2>
      <p className="mb-3 text-sm text-gray-500">
        Nickname defaults to first name. User must change password on first login.
      </p>
      <div className="mb-6 grid grid-cols-1 gap-3 rounded-lg border border-gray-200 p-4 sm:grid-cols-2">
        <input
          placeholder="john"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
        <input
          type="password"
          placeholder="Temporary Password (min 6 characters)"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          type="password"
          placeholder="Confirm Password"
          value={pw2}
          onChange={(e) => setPw2(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        {createError && <p className="col-span-2 text-sm text-red-600">{createError}</p>}
        {createSuccess && (
          <p className="col-span-2 text-sm text-green-700">{createSuccess}</p>
        )}
        <button
          onClick={handleCreate}
          className="col-span-2 rounded bg-[#28324f] py-2 text-sm font-semibold text-white hover:bg-[#1c2439]"
        >
          Create User
        </button>
      </div>

      <h2 className="mb-3 text-lg font-bold">All Users</h2>
      {loading && <p className="text-gray-500">Loading…</p>}
      {!loading && users.length === 0 && <p className="text-gray-500">No users yet.</p>}

      {users.length > 0 && (
        <div className="max-h-80 space-y-3 overflow-y-auto rounded-md border border-gray-200 p-2">
          {users.map((u) => {
            const isSelf = u.user_id === admin?.user_id;
            return (
              <div key={u.user_id} className="rounded-lg border border-gray-200 p-4">
                <div className="mb-2 flex items-start justify-between">
                  <div>
                    <p className="font-semibold">
                      {u.username} — nickname: <span className="font-normal">{u.nickname}</span>
                    </p>
                    <p className="text-xs text-gray-500">
                      ID: {u.user_id} ·{" "}
                      {u.must_change_password ? "⚠️ Must change password" : "✅ Password set"}
                    </p>
                  </div>
                  {!isSelf && (
                    <button
                      onClick={() => setDeleteTarget(deleteTarget === u.user_id ? null : u.user_id)}
                      className="text-red-500 hover:text-red-700"
                      title="Delete user"
                    >
                      🗑️
                    </button>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={u.role}
                    disabled={isSelf}
                    onChange={(e) => handleRoleUpdate(u.user_id, e.target.value)}
                    className="rounded border border-gray-300 px-2 py-1 text-sm disabled:bg-gray-100"
                  >
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>

                  {resetTarget === u.user_id ? (
                    <div className="flex items-center gap-2">
                      <input
                        type="password"
                        placeholder="New password"
                        value={resetPw}
                        onChange={(e) => setResetPw(e.target.value)}
                        className="rounded border border-gray-300 px-2 py-1 text-sm"
                      />
                      <button
                        onClick={() => handleResetPassword(u.user_id)}
                        className="rounded bg-[#28324f] px-3 py-1 text-sm text-white"
                      >
                        Reset
                      </button>
                      <button
                        onClick={() => {
                          setResetTarget(null);
                          setResetError(null);
                        }}
                        className="text-sm text-gray-500"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setResetTarget(u.user_id)}
                      className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-100"
                    >
                      Reset password
                    </button>
                  )}
                </div>
                {resetTarget === u.user_id && resetError && (
                  <p className="mt-1 text-sm text-red-600">{resetError}</p>
                )}

                {deleteTarget === u.user_id && (
                  <div className="mt-3 rounded border border-yellow-300 bg-yellow-50 p-3">
                    <p className="mb-2 text-sm">Delete user {u.username}?</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleDelete(u.user_id)}
                        className="rounded bg-red-600 px-3 py-1 text-sm text-white"
                      >
                        Yes
                      </button>
                      <button
                        onClick={() => setDeleteTarget(null)}
                        className="rounded border border-gray-300 px-3 py-1 text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
