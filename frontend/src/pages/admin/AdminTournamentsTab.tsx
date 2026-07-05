import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import * as tournamentsApi from "../../api/tournaments";
import * as matchesApi from "../../api/matches";
import { ApiError } from "../../api/client";
import type { Tournament } from "../../api/types";

const SPORTS = ["Cricket", "Football", "Formula 1", "Tennis", "Basketball", "Rugby", "Golf", "Hockey", "Other"];
const STATUSES = ["upcoming", "active", "completed"];

export function AdminTournamentsTab() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [matchCounts, setMatchCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  const [tid, setTid] = useState("");
  const [name, setName] = useState("");
  const [sport, setSport] = useState(SPORTS[0]);
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10));
  const [allowedMisses, setAllowedMisses] = useState(3);
  const [penaltyPoints, setPenaltyPoints] = useState(1.0);
  const [createError, setCreateError] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const reload = () => {
    setLoading(true);
    tournamentsApi
      .getTournaments()
      .then(async (ts) => {
        setTournaments(ts);
        const counts: Record<string, number> = {};
        await Promise.all(
          ts.map(async (t) => {
            const ms = await matchesApi.getMatches(t.tournament_id);
            counts[t.tournament_id] = ms.length;
          })
        );
        setMatchCounts(counts);
      })
      .finally(() => setLoading(false));
  };

  useEffect(reload, []);

  const handleCreate = async () => {
    setCreateError(null);
    if (!tid.trim() || !name.trim()) return setCreateError("ID and Name required.");
    try {
      await tournamentsApi.createTournament({
        tournament_id: tid.trim(),
        name: name.trim(),
        sport,
        start_date: startDate,
        allowed_misses: allowedMisses,
        penalty_points: penaltyPoints,
      });
      setTid("");
      setName("");
      reload();
    } catch (e) {
      setCreateError(e instanceof ApiError ? e.message : "Could not create tournament.");
    }
  };

  const handleStatusUpdate = async (id: string, status: string) => {
    await tournamentsApi.updateTournamentStatus(id, status);
    reload();
  };

  const handleDelete = async (id: string) => {
    await tournamentsApi.deleteTournament(id);
    setDeleteTarget(null);
    reload();
  };

  return (
    <div>
      <h2 className="mb-3 text-lg font-bold">Create Tournament</h2>
      <div className="mb-6 grid grid-cols-1 gap-3 rounded-lg border border-gray-200 p-4 sm:grid-cols-2">
        <input
          placeholder="IPL2026"
          value={tid}
          onChange={(e) => setTid(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          placeholder="IPL 2026"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <select
          value={sport}
          onChange={(e) => setSport(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          {SPORTS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <label className="flex flex-col gap-1 text-sm text-gray-600">
          Free Misses Allowed
          <input
            type="number"
            min={0}
            max={20}
            value={allowedMisses}
            onChange={(e) => setAllowedMisses(Number(e.target.value))}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-600">
          Penalty Points per Miss
          <input
            type="number"
            min={0}
            max={10}
            step={0.5}
            value={penaltyPoints}
            onChange={(e) => setPenaltyPoints(Number(e.target.value))}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </label>
        <p className="col-span-2 text-sm text-gray-500">
          Users get {allowedMisses} free misses. Each extra miss costs {penaltyPoints} pts.
        </p>
        {createError && <p className="col-span-2 text-sm text-rose-600">{createError}</p>}
        <button
          onClick={handleCreate}
          className="btn-raised col-span-2 rounded bg-[#28324f] py-2 text-sm font-semibold text-white hover:bg-[#1c2439]"
        >
          Create Tournament
        </button>
      </div>

      <h2 className="mb-3 text-lg font-bold">Existing Tournaments</h2>
      {loading && <p className="text-gray-500">Loading…</p>}
      {!loading && tournaments.length === 0 && (
        <p className="text-gray-500">No tournaments yet.</p>
      )}

      <div className="space-y-3">
        {tournaments.map((t) => (
          <div key={t.tournament_id} className="rounded-lg border border-gray-200 p-4">
            <div className="mb-2 flex items-start justify-between">
              <div>
                <p className="font-semibold">
                  {t.name} — {t.sport}
                </p>
                <p className="text-xs text-gray-500">
                  ID: {t.tournament_id} · Starts: {t.start_date} · Misses: {t.allowed_misses} ·
                  Penalty: {t.penalty_points} pts
                </p>
              </div>
              <button
                onClick={() =>
                  setDeleteTarget(deleteTarget === t.tournament_id ? null : t.tournament_id)
                }
                className="text-rose-500 hover:text-rose-700"
                title="Delete tournament and all data"
              >
                <Trash2 size={16} />
              </button>
            </div>
            <div className="flex items-center gap-3">
              <select
                value={t.status}
                onChange={(e) => handleStatusUpdate(t.tournament_id, e.target.value)}
                className="rounded border border-gray-300 px-2 py-1 text-sm"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <span className="text-sm text-gray-500">
                Matches: {matchCounts[t.tournament_id] ?? "…"}
              </span>
            </div>

            {deleteTarget === t.tournament_id && (
              <div className="mt-3 rounded border border-rose-300 bg-rose-50 p-3">
                <p className="mb-2 text-sm text-rose-800">
                  Delete {t.name}? This will permanently delete all matches, votes, points and
                  registrations for this tournament.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleDelete(t.tournament_id)}
                    className="btn-raised rounded bg-rose-600 px-3 py-1 text-sm text-white"
                  >
                    Yes, delete everything
                  </button>
                  <button
                    onClick={() => setDeleteTarget(null)}
                    className="btn-raised rounded border border-gray-300 px-3 py-1 text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
