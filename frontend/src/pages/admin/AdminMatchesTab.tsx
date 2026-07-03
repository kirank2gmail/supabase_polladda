import { useEffect, useState } from "react";
import * as tournamentsApi from "../../api/tournaments";
import * as matchesApi from "../../api/matches";
import { ApiError } from "../../api/client";
import type { BulkImportResult, MatchOut, Tournament, VoteOut } from "../../api/types";

const COMMON_TIMEZONES = [
  "Asia/Kolkata", "Europe/London", "Europe/Paris", "Europe/Berlin",
  "America/New_York", "America/Chicago", "America/Los_Angeles",
  "Australia/Sydney", "Australia/Brisbane", "Asia/Dubai", "Asia/Singapore",
  "Asia/Tokyo", "Pacific/Auckland", "UTC",
];

function optionsFromTitle(title: string): string {
  if (!title.trim()) return "";
  const parts = title
    .trim()
    .split(/\s+(?:vs\.?|v\.?)\s+|\s*\/\s*|\s+-\s+/i)
    .map((p) => p.trim())
    .filter(Boolean);
  return parts.length >= 2 ? parts.join("|") : "";
}

function validateOptions(s: string): string | null {
  const parts = s.split("|").map((p) => p.trim()).filter(Boolean);
  if (parts.length < 2) return "At least 2 options required, pipe-separated e.g. SRH|RCB";
  return null;
}

export function AdminMatchesTab() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selected, setSelected] = useState("");
  const [matches, setMatches] = useState<MatchOut[]>([]);
  const [mode, setMode] = useState<"single" | "bulk">("single");

  useEffect(() => {
    tournamentsApi.getTournaments().then((ts) => {
      setTournaments(ts);
      if (ts.length > 0) setSelected(ts[0].tournament_id);
    });
  }, []);

  const reloadMatches = () => {
    if (!selected) return;
    matchesApi.getMatches(selected).then(setMatches);
  };

  useEffect(reloadMatches, [selected]);

  if (tournaments.length === 0) {
    return <p className="text-yellow-700">Create a tournament first.</p>;
  }

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

      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setMode("single")}
          className={`rounded px-3 py-1.5 text-sm font-medium ${
            mode === "single" ? "bg-[#28324f] text-white" : "border border-gray-300"
          }`}
        >
          ➕ Add Single Match
        </button>
        <button
          onClick={() => setMode("bulk")}
          className={`rounded px-3 py-1.5 text-sm font-medium ${
            mode === "bulk" ? "bg-[#28324f] text-white" : "border border-gray-300"
          }`}
        >
          📤 Bulk Upload CSV
        </button>
      </div>

      {mode === "single" ? (
        <SingleMatchForm tournamentId={selected} onCreated={reloadMatches} />
      ) : (
        <BulkUploadForm tournamentId={selected} onImported={reloadMatches} />
      )}

      <h2 className="mb-3 mt-6 text-lg font-bold">Matches</h2>
      {matches.length === 0 && <p className="text-gray-500">No matches yet.</p>}
      {matches.length > 0 && (
        <div className="max-h-80 space-y-3 overflow-y-auto rounded-md border border-gray-200 p-2">
          {matches.map((m) => (
            <MatchRow key={m.match_id} match={m} onDeleted={reloadMatches} />
          ))}
        </div>
      )}
    </div>
  );
}

