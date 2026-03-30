import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'];

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-[#1a1a1a] border border-white/10 px-3 py-2 text-xs font-mono">
      <p className="text-zinc-200 font-bold">{d.name}</p>
      <p className="text-zinc-400">{d.value.toFixed(1)}%</p>
    </div>
  );
}

export function AllocationChart({ strategies, allocationResult }) {
  if (!strategies || strategies.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-zinc-500 font-mono" data-testid="allocation-empty">
        Add strategies to see allocation
      </div>
    );
  }

  const data = strategies.map(s => ({
    name: s.name,
    value: s.weight_percent || 0,
  }));

  return (
    <div className="h-full flex flex-col" data-testid="allocation-chart">
      <ResponsiveContainer width="100%" height="70%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius="45%"
            outerRadius="75%"
            paddingAngle={2}
            dataKey="value"
            stroke="none"
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex-1 overflow-y-auto space-y-1 px-1" data-testid="allocation-legend">
        {data.map((d, i) => (
          <div key={d.name} className="flex items-center justify-between text-[10px] font-mono">
            <div className="flex items-center gap-1.5 min-w-0">
              <div className="w-2 h-2 shrink-0 rounded-sm" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
              <span className="text-zinc-300 truncate">{d.name}</span>
            </div>
            <span className="text-zinc-400 ml-2 shrink-0">{d.value.toFixed(1)}%</span>
          </div>
        ))}
      </div>

      {/* Method badge */}
      {allocationResult && (
        <div className="pt-1 border-t border-white/5 mt-1">
          <p className="text-[9px] font-mono text-zinc-600 uppercase text-center">
            Method: {allocationResult.method?.replace(/_/g, ' ')}
          </p>
        </div>
      )}
    </div>
  );
}
