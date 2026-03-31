import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  TrendingUp, TrendingDown, Activity, Zap, Target, Play,
  Loader2, CheckCircle2, BarChart3, ArrowRight, Settings
} from 'lucide-react';

const BACKEND_URL = "http://localhost:8001";
const API = `${BACKEND_URL}/api`;

const TEMPLATE_ICONS = {
  mean_reversion: TrendingDown,
  trend_following: TrendingUp,
  breakout: Zap,
  hybrid: Activity
};

const TEMPLATE_COLORS = {
  mean_reversion: 'from-blue-500/20 to-cyan-500/20 border-blue-500/40',
  trend_following: 'from-emerald-500/20 to-green-500/20 border-emerald-500/40',
  breakout: 'from-amber-500/20 to-orange-500/20 border-amber-500/40',
  hybrid: 'from-purple-500/20 to-pink-500/20 border-purple-500/40'
};

const BADGE_COLORS = {
  mean_reversion: 'border-blue-500/50 text-blue-400',
  trend_following: 'border-emerald-500/50 text-emerald-400',
  breakout: 'border-amber-500/50 text-amber-400',
  hybrid: 'border-purple-500/50 text-purple-400'
};

export default function StrategyTemplateSelector({ symbol = 'EURUSD', timeframe = '1h', onResultsReceived }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/strategy/templates`);
      if (response.data.success) {
        setTemplates(response.data.templates);
      }
    } catch (error) {
      console.error('Failed to load templates:', error);
      toast.error('Failed to load strategy templates');
    } finally {
      setLoading(false);
    }
  };

  const runBacktest = async (templateId) => {
    setRunning(true);
    setSelectedTemplate(templateId);
    setResults(null);

    try {
      const response = await axios.post(`${API}/strategy/templates/${templateId}/backtest`, {
        template_id: templateId,
        symbol: symbol,
        timeframe: timeframe,
        backtest_days: 365,
        initial_balance: 10000.0
      }, { timeout: 120000 });

      if (response.data.success) {
        setResults(response.data);
        toast.success(`Backtest complete: ${response.data.metrics.total_trades} trades`);
        
        if (onResultsReceived) {
          onResultsReceived(response.data);
        }
      }
    } catch (error) {
      const msg = error.response?.data?.detail || error.message;
      toast.error(`Backtest failed: ${msg}`);
      setResults(null);
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="strategy-template-selector">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Target className="w-4 h-4 text-amber-400" />
            Strategy Templates
          </h3>
          <p className="text-xs text-zinc-500 mt-0.5">Select a pre-built strategy to backtest with real data</p>
        </div>
        <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
          {symbol} / {timeframe.toUpperCase()}
        </Badge>
      </div>

      {/* Templates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {templates.map((template) => {
          const Icon = TEMPLATE_ICONS[template.id] || Activity;
          const colorClass = TEMPLATE_COLORS[template.id] || TEMPLATE_COLORS.hybrid;
          const badgeClass = BADGE_COLORS[template.id] || BADGE_COLORS.hybrid;
          const isSelected = selectedTemplate === template.id;
          const isRunningThis = running && isSelected;

          return (
            <div
              key={template.id}
              className={`relative rounded-lg p-3 border bg-gradient-to-br transition-all cursor-pointer
                ${colorClass}
                ${isSelected ? 'ring-2 ring-white/30' : 'hover:border-white/30'}
              `}
              onClick={() => !running && setSelectedTemplate(template.id)}
              data-testid={`template-${template.id}`}
            >
              {/* Template Header */}
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded bg-black/30">
                    <Icon className="w-4 h-4 text-white" />
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-white">{template.name}</h4>
                    <p className="text-[10px] text-zinc-400">{template.best_for}</p>
                  </div>
                </div>
                <Badge variant="outline" className={`text-[9px] ${badgeClass}`}>
                  {template.risk_per_trade}
                </Badge>
              </div>

              {/* Description */}
              <p className="text-xs text-zinc-400 mb-3 line-clamp-2">{template.description}</p>

              {/* Run Button */}
              <Button
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  runBacktest(template.id);
                }}
                disabled={running}
                className={`w-full h-7 text-xs font-semibold
                  ${isSelected 
                    ? 'bg-white text-black hover:bg-zinc-200' 
                    : 'bg-white/10 text-white hover:bg-white/20'}
                `}
                data-testid={`run-${template.id}`}
              >
                {isRunningThis ? (
                  <>
                    <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="w-3 h-3 mr-1.5" />
                    Run Backtest
                  </>
                )}
              </Button>
            </div>
          );
        })}
      </div>

      {/* Results Panel */}
      {results && (
        <div className="bg-[#0A0A0B] border border-white/10 rounded-lg p-4 mt-4" data-testid="backtest-results">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <h4 className="text-sm font-semibold text-white">{results.template.name} Results</h4>
            </div>
            <Badge 
              variant="outline" 
              className={`text-xs ${
                results.score.grade === 'A' || results.score.grade === 'B' 
                  ? 'border-emerald-500/50 text-emerald-400' 
                  : results.score.grade === 'C' 
                    ? 'border-amber-500/50 text-amber-400'
                    : 'border-red-500/50 text-red-400'
              }`}
            >
              Grade: {results.score.grade}
            </Badge>
          </div>

          {/* Backtest Info */}
          <div className="text-xs text-zinc-500 mb-3">
            <span className="text-amber-400">REAL DATA</span> • {results.backtest.candles_used.toLocaleString()} candles • {results.backtest.date_range}
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-4 gap-3 mb-3">
            <MetricCard 
              label="Total Trades" 
              value={results.metrics.total_trades} 
              icon={BarChart3}
            />
            <MetricCard 
              label="Win Rate" 
              value={`${results.metrics.win_rate}%`}
              positive={results.metrics.win_rate > 50}
            />
            <MetricCard 
              label="Profit Factor" 
              value={results.metrics.profit_factor.toFixed(2)}
              positive={results.metrics.profit_factor > 1}
              highlight
            />
            <MetricCard 
              label="Max DD" 
              value={`${results.metrics.max_drawdown_percent.toFixed(1)}%`}
              positive={results.metrics.max_drawdown_percent < 20}
            />
          </div>

          {/* P&L Summary */}
          <div className="flex items-center justify-between p-2 rounded bg-black/30">
            <span className="text-xs text-zinc-400">Net Profit</span>
            <span className={`text-sm font-bold ${results.metrics.net_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {results.metrics.net_profit >= 0 ? '+' : ''}${results.metrics.net_profit.toFixed(2)}
            </span>
          </div>

          {/* Equity Summary */}
          <div className="mt-3 pt-3 border-t border-white/10">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Equity Curve</span>
              <span className="text-zinc-400">
                ${results.equity_curve_summary.start_equity.toFixed(0)} 
                <ArrowRight className="w-3 h-3 inline mx-1" />
                ${results.equity_curve_summary.end_equity.toFixed(0)}
                <span className="text-zinc-600 ml-1">
                  (Peak: ${results.equity_curve_summary.peak_equity.toFixed(0)})
                </span>
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, icon: Icon, positive, highlight }) {
  return (
    <div className={`p-2 rounded ${highlight ? 'bg-amber-500/10 border border-amber-500/30' : 'bg-white/5'}`}>
      <div className="text-[10px] text-zinc-500 mb-0.5">{label}</div>
      <div className={`text-sm font-semibold ${
        highlight ? 'text-amber-400' :
        positive === true ? 'text-emerald-400' :
        positive === false ? 'text-red-400' :
        'text-white'
      }`}>
        {value}
      </div>
    </div>
  );
}
