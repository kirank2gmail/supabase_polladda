import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { changePassword } from "../api/auth";
import { ApiError } from "../api/client";

export function LoginPage() {
  const { user, mustChangePassword, login, completePasswordChange } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");
  const [pwError, setPwError] = useState<string | null>(null);

  if (user && !mustChangePassword) {
    return <Navigate to="/" replace />;
  }

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!username.trim()) {
      setError("Please enter your username.");
      return;
    }
    setSubmitting(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Username or password is incorrect."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleChangePassword = async (e: FormEvent) => {
    e.preventDefault();
    setPwError(null);
    if (newPw.length < 6) {
      setPwError("Min 6 characters required.");
      return;
    }
    if (newPw !== newPw2) {
      setPwError("Passwords do not match.");
      return;
    }
    try {
      await changePassword(newPw);
      completePasswordChange();
    } catch (err) {
      setPwError(err instanceof ApiError ? err.message : "Could not set password.");
    }
  };

  if (user && mustChangePassword) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
          <h1 className="mb-2 text-xl font-bold text-gray-900">🔑 Set Your Password</h1>
          <p className="mb-6 text-sm text-gray-500">
            You must set a new password before continuing.
          </p>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <input
              type="password"
              placeholder="New password (min 6 chars)"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
            />
            <input
              type="password"
              placeholder="Confirm new password"
              value={newPw2}
              onChange={(e) => setNewPw2(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
            />
            {pwError && <p className="text-sm text-red-600">{pwError}</p>}
            <button
              type="submit"
              className="w-full rounded bg-purple-600 py-2 text-sm font-semibold text-white hover:bg-purple-700"
            >
              Set Password
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-1 text-center text-3xl font-extrabold text-gray-900">
          🏆 SportsPoll
        </h1>
        <p className="mb-6 text-center text-sm text-gray-400">Predict · Compete · Win</p>
        <form onSubmit={handleLogin} className="space-y-4">
          <input
            type="text"
            placeholder="Enter your username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-purple-600 py-2 text-sm font-semibold text-white hover:bg-purple-700 disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
