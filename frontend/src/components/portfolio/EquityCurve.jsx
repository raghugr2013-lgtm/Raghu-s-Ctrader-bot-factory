import { useMemo } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#1a1a1a] border border-white/10 px-3 py-2 text-xs font-mono">
      <p className="text-zinc-500 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
        </p>
      ))}
    </div>
  );
}

export function EquityCurve({ backtestResult }) {
  const data = useMemo(() => {
    if (!backtestResult?.equity_curve) return [];
    return backtestResult.equity_curve.map((pt, i) => ({
      idx: i,
      balance: pt.balance,
      drawdown: -pt.drawdown_percent,  // Invert for visual
    }));
  }, [backtestResult]);

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-zinc-500 font-mono" data-testid="equity-empty">
        Run portfolio backtest to see equity curve
      </div>
    );
  }

  const metrics = backtestResult?.metrics;

  return (
    <div className="h-full flex flex-col" data-testid="equity-curve">
      {/* Summary row */}
      {metrics && (
        <div className="flex gap-4 text-[10px] font-mono px-1 pb-2 flex-wrap">
          <div><span className="text-zinc-500">P&L </span><span className={metrics.net_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}>${metrics.net_profit.toLocaleString()}</span></div>
          <div><span className="text-zinc-500">Return </span><span className="text-blue-400">{metrics.total_return_percent}%</span></div>
          <div><span className="text-zinc-500">Sharpe </span><span className="text-cyan-400">{metrics.sharpe_ratio}</span></div>
          <div><span className="text-zinc-500">Max DD </span><span className="text-red-400">{metrics.max_drawdown_percent}%</span></div>
          <div><span className="text-zinc-500">Win </span><span className="text-yellow-400">{metrics.win_rate}%</span></div>
          <div><span className="text-zinc-500">Grade </span><span className="text-amber-400 font-bold">{backtestResult.grade}</span></div>
        </div>
      )}

      {/* Charts */}
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="60%">
          <ComposedChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="idx" hide />
            <YAxis
              domain={['auto', 'auto']}
              tick={{ fontSize: 9, fill: '#52525B', fontFamily: 'monospace' }}
              tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
              width={45}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={backtestResult?.initial_balance} stroke="rgba(255,255,255,0.1)" strokeDasharray="3 3" />
            <Area type="monotone" dataKey="balance" stroke="#3b82f6" fill="rgba(59,130,246,0.1)" strokeWidth={1.5} name="Balance" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
        <ResponsiveContainer width="100%" height="40%">
          <ComposedChart data={data} margin={{ top: 0, right: 10, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="idx" hide />
            <YAxis
              domain={['auto', 0]}
              tick={{ fontSize: 9, fill: '#52525B', fontFamily: 'monospace' }}
              tickFormatter={v => `${v.toFixed(1)}%`}
              width={45}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" />
            <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="rgba(239,68,68,0.15)" strokeWidth={1} name="Drawdown %" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
