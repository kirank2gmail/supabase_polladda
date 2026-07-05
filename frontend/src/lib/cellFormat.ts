// TS port of data/leaderboard_builder.py's cell_text()/cell_colours() — same
// branch order, so React never disagrees with Streamlit on a cell's
// displayed text for the same value. The colors themselves are a
// deliberate, React-only divergence (softened from Streamlit's original
// jewel tones to a gentler, still-accessible palette) — same precedent as
// the earlier background-tinting removal in LeaderboardTable.tsx.
import type { CellValue } from "../api/types";

const COLOURS: Record<string, [string, string | null]> = {
  win: ["#15803d", "#dcfce7"],   // green-700 / green-100
  loss: ["#be123c", "#ffe4e6"],  // rose-700 / rose-100
  miss: ["#b45309", "#fef3c7"],  // amber-700 / amber-100
  aband: ["#6b7280", "#f3f4f6"], // gray-500 / gray-100
  quit: ["#6d28d9", "#f3e8ff"],  // violet-700 / violet-100
  neu: ["#4b5563", null],        // gray-600
  black: ["#1f2937", null],      // gray-800
};

export function cellText(val: CellValue): string {
  if (val === null || val === undefined || val === "") return "—"; // —
  if (val === "A") return "A";
  if (val === "Q") return "Q";
  if (val === "miss" || val === "M") return "M";
  if (typeof val === "string" && val.startsWith("−")) return `-${val.slice(1)}`; // −
  const f = typeof val === "number" ? val : Number(val);
  if (!Number.isNaN(f)) {
    if (f > 0) return `+${f.toFixed(2)}`;
    if (f < 0) return f.toFixed(2);
    return "0";
  }
  return String(val);
}

export function cellColours(val: CellValue): { fg: string; bg: string | null } {
  const pick = (key: string) => {
    const [fg, bg] = COLOURS[key];
    return { fg, bg };
  };
  if (val === null || val === undefined || val === "") return pick("neu");
  if (val === "A") return pick("aband");
  if (val === "Q") return pick("quit");
  if (val === "miss" || val === "M") return pick("miss");
  if (typeof val === "string" && val.startsWith("−")) return pick("loss");
  const f = typeof val === "number" ? val : Number(val);
  if (!Number.isNaN(f)) {
    if (f > 0) return pick("win");
    if (f < 0) return pick("loss");
    return pick("neu");
  }
  return pick("black");
}
