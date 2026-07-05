import { NavLink } from "react-router-dom";
import { Home, Trophy, User, Settings } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function Navbar() {
  const { user, logout } = useAuth();

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium ${
      isActive ? "bg-[#28324f] text-white" : "text-gray-600 hover:bg-gray-100"
    }`;

  return (
    <div className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-2">
        <div className="flex items-center gap-4">
          <span className="text-lg font-extrabold">🏆</span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={linkClass}>
              <Home size={16} /> Home
            </NavLink>
            <NavLink to="/leaderboard" className={linkClass}>
              <Trophy size={16} /> Leaderboard
            </NavLink>
            <NavLink to="/profile" className={linkClass}>
              <User size={16} /> Profile
            </NavLink>
            {user?.role === "admin" && (
              <NavLink to="/admin" className={linkClass}>
                <Settings size={16} /> Admin
              </NavLink>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <span className="flex items-center gap-1.5">
            <User size={16} /> {user?.nickname}
          </span>
          <button
            onClick={logout}
            className="btn-raised rounded border border-gray-300 px-3 py-1 hover:bg-gray-100"
          >
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}
