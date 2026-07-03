import { useEffect, useState } from "react";
import * as tournamentsApi from "../../api/tournaments";
import * as matchesApi from "../../api/matches";
import * as resultsApi from "../../api/results";
import { ApiError } from "../../api/client";
import type { MatchOut, PenaltyOut, Tournament, User } from "../../api/types";
import * as usersApi from "../../api/users";

export function AdminResultsTab() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selected, setSelected] = useState("");
  const [matches, setMatches] = useState<MatchOut[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [penalties, setPenalties] = useState<PenaltyOut[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recalculating, setRecalculating] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  useEffect(() => {
    tournamentsApi.getTournaments().then((ts) => {
      setTournaments(ts);
      if (ts.length > 0) setSelected(ts[0].tournament_id);
    });
    usersApi.getUsers().then(setUsers);
  }, []);

  const reload = () => {
    if (!selected) return;
    matchesApi.getMatches(selected).then(setMatches);
    resultsApi.getPenalties(selected).then(setPenalties);
  };

  useEffect(reload, [selected]);

  if (tournaments.length === 0) return <p className="text-yellow-700">No tournaments found.</p>;
  if (matches.length === 0 && selected) {
    // still render the selector + recalc buttons even with no matches yet
  }

  const pending = matches.filter((m) => !["completed", "abandoned"].includes(m.status) && !m.is_voting_open);
  const stillOpen = matches.filter((m) => !["completed", "abandoned"].includes(m.status) && m.is_voting_open);
  const done = matches.filter((m) => ["completed", "abandoned"].includes(m.status));

  const handleRecalculate = async () => {
    setMessage(null);
    setError(null);
    setRecalculating(true);
    try {
      const r = await resultsApi.recalculateTournament(selected);
      let msg = `Done — ${r.recalculated} match(es) recalculated`;
      if (r.abandoned) msg += `, ${r.abandoned} abandoned (no votes)`;
      if (r.errors) msg += `, ${r.errors} error(s)`;
      setMessage(msg);
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Recalculate failed — check the API server log.");
    } finally {
      setRecalculating(false);
    }
  };

  const handleRebuild = async () => {
    setMessage(null);
    setError(null);
    setRebuilding(true);
    try {
      const r = await resultsApi.rebuildMatchPlayers(selected);
      setMessage(`Done — ${r.written} record(s) written.`);
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Rebuild failed — check the API server log.");
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <div>
      <select
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
        className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm"
      >
        {tournaments.map((t) => (
          <option key={t.tournament_id} value={t.tournament_id}>
            {t.name}
          </option>
        ))}
      </select>

      {message && (
        <div className="mb-4 rounded border border-green-300 bg-green-50 p-2 text-sm text-green-800">
          {message}
        </div>
      )}
      {error && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mb-4 flex items-center justify-between rounded-lg border border-gray-200 p-4">
        <div>
          <p className="font-semibold">🔄 Recalculate All Points</p>
          <p className="text-sm text-gray-500">
            Recalculates points for every completed match in chronological order. Can take up to
            a minute for large tournaments.
          </p>
        </div>
        <button
          onClick={handleRecalculate}
          disabled={recalculating}
          className="rounded bg-[#28324f] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1c2439] disabled:opacity-50"
        >
          {recalculating ? "Recalculating…" : "Recalculate Tournament"}
        </button>
      </div>

      <div className="mb-6 flex items-center justify-between rounded-lg border border-gray-200 p-4">
        <div>
          <p className="font-semibold">🗂️ Rebuild match_players</p>
          <p className="text-sm text-gray-500">
            Rebuilds from scratch: voted + missed records, quit records preserved.
          </p>
        </div>
        <button
          onClick={handleRebuild}
          disabled={rebuilding}
          className="rounded border border-gray-300 px-4 py-2 text-sm font-semibold hover:bg-gray-100 disabled:opacity-50"
        >
          {rebuilding ? "Rebuilding…" : "Rebuild match_players"}
        </button>
      </div>

      <h2 className="mb-2 text-lg font-bold">🎯 Awaiting Result Entry</h2>
      <p className="mb-2 text-sm text-gray-500">Poll closed — enter the winner to calculate points.</p>
      {pending.length === 0 && <p className="mb-4 text-gray-400">No matches awaiting result.</p>}
      {pending.length > 0 && (
        <div className="mb-6 max-h-80 space-y-2 overflow-y-auto rounded-md border border-gray-200 p-2">
          {pending.map((m) => (
            <ResultEntryRow key={m.match_id} match={m} onSaved={reload} />
          ))}
        </div>
      )}

      <h2 className="mb-2 text-lg font-bold">⏳ Voting Still Open</h2>
      <p className="mb-2 text-sm text-gray-500">Results cannot be entered until voting closes.</p>
      {stillOpen.length === 0 && <p className="mb-4 text-gray-400">No matches with open voting.</p>}
      {stillOpen.length > 0 && (
        <div className="mb-6 max-h-80 space-y-2 overflow-y-auto rounded-md border border-gray-200 p-2">
          {stillOpen.map((m) => (
            <StillOpenRow key={m.match_id} match={m} />
          ))}
        </div>
      )}

      <h2 className="mb-2 text-lg font-bold">✏️ Update / Correct Result</h2>
      <p className="mb-2 text-sm text-gray-500">Change the result for a match — points recalculate automatically.</p>
      {done.length === 0 && <p className="mb-4 text-gray-400">No completed matches.</p>}
      {done.length > 0 && (
        <div className="mb-6 max-h-80 space-y-2 overflow-y-auto rounded-md border border-gray-200 p-2">
          {done.map((m) => (
            <UpdateResultRow key={m.match_id} match={m} onSaved={reload} />
          ))}
        </div>
      )}

      <PenaltiesSection
        tournamentId={selected}
        penalties={penalties}
        users={users}
        onChanged={reload}
      />
    </div>
  );
}

function ResultEntryRow({ match, onSaved }: { match: MatchOut; onSaved: () => void }) {
  const opts = match.options.split("|").map((o) => o.trim()).filter(Boolean);
  const [winner, setWinner] = useState(opts[0] ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const r = await resultsApi.saveMatchResult(match.match_id, match.tournament_id, winner);
      if (r.abandoned) {
        setError(`${match.title} has no votes — marked as abandoned. No points calculated.`);
      }
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save result.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-gray-200 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-semibold">{match.title}</p>
          <p className="text-xs text-gray-500">
            {match.match_id} · {match.match_date} {match.start_time} · Scoring: {match.scoring_mode}
          </p>
        </div>
        <select
          value={winner}
          onChange={(e) => setWinner(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        >
          {opts.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded bg-[#28324f] px-3 py-1.5 text-sm font-semibold text-white hover:bg-[#1c2439] disabled:opacity-50"
        >
          Save Result
        </button>
      </div>
      {error && <p className="mt-1 text-sm text-yellow-700">{error}</p>}
    </div>
  );
}

function StillOpenRow({ match }: { match: MatchOut }) {
  const [voteCount, setVoteCount] = useState<number | null>(null);

  useEffect(() => {
    matchesApi.getMatchVotes(match.match_id).then((v) => setVoteCount(v.length));
  }, [match.match_id]);

  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
      <div>
        <p className="font-semibold">{match.title}</p>
        <p className="text-xs text-gray-500">
          {match.match_id} · Closes: {match.start_time} {match.timezone.split("/").pop()} ·
          Scoring: {match.scoring_mode}
        </p>
      </div>
      <span className="text-sm text-gray-600">Votes cast: {voteCount ?? "…"}</span>
    </div>
  );
}

function UpdateResultRow({ match, onSaved }: { match: MatchOut; onSaved: () => void }) {
  const opts = match.options.split("|").map((o) => o.trim()).filter(Boolean);
  const isAband = match.status === "abandoned" || match.result === "abandoned";
  const [newWinner, setNewWinner] = useState(opts.includes(match.result) ? match.result : opts[0] ?? "");
  const [saving, setSaving] = useState(false);

  const changed = newWinner !== match.result || isAband;

  const handleUpdate = async () => {
    setSaving(true);
    try {
      await resultsApi.saveMatchResult(match.match_id, match.tournament_id, newWinner);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 p-3">
      <div>
        <p className="font-semibold">{match.title}</p>
        <p className="text-xs text-gray-500">
          {match.match_id} ·{" "}
          {isAband ? "⛔ Abandoned" : `Result: ${match.result}`} · Scoring: {match.scoring_mode}
        </p>
      </div>
      <select
        value={newWinner}
        onChange={(e) => setNewWinner(e.target.value)}
        className="rounded border border-gray-300 px-2 py-1 text-sm"
      >
        {opts.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <button
        onClick={handleUpdate}
        disabled={!changed || saving}
        className="rounded bg-[#28324f] px-3 py-1.5 text-sm font-semibold text-white hover:bg-[#1c2439] disabled:opacity-50"
      >
        Update Result
      </button>
    </div>
  );
}

function PenaltiesSection({
  tournamentId,
  penalties,
  users,
  onChanged,
}: {
  tournamentId: string;
  penalties: PenaltyOut[];
  users: User[];
  onChanged: () => void;
}) {
  const [userId, setUserId] = useState(users[0]?.user_id ?? "");
  const [points, setPoints] = useState(1.0);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId && users.length > 0) setUserId(users[0].user_id);
  }, [users, userId]);

  const handleAdd = async () => {
    setError(null);
    if (!reason.trim()) return setError("Reason is required.");
    await resultsApi.addPenalty(tournamentId, userId, points, reason.trim());
    setReason("");
    onChanged();
  };

  const handleDelete = async (id: string) => {
    await resultsApi.deletePenalty(id);
    onChanged();
  };

  return (
    <div>
      <h2 className="mb-2 text-lg font-bold">💸 Manual Penalties</h2>
      <p className="mb-2 text-sm text-gray-500">
        Deduct points from a player manually. Flows to the bank, doesn't affect rank.
      </p>
      <div className="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-gray-200 p-4">
        <select
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          className="rounded border border-gray-300 px-2 py-2 text-sm"
        >
          {users.map((u) => (
            <option key={u.user_id} value={u.user_id}>
              {u.nickname}
            </option>
          ))}
        </select>
        <input
          type="number"
          min={0.5}
          step={0.5}
          value={points}
          onChange={(e) => setPoints(Number(e.target.value))}
          className="w-24 rounded border border-gray-300 px-2 py-2 text-sm"
        />
        <input
          placeholder="Reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="flex-1 rounded border border-gray-300 px-2 py-2 text-sm"
        />
        <button
          onClick={handleAdd}
          className="rounded bg-[#28324f] px-3 py-2 text-sm font-semibold text-white hover:bg-[#1c2439]"
        >
          Add Penalty
        </button>
      </div>
      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}

      {penalties.length === 0 ? (
        <p className="text-gray-400">No penalties recorded for this tournament.</p>
      ) : (
        <div className="max-h-80 space-y-1 overflow-y-auto rounded-md border border-gray-200 p-2">
          {penalties.map((p) => (
            <div
              key={p.penalty_id}
              className="flex items-center justify-between rounded border border-gray-100 px-3 py-2 text-sm"
            >
              <span className="font-semibold">{p.player_name}</span>
              <span className="font-bold text-red-700">-{p.points.toFixed(2)}</span>
              <span className="flex-1 px-3 text-gray-600">{p.reason}</span>
              <span className="text-xs text-gray-400">{p.created_at.slice(0, 10)}</span>
              <button
                onClick={() => handleDelete(p.penalty_id)}
                className="ml-2 text-red-500 hover:text-red-700"
              >
                🗑️
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
