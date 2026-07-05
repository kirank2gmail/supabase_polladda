import type { PenaltyOut } from "../api/types";

export function PenaltiesTable({ penalties }: { penalties: PenaltyOut[] }) {
  if (!penalties || penalties.length === 0) {
    return <p className="text-sm text-gray-500">No penalties recorded for this tournament.</p>;
  }

  return (
    <div>
      <div className="max-h-80 overflow-auto rounded-md border border-gray-200">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0">
            <tr className="bg-[#28324f] text-left text-white">
              <th className="px-3 py-2">Player</th>
              <th className="px-3 py-2">Points</th>
              <th className="px-3 py-2">Reason</th>
              <th className="px-3 py-2">Date</th>
            </tr>
          </thead>
          <tbody>
            {penalties.map((p) => (
              <tr key={p.penalty_id} className="border-b border-gray-100">
                <td className="px-3 py-2 font-semibold">{p.player_name}</td>
                <td className="px-3 py-2 font-bold text-rose-700">
                  -{p.points.toFixed(2)}
                </td>
                <td className="px-3 py-2 text-gray-600">{p.reason}</td>
                <td className="px-3 py-2 text-xs text-gray-400">
                  {p.created_at.slice(0, 10)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
