import { NavLink } from "react-router-dom";
import { Home, Trophy, User, Settings, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function Navbar() {
  const { user, logout } = useAuth();

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex flex-col items-center gap-0.5 rounded px-2 py-1 text-[11px] leading-none font-medium ${
      isActive ? "bg-[#28324f] text-white" : "text-gray-600 hover:bg-white"
    }`;

  return (
    <div className="border-b border-gray-200 bg-gray-200">
      <div className="mx-auto flex max-w-[614px] items-center justify-between px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-extrabold">🏆</span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={linkClass}>
              <Home size={16} />
              Home
            </NavLink>
            <NavLink to="/leaderboard" className={linkClass}>
              <Trophy size={16} />
              Leaderboard
            </NavLink>
            <NavLink to="/profile" className={linkClass}>
              <User size={16} />
              Profile
            </NavLink>
            {user?.role === "admin" && (
              <NavLink to="/admin" className={linkClass}>
                <Settings size={16} />
                Admin
              </NavLink>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-2 text-gray-500">
          <span className="flex flex-col items-center gap-0.5 text-[11px] leading-none">
            <User size={16} />
            {user?.nickname}
          </span>
          <button
            onClick={logout}
            className="btn-raised flex flex-col items-center gap-0.5 rounded border border-gray-300 px-2 py-1 text-[11px] leading-none hover:bg-white"
          >
            <LogOut size={16} />
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}
