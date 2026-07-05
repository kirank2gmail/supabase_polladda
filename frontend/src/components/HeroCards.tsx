import { Award } from "lucide-react";
import type { HeroStat } from "../api/types";

const CARDS: { key: string; label: string; icon: string; unit: string }[] = [
  { key: "top_win_streak", label: "Longest Win Streak", icon: "🔥", unit: "consecutive wins (misses ignored)" },
  { key: "top_loss_streak", label: "Longest Loss Streak", icon: "💀", unit: "consecutive losses (misses ignored)" },
  { key: "top_missed", label: "Most Missed Votes", icon: "⚠️", unit: "missed" },
];

export function HeroCards({ heroes }: { heroes: Record<string, HeroStat> }) {
  if (!heroes || Object.keys(heroes).length === 0) return null;

  return (
    <div className="mb-3">
      <h3 className="mb-1 flex items-center gap-1.5 text-sm font-bold">
        <Award size={14} /> Highlights
      </h3>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {CARDS.map(({ key, label, icon, unit }) => {
          const hero = heroes[key];
          if (!hero) return null;
          return (
            <div key={key} className="rounded-lg border border-gray-200 p-2">
              <div className="text-xs font-semibold text-gray-600">
                {icon} {label}
              </div>
              <div className="text-sm font-bold text-gray-900">{hero.names}</div>
              <div className="text-xs text-gray-500">
                {hero.value} {unit}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
