import { useEffect, useState } from 'react';
import type { Score } from '../types';

const DIMENSIONS: { key: keyof Score['dimensions']; label: string; weight: string }[] = [
  { key: 'description_quality',   label: 'Description Quality',    weight: '25%' },
  { key: 'code_clarity',          label: 'Code Clarity',           weight: '25%' },
  { key: 'test_coverage_signal',  label: 'Test Coverage',          weight: '20%' },
  { key: 'pr_size_appropriate',   label: 'PR Size',                weight: '15%' },
  { key: 'review_responsiveness', label: 'Review Responsiveness',  weight: '10%' },
  { key: 'iteration_quality',     label: 'Iteration Quality',      weight: '5%'  },
];

// Handles both legacy flat-number format and nested {score, rationale} format
function dimScore(d: Score['dimensions'][keyof Score['dimensions']]): number {
  if (typeof d === 'number') return d;
  return d?.score ?? 0;
}
function dimRationale(d: Score['dimensions'][keyof Score['dimensions']]): string {
  if (typeof d === 'number') return '';
  return d?.rationale ?? '';
}

function DimensionBar({ score, label, weight, rationale }: {
  score: number; label: string; weight: string; rationale: string;
}) {
  const color = score >= 70 ? 'bg-emerald-500' : score >= 45 ? 'bg-amber-400' : 'bg-red-400';
  return (
    <div className="mb-3">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span className="font-medium text-gray-700">{label}</span>
        <span>{weight} weight · <span className="font-semibold text-gray-800">{score}/100</span></span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2 mb-1">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${score}%` }} />
      </div>
      <p className="text-xs text-gray-400 italic">{rationale}</p>
    </div>
  );
}

function complexityBadge(c: string) {
  const map: Record<string, string> = {
    small:  'bg-green-100 text-green-700',
    medium: 'bg-amber-100 text-amber-700',
    large:  'bg-red-100 text-red-700',
  };
  return map[c] ?? 'bg-gray-100 text-gray-700';
}

interface Props {
  username: string;
  onBack: () => void;
}

export default function ScoreDetail({ username, onBack }: Props) {
  const [scores, setScores] = useState<Score[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/scores/${username}`)
      .then(r => r.json())
      .then(data => { setScores(data); setLoading(false); });
  }, [username]);

  if (loading) {
    return <div className="text-center py-20 text-gray-400">Loading scores…</div>;
  }

  return (
    <div>
      <button
        onClick={onBack}
        className="mb-6 text-sm text-indigo-600 hover:underline flex items-center gap-1"
      >
        ← Back to leaderboard
      </button>
      <h2 className="text-2xl font-bold text-gray-800 mb-1">{username}</h2>
      <p className="text-sm text-gray-400 mb-6">{scores.length} scored MR{scores.length !== 1 ? 's' : ''}</p>

      {scores.length === 0 ? (
        <div className="text-gray-400 text-center py-10">No MR scores found.</div>
      ) : (
        <div className="space-y-5">
          {scores.map(s => (
            <div key={s.id} className="border border-gray-200 rounded-xl p-5 shadow-sm bg-white">
              <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                  <a
                    href={`https://gitlab.com/${s.project_id}/-/merge_requests/${s.mr_iid}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-semibold text-gray-800 hover:text-indigo-600 transition-colors"
                  >
                    MR !{s.mr_iid} — {s.title}
                  </a>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(s.scored_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}
                    &nbsp;·&nbsp;{s.project_id}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-2xl font-bold text-indigo-600">{s.total_score.toFixed(0)}<span className="text-sm text-gray-400">/100</span></div>
                  <div className="text-sm font-semibold text-gray-700">{s.points} pts</div>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${complexityBadge(s.complexity)}`}>
                    {s.complexity} ×{s.complexity_multiplier}
                  </span>
                  {s.streak_eligible && (
                    <div className="mt-1 text-xs text-amber-600 font-medium">🔥 streak eligible</div>
                  )}
                </div>
              </div>
              <div>
                {DIMENSIONS.map(d => (
                  <DimensionBar
                    key={d.key}
                    score={dimScore(s.dimensions[d.key])}
                    label={d.label}
                    weight={d.weight}
                    rationale={dimRationale(s.dimensions[d.key])}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