function SingleMatchForm({
  tournamentId,
  onCreated,
}: {
  tournamentId: string;
  onCreated: () => void;
}) {
  const [matchId, setMatchId] = useState("");
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [matchDate, setMatchDate] = useState(new Date().toISOString().slice(0, 10));
  const [startTime, setStartTime] = useState("19:30");
  const [timezone, setTimezone] = useState(COMMON_TIMEZONES[0]);
  const [options, setOptions] = useState("");
  const [scoringMode, setScoringMode] = useState("ratio");
  const [fixedOdds, setFixedOdds] = useState(2.0);
  const [pollMode, setPollMode] = useState("closed");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleTitleChange = (t: string) => {
    setTitle(t);
    if (!options) setOptions(optionsFromTitle(t));
  };

  const optionsError = options ? validateOptions(options) : null;

  const handleSubmit = async () => {
    setError(null);
    setSuccess(null);
    if (!matchId.trim() || !title.trim()) return setError("ID and Title required.");
    const err = validateOptions(options);
    if (err) return setError(err);

    try {
      await matchesApi.createMatch(tournamentId, {
        match_id: matchId.trim(),
        title: title.trim(),
        location,
        match_date: matchDate,
        start_time: startTime,
        timezone,
        options,
        scoring_mode: scoringMode,
        fixed_odds: fixedOdds,
        poll_mode: pollMode,
      });
      setSuccess(`Match ${matchId} added!`);
      setMatchId("");
      setTitle("");
      setOptions("");
      onCreated();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create match.");
    }
  };

  return (
    <div className="mb-6 space-y-3 rounded-lg border border-gray-200 p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <input
          placeholder="Match ID (IPL2026-M001)"
          value={matchId}
          onChange={(e) => setMatchId(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          placeholder="Title (SRH vs RCB)"
          value={title}
          onChange={(e) => handleTitleChange(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          placeholder="Location"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          type="date"
          value={matchDate}
          onChange={(e) => setMatchDate(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          type="time"
          value={startTime}
          onChange={(e) => setStartTime(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <select
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          {COMMON_TIMEZONES.map((tz) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </select>
      </div>

      <input
        placeholder="Vote Options (pipe separated, min 2) — SRH|RCB"
        value={options}
        onChange={(e) => setOptions(e.target.value)}
        className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
      />
      {options && optionsError && <p className="text-sm text-red-600">{optionsError}</p>}
      {options && !optionsError && (
        <p className="text-sm text-green-700">
          {options.split("|").filter(Boolean).length} options:{" "}
          {options.split("|").filter(Boolean).join(" · ")}
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <select
          value={scoringMode}
          onChange={(e) => setScoringMode(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="ratio">📊 Ratio (dynamic)</option>
          <option value="fixed">🎯 Fixed Odds</option>
        </select>
        <input
          type="number"
          min={0.1}
          max={100}
          step={0.5}
          disabled={scoringMode === "ratio"}
          value={fixedOdds}
          onChange={(e) => setFixedOdds(Number(e.target.value))}
          className="rounded border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
        />
        <select
          value={pollMode}
          onChange={(e) => setPollMode(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="closed">🔒 Closed (votes hidden till end)</option>
          <option value="open">👁 Open (always visible)</option>
        </select>
      </div>

      <p className="text-sm text-gray-500">
        {scoringMode === "ratio"
          ? "Ratio: Winners share all points lost by losers and penalised missed voters."
          : `Fixed: Winners get +${fixedOdds} pts each. Losers = -1 -> bank.`}
      </p>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {success && <p className="text-sm text-green-700">{success}</p>}

      <button
        onClick={handleSubmit}
        className="rounded bg-[#28324f] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1c2439]"
      >
        Add Match
      </button>
    </div>
  );
}

function BulkUploadForm({
  tournamentId,
  onImported,
}: {
  tournamentId: string;
  onImported: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [previewRows, setPreviewRows] = useState<string[][]>([]);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BulkImportResult | null>(null);

  const handleFile = async (f: File | null) => {
    setFile(f);
    setResult(null);
    setError(null);
    setPreviewRows([]);
    if (!f) return;
    // Lightweight client-side preview only — naive split, no quoted-comma
    // support. Authoritative parsing/validation happens server-side.
    const text = await f.text();
    const lines = text.trim().split(/\r?\n/).slice(0, 11);
    setPreviewRows(lines.map((l) => l.split(",")));
  };

  const handleImport = async () => {
    if (!file) return;
    setError(null);
    setResult(null);
    try {
      const res = await matchesApi.bulkUploadMatches(tournamentId, file);
      setResult(res);
      onImported();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Import failed.");
    }
  };

  return (
    <div className="mb-6 space-y-3 rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">
        <strong>CSV columns:</strong> match_id, title, location, match_date, start_time,
        timezone, options, scoring_mode, fixed_odds, poll_mode
        <br />
        options auto-filled from title if left blank · scoring_mode: ratio/fixed · poll_mode:
        closed/open
      </p>
      <input
        type="file"
        accept=".csv"
        onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
        className="text-sm"
      />

      {previewRows.length > 0 && (
        <div className="overflow-x-auto rounded border border-gray-200">
          <table className="w-full text-xs">
            <tbody>
              {previewRows.map((row, i) => (
                <tr key={i} className={i === 0 ? "bg-gray-100 font-semibold" : ""}>
                  {row.map((cell, j) => (
                    <td key={j} className="whitespace-nowrap border-b border-gray-100 px-2 py-1">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {typeof error === "string" ? error : JSON.stringify(error)}
        </div>
      )}
      {result && (
        <div className="rounded border border-green-300 bg-green-50 p-2 text-sm text-green-800">
          {result.created} match(es) imported!
          {result.skipped.length > 0 && (
            <ul className="mt-1 list-disc pl-4 text-yellow-700">
              {result.skipped.map((s) => (
                <li key={s.match_id}>
                  {s.match_id}: {s.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <button
        onClick={handleImport}
        disabled={!file}
        className="rounded bg-[#28324f] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1c2439] disabled:opacity-50"
      >
        Import All
      </button>
    </div>
  );
}

function MatchRow({ match, onDeleted }: { match: MatchOut; onDeleted: () => void }) {
  const [showVotes, setShowVotes] = useState(false);
  const [votes, setVotes] = useState<VoteOut[] | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const toggleVotes = async () => {
    if (!showVotes && votes === null) {
      setVotes(await matchesApi.getMatchVotes(match.match_id));
    }
    setShowVotes(!showVotes);
  };

  const handleDeleteVote = async (userId: string) => {
    await matchesApi.deleteMatchVote(match.match_id, userId);
    setVotes(await matchesApi.getMatchVotes(match.match_id));
  };

  const handleDeleteMatch = async () => {
    await matchesApi.deleteMatch(match.match_id);
    onDeleted();
  };

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="font-semibold">{match.title}</p>
          <p className="text-xs text-gray-500">
            {match.match_id} · {match.location} · {match.match_date} {match.start_time}{" "}
            {match.timezone.split("/").pop()} · Options: {match.options} · Scoring:{" "}
            {match.scoring_mode}
            {match.scoring_mode === "fixed" ? ` @ ${match.fixed_odds}` : ""} · Poll:{" "}
            {match.poll_mode} · Status: {match.status}
            {match.result ? ` · Result: ${match.result}` : ""}
          </p>
          <button onClick={toggleVotes} className="mt-1 text-xs text-[#28324f] hover:underline">
            👁 {showVotes ? "Hide votes" : "View votes"}
          </button>
        </div>
        <button
          onClick={() => setConfirmDelete(!confirmDelete)}
          className="text-red-500 hover:text-red-700"
        >
          🗑️ Delete
        </button>
      </div>

      {showVotes && votes && (
        <div className="mt-2 space-y-1 border-t border-gray-100 pt-2">
          {votes.length === 0 && <p className="text-xs text-gray-400">No votes yet.</p>}
          {votes.map((v) => (
            <div key={v.vote_id} className="flex items-center justify-between text-sm">
              <span>
                <strong>{v.player_name}</strong> → {v.vote}
              </span>
              <button
                onClick={() => handleDeleteVote(v.user_id)}
                className="text-red-500 hover:text-red-700"
              >
                🗑️
              </button>
            </div>
          ))}
        </div>
      )}

      {confirmDelete && (
        <div className="mt-3 rounded border border-yellow-300 bg-yellow-50 p-3">
          <p className="mb-2 text-sm">Delete {match.title}?</p>
          <div className="flex gap-2">
            <button
              onClick={handleDeleteMatch}
              className="rounded bg-red-600 px-3 py-1 text-sm text-white"
            >
              Yes
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="rounded border border-gray-300 px-3 py-1 text-sm"
            >
              No
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
