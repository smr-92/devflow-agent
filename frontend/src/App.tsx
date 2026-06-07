import { useState } from 'react';
import Leaderboard from './components/Leaderboard';
import ScoreDetail from './components/ScoreDetail';
import './index.css';

export default function App() {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">D</div>
        <span className="font-semibold text-gray-800 text-lg">DevFlow</span>
        <span className="text-gray-300 mx-1">|</span>
        <span className="text-gray-500 text-sm">Developer Dashboard</span>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {selected === null ? (
          <>
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-gray-900">Leaderboard</h1>
              <p className="text-sm text-gray-500 mt-1">Click a developer to see their MR scores</p>
            </div>
            <Leaderboard onSelect={setSelected} />
          </>
        ) : (
          <ScoreDetail username={selected} onBack={() => setSelected(null)} />
        )}
      </main>
    </div>
  );
}
