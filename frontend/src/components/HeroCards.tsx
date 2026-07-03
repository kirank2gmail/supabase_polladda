import type { HeroStat } from "../api/types";

const CARDS: { key: string; label: string; icon: string; unit: string }[] = [
  { key: "top_win_streak", label: "Longest Win Streak", icon: "🔥", unit: "consecutive wins (misses ignored)" },
  { key: "top_loss_streak", label: "Longest Loss Streak", icon: "💀", unit: "consecutive losses (misses ignored)" },
  { key: "top_missed", label: "Most Missed Votes", icon: "⚠️", unit: "missed" },
];

export function HeroCards({ heroes }: { heroes: Record<string, HeroStat> }) {
  if (!heroes || Object.keys(heroes).length === 0) return null;

  return (
    <div className="mb-4">
      <h3 className="mb-2 text-lg font-bold">🎖️ Highlights</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {CARDS.map(({ key, label, icon, unit }) => {
          const hero = heroes[key];
          if (!hero) return null;
          return (
            <div key={key} className="rounded-lg border border-gray-200 p-4">
              <div className="mb-1 font-semibold">
                {icon} {label}
              </div>
              <div className="font-bold text-gray-900">{hero.names}</div>
              <div className="text-sm text-gray-500">
                {hero.value} {unit}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
