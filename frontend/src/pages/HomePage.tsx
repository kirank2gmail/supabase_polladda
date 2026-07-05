import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Home as HomeIcon,
  CalendarClock,
  Hourglass,
  ClipboardList,
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

type HomeTabKey = "upcoming" | "in_progress" | "completed";

export function HomePage() {
  const navigate = useNavigate();
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [data, setData] = useState<HomeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<HomeTabKey>("upcoming");

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
          <div className="mb-4 flex gap-2 border-b border-gray-200">
            {(
              [
                { key: "upcoming", label: `Upcoming (${data.upcoming.length})`, icon: CalendarClock },
                { key: "in_progress", label: `In Progress (${data.in_progress.length})`, icon: Hourglass },
                { key: "completed", label: `Past (${data.completed.length})`, icon: ClipboardList },
              ] as const
            ).map((t) => (
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

          {tab === "upcoming" && (
            <Section emptyLabel="No upcoming matches.">
              {data.upcoming.map((c, i) => (
                <UpcomingCard key={c.match.match_id} card={c} index={i} onClick={goToMatch} />
              ))}
            </Section>
          )}

          {tab === "in_progress" && (
            <Section
              subtitle="Voting closed — result not yet updated by admin."
              emptyLabel="No matches awaiting result."
            >
              {data.in_progress.map((c, i) => (
                <InProgressCard key={c.match.match_id} card={c} index={i} onClick={goToMatch} />
              ))}
            </Section>
          )}

          {tab === "completed" && (
            <Section emptyLabel="No completed matches yet.">
              {data.completed.map((c, i) => (
                <CompletedCard key={c.match.match_id} card={c} index={i} onClick={goToMatch} />
              ))}
            </Section>
          )}
        </>
      )}
    </div>
  );
}

function Section({
  subtitle,
  emptyLabel,
  children,
}: {
  subtitle?: string;
  emptyLabel: string;
  children: React.ReactNode[];
}) {
  return (
    <div>
      {subtitle && <p className="mb-2 text-sm text-gray-500">{subtitle}</p>}
      {children.length === 0 ? (
        <p className="text-sm text-gray-500">{emptyLabel}</p>
      ) : (
        <div className="divide-y divide-gray-100 rounded-md border border-gray-200 p-2">
          {children}
        </div>
      )}
    </div>
  );
}

function UpcomingCard({
  card,
  index,
  onClick,
}: {
  card: HomeMatchOut;
  index: number;
  onClick: (matchId: string) => void;
}) {
  const { match, times, countdown, my_vote } = card;
  const sevClass = countdown ? SEVERITY_STYLES[countdown.severity] : "";
  const rowBg = index % 2 === 1 ? "bg-gray-50" : "bg-white";

  return (
    <div className={`flex flex-col gap-2 px-2 py-3 ${rowBg}`}>
      <div className="flex gap-2">
        <div className="w-1/2">
          <p className="font-semibold">
            <span className="text-xs font-normal text-gray-400">{match.match_id}.</span> {match.title}
          </p>
          <p className="flex items-center gap-1 text-xs text-gray-500">
            <Calendar size={12} /> {times.local}
          </p>
          <p className="flex items-center gap-1 text-xs text-gray-500">
            <MapPin size={12} /> {match.location}
          </p>
          {times.user && (
            <p className="flex items-center gap-1 text-xs text-gray-500">
              <Clock size={12} /> Your time: {times.user}
            </p>
          )}
        </div>
        <div className="w-1/2">
          {my_vote && (
            <p className="mb-1 flex items-center gap-1 text-sm">
              Your vote: <b>{my_vote}</b> <CheckCircle2 size={14} className="text-green-700" />
            </p>
          )}
          <button
            onClick={() => onClick(match.match_id)}
            className="btn-raised w-full rounded border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
          >
            {my_vote ? "Change →" : "Vote Now →"}
          </button>
        </div>
      </div>
      {countdown && (
        <span className={`inline-block w-fit rounded border px-2 py-1 text-xs font-medium ${sevClass}`}>
          {countdown.message}
        </span>
      )}
    </div>
  );
}

