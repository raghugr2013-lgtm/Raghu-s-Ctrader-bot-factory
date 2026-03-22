import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, BarChart, Bar, ReferenceLine, Legend,
  ComposedChart
} from 'recharts';
import { cn } from '@/lib/utils';

// Dark theme color palette
const COLORS = {
  primary: '#10b981',     // emerald-500
  secondary: '#3b82f6',   // blue-500
  tertiary: '#a855f7',    // purple-500
  warning: '#f59e0b',     // amber-500
  danger: '#ef4444',      // red-500
  muted: '#71717a',       // zinc-500
  gridLine: '#27272a',    // zinc-800
  background: '#0a0a0a',
  text: '#a1a1aa',        // zinc-400
};

// Custom Tooltip Component
const CustomTooltip = ({ active, payload, label, prefix = '', suffix = '' }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#18181B] border border-white/10 p-2 rounded-sm shadow-lg">
        <p className="text-[10px] text-zinc-500 font-mono mb-1">{label}</p>
        {payload.map((entry, index) => (
          <p key={index} className="text-xs font-mono" style={{ color: entry.color }}>
            {entry.name}: {prefix}{typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}{suffix}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

/**
 * Equity Curve Chart
 * Shows backtest equity curve with optional Monte Carlo median overlay
 */
export function EquityCurveChart({ 
  backtestData = [], 
  monteCarloMedian = [],
  height = 200,
  showMonteCarlo = true 
}) {
  // Combine data for the chart
  const combinedData = backtestData.map((point, index) => ({
    index: index + 1,
    backtest: point.balance || point.equity || point.value,
    monteCarlo: monteCarloMedian[index]?.balance || monteCarloMedian[index]?.equity || null
  }));

  return (
    <div className="w-full" style={{ height }}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Equity Curve</h4>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-[9px] text-zinc-500 font-mono">Backtest</span>
          </div>
          {showMonteCarlo && (
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              <span className="text-[9px] text-zinc-500 font-mono">MC Median</span>
            </div>
          )}
        </div>
      </div>
      <ResponsiveContainer width="100%" height="90%">
        <LineChart data={combinedData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.gridLine} />
          <XAxis 
            dataKey="index" 
            tick={{ fill: COLORS.text, fontSize: 9 }}
            tickLine={{ stroke: COLORS.gridLine }}
            axisLine={{ stroke: COLORS.gridLine }}
            tickFormatter={(value) => `#${value}`}
          />
          <YAxis 
            tick={{ fill: COLORS.text, fontSize: 9 }}
            tickLine={{ stroke: COLORS.gridLine }}
            axisLine={{ stroke: COLORS.gridLine }}
            tickFormatter={(value) => `$${(value/1000).toFixed(0)}k`}
          />
          <Tooltip content={<CustomTooltip prefix="$" />} />
          <Line 
            type="monotone" 
            dataKey="backtest" 
            stroke={COLORS.primary}
            strokeWidth={2}
            dot={false}
            name="Backtest"
          />
          {showMonteCarlo && (
            <Line 
              type="monotone" 
              dataKey="monteCarlo" 
              stroke={COLORS.secondary}
              strokeWidth={1.5}
              strokeDasharray="4 2"
              dot={false}
              name="MC Median"
            />
          )}
          <ReferenceLine y={10000} stroke={COLORS.muted} strokeDasharray="3 3" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Drawdown Curve Chart
 * Shows drawdown percentage over time
 */
export function DrawdownChart({ 
  drawdownData = [], 
  maxDrawdown = 0,
  height = 160 
}) {
  const chartData = drawdownData.map((point, index) => ({
    index: index + 1,
    drawdown: point.drawdown || point.value || point,
  }));

  // Add max drawdown reference
  const maxDD = maxDrawdown || Math.max(...chartData.map(d => Math.abs(d.drawdown)));

  return (
    <div className="w-full" style={{ height }}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Drawdown Curve</h4>
        <span className="text-[9px] font-mono text-red-400">Max DD: {maxDD.toFixed(1)}%</span>
      </div>
      <ResponsiveContainer width="100%" height="90%">
        <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.gridLine} />
          <XAxis 
            dataKey="index"
            tick={{ fill: COLORS.text, fontSize: 9 }}
            tickLine={{ stroke: COLORS.gridLine }}
            axisLine={{ stroke: COLORS.gridLine }}
          />
          <YAxis 
            tick={{ fill: COLORS.text, fontSize: 9 }}
            tickLine={{ stroke: COLORS.gridLine }}
            axisLine={{ stroke: COLORS.gridLine }}
            tickFormatter={(value) => `${value.toFixed(0)}%`}
            domain={[0, 'auto']}
          />
          <Tooltip content={<CustomTooltip suffix="%" />} />
          <ReferenceLine y={10} stroke={COLORS.warning} strokeDasharray="3 3" label={{ value: '10%', position: 'right', fill: COLORS.warning, fontSize: 9 }} />
          <Area 
            type="monotone" 
            dataKey="drawdown"
            stroke={COLORS.danger}
            fill={COLORS.danger}
            fillOpacity={0.2}
            strokeWidth={1.5}
            name="Drawdown"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Monte Carlo Distribution Histogram
 * Shows distribution of final returns across simulations
 */
export function MonteCarloHistogram({ 
  distributionData = [],
  percentiles = { p5: 0, p50: 0, p95: 0 },
  height = 180
}) {
  // Group data into histogram bins
  const binCount = 20;
  const values = distributionData.map(d => d.finalReturn || d.value || d);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const binWidth = (max - min) / binCount;

  const histogramData = [];
  for (let i = 0; i < binCount; i++) {
    const binStart = min + (i * binWidth);
    const binEnd = binStart + binWidth;
    const count = values.filter(v => v >= binStart && v < binEnd).length;
    histogramData.push({
      bin: `${binStart.toFixed(0)}`,
      binLabel: `${binStart.toFixed(0)}% - ${binEnd.toFixed(0)}%`,
      count,
      binStart,
      isPositive: binStart >= 0
    });
  }

  return (
    <div className="w-full" style={{ height }}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Monte Carlo Distribution</h4>
        <div className="flex items-center gap-3 text-[9px] font-mono">
          <span className="text-red-400">P5: {percentiles.p5?.toFixed(1)}%</span>
          <span className="text-amber-400">P50: {percentiles.p50?.toFixed(1)}%</span>
          <span className="text-emerald-400">P95: {percentiles.p95?.toFixed(1)}%</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height="90%">
        <BarChart data={histogramData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.gridLine} vertical={false} />
          <XAxis 
            dataKey="bin"
            tick={{ fill: COLORS.text, fontSize: 8 }}
            tickLine={{ stroke: COLORS.gridLine }}
            axisLine={{ stroke: COLORS.gridLine }}
            interval={2}
            tickFormatter={(value) => `${value}%`}
          />
          <YAxis 
            tick={{ fill: COLORS.text, fontSize: 9 }}
            tickLine={{ stroke: COLORS.gridLine }}
            axisLine={{ stroke: COLORS.gridLine }}
            tickFormatter={(value) => value}
          />
          <Tooltip 
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;
                return (
                  <div className="bg-[#18181B] border border-white/10 p-2 rounded-sm shadow-lg">
                    <p className="text-[10px] text-zinc-500 font-mono">{data.binLabel}</p>
                    <p className="text-xs font-mono text-zinc-300">{data.count} simulations</p>
                  </div>
                );
              }
              return null;
            }} 
          />
          <ReferenceLine x="0" stroke={COLORS.muted} strokeDasharray="3 3" />
          <Bar 
            dataKey="count"
            fill={COLORS.primary}
            radius={[2, 2, 0, 0]}
            name="Count"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Combined Validation Chart Panel
 * Displays all charts in a grid layout
 */
export function ValidationChartPanel({ 
  equityCurve = [],
  drawdownCurve = [],
  monteCarloDistribution = [],
  monteCarloMedian = [],
  maxDrawdown = 0,
  percentiles = { p5: 0, p50: 0, p95: 0 }
}) {
  // Generate sample data if not provided
  const hasEquityData = equityCurve.length > 0;
  const hasDrawdownData = drawdownCurve.length > 0;
  const hasMCData = monteCarloDistribution.length > 0;

  const sampleEquityData = hasEquityData ? equityCurve : 
    Array.from({ length: 50 }, (_, i) => ({
      balance: 10000 + (Math.random() * 2000 - 500) * (i / 50) + (i * 50)
    }));

  const sampleDrawdownData = hasDrawdownData ? drawdownCurve :
    Array.from({ length: 50 }, (_, i) => ({
      drawdown: Math.abs(Math.sin(i / 10) * 8 + Math.random() * 3)
    }));

  const sampleMCData = hasMCData ? monteCarloDistribution :
    Array.from({ length: 1000 }, () => ({
      finalReturn: (Math.random() * 80 - 20) + Math.random() * 10
    }));

  const sampleMCMedian = monteCarloMedian.length > 0 ? monteCarloMedian :
    Array.from({ length: 50 }, (_, i) => ({
      balance: 10000 + (i * 40) + Math.random() * 300
    }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Equity Curve */}
        <div className="bg-[#0F0F10] border border-white/5 p-3 rounded-sm" data-testid="equity-curve-chart">
          <EquityCurveChart 
            backtestData={sampleEquityData}
            monteCarloMedian={sampleMCMedian}
            height={180}
          />
        </div>

        {/* Drawdown Curve */}
        <div className="bg-[#0F0F10] border border-white/5 p-3 rounded-sm" data-testid="drawdown-chart">
          <DrawdownChart 
            drawdownData={sampleDrawdownData}
            maxDrawdown={maxDrawdown || 12.5}
            height={180}
          />
        </div>
      </div>

      {/* Monte Carlo Distribution */}
      <div className="bg-[#0F0F10] border border-white/5 p-3 rounded-sm" data-testid="montecarlo-histogram">
        <MonteCarloHistogram 
          distributionData={sampleMCData}
          percentiles={percentiles.p5 ? percentiles : { p5: -15, p50: 22, p95: 58 }}
          height={160}
        />
      </div>
    </div>
  );
}

/**
 * Mini Chart for Dashboard Cards
 */
export function MiniEquityChart({ data = [], height = 50, color = COLORS.primary }) {
  const chartData = data.length > 0 ? data.map((v, i) => ({ index: i, value: v })) :
    Array.from({ length: 20 }, (_, i) => ({ index: i, value: 100 + Math.random() * 20 + i }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
        <Line 
          type="monotone" 
          dataKey="value" 
          stroke={color}
          strokeWidth={1.5}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default {
  EquityCurveChart,
  DrawdownChart,
  MonteCarloHistogram,
  ValidationChartPanel,
  MiniEquityChart,
  COLORS
};
