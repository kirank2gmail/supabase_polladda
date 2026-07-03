import { useEffect, useState } from "react";
import { getLeaderboard, getTournaments } from "../api/tournaments";
import type { LeaderboardResponse, Tournament } from "../api/types";
import { LeaderboardTable } from "../components/LeaderboardTable";
import { HeroCards } from "../components/HeroCards";
import { PenaltiesTable } from "../components/PenaltiesTable";

export function LeaderboardPage() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    <div className="mx-auto max-w-5xl p-4">
      <h1 className="mb-4 text-xl font-bold">🏅 Leaderboard</h1>

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
      {error && <p className="text-red-600">{error}</p>}

      {!loading && !error && data && data.rows.length === 0 && (
        <p className="text-gray-500">No results recorded yet for this tournament.</p>
      )}

      {!loading && !error && data && data.rows.length > 0 && (
        <>
          <HeroCards heroes={data.heroes} />
          <h2 className="mb-2 text-lg font-bold">📊 Leaderboard</h2>
          <LeaderboardTable data={data} />
          <PenaltiesTable penalties={data.penalties} />
        </>
      )}
    </div>
  );
}
