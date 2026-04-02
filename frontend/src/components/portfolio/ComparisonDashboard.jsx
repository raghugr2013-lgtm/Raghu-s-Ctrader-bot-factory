import { useState, useCallback } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Loader2, TrendingUp } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const METHODS = [
  { value: 'equal_weight', label: 'Equal Weight' },
  { value: 'risk_parity', label: 'Risk Parity' },
  { value: 'max_sharpe', label: 'Max Sharpe' },
  { value: 'min_variance', label: 'Min Variance' },
  { value: 'max_diversification', label: 'Max Diversif.' },
];

export function ComparisonDashboard({ portfolio, onRefresh }) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const runComparison = useCallback(async () => {
    if (!portfolio?.id) return;
    setLoading(true);
    setResults([]);
    const out = [];

    for (const m of METHODS) {
      try {
        const res = await axios.post(`${API}/portfolio/${portfolio.id}/optimize`, { method: m.value });
        out.push({ method: m.label, key: m.value, ...res.data });
      } catch (e) {
        out.push({ method: m.label, key: m.value, error: true });
      }
    }

    setResults(out);
    setLoading(false);
    toast.success('Comparison complete');

    // Apply best Sharpe to portfolio
    const best = out.filter(r => !r.error).sort((a, b) => (b.expected_sharpe || 0) - (a.expected_sharpe || 0))[0];
    if (best) {
      onRefresh(portfolio.id);
    }
  }, [portfolio, onRefresh]);

  const hasMethods = results.length > 0;
  const bestSharpe = hasMethods ? results.filter(r => !r.error).sort((a, b) => (b.expected_sharpe || 0) - (a.expected_sharpe || 0))[0] : null;

  return (
    <div className="space-y-3" data-testid="comparison-dashboard">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Allocation Comparison</p>
        <Button
          onClick={runComparison}
          disabled={loading || (portfolio?.strategies?.length || 0) < 2}
          className="bg-violet-700 hover:bg-violet-600 text-white font-mono uppercase text-[10px] h-6 px-3"
          data-testid="run-comparison-btn"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <TrendingUp className="w-3 h-3 mr-1" />}
          COMPARE ALL
        </Button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono py-4 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> Running 5 optimization methods...
        </div>
      )}

      {hasMethods && (
        <>
          {/* Metrics Table */}
          <div className="overflow-x-auto" data-testid="comparison-table">
            <table className="w-full text-[10px] font-mono border-collapse">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-1.5 px-2 text-zinc-500 uppercase">Method</th>
                  <th className="text-right py-1.5 px-2 text-zinc-500 uppercase">Return</th>
                  <th className="text-right py-1.5 px-2 text-zinc-500 uppercase">Volatility</th>
                  <th className="text-right py-1.5 px-2 text-zinc-500 uppercase">Sharpe</th>
                  <th className="text-right py-1.5 px-2 text-zinc-500 uppercase">vs Equal</th>
                </tr>
              </thead>
              <tbody>
                {results.map(r => {
                  if (r.error) return (
                    <tr key={r.key} className="border-b border-white/5">
                      <td className="py-1.5 px-2 text-zinc-400">{r.method}</td>
                      <td colSpan={4} className="py-1.5 px-2 text-red-400 text-center">Error</td>
                    </tr>
                  );
                  const isBest = bestSharpe?.key === r.key;
                  return (
                    <tr key={r.key} className={`border-b border-white/5 ${isBest ? 'bg-emerald-500/5' : ''}`} data-testid={`comparison-row-${r.key}`}>
                      <td className="py-1.5 px-2 text-zinc-300">
                        {r.method}
                        {isBest && <Badge variant="outline" className="ml-1.5 text-[8px] border-emerald-500/30 text-emerald-400 px-1 py-0 h-3.5">BEST</Badge>}
                      </td>
                      <td className={`py-1.5 px-2 text-right ${r.expected_return >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{r.expected_return?.toFixed(2)}%</td>
                      <td className="py-1.5 px-2 text-right text-yellow-400">{r.expected_volatility?.toFixed(2)}%</td>
                      <td className="py-1.5 px-2 text-right text-cyan-400 font-bold">{r.expected_sharpe?.toFixed(2)}</td>
                      <td className={`py-1.5 px-2 text-right ${r.improvement_vs_equal > 0 ? 'text-emerald-400' : r.improvement_vs_equal < 0 ? 'text-red-400' : 'text-zinc-500'}`}>
                        {r.improvement_vs_equal > 0 ? '+' : ''}{r.improvement_vs_equal?.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Weight comparison */}
          <div className="space-y-2" data-testid="weight-comparison">
            <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Weight Distribution</p>
            {results.filter(r => !r.error).map(r => (
              <div key={r.key} className="space-y-1">
                <p className="text-[9px] font-mono text-zinc-500">{r.method}</p>
                <div className="flex h-4 w-full overflow-hidden rounded-sm">
                  {Object.entries(r.weights || {}).map(([name, w], i) => (
                    <div
                      key={name}
                      className="h-full relative group"
                      style={{
                        width: `${w * 100}%`,
                        backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'][i % 5],
                        minWidth: w > 0 ? '2px' : 0,
                      }}
                      title={`${name}: ${(w * 100).toFixed(1)}%`}
                    />
                  ))}
                </div>
              </div>
            ))}
            {/* Legend for bars */}
            <div className="flex gap-3 flex-wrap mt-1">
              {portfolio?.strategies?.map((s, i) => (
                <div key={s.name} className="flex items-center gap-1 text-[9px] font-mono text-zinc-500">
                  <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'][i % 5] }} />
                  {s.name}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
