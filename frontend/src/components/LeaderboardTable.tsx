import { useEffect, useMemo, useRef, useState } from "react";
import type { LeaderboardResponse } from "../api/types";
import { cellColours, cellText } from "../lib/cellFormat";

const MEDALS = ["🥇", "🥈", "🥉"];

// Must match the #/Player/Points <th>/<td> widths below (48 + 160 + 90) —
// used to size the invisible spacer in the custom scrollbar row so it
// lines up under the scrollable table, not the fixed one.
const FROZEN_WIDTH = 48 + 160 + 90;

type SortKey = "total_points" | "win_pct" | "name";
const SORT_OPTIONS: { label: string; key: SortKey; desc: boolean }[] = [
  { label: "Points", key: "total_points", desc: true },
  { label: "Win %", key: "win_pct", desc: true },
  { label: "Alphabetical", key: "name", desc: false },
];

export function LeaderboardTable({ data }: { data: LeaderboardResponse }) {
  const [sortIdx, setSortIdx] = useState(0);
  const sort = SORT_OPTIONS[sortIdx];

  // The scrolling table's native scrollbar is hidden (.scrollbar-hide) so
  // it doesn't reserve extra height that the fixed table lacks — that
  // mismatch was making the two tables' bottoms misalign. A separate,
  // visible scrollbar strip below both tables drives the real scroll
  // position instead, kept in sync via these two refs.
  const contentRef = useRef<HTMLDivElement>(null);
  const scrollbarRef = useRef<HTMLDivElement>(null);
  const [contentWidth, setContentWidth] = useState(0);

  useEffect(() => {
    if (contentRef.current) {
      setContentWidth(contentRef.current.scrollWidth);
    }
  }, [data]);

  const syncFromContent = () => {
    if (scrollbarRef.current && contentRef.current) {
      scrollbarRef.current.scrollLeft = contentRef.current.scrollLeft;
    }
  };
  const syncFromScrollbar = () => {
    if (scrollbarRef.current && contentRef.current) {
      contentRef.current.scrollLeft = scrollbarRef.current.scrollLeft;
    }
  };

  // Single sorted source of truth — both the frozen and scrolling tables
  // below map over this same array, so a sort change always reorders them
  // in lockstep; there's no separate state to keep in sync.
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
      <div className="mb-3 flex items-center gap-2">
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

      {/*
        Two separate <table> elements instead of one wide table with sticky
        columns: a CSS `position: sticky` approach here left a visible seam
        where scrolled match-column content peeked through behind the
        Player/Points cells. Splitting into a fixed (never-scrolls) table
        for #/Player/Points and a second, independently horizontally-
        scrollable table for everything else avoids that rendering
        entirely — there's nothing to peek through because the fixed
        table's cells are never overlaid by scrolling content.
        Both tables share identical row padding/borders/backgrounds so
        rows line up pixel-for-pixel and the join between them reads as
        one continuous table rather than two components glued together.
      */}
      <div className="flex overflow-hidden rounded-md border border-gray-300">
        <table className="flex-none border-collapse text-sm whitespace-nowrap">
          <thead>
            <tr className="bg-[#28324f] text-white">
              <th className="w-12 px-3 py-2 text-center">#</th>
              <th className="w-[160px] px-3 py-2 text-left">Player</th>
              <th className="w-[90px] px-3 py-2 text-right">Points</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const pts = Number(row.total_points);
              const rowBg = i % 2 === 1 ? "bg-gray-50" : "bg-white";
              const ptsFg = pts >= 0 ? "text-[#15803d]" : "text-[#be123c]";
              const ptsStr = pts >= 0 ? `+${pts.toFixed(2)}` : pts.toFixed(2);

              return (
                <tr key={row.user_id} className={rowBg}>
                  <td className="w-12 border-b border-gray-200 px-3 py-2 text-center">
                    {i < 3 ? MEDALS[i] : i + 1}
                  </td>
                  <td className="w-[160px] overflow-hidden text-ellipsis border-b border-gray-200 px-3 py-2 font-semibold">
                    {row.name}
                  </td>
                  <td
                    className={`w-[90px] border-b border-gray-200 px-3 py-2 text-right font-bold ${ptsFg}`}
                  >
                    {ptsStr}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-[#28324f] bg-[#f0f4ff] font-bold">
              <td className="w-12 px-3 py-2 text-center">—</td>
              <td className="w-[160px] px-3 py-2">Total</td>
              <td
                className={`w-[90px] px-3 py-2 text-right ${
                  data.grand_total >= 0 ? "text-[#15803d]" : "text-[#be123c]"
                }`}
              >
                {data.grand_total >= 0
                  ? `+${data.grand_total.toFixed(2)}`
                  : data.grand_total.toFixed(2)}
              </td>
            </tr>
          </tfoot>
        </table>

        <div
          ref={contentRef}
          onScroll={syncFromContent}
          className="scrollbar-hide min-w-0 flex-1 overflow-x-auto"
        >
          <table className="w-full border-collapse text-sm whitespace-nowrap">
            <thead>
              <tr className="bg-[#28324f] text-white">
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
                const rowBg = i % 2 === 1 ? "bg-gray-50" : "bg-white";
                const missed = Number(row.missed);
                const missFg = missed > 0 ? "text-[#b45309]" : "text-gray-900";

                return (
                  <tr key={row.user_id} className={rowBg}>
                    <td className="border-b border-gray-200 px-3 py-2 text-right text-gray-600">
                      {Number(row.win_pct).toFixed(0)}%
                    </td>
                    <td
                      className={`border-b border-gray-200 px-3 py-2 text-right font-semibold ${missFg}`}
                    >
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
      </div>

      {/* Custom scrollbar row — spacer under the fixed table, real
          (visible) scrollbar under the scrollable one, synced above. */}
      <div className="flex">
        <div style={{ width: FROZEN_WIDTH }} className="flex-none" />
        <div
          ref={scrollbarRef}
          onScroll={syncFromScrollbar}
          className="min-w-0 flex-1 overflow-x-auto overflow-y-hidden"
        >
          <div style={{ width: contentWidth, height: 1 }} />
        </div>
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
