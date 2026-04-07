import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Leaderboard from '@/components/leaderboard/Leaderboard';
import { Button } from '@/components/ui/button';
import { ChevronLeft, Trophy } from 'lucide-react';

// Mock strategies for testing
const MOCK_STRATEGIES = [
  {
    id: 'strat-001',
    name: 'EMA Crossover Pro',
    market: 'EURUSD',
    timeframe: 'H1',
    strategyType: 'Trend',
    bootstrapSurvival: 93,
    monteCarloSurvival: 91,
    riskOfRuin: 3.5,
    maxDrawdown: 5.2,
    sensitivityScore: 78,
    profitability: 72,
    totalTrades: 245
  },
  {
    id: 'strat-002',
    name: 'RSI Mean Reversion',
    market: 'XAUUSD',
    timeframe: 'M15',
    strategyType: 'Mean Reversion',
    bootstrapSurvival: 85,
    monteCarloSurvival: 82,
    riskOfRuin: 8.2,
    maxDrawdown: 12.5,
    sensitivityScore: 65,
    profitability: 68,
    totalTrades: 412
  },
  {
    id: 'strat-003',
    name: 'Breakout Hunter',
    market: 'US100',
    timeframe: 'H4',
    strategyType: 'Breakout',
    bootstrapSurvival: 78,
    monteCarloSurvival: 75,
    riskOfRuin: 12.1,
    maxDrawdown: 18.3,
    sensitivityScore: 55,
    profitability: 80,
    totalTrades: 156
  },
  {
    id: 'strat-004',
    name: 'Scalper Elite',
    market: 'EURUSD',
    timeframe: 'M5',
    strategyType: 'Scalping',
    bootstrapSurvival: 68,
    monteCarloSurvival: 65,
    riskOfRuin: 22.5,
    maxDrawdown: 25.0,
    sensitivityScore: 45,
    profitability: 55,
    totalTrades: 1250
  },
  {
    id: 'strat-005',
    name: 'Gold Momentum',
    market: 'XAUUSD',
    timeframe: 'H1',
    strategyType: 'Momentum',
    bootstrapSurvival: 88,
    monteCarloSurvival: 86,
    riskOfRuin: 5.8,
    maxDrawdown: 9.2,
    sensitivityScore: 72,
    profitability: 75,
    totalTrades: 189
  },
  {
    id: 'strat-006',
    name: 'Index Swing Trader',
    market: 'US100',
    timeframe: 'D1',
    strategyType: 'Swing',
    bootstrapSurvival: 91,
    monteCarloSurvival: 89,
    riskOfRuin: 4.2,
    maxDrawdown: 7.8,
    sensitivityScore: 82,
    profitability: 70,
    totalTrades: 85
  }
];

export default function LeaderboardPage() {
  const navigate = useNavigate();
  const [selectedStrategy, setSelectedStrategy] = useState(null);

  return (
    <div className="min-h-screen bg-[#050505] p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header with Version */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/')}
              className="text-zinc-400 hover:text-white"
            >
              <ChevronLeft className="w-4 h-4 mr-1" /> Back
            </Button>
            <div className="flex items-center gap-3">
              <Trophy className="w-6 h-6 text-amber-400" />
              <h1 className="text-2xl font-bold text-white">Strategy Leaderboard</h1>
            </div>
          </div>
          <div className="bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded text-xs font-mono font-bold">
            BUILD: v2.1-PROP-SCORE
          </div>
        </div>

        {/* Test Status Banner */}
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 mb-6">
          <p className="text-blue-400 font-mono text-sm">
            ✓ Leaderboard with MOCK DATA - Testing UI components
          </p>
          <p className="text-blue-300/70 font-mono text-xs mt-1">
            Strategies are ranked by Prop Score. Filter by market, type, or prop-ready status.
          </p>
        </div>

        {/* Leaderboard Component */}
        <Leaderboard 
          strategies={MOCK_STRATEGIES}
          onSelectStrategy={(strategy) => {
            setSelectedStrategy(strategy);
            console.log('Selected strategy:', strategy);
          }}
          view="table"
        />

        {/* Selected Strategy Debug */}
        {selectedStrategy && (
          <div className="mt-6 bg-[#0A0A0A] border border-white/5 p-6 rounded-lg">
            <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-300 mb-4">Selected Strategy</h3>
            <pre className="bg-black/50 p-4 rounded text-xs font-mono text-zinc-400 overflow-auto">
              {JSON.stringify(selectedStrategy, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
