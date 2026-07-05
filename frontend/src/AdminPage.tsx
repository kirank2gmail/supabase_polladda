import { useState } from "react";
import { Users, Trophy, ClipboardList, Target, LogOut, Settings } from "lucide-react";
import { useAuth } from "./context/AuthContext";
import { AdminUsersTab } from "./pages/admin/AdminUsersTab";
import { AdminTournamentsTab } from "./pages/admin/AdminTournamentsTab";
import { AdminMatchesTab } from "./pages/admin/AdminMatchesTab";
import { AdminResultsTab } from "./pages/admin/AdminResultsTab";
import { AdminQuitTab } from "./pages/admin/AdminQuitTab";

const TABS = [
  { key: "users", label: "Users", icon: Users },
  { key: "tournaments", label: "Tournaments", icon: Trophy },
  { key: "matches", label: "Matches", icon: ClipboardList },
  { key: "results", label: "Results", icon: Target },
  { key: "quit", label: "Player Quit", icon: LogOut },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function AdminPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<TabKey>("users");

  return (
    <div className="mx-auto max-w-[614px] p-4">
      <h1 className="flex items-center gap-2 text-xl font-bold">
        <Settings size={20} /> Admin Panel
      </h1>
      <p className="mb-4 text-sm text-gray-500">Logged in as {user?.nickname}</p>

      <div className="mb-4 flex gap-2 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-b-2 border-[#28324f] text-[#28324f]"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            <t.icon size={16} /> {t.label}
          </button>
        ))}
      </div>

      {tab === "users" && <AdminUsersTab />}
      {tab === "tournaments" && <AdminTournamentsTab />}
      {tab === "matches" && <AdminMatchesTab />}
      {tab === "results" && <AdminResultsTab />}
      {tab === "quit" && <AdminQuitTab />}
    </div>
  );
}
