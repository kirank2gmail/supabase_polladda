import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  MapPin,
  Calendar,
  Clock,
  PauseCircle,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  BarChart3,
  User,
  Trophy,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getMatches } from "../api/matches";
import { getMatchDetail, castVote, getPollSummary, getResultBreakdown } from "../api/votes";
import type {
  MatchDetailResponse,
  PollSummaryResponse,
  ResultBreakdownResponse,
} from "../api/types";

interface NavState {
  matchList?: string[];
  tournamentId?: string;
}

const SEVERITY_STYLES: Record<string, string> = {
  success: "bg-green-50 text-green-700 border-green-200",
  warning: "bg-yellow-50 text-yellow-700 border-yellow-200",
  error: "bg-rose-50 text-rose-700 border-rose-200",
};

export function MatchPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const navState = (location.state as NavState) || {};

  const [detail, setDetail] = useState<MatchDetailResponse | null>(null);
  const [poll, setPoll] = useState<PollSummaryResponse | null>(null);
  const [result, setResult] = useState<ResultBreakdownResponse | null>(null);
  const [matchList, setMatchList] = useState<string[]>(navState.matchList ?? []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [voting, setVoting] = useState(false);
  const [voteError, setVoteError] = useState<string | null>(null);
  const [voteSuccess, setVoteSuccess] = useState<string | null>(null);

  const isAdmin = user?.role === "admin";

  useEffect(() => {
    if (!matchId) return;
    setLoading(true);
    setError(null);
    setResult(null);

    getMatchDetail(matchId)
      .then(async (d) => {
        setDetail(d);
        try {
          setPoll(await getPollSummary(matchId));
        } catch {
          setPoll(null);
        }
        if (d.match.status === "completed" && !d.match.is_voting_open) {
          try {
            setResult(await getResultBreakdown(matchId));
          } catch {
            setResult(null);
          }
        }
        if (matchList.length === 0 && d.match.tournament_id) {
          const ms = await getMatches(d.match.tournament_id);
          setMatchList(ms.map((m) => m.match_id));
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId]);

  const refetchAfterVote = async () => {
    if (!matchId) return;
    const d = await getMatchDetail(matchId);
    setDetail(d);
    try {
      setPoll(await getPollSummary(matchId));
    } catch {
      setPoll(null);
    }
  };

  const handleVote = async (option: string) => {
    if (!matchId) return;
    setVoting(true);
    setVoteError(null);
    setVoteSuccess(null);
    try {
      await castVote(matchId, option);
      await refetchAfterVote();
      setVoteSuccess(`Vote placed for ${option} ✅`);
    } catch (e) {
      setVoteError(String(e));
    } finally {
      setVoting(false);
    }
  };

  if (loading) {
    return <div className="mx-auto max-w-3xl p-4 text-gray-500">Loading…</div>;
  }
  if (error && !detail) {
    return <div className="mx-auto max-w-3xl p-4 text-rose-600">{error}</div>;
  }
  if (!detail || !matchId) {
    return <div className="mx-auto max-w-3xl p-4 text-rose-600">Match not found.</div>;
  }

  const { match, times, countdown, my_vote } = detail;
  const options = match.options.split("|").map((o) => o.trim()).filter(Boolean);
  const curIdx = matchList.indexOf(matchId);
  const hasPrev = curIdx > 0;
  const hasNext = curIdx >= 0 && curIdx < matchList.length - 1;

  return (
    <div className="mx-auto max-w-3xl p-4">
      <NavBar
        onBack={() => navigate("/", { state: { tournamentId: navState.tournamentId } })}
        onPrev={hasPrev ? () => navigate(`/match/${matchList[curIdx - 1]}`, { state: navState }) : undefined}
        onNext={hasNext ? () => navigate(`/match/${matchList[curIdx + 1]}`, { state: navState }) : undefined}
      />

      <h1 className="mb-1 text-xl font-bold">{match.title}</h1>
      <p className="mb-3 text-xs text-gray-400">
        {match.tournament_id} · {match.match_id}
      </p>

      <div className="mb-3 grid grid-cols-3 gap-3 text-sm">
        <div>
          <p className="flex items-center gap-1 text-gray-400"><MapPin size={12} /> Location</p>
          <p className="font-semibold">{match.location}</p>
        </div>
        <div>
          <p className="flex items-center gap-1 text-gray-400"><Calendar size={12} /> Date</p>
          <p className="font-semibold">{match.match_date}</p>
        </div>
        <div>
          <p className="flex items-center gap-1 text-gray-400"><Clock size={12} /> Local</p>
          <p className="font-semibold">
            {match.start_time} {match.timezone.split("/").pop()}
          </p>
        </div>
      </div>

      {times.user && (
        <p className="mb-1 text-xs text-gray-500">
          Your time: <b>{times.user}</b> · UTC: {times.utc}
        </p>
      )}
      {!times.user && <p className="mb-1 text-xs text-gray-500">UTC: {times.utc}</p>}

      <div className={`mb-4 rounded border px-3 py-2 text-sm ${SEVERITY_STYLES[countdown.severity]}`}>
        {countdown.message}
      </div>

      <hr className="my-4 border-gray-200" />

      {match.is_voting_open ? (
        <VotingSection
          options={options}
          myVote={my_vote?.vote ?? null}
          voting={voting}
          onVote={handleVote}
          voteError={voteError}
          voteSuccess={voteSuccess}
        />
      ) : (
        match.status === "upcoming" && (
          <p className="mb-4 flex items-center gap-1 rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">
            <PauseCircle size={14} /> Voting closed — result pending from admin.
          </p>
        )
      )}

      <hr className="my-4 border-gray-200" />

      <PollSection poll={poll} />

      {match.status === "completed" && !match.is_voting_open && result && (
        <>
          <hr className="my-4 border-gray-200" />
          <ResultSection result={result} />
        </>
      )}

      {!isAdmin && null}
    </div>
  );
}

function NavBar({
  onBack,
  onPrev,
  onNext,
}: {
  onBack: () => void;
  onPrev?: () => void;
  onNext?: () => void;
}) {
  return (
    <div className="mb-4 grid grid-cols-[2fr_1fr_1fr] gap-2">
      <button
        onClick={onBack}
        className="btn-raised rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
      >
        ← Back to Matches
      </button>
      <button
        onClick={onPrev}
        disabled={!onPrev}
        className="btn-raised rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        ◀ Previous
      </button>
      <button
        onClick={onNext}
        disabled={!onNext}
        className="btn-raised rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Next ▶
      </button>
    </div>
  );
}

function VotingSection({
  options,
  myVote,
  voting,
  onVote,
  voteError,
  voteSuccess,
}: {
  options: string[];
  myVote: string | null;
  voting: boolean;
  onVote: (option: string) => void;
  voteError: string | null;
  voteSuccess: string | null;
}) {
  const [choice, setChoice] = useState(myVote ?? options[0] ?? "");

  return (
    <div className="mb-2">
      {myVote && (
        <p className="mb-2 rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">
          Current vote: <b>{myVote}</b>
        </p>
      )}
      <h3 className="mb-2 font-semibold">Cast / Update Your Vote</h3>
      {options.length <= 6 ? (
        <div className="flex flex-wrap gap-2">
          {options.map((opt) => (
            <button
              key={opt}
              disabled={voting}
              onClick={() => onVote(opt)}
              className={`btn-raised rounded px-4 py-2 text-sm font-medium disabled:opacity-50 ${
                myVote === opt
                  ? "bg-[#28324f] text-white"
                  : "border border-gray-300 hover:bg-gray-50"
              }`}
            >
              {myVote === opt ? (
                <span className="inline-flex items-center gap-1">
                  <CheckCircle2 size={14} /> {opt}
                </span>
              ) : (
                opt
              )}
            </button>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <select
            className="rounded border border-gray-300 px-3 py-2 text-sm"
            value={choice}
            onChange={(e) => setChoice(e.target.value)}
          >
            {options.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
          <button
            disabled={voting}
            onClick={() => onVote(choice)}
            className="btn-raised rounded bg-[#28324f] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Confirm Vote
          </button>
        </div>
      )}
      {voteSuccess && (
        <p className="mt-2 rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          {voteSuccess}
        </p>
      )}
      {voteError && (
        <p className="mt-2 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {voteError}
        </p>
      )}
    </div>
  );
}

function PollSection({ poll }: { poll: PollSummaryResponse | null }) {
  const [openOption, setOpenOption] = useState<string | null>(null);

  return (
    <div>
      <h3 className="mb-2 flex items-center gap-1.5 font-semibold">
        <BarChart3 size={16} /> Poll
      </h3>
      {!poll ? (
        <p className="text-sm text-gray-500">Poll data unavailable.</p>
      ) : poll.hidden ? (
        <p className="text-sm text-gray-500">
          <b>{poll.total}</b> vote(s) cast — results visible after voting closes.
        </p>
      ) : poll.total === 0 ? (
        <p className="text-sm text-gray-500">No votes cast yet.</p>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-gray-500">{poll.total} total votes</p>
          {poll.options.map((o) => (
            <div key={o.option}>
              <div className="flex items-center justify-between text-sm">
                <span className="font-mono">{o.option}</span>
                <span className="text-gray-500">
                  {o.pct}% ({o.count})
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded bg-gray-100">
                <div
                  className="h-full bg-[#28324f]"
                  style={{ width: `${o.pct}%` }}
                />
              </div>
              {o.voters && o.voters.length > 0 && (
                <button
                  onClick={() => setOpenOption(openOption === o.option ? null : o.option)}
                  className="mt-1 text-xs text-blue-600 hover:underline"
                >
                  {openOption === o.option ? "Hide voters" : `Who voted ${o.option}`}
                </button>
              )}
              {openOption === o.option && o.voters && (
                <ul className="mt-1 rounded border border-gray-100 bg-gray-50 p-2 text-xs">
                  {o.voters.map((v) => (
                    <li key={v.user_id} className="flex items-center gap-1 py-0.5">
                      <User size={11} /> {v.name}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ResultSection({ result }: { result: ResultBreakdownResponse }) {
  const [openOption, setOpenOption] = useState<string | null>(null);
  const [showMissed, setShowMissed] = useState(false);

  return (
    <div>
      <h3 className="mb-2 flex items-center gap-1.5 font-semibold">
        <Trophy size={16} /> Result: {result.result} Won
      </h3>
      {result.winner_points > 0 && (
        <p className="mb-2 text-xs text-gray-500">
          Points awarded to correct voters: <b>+{result.winner_points}</b> each
        </p>
      )}
      <div className="space-y-2">
        {result.options.map((o) => (
          <div key={o.option} className="rounded border border-gray-200">
            <button
              onClick={() => setOpenOption(openOption === o.option ? null : o.option)}
              className="flex w-full items-center justify-between px-3 py-2 text-sm"
            >
              <span className="inline-flex items-center gap-1">
                {o.is_win ? (
                  <CheckCircle2 size={14} className="text-green-700" />
                ) : (
                  <XCircle size={14} className="text-rose-700" />
                )}
                <b>{o.option}</b> voters{" "}
                <span className="text-gray-500">
                  ({o.voters.length}) — {o.pts_label}
                </span>
              </span>
              <span className="text-gray-400">{openOption === o.option ? "▲" : "▼"}</span>
            </button>
            {openOption === o.option && (
              <div className="border-t border-gray-100 px-3 py-2 text-xs">
                {o.voters.length === 0 ? (
                  <p className="text-gray-500">No votes.</p>
                ) : (
                  o.voters.map((v) => (
                    <p key={v.user_id} className="flex items-center gap-1 py-0.5">
                      <User size={11} /> <b>{v.name}</b>{" "}
                      <span className={v.points > 0 ? "text-green-700" : "text-rose-700"}>
                        {v.points > 0 ? `+${v.points}` : v.points} pts
                      </span>
                    </p>
                  ))
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {result.missed.length > 0 && (
        <div className="mt-3 rounded border border-gray-200">
          <button
            onClick={() => setShowMissed(!showMissed)}
            className="flex w-full items-center justify-between px-3 py-2 text-sm"
          >
            <span className="flex items-center gap-1">
              <AlertTriangle size={14} /> Missed / Penalised ({result.missed.length})
            </span>
            <span className="text-gray-400">{showMissed ? "▲" : "▼"}</span>
          </button>
          {showMissed && (
            <div className="border-t border-gray-100 px-3 py-2 text-xs">
              {result.missed.map((p) => (
                <p key={p.user_id} className="flex items-center gap-1 py-0.5">
                  <User size={11} /> <b>{p.name}</b> {p.note} — {p.points} pts
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
