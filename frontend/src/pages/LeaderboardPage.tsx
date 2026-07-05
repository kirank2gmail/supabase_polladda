import { useEffect, useState } from "react";
import { Trophy, BarChart3, Search, Coins, Download } from "lucide-react";
import { getLeaderboard, getTournaments } from "../api/tournaments";
import type { LeaderboardResponse, Tournament } from "../api/types";
import { LeaderboardTable } from "../components/LeaderboardTable";
import { HeroCards } from "../components/HeroCards";
import { PenaltiesTable } from "../components/PenaltiesTable";
import { MatchDetailsSection } from "../components/MatchDetailsSection";
import { buildLeaderboardCsv, downloadCsv } from "../lib/csvExport";

type LbTabKey = "leaderboard" | "matches" | "penalties";

const TABS = [
  { key: "leaderboard", label: "Leaderboard", icon: BarChart3 },
  { key: "matches", label: "Match Details", icon: Search },
  { key: "penalties", label: "Penalties", icon: Coins },
] as const;

export function LeaderboardPage() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<LbTabKey>("leaderboard");

  useEffect(() => {
    getTournaments()
      .then((ts) => {
        setTournaments(ts);
        if (ts.length > 0) setSelected(ts[0].tournament_id);
        else setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    getLeaderboard(selected)
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [selected]);

  return (
    <div className="mx-auto max-w-[614px] p-4">
      <h1 className="mb-4 flex items-center gap-2 text-xl font-bold">
        <Trophy size={20} /> Leaderboard
      </h1>

      {tournaments.length > 0 && (
        <select
          className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {tournaments.map((t) => (
            <option key={t.tournament_id} value={t.tournament_id}>
              {t.name}
            </option>
          ))}
        </select>
      )}

      {loading && <p className="text-gray-500">Loading…</p>}
      {error && <p className="text-rose-600">{error}</p>}

      {!loading && !error && data && data.rows.length === 0 && (
        <p className="text-gray-500">No results recorded yet for this tournament.</p>
      )}

      {!loading && !error && data && data.rows.length > 0 && (
        <>
          <HeroCards heroes={data.heroes} />

          <div className="mb-4 flex gap-2 border-b border-gray-200">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex flex-1 flex-col items-center gap-0.5 px-2 py-2 text-[11px] leading-none font-medium ${
                  tab === t.key
                    ? "border-b-2 border-[#28324f] text-[#28324f]"
                    : "text-gray-500 hover:text-gray-800"
                }`}
              >
                <t.icon size={16} />
                {t.label}
              </button>
            ))}
          </div>

          {tab === "leaderboard" && (
            <LeaderboardTable
              data={data}
              extra={
                <button
                  onClick={() =>
                    downloadCsv(`leaderboard_${selected}.csv`, buildLeaderboardCsv(data))
                  }
                  className="btn-raised flex items-center gap-1.5 rounded bg-[#28324f] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#1c2439]"
                >
                  <Download size={14} /> Download CSV
                </button>
              }
            />
          )}

          {tab === "matches" && <MatchDetailsSection data={data} />}

          {tab === "penalties" && <PenaltiesTable penalties={data.penalties} />}
        </>
      )}
    </div>
  );
}
