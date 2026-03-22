import { useMemo } from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

function getCellColor(val) {
  if (val >= 0.7) return 'bg-red-500/80 text-white';
  if (val >= 0.4) return 'bg-orange-500/50 text-white';
  if (val >= 0.2) return 'bg-yellow-500/30 text-zinc-200';
  if (val >= -0.2) return 'bg-zinc-700/40 text-zinc-300';
  if (val >= -0.4) return 'bg-cyan-500/30 text-zinc-200';
  if (val >= -0.7) return 'bg-blue-500/50 text-white';
  return 'bg-blue-600/80 text-white';
}

export function CorrelationHeatmap({ correlationResult, strategies }) {
  const names = useMemo(() => (strategies || []).map(s => s.name), [strategies]);
  const matrix = correlationResult?.matrix || {};

  if (!correlationResult || names.length < 2) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-zinc-500 font-mono" data-testid="correlation-empty">
        Run correlation analysis with 2+ strategies
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="correlation-heatmap">
      {/* Stats bar */}
      <div className="flex gap-4 text-[10px] font-mono">
        <div>
          <span className="text-zinc-500 uppercase">Avg Correlation</span>
          <span className={`ml-2 font-bold ${correlationResult.average_correlation > 0.5 ? 'text-red-400' : correlationResult.average_correlation < -0.1 ? 'text-emerald-400' : 'text-zinc-300'}`}>
            {correlationResult.average_correlation?.toFixed(3)}
          </span>
        </div>
        <div>
          <span className="text-zinc-500 uppercase">Diversification</span>
          <span className={`ml-2 font-bold ${correlationResult.diversification_score >= 70 ? 'text-emerald-400' : correlationResult.diversification_score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
            {correlationResult.diversification_score?.toFixed(0)}/100
          </span>
        </div>
      </div>

      {/* Matrix */}
      <TooltipProvider delayDuration={100}>
        <div className="overflow-auto">
          <table className="w-full border-collapse" data-testid="correlation-matrix">
            <thead>
              <tr>
                <th className="text-[9px] font-mono text-zinc-600 p-1 text-left w-20" />
                {names.map(n => (
                  <th key={n} className="text-[9px] font-mono text-zinc-500 p-1 text-center truncate max-w-[80px]">{n}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {names.map(rowName => (
                <tr key={rowName}>
                  <td className="text-[9px] font-mono text-zinc-500 p-1 truncate max-w-[80px]">{rowName}</td>
                  {names.map(colName => {
                    const val = rowName === colName ? 1.0 : (matrix[rowName]?.[colName] ?? 0);
                    const isDiag = rowName === colName;
                    return (
                      <Tooltip key={colName}>
                        <TooltipTrigger asChild>
                          <td
                            className={`text-center text-[10px] font-mono font-bold p-2 cursor-default transition-opacity hover:opacity-80 ${isDiag ? 'bg-zinc-800 text-zinc-400' : getCellColor(val)}`}
                            data-testid={`cell-${rowName}-${colName}`}
                          >
                            {val.toFixed(2)}
                          </td>
                        </TooltipTrigger>
                        <TooltipContent className="bg-[#1a1a1a] border-white/10 text-xs font-mono">
                          <p>{rowName} / {colName}</p>
                          <p className="text-zinc-400">r = {val.toFixed(4)}</p>
                        </TooltipContent>
                      </Tooltip>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </TooltipProvider>

      {/* Legend */}
      <div className="flex items-center gap-1 text-[9px] font-mono text-zinc-500">
        <span>-1</span>
        <div className="flex h-3 flex-1">
          <div className="flex-1 bg-blue-600/80" />
          <div className="flex-1 bg-blue-500/50" />
          <div className="flex-1 bg-cyan-500/30" />
          <div className="flex-1 bg-zinc-700/40" />
          <div className="flex-1 bg-yellow-500/30" />
          <div className="flex-1 bg-orange-500/50" />
          <div className="flex-1 bg-red-500/80" />
        </div>
        <span>+1</span>
      </div>

      {/* Recs */}
      {correlationResult.recommendations?.length > 0 && (
        <div className="space-y-0.5 pt-1 border-t border-white/5">
          {correlationResult.recommendations.map((r, i) => (
            <p key={i} className="text-[10px] text-zinc-400 font-mono">- {r}</p>
          ))}
        </div>
      )}
    </div>
  );
}
