import { useEffect, useState } from 'react';
import type { Developer } from '../types';

const MEDALS = ['🥇', '🥈', '🥉'];

function ScoreBar({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value));
  const color = pct >= 70 ? 'bg-emerald-500' : pct >= 45 ? 'bg-amber-400' : 'bg-red-400';
  return (
    <div className="w-24 bg-gray-200 rounded-full h-2 inline-block align-middle ml-2">
      <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
    </div>
  );
}

interface Props {
  onSelect: (username: string) => void;
}

export default function Leaderboard({ onSelect }: Props) {
  const [devs, setDevs] = useState<Developer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/leaderboard')
      .then(r => r.json())
      .then(data => { setDevs(data); setLoading(false); });
  }, []);

  if (loading) {
    return <div className="text-center py-20 text-gray-400">Loading leaderboard…</div>;
  }

  if (devs.length === 0) {
    return (
      <div className="text-center py-20 text-gray-400">
        No scores yet. Run <code className="bg-gray-100 px-1 rounded">python agent.py</code> to score some MRs.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-500 uppercase text-xs tracking-wide">
          <tr>
            <th className="px-5 py-3 text-left">Rank</th>
            <th className="px-5 py-3 text-left">Developer</th>
            <th className="px-5 py-3 text-right">Points</th>
            <th className="px-5 py-3 text-right">MRs</th>
            <th className="px-5 py-3 text-right">Streak Eligible</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {devs.map(dev => (
            <tr
              key={dev.id}
              className="hover:bg-indigo-50 cursor-pointer transition-colors"
              onClick={() => onSelect(dev.username)}
            >
              <td className="px-5 py-4 font-mono text-gray-400">
                {dev.rank <= 3 ? MEDALS[dev.rank - 1] : `#${dev.rank}`}
              </td>
              <td className="px-5 py-4 font-semibold text-gray-800">{dev.username}</td>
              <td className="px-5 py-4 text-right">
                <span className="font-bold text-indigo-600">{dev.total_points.toFixed(1)}</span>
                <ScoreBar value={(dev.total_points / Math.max(...devs.map(d => d.total_points))) * 100} />
              </td>
              <td className="px-5 py-4 text-right text-gray-600">{dev.mr_count}</td>
              <td className="px-5 py-4 text-right">
                {dev.streak_eligible_count > 0 ? (
                  <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-700 text-xs font-medium px-2 py-0.5 rounded-full">
                    🔥 {dev.streak_eligible_count}
                  </span>
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
