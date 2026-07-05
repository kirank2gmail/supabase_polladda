import { useMemo, useState } from "react";
import type { LeaderboardResponse } from "../api/types";
import { cellColours, cellText } from "../lib/cellFormat";

const MEDALS = ["🥇", "🥈", "🥉"];

type SortKey = "total_points" | "win_pct" | "name";
const SORT_OPTIONS: { label: string; key: SortKey; desc: boolean }[] = [
  { label: "Points", key: "total_points", desc: true },
  { label: "Win %", key: "win_pct", desc: true },
  { label: "Alphabetical", key: "name", desc: false },
];

export function LeaderboardTable({
  data,
  extra,
}: {
  data: LeaderboardResponse;
  extra?: React.ReactNode;
}) {
  const [sortIdx, setSortIdx] = useState(0);
  const sort = SORT_OPTIONS[sortIdx];

  const rows = useMemo(() => {
    const sorted = [...data.rows].sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (typeof av === "number" && typeof bv === "number") {
        return sort.desc ? bv - av : av - bv;
      }
      return String(av).localeCompare(String(bv));
    });
    return sorted;
  }, [data.rows, sort]);

  const labels = data.col_match_ids.map((mid) => data.labels[mid] ?? mid);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Sort by</span>
          <select
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            value={sortIdx}
            onChange={(e) => setSortIdx(Number(e.target.value))}
          >
            {SORT_OPTIONS.map((o, i) => (
              <option key={o.label} value={i}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        {extra}
      </div>

      {/* Single table, single native horizontal scrollbar (visible at the
          bottom of this container) — a prior frozen-column + custom-scrollbar
          split caused mobile touch scrolling to break, so back to the
          simplest thing that reliably scrolls on touch devices. */}
      <div className="touch-pan-x overflow-x-auto overscroll-x-contain rounded-md border border-gray-300">
        <table className="w-full border-collapse text-sm whitespace-nowrap">
          <thead>
            <tr className="bg-[#28324f] text-white">
              <th className="px-3 py-2 text-center">#</th>
              <th className="px-3 py-2 text-left">Player</th>
              <th className="px-3 py-2 text-right">Points</th>
              <th className="px-3 py-2 text-right">Win%</th>
              <th className="px-3 py-2 text-right">Missed</th>
              {labels.map((lbl, i) => (
                <th key={data.col_match_ids[i]} className="px-3 py-2 text-center">
                  {lbl}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const pts = Number(row.total_points);
              const rowBg = i % 2 === 1 ? "bg-gray-50" : "bg-white";
              const ptsFg = pts >= 0 ? "text-[#15803d]" : "text-[#be123c]";
              const ptsStr = pts >= 0 ? `+${pts.toFixed(2)}` : pts.toFixed(2);
              const missed = Number(row.missed);
              const missFg = missed > 0 ? "text-[#b45309]" : "text-gray-900";

              return (
                <tr key={row.user_id} className={rowBg}>
                  <td className="border-b border-gray-200 px-3 py-2 text-center">
                    {i < 3 ? MEDALS[i] : i + 1}
                  </td>
                  <td className="border-b border-gray-200 px-3 py-2 font-semibold">
                    {row.name}
                  </td>
                  <td className={`border-b border-gray-200 px-3 py-2 text-right font-bold ${ptsFg}`}>
                    {ptsStr}
                  </td>
                  <td className="border-b border-gray-200 px-3 py-2 text-right text-gray-600">
                    {Number(row.win_pct).toFixed(0)}%
                  </td>
                  <td className={`border-b border-gray-200 px-3 py-2 text-right font-semibold ${missFg}`}>
                    {missed}
                  </td>
                  {data.col_match_ids.map((mid) => {
                    const val = row[mid] ?? null;
                    const { fg } = cellColours(val as never);
                    return (
                      <td
                        key={mid}
                        className="border-b border-gray-200 px-3 py-2 text-right font-semibold"
                        style={{ color: fg }}
                      >
                        {cellText(val as never)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-[#28324f] bg-[#f0f4ff] font-bold">
              <td className="px-3 py-2 text-center">—</td>
              <td className="px-3 py-2">Total</td>
              <td
                className={`px-3 py-2 text-right ${
                  data.grand_total >= 0 ? "text-[#15803d]" : "text-[#be123c]"
                }`}
              >
                {data.grand_total >= 0
                  ? `+${data.grand_total.toFixed(2)}`
                  : data.grand_total.toFixed(2)}
              </td>
              <td />
              <td />
              {data.col_match_ids.map((mid) => {
                const t = data.col_totals[mid] ?? 0;
                const color =
                  t > 0 ? "text-[#15803d]" : t < 0 ? "text-[#be123c]" : "text-gray-600";
                const val = t > 0 ? `+${t.toFixed(2)}` : t < 0 ? t.toFixed(2) : "0";
                return (
                  <td key={mid} className={`px-3 py-2 text-right ${color}`}>
                    {val}
                  </td>
                );
              })}
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="mt-3">
        🏦 <span className="font-semibold">Bank:</span>{" "}
        <span
          className={`font-bold ${
            data.bank > 0
              ? "text-[#15803d]"
              : data.bank < 0
              ? "text-[#be123c]"
              : "text-gray-600"
          }`}
        >
          {data.bank > 0 ? `+${data.bank.toFixed(2)}` : data.bank.toFixed(2)} pts
        </span>
      </p>
    </div>
  );
}
