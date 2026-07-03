// TS port of pages/leaderboard.py's CSV export (lines 83-101): same column
// set/order (rank, name, points, win%, missed, then match columns renamed to
// their labels) and the same cell_text() formatting for match columns, built
// from data.rows in its original (backend-ranked) order — matches Streamlit's
// "built before sort" comment so the download always reflects points order
// regardless of the on-page sort control.
import type { LeaderboardResponse } from "../api/types";
import { cellText } from "./cellFormat";

function csvField(value: unknown): string {
  const s = String(value ?? "");
  if (/[",\n]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function buildLeaderboardCsv(data: LeaderboardResponse): string {
  const headers = [
    "#",
    "Player",
    "Points",
    "Win%",
    "Missed",
    ...data.match_ids_desc.map((mid) => data.labels[mid] ?? mid),
  ];

  const lines = [headers.map(csvField).join(",")];

  for (const row of data.rows) {
    const fields = [
      row.rank,
      row.name,
      row.total_points,
      row.win_pct,
      row.missed,
      ...data.match_ids_desc.map((mid) => cellText(row[mid] as never)),
    ];
    lines.push(fields.map(csvField).join(","));
  }

  return lines.join("\n");
}

export function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
