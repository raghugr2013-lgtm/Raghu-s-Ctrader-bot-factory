import { Badge } from '@/components/ui/badge';

export function MonteCarloViz({ mcResult }) {
  if (!mcResult) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-zinc-500 font-mono" data-testid="mc-empty">
        Run Monte Carlo to see risk analysis
      </div>
    );
  }

  const grade = mcResult.grade;
  const gradeColor = { S: 'text-amber-300', A: 'text-emerald-400', B: 'text-blue-400', C: 'text-yellow-400', D: 'text-orange-400', F: 'text-red-400' }[grade] || 'text-zinc-400';

  return (
    <div className="space-y-3" data-testid="monte-carlo-viz">
      {/* Score header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`text-3xl font-extrabold ${gradeColor}`} style={{ fontFamily: 'Barlow Condensed, sans-serif' }} data-testid="mc-grade">{grade}</span>
          <div>
            <p className="text-xs font-mono font-bold text-zinc-300">{mcResult.robustness_score}/100</p>
            <p className="text-[10px] font-mono text-zinc-500">{mcResult.risk_level} Risk</p>
          </div>
        </div>
        <Badge variant="outline" className={`text-[9px] px-2 py-0 h-5 font-mono ${mcResult.robustness_score >= 70 ? 'border-emerald-500/40 text-emerald-400' : 'border-red-500/40 text-red-400'}`}>
          {mcResult.robustness_score >= 70 ? 'ROBUST' : 'WEAK'}
        </Badge>
      </div>

      {/* Key metrics grid */}
      <div className="grid grid-cols-2 gap-2" data-testid="mc-metrics">
        <MetricBox label="Profit Probability" value={`${mcResult.profit_probability}%`} good={mcResult.profit_probability >= 70} />
        <MetricBox label="Ruin Probability" value={`${mcResult.ruin_probability}%`} good={mcResult.ruin_probability < 5} invert />
        <MetricBox label="Expected Return" value={`${mcResult.expected_return_percent}%`} good={mcResult.expected_return_percent > 0} />
        <MetricBox label="Worst Drawdown" value={`${mcResult.worst_case_drawdown}%`} good={mcResult.worst_case_drawdown < 20} invert />
        <MetricBox label="Avg Drawdown" value={`${mcResult.average_drawdown}%`} good={mcResult.average_drawdown < 10} invert />
        <MetricBox label="Simulations" value={mcResult.num_simulations?.toLocaleString()} neutral />
      </div>

      {/* Confidence intervals */}
      <div className="bg-[#0F0F10] border border-white/5 p-2 space-y-1.5">
        <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">95% Confidence Intervals</p>
        <CIBar label="Balance" lo={mcResult.balance_ci_lower} hi={mcResult.balance_ci_upper} format={v => `$${v?.toLocaleString()}`} />
        <CIBar label="Return" lo={mcResult.return_ci_lower} hi={mcResult.return_ci_upper} format={v => `${v?.toFixed(2)}%`} />
      </div>

      {/* Insights */}
      {(mcResult.strengths?.length > 0 || mcResult.weaknesses?.length > 0) && (
        <div className="space-y-1 pt-1 border-t border-white/5">
          {mcResult.strengths?.map((s, i) => (
            <p key={`s-${i}`} className="text-[10px] text-emerald-400/80 font-mono">+ {s}</p>
          ))}
          {mcResult.weaknesses?.map((w, i) => (
            <p key={`w-${i}`} className="text-[10px] text-red-400/80 font-mono">- {w}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function MetricBox({ label, value, good, invert, neutral }) {
  let color = 'text-zinc-300';
  if (!neutral) {
    const positive = invert ? !good : good;
    color = positive ? 'text-emerald-400' : 'text-red-400';
  }
  return (
    <div className="bg-[#0F0F10] border border-white/5 px-2 py-1.5">
      <p className="text-[9px] font-mono uppercase tracking-widest text-zinc-600">{label}</p>
      <p className={`text-sm font-bold font-mono ${color}`}>{value}</p>
    </div>
  );
}

function CIBar({ label, lo, hi, format }) {
  return (
    <div className="flex items-center gap-2 text-[10px] font-mono">
      <span className="text-zinc-500 w-14 shrink-0">{label}</span>
      <span className="text-red-400/70">{format(lo)}</span>
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full relative mx-1">
        <div className="absolute inset-y-0 left-[10%] right-[10%] bg-gradient-to-r from-red-500/40 via-blue-500/40 to-emerald-500/40 rounded-full" />
      </div>
      <span className="text-emerald-400/70">{format(hi)}</span>
    </div>
  );
}
