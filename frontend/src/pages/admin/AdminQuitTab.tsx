import { useEffect, useState } from "react";
import { Circle, Ban, CheckCircle2 } from "lucide-react";
import * as tournamentsApi from "../../api/tournaments";
import * as quitApi from "../../api/quit";
import { ApiError } from "../../api/client";
import type { MatchLabelOut, MissFloorStatus, PlayerStatusOut, Tournament } from "../../api/types";

export function AdminQuitTab() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selected, setSelected] = useState("");
  const [players, setPlayers] = useState<PlayerStatusOut[]>([]);
  const [matches, setMatches] = useState<MatchLabelOut[]>([]);
  const [floorStatus, setFloorStatus] = useState<MissFloorStatus | null>(null);

  useEffect(() => {
    tournamentsApi.getTournaments().then((ts) => {
      setTournaments(ts);
      if (ts.length > 0) setSelected(ts[0].tournament_id);
    });
  }, []);

  const reload = () => {
    if (!selected) return;
    quitApi.getQuitStatus(selected).then((r) => {
      setPlayers(r.players);
      setMatches(r.matches);
    });
    quitApi.getMissFloorStatus(selected).then(setFloorStatus);
  };

  useEffect(reload, [selected]);

  if (tournaments.length === 0) return <p className="text-yellow-700">No tournaments found.</p>;
  if (players.length === 0) {
    return (
      <div>
        <TournamentSelect tournaments={tournaments} selected={selected} onChange={setSelected} />
        <p className="text-gray-500">
          No match_players records yet. Run "Rebuild match_players" in Results first.
        </p>
      </div>
    );
  }

  const sortedPlayers = [...players].sort((a, b) =>
    a.has_quit_records === b.has_quit_records ? a.name.localeCompare(b.name) : a.has_quit_records ? -1 : 1
  );
  const activePlayers = sortedPlayers.filter((p) => !p.has_quit_records);
  const quitPlayers = sortedPlayers.filter((p) => p.has_quit_records);

  return (
    <div>
      <TournamentSelect tournaments={tournaments} selected={selected} onChange={setSelected} />

      <h2 className="mb-2 text-lg font-bold">Current Player Status</h2>
      <div className="mb-6 overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="px-3 py-2">Player</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right">Active</th>
              <th className="px-3 py-2 text-right">Quit</th>
            </tr>
          </thead>
          <tbody>
            {sortedPlayers.map((p) => (
              <tr key={p.user_id} className="border-t border-gray-100">
                <td className="px-3 py-2 font-semibold">{p.name}</td>
                <td className="px-3 py-2">
                  {p.has_quit_records ? (
                    <span className="inline-flex items-center gap-1 text-rose-600">
                      <Circle size={8} className="fill-rose-600 text-rose-600" /> Quit from: {p.quit_since_label}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-green-700">
                      <Circle size={8} className="fill-green-700 text-green-700" /> Active
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-right">{p.active_matches}</td>
                <td className="px-3 py-2 text-right">{p.quit_matches}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <QuitForm
        tournamentId={selected}
        activePlayers={activePlayers}
        matches={matches}
        onDone={reload}
      />
      <ReinstateForm
        tournamentId={selected}
        quitPlayers={quitPlayers}
        matches={matches}
        onDone={reload}
      />
      <MissFloorSection
        tournamentId={selected}
        status={floorStatus}
        matches={matches}
        onDone={reload}
      />
    </div>
  );
}

function TournamentSelect({
  tournaments,
  selected,
  onChange,
}: {
  tournaments: Tournament[];
  selected: string;
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={selected}
      onChange={(e) => onChange(e.target.value)}
      className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm"
    >
      {tournaments.map((t) => (
        <option key={t.tournament_id} value={t.tournament_id}>
          {t.name}
        </option>
      ))}
    </select>
  );
}

function QuitForm({
  tournamentId,
  activePlayers,
  matches,
  onDone,
}: {
  tournamentId: string;
  activePlayers: PlayerStatusOut[];
  matches: MatchLabelOut[];
  onDone: () => void;
}) {
  const [userId, setUserId] = useState(activePlayers[0]?.user_id ?? "");
  const [matchId, setMatchId] = useState(matches[matches.length - 1]?.match_id ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId && activePlayers.length > 0) setUserId(activePlayers[0].user_id);
    if (!matchId && matches.length > 0) setMatchId(matches[matches.length - 1].match_id);
  }, [activePlayers, matches, userId, matchId]);

  if (activePlayers.length === 0) {
    return (
      <div className="mb-6">
        <h2 className="mb-2 text-lg font-bold">Mark Player as Quit</h2>
        <p className="text-gray-400">No active players to quit.</p>
      </div>
    );
  }

  const handleQuit = async () => {
    setMessage(null);
    setError(null);
    try {
      const r = await quitApi.quitPlayer(tournamentId, userId, matchId);
      const name = activePlayers.find((p) => p.user_id === userId)?.name ?? userId;
      setMessage(
        r.updated === 0
          ? `No match_players records found for ${name} at or after the selected match.`
          : `${name} marked as quit — ${r.updated} record(s) updated. Run Recalculate Tournament to apply to points.`
      );
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not mark player as quit.");
    }
  };

  return (
    <div className="mb-6 rounded-lg border border-gray-200 p-4">
      <h2 className="mb-1 text-lg font-bold">Mark Player as Quit</h2>
      <p className="mb-3 text-sm text-gray-500">
        Sets match_players records from the selected match onwards to quit status.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          className="rounded border border-gray-300 px-2 py-2 text-sm"
        >
          {activePlayers.map((p) => (
            <option key={p.user_id} value={p.user_id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          value={matchId}
          onChange={(e) => setMatchId(e.target.value)}
          className="flex-1 rounded border border-gray-300 px-2 py-2 text-sm"
        >
          {matches.map((m) => (
            <option key={m.match_id} value={m.match_id}>
              {m.label}
            </option>
          ))}
        </select>
        <button
          onClick={handleQuit}
          className="btn-raised rounded bg-[#28324f] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1c2439]"
        >
          Mark as Quit
        </button>
      </div>
      {message && (
        <div className="mt-3 rounded border border-green-300 bg-green-50 p-2 text-sm text-green-800">
          {message}
        </div>
      )}
      {error && (
        <div className="mt-3 rounded border border-rose-300 bg-rose-50 p-2 text-sm text-rose-700">
          {error}
        </div>
      )}
    </div>
  );
}

function ReinstateForm({
  tournamentId,
  quitPlayers,
  matches,
  onDone,
}: {
  tournamentId: string;
  quitPlayers: PlayerStatusOut[];
  matches: MatchLabelOut[];
  onDone: () => void;
}) {
  const [userId, setUserId] = useState(quitPlayers[0]?.user_id ?? "");
  const [matchId, setMatchId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (quitPlayers.length === 0) return;
    if (!userId) setUserId(quitPlayers[0].user_id);
    const player = quitPlayers.find((p) => p.user_id === (userId || quitPlayers[0].user_id));
    if (!matchId && player?.quit_from_match_id) setMatchId(player.quit_from_match_id);
  }, [quitPlayers, userId, matchId]);

  if (quitPlayers.length === 0) {
    return (
      <div className="mb-6">
        <h2 className="mb-2 text-lg font-bold">Reinstate Player</h2>
        <p className="text-gray-400">No quit players to reinstate.</p>
      </div>
    );
  }

  const handleReinstate = async () => {
    setMessage(null);
    setError(null);
    try {
      const r = await quitApi.reinstatePlayer(tournamentId, userId, matchId);
      const name = quitPlayers.find((p) => p.user_id === userId)?.name ?? userId;
      setMessage(
        `${name} reinstated — ${r.removed} quit record(s) removed, match_players rebuilt. Run Recalculate Tournament to apply to points.`
      );
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reinstate player.");
    }
  };

  return (
    <div className="mb-6 rounded-lg border border-gray-200 p-4">
      <h2 className="mb-1 text-lg font-bold">Reinstate Player</h2>
      <p className="mb-3 text-sm text-gray-500">
        Removes quit records from the selected match onwards; earlier quit records preserved.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={userId}
          onChange={(e) => {
            setUserId(e.target.value);
            const p = quitPlayers.find((pl) => pl.user_id === e.target.value);
            setMatchId(p?.quit_from_match_id ?? "");
          }}
          className="rounded border border-gray-300 px-2 py-2 text-sm"
        >
          {quitPlayers.map((p) => (
            <option key={p.user_id} value={p.user_id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          value={matchId}
          onChange={(e) => setMatchId(e.target.value)}
          className="flex-1 rounded border border-gray-300 px-2 py-2 text-sm"
        >
          {matches.map((m) => (
            <option key={m.match_id} value={m.match_id}>
              {m.label}
            </option>
          ))}
        </select>
        <button
          onClick={handleReinstate}
          className="btn-raised rounded bg-[#28324f] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1c2439]"
        >
          Reinstate
        </button>
      </div>
      {message && (
        <div className="mt-3 rounded border border-green-300 bg-green-50 p-2 text-sm text-green-800">
          {message}
        </div>
      )}
      {error && (
        <div className="mt-3 rounded border border-rose-300 bg-rose-50 p-2 text-sm text-rose-700">
          {error}
        </div>
      )}
    </div>
  );
}

function MissFloorSection({
  tournamentId,
  status,
  matches,
  onDone,
}: {
  tournamentId: string;
  status: MissFloorStatus | null;
  matches: MatchLabelOut[];
  onDone: () => void;
}) {
  const [matchId, setMatchId] = useState(matches[0]?.match_id ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId && matches.length > 0) setMatchId(matches[0].match_id);
  }, [matches, matchId]);

  const handleApply = async () => {
    setMessage(null);
    setError(null);
    try {
      const r = await quitApi.applyMissFloor(tournamentId, matchId);
      setMessage(
        `Miss floor applied — ${r.written} synthetic record(s) written. Run Recalculate Tournament to apply to points.`
      );
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not apply miss floor.");
    }
  };

  const handleRemove = async () => {
    setMessage(null);
    setError(null);
    try {
      const r = await quitApi.removeMissFloor(tournamentId);
      setMessage(`Miss floor removed — ${r.removed} record(s) deleted. Run Recalculate Tournament to apply.`);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not remove miss floor.");
    }
  };

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <h2 className="mb-1 flex items-center gap-2 text-lg font-bold">
        <Ban size={18} /> Miss Floor (Knockout Stage)
      </h2>
      <p className="mb-3 text-sm text-gray-500">
        Max out every active player's free-miss allowance from a chosen match onwards.
      </p>

      {status ? (
        <div>
          <p className="mb-2 flex items-center gap-1 text-sm text-blue-800">
            <CheckCircle2 size={14} /> Miss floor active from {status.label} — {status.player_count} player(s),{" "}
            {status.record_count} synthetic record(s).
          </p>
          <button
            onClick={handleRemove}
            className="btn-raised rounded border border-gray-300 px-4 py-2 text-sm font-semibold hover:bg-gray-100"
          >
            Remove Miss Floor
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-400">No miss floor active.</span>
          <select
            value={matchId}
            onChange={(e) => setMatchId(e.target.value)}
            className="flex-1 rounded border border-gray-300 px-2 py-2 text-sm"
          >
            {matches.map((m) => (
              <option key={m.match_id} value={m.match_id}>
                {m.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleApply}
            className="btn-raised rounded bg-[#28324f] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1c2439]"
          >
            Apply Miss Floor
          </button>
        </div>
      )}
      {message && (
        <div className="mt-3 rounded border border-green-300 bg-green-50 p-2 text-sm text-green-800">
          {message}
        </div>
      )}
      {error && (
        <div className="mt-3 rounded border border-rose-300 bg-rose-50 p-2 text-sm text-rose-700">
          {error}
        </div>
      )}
    </div>
  );
}
