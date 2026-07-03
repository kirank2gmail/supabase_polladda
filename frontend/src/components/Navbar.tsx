import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function Navbar() {
  const { user, logout } = useAuth();

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded px-3 py-1.5 text-sm font-medium ${
      isActive ? "bg-purple-600 text-white" : "text-gray-600 hover:bg-gray-100"
    }`;

  return (
    <div className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-2">
        <div className="flex items-center gap-4">
          <span className="text-lg font-extrabold">🏆</span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={linkClass}>
              🏠 Home
            </NavLink>
            <NavLink to="/leaderboard" className={linkClass}>
              🏅 Leaderboard
            </NavLink>
            <NavLink to="/profile" className={linkClass}>
              👤 Profile
            </NavLink>
            {user?.role === "admin" && (
              <NavLink to="/admin" className={linkClass}>
                ⚙️ Admin
              </NavLink>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <span>👤 {user?.nickname}</span>
          <button
            onClick={logout}
            className="rounded border border-gray-300 px-3 py-1 hover:bg-gray-100"
          >
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}
