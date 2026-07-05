import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Home as HomeIcon,
  CalendarClock,
  Hourglass,
  ClipboardList,
  Trophy,
  MapPin,
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Circle,
} from "lucide-react";
import { getHome } from "../api/home";
import { getMatches } from "../api/matches";
import { getTournaments } from "../api/tournaments";
import type { HomeMatchOut, HomeResponse, Tournament } from "../api/types";

const SEVERITY_STYLES: Record<string, string> = {
  success: "bg-green-50 text-green-700 border-green-200",
  warning: "bg-yellow-50 text-yellow-700 border-yellow-200",
  error: "bg-rose-50 text-rose-700 border-rose-200",
};

export function HomePage() {
  const navigate = useNavigate();
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [data, setData] = useState<HomeResponse | null>(null);
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
    getHome(selected)
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [selected]);

  const goToMatch = async (matchId: string) => {
    // Nav list is the full tournament in ascending chronological order,
    // same as pages/home.py's _go_match — not reconstructed from the
    // upcoming/in_progress/completed cards, which would mix a reversed
    // (newest-first) completed segment in with the ascending ones.
    let matchList: string[] = [];
    try {
      const all = await getMatches(selected);
      matchList = all.map((m) => m.match_id);
    } catch {
      /* best-effort — MatchPage re-fetches its own fallback list if empty */
    }
    navigate(`/match/${encodeURIComponent(matchId)}`, {
      state: { matchList, tournamentId: selected },
    });
  };

  return (
    <div className="mx-auto max-w-[614px] p-4">
      <h1 className="mb-4 flex items-center gap-2 text-xl font-bold">
        <HomeIcon size={20} /> Home
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

      {!loading && !error && data && (
        <>
          <Section
            icon={CalendarClock}
            title={`Upcoming Matches (${data.upcoming.length})`}
            emptyLabel="No upcoming matches."
          >
            {data.upcoming.map((c) => (
              <UpcomingCard key={c.match.match_id} card={c} onClick={goToMatch} />
            ))}
          </Section>

          <Section
            icon={Hourglass}
            title={`In Progress (${data.in_progress.length})`}
            subtitle="Voting closed — result not yet updated by admin."
            emptyLabel="No matches awaiting result."
          >
            {data.in_progress.map((c) => (
              <InProgressCard key={c.match.match_id} card={c} onClick={goToMatch} />
            ))}
          </Section>

          <Section
            icon={ClipboardList}
            title={`Past Matches (${data.completed.length})`}
            emptyLabel="No completed matches yet."
          >
            {data.completed.map((c) => (
              <CompletedCard key={c.match.match_id} card={c} onClick={goToMatch} />
            ))}
          </Section>

          <div className="mt-4 flex justify-center">
            <button
              onClick={() => navigate("/leaderboard")}
              className="btn-raised flex items-center gap-2 rounded bg-[#28324f] px-4 py-2 text-sm font-medium text-white hover:bg-[#1c2439]"
            >
              <Trophy size={16} /> View Full Leaderboard
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  subtitle,
  emptyLabel,
  children,
}: {
  icon: React.ComponentType<{ size?: number }>;
  title: string;
  subtitle?: string;
  emptyLabel: string;
  children: React.ReactNode[];
}) {
  return (
    <div className="mb-5">
      <h2 className="mb-1 flex items-center gap-2 text-lg font-bold">
        <Icon size={18} /> {title}
      </h2>
      {subtitle && <p className="mb-2 text-sm text-gray-500">{subtitle}</p>}
      {children.length === 0 ? (
        <p className="text-sm text-gray-500">{emptyLabel}</p>
      ) : (
        <div className="max-h-80 divide-y divide-gray-100 overflow-y-auto rounded-md border border-gray-200 p-2">
          {children}
        </div>
      )}
    </div>
  );
}

function UpcomingCard({
  card,
  onClick,
}: {
  card: HomeMatchOut;
  onClick: (matchId: string) => void;
}) {
  const { match, times, countdown, my_vote } = card;
  const sevClass = countdown ? SEVERITY_STYLES[countdown.severity] : "";

  return (
    <div className="grid grid-cols-1 gap-2 py-3 sm:grid-cols-[4fr_3fr_2fr] sm:items-center">
      <div>
        <p className="font-semibold">{match.title}</p>
        <p className="text-xs text-gray-500">
          <span className="inline-flex items-center gap-1"><MapPin size={12} /> {match.location}</span> <span className="inline-flex items-center gap-1"><Calendar size={12} /> {times.local}</span>
        </p>
        {times.user && (
          <p className="flex items-center gap-1 text-xs text-gray-500">
            <Clock size={12} /> Your time: {times.user}
          </p>
        )}
      </div>
      <div>
        {countdown && (
          <span className={`inline-block rounded border px-2 py-1 text-xs font-medium ${sevClass}`}>
            {countdown.message}
          </span>
        )}
      </div>
      <div className="text-right">
        {my_vote && (
          <p className="mb-1 flex items-center justify-end gap-1 text-sm">
            Your vote: <b>{my_vote}</b> <CheckCircle2 size={14} className="text-green-700" />
          </p>
        )}
        <button
          onClick={() => onClick(match.match_id)}
          className="btn-raised rounded bg-[#28324f] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#1c2439]"
        >
          {my_vote ? "Change →" : "Vote Now →"}
        </button>
      </div>
    </div>
  );
}

function InProgressCard({
  card,
  onClick,
}: {
  card: HomeMatchOut;
  onClick: (matchId: string) => void;
}) {
  const { match, times, my_vote } = card;
  return (
    <div className="grid grid-cols-1 gap-2 py-3 sm:grid-cols-[4fr_3fr_2fr] sm:items-center">
      <div>
        <p className="font-semibold">{match.title}</p>
        <p className="text-xs text-gray-500">
          <span className="inline-flex items-center gap-1"><MapPin size={12} /> {match.location}</span> <span className="inline-flex items-center gap-1"><Calendar size={12} /> {times.local}</span>
        </p>
      </div>
      <div className="text-sm">
        {my_vote ? (
          <p className="flex items-center gap-1">
            You voted: <b>{my_vote}</b> <CheckCircle2 size={14} className="text-green-700" />
          </p>
        ) : (
          <p className="flex items-center gap-1 text-gray-500">
            <AlertTriangle size={14} /> No vote cast
          </p>
        )}
        <p className="flex items-center gap-1 text-xs text-rose-600">
          <Circle size={8} className="fill-rose-600 text-rose-600" /> Poll closed — awaiting result
        </p>
      </div>
      <div className="text-right">
        <button
          onClick={() => onClick(match.match_id)}
          className="btn-raised rounded border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
        >
          View Votes →
        </button>
      </div>
    </div>
  );
}

function CompletedCard({
  card,
  onClick,
}: {
  card: HomeMatchOut;
  onClick: (matchId: string) => void;
}) {
  const { match, times, my_vote, my_points, correct } = card;
  const pts = my_points ?? 0;
  const ptsStr = pts > 0 ? `+${pts.toFixed(2)}` : pts.toFixed(2);
  const ptsClass = pts > 0 ? "text-green-700" : pts < 0 ? "text-rose-700" : "text-gray-600";

  return (
    <div className="grid grid-cols-1 gap-2 py-3 sm:grid-cols-[4fr_3fr_2fr] sm:items-center">
      <div>
        <p className="font-semibold">{match.title}</p>
        <p className="text-xs text-gray-500">
          <span className="inline-flex items-center gap-1"><MapPin size={12} /> {match.location}</span> <span className="inline-flex items-center gap-1"><Calendar size={12} /> {times.local}</span>
        </p>
      </div>
      <div className="text-sm">
        <p>Result: <b>{match.result}</b></p>
        {my_vote ? (
          <p className="flex items-center gap-1 text-gray-500">
            Your vote: {my_vote}{" "}
            {correct ? (
              <CheckCircle2 size={14} className="text-green-700" />
            ) : (
              <XCircle size={14} className="text-rose-700" />
            )}
          </p>
        ) : (
          <p className="flex items-center gap-1 text-gray-500">
            <AlertTriangle size={14} /> No vote cast
          </p>
        )}
      </div>
      <div className="text-right">
        <p className={`mb-1 text-sm font-bold ${ptsClass}`}>{ptsStr} pts</p>
        <button
          onClick={() => onClick(match.match_id)}
          className="btn-raised rounded border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
        >
          Details →
        </button>
      </div>
    </div>
  );
}
