// Line-for-line TS port of data/leaderboard_builder.py's cell_text()/
// cell_colours() — same branch order, so React never disagrees with
// Streamlit on a cell's displayed text or color for the same value.
import type { CellValue } from "../api/types";

const COLOURS: Record<string, [string, string | null]> = {
  win: ["#0e6e24", "#d1f0d7"],
  loss: ["#a01414", "#fcd7d7"],
  miss: ["#8c5500", "#fff3cd"],
  aband: ["#777777", "#e0e0e0"],
  quit: ["#5a3e8a", "#e8e0f0"],
  neu: ["#555555", null],
  black: ["#111111", null],
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