function InProgressCard({
  card,
  index,
  onClick,
}: {
  card: HomeMatchOut;
  index: number;
  onClick: (matchId: string) => void;
}) {
  const { match, times, my_vote } = card;
  const rowBg = index % 2 === 1 ? "bg-gray-50" : "bg-white";
  return (
    <div className={`flex flex-col gap-2 px-2 py-3 ${rowBg}`}>
      <div className="flex gap-2">
        <div className="w-1/2">
          <p className="font-semibold">
            <span className="text-xs font-normal text-gray-400">{match.match_id}.</span> {match.title}
          </p>
          <p className="flex items-center gap-1 text-xs text-gray-500">
            <Calendar size={12} /> {times.local}
          </p>
          <p className="flex items-center gap-1 text-xs text-gray-500">
            <MapPin size={12} /> {match.location}
          </p>
          <p className="flex items-center gap-1 text-xs text-rose-600">
            <Circle size={8} className="fill-rose-600 text-rose-600" /> Poll closed — awaiting result
          </p>
        </div>
        <div className="w-1/2">
          {my_vote ? (
            <p className="mb-1 flex items-center gap-1 text-sm">
              You voted: <b>{my_vote}</b> <CheckCircle2 size={14} className="text-green-700" />
            </p>
          ) : (
            <p className="mb-1 flex items-center gap-1 text-sm text-gray-500">
              <AlertTriangle size={14} /> No vote cast
            </p>
          )}
          <button
            onClick={() => onClick(match.match_id)}
            className="btn-raised w-full rounded border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
          >
            View Votes →
          </button>
        </div>
      </div>
    </div>
  );
}

function CompletedCard({
  card,
  index,
  onClick,
}: {
  card: HomeMatchOut;
  index: number;
  onClick: (matchId: string) => void;
}) {
  const { match, times, my_vote, my_points, correct } = card;
  const pts = my_points ?? 0;
  const ptsStr = pts > 0 ? `+${pts.toFixed(2)}` : pts.toFixed(2);
  const ptsClass = pts > 0 ? "text-green-700" : pts < 0 ? "text-rose-700" : "text-gray-600";
  const rowBg = index % 2 === 1 ? "bg-gray-50" : "bg-white";

  return (
    <div className={`flex flex-col gap-2 px-2 py-3 ${rowBg}`}>
      <div className="flex gap-2">
        <div className="w-1/2">
          <p className="font-semibold">
            <span className="text-xs font-normal text-gray-400">{match.match_id}.</span> {match.title}
          </p>
          <p className="flex items-center gap-1 text-xs text-gray-500">
            <Calendar size={12} /> {times.local}
          </p>
          <p className="flex items-center gap-1 text-xs text-gray-500">
            <MapPin size={12} /> {match.location}
          </p>
          <p className="text-xs text-gray-500">Result: <b>{match.result}</b></p>
        </div>
        <div className="w-1/2">
          {my_vote ? (
            <p className="mb-1 flex items-center gap-1 text-sm text-gray-500">
              Your vote: {my_vote}{" "}
              {correct ? (
                <CheckCircle2 size={14} className="text-green-700" />
              ) : (
                <XCircle size={14} className="text-rose-700" />
              )}
            </p>
          ) : (
            <p className="mb-1 flex items-center gap-1 text-sm text-gray-500">
              <AlertTriangle size={14} /> No vote cast
            </p>
          )}
          <p className={`mb-1 text-sm font-bold ${ptsClass}`}>{ptsStr} pts</p>
          <button
            onClick={() => onClick(match.match_id)}
            className="btn-raised w-full rounded border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
          >
            Details →
          </button>
        </div>
      </div>
    </div>
  );
}
