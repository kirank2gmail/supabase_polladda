import { useState } from "react";
import type { LeaderboardResponse } from "../api/types";
import { cellColours, cellText } from "../lib/cellFormat";

const COLS_PER_ROW = 6;

function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

// Inline analog of pages/leaderboard.py's "Match Details" button grid. The
// Streamlit version navigates to a full match voting/results page; that page
// doesn't exist in React yet, so instead of linking to a route that isn't
// built, clicking a match expands an inline per-player breakdown using data
// already present in the leaderboard response (no extra API calls).
export function MatchDetailsSection({ data }: { data: LeaderboardResponse }) {
  const [selected, setSelected] = useState<string | null>(null);

  if (data.match_ids_desc.length === 0) return null;

  const match = selected
    ? data.matches_asc.find((m) => m.match_id === selected)
    : null;

  const breakdown = selected
    ? [...data.rows]
        .map((row) => ({ name: row.name, val: row[selected] ?? null }))
        .sort((a, b) => {
          const av = typeof a.val === "number" ? a.val : -Infinity;
          const bv = typeof b.val === "number" ? b.val : -Infinity;
          return bv - av;
        })
    : [];

  return (
    <div className="mt-4">
      <h4 className="mb-2 font-bold">🔍 Match Details</h4>
      <div className="max-h-40 overflow-y-auto rounded-md border border-gray-200 p-3">
        {chunk(data.match_ids_desc, COLS_PER_ROW).map((row, ri) => (
          <div key={ri} className="mb-2 grid grid-cols-3 gap-2 sm:grid-cols-6">
            {row.map((mid) => {
              const m = data.matches_asc.find((x) => x.match_id === mid);
              const isActive = selected === mid;
              return (
                <button
                  key={mid}
                  title={m?.title ?? mid}
                  onClick={() => setSelected(isActive ? null : mid)}
                  className={`truncate rounded border px-2 py-1 text-xs font-medium ${
                    isActive
                      ? "border-[#28324f] bg-[#28324f] text-white"
                      : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  {data.labels[mid] ?? mid}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {selected && match && (
        <div className="mt-3 rounded-md border border-gray-200 p-3">
          <div className="mb-2 flex items-baseline justify-between">
            <h5 className="font-bold">{match.title}</h5>
            <span className="text-xs text-gray-500">
              {match.result ? `Result: ${match.result}` : match.status}
            </span>
          </div>
          <div className="max-h-48 overflow-auto">
            <table className="w-full border-collapse text-sm">
              <tbody>
                {breakdown.map(({ name, val }) => {
                  const { fg, bg } = cellColours(val as never);
                  return (
                    <tr key={name} className="border-b border-gray-100">
                      <td className="px-2 py-1 font-medium">{name}</td>
                      <td
                        className="px-2 py-1 text-right font-semibold"
                        style={{ color: fg, background: bg ?? undefined }}
                      >
                        {cellText(val as never)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
