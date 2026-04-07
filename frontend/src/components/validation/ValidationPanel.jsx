import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  PropScoreGauge,
  PropScoreBadge,
  ValidationMetricCard,
  StatusBadge,
  PropScoreBreakdown,
  calculatePropScore,
  getDecisionStatus
} from './PropScore';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip as RechartsTooltip, ResponsiveContainer, Area, AreaChart
} from 'recharts';
import {
  Loader2, RefreshCw, Shield, TrendingDown, Activity,
  Gauge, Zap, Target, AlertTriangle, ChevronDown, ChevronUp,
  BarChart3, PieChart, Clock
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

/**
 * Advanced Validation Panel Component
 * Displays comprehensive validation results with professional UI
 */
export default function ValidationPanel({ 
  trades = [], 
  parameters = {},
  sessionId,
  strategyName,
  onValidationComplete,
  compact = false
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [validationResults, setValidationResults] = useState(null);
  const [expanded, setExpanded] = useState(!compact);

  // Run full validation
  const runValidation = async () => {
    if (!trades || trades.length < 10) {
      setError('Need at least 10 trades for validation');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API}/advanced/full-validation`, {
        session_id: sessionId,
        strategy_name: strategyName,
        trades: trades,
        parameters: parameters,
        initial_balance: 10000,
        risk_per_trade_percent: 2.0
      });

      const data = response.data;
      
      // Calculate prop score from results
      const propScoreMetrics = {
        bootstrapSurvival: data.results?.bootstrap?.survival_rate || 0,
        monteCarloSurvival: data.results?.risk_of_ruin?.survival_probability || 0,
        maxDrawdown: 100 - (data.results?.risk_of_ruin?.survival_probability || 0),
        sensitivityScore: data.results?.sensitivity?.robustness_score || 50,
        walkForwardScore: 70, // Default if not available
        profitability: data.results?.bootstrap?.profit_probability || 0,
        challengePassProb: data.results?.bootstrap?.survival_rate / 100 || 0,
        consistencyScore: 100 - (data.results?.sensitivity?.overfitting_risk || 0)
      };

      const propScore = calculatePropScore(propScoreMetrics);
      
      setValidationResults({
        ...data,
        propScore,
        propScoreMetrics,
        decision: getDecisionStatus(propScore)
      });

      if (onValidationComplete) {
        onValidationComplete({ ...data, propScore });
      }
    } catch (err) {
      console.error('Validation error:', err);
      setError(err.response?.data?.detail || 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  // Auto-run validation when trades change
  useEffect(() => {
    if (trades && trades.length >= 10 && !validationResults) {
      // runValidation();
    }
  }, [trades]);

  if (compact && !expanded) {
    return (
      <div 
        className="bg-[#0A0A0A] border border-white/5 p-3 rounded-sm cursor-pointer hover:border-white/10 transition-colors"
        onClick={() => setExpanded(true)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="w-4 h-4 text-violet-400" />
            <span className="text-sm font-mono uppercase tracking-wider text-zinc-300">Validation</span>
          </div>
          <div className="flex items-center gap-2">
            {validationResults ? (
              <PropScoreBadge score={validationResults.propScore} size="sm" />
            ) : (
              <Badge variant="outline" className="text-[10px] text-zinc-500">Not Run</Badge>
            )}
            <ChevronDown className="w-4 h-4 text-zinc-500" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[#0A0A0A] border border-white/5 rounded-sm overflow-hidden">
      {/* Header */}
      <div 
        className={cn(
          "border-b border-white/5 px-4 py-3 bg-[#18181B] flex items-center justify-between",
          compact && "cursor-pointer hover:bg-[#1f1f23]"
        )}
        onClick={compact ? () => setExpanded(false) : undefined}
      >
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-violet-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Advanced Validation</h3>
          {validationResults && (
            <PropScoreBadge score={validationResults.propScore} size="sm" />
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={(e) => { e.stopPropagation(); runValidation(); }}
            disabled={loading || !trades || trades.length < 10}
            className="bg-violet-600/20 hover:bg-violet-600/30 text-violet-400 border border-violet-500/30 font-mono uppercase text-[10px] h-7 px-3"
          >
            {loading ? (
              <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> VALIDATING...</>
            ) : (
              <><RefreshCw className="w-3 h-3 mr-1" /> VALIDATE</>
            )}
          </Button>
          {compact && <ChevronUp className="w-4 h-4 text-zinc-500" />}
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-sm p-3 mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <span className="text-sm text-red-400">{error}</span>
            </div>
          </div>
        )}

        {!validationResults && !loading && (
          <div className="text-center py-8">
            <Shield className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
            <p className="text-sm text-zinc-400 font-mono">Click VALIDATE to run advanced analysis</p>
            <p className="text-xs text-zinc-600 font-mono mt-1">Requires at least 10 trades</p>
          </div>
        )}

        {loading && (
          <div className="text-center py-8">
            <Loader2 className="w-12 h-12 text-violet-400 mx-auto mb-3 animate-spin" />
            <p className="text-sm text-zinc-400 font-mono">Running advanced validation...</p>
            <p className="text-xs text-zinc-600 font-mono mt-1">Bootstrap, Sensitivity, Risk of Ruin, Slippage</p>
          </div>
        )}

        {validationResults && !loading && (
          <div className="space-y-6">
            {/* Decision Banner */}
            <div className={cn(
              "p-4 rounded-sm border flex items-center justify-between",
              validationResults.decision.color === 'emerald' && 'bg-emerald-500/10 border-emerald-500/30',
              validationResults.decision.color === 'amber' && 'bg-amber-500/10 border-amber-500/30',
              validationResults.decision.color === 'red' && 'bg-red-500/10 border-red-500/30'
            )}>
              <div className="flex items-center gap-4">
                <PropScoreGauge score={validationResults.propScore} size={80} />
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {React.createElement(validationResults.decision.icon, {
                      className: cn('w-5 h-5', 
                        validationResults.decision.color === 'emerald' && 'text-emerald-400',
                        validationResults.decision.color === 'amber' && 'text-amber-400',
                        validationResults.decision.color === 'red' && 'text-red-400'
                      )
                    })}
                    <span className={cn(
                      'text-lg font-bold uppercase font-mono',
                      validationResults.decision.color === 'emerald' && 'text-emerald-400',
                      validationResults.decision.color === 'amber' && 'text-amber-400',
                      validationResults.decision.color === 'red' && 'text-red-400'
                    )}>
                      {validationResults.decision.status}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 font-mono">{validationResults.decision.description}</p>
                  <p className="text-[10px] text-zinc-600 font-mono mt-1">Overall Grade: {validationResults.overall_grade}</p>
                </div>
              </div>
              <StatusBadge status={validationResults.is_deployable ? 'PROP SAFE' : 'NOT DEPLOYABLE'} />
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <ValidationMetricCard
                label="Bootstrap Survival"
                value={validationResults.results?.bootstrap?.survival_rate || 0}
                icon={Shield}
                type="survival"
                tooltip="Percentage of bootstrap simulations that survived without hitting ruin threshold"
              />
              <ValidationMetricCard
                label="Sensitivity Score"
                value={validationResults.results?.sensitivity?.robustness_score || 0}
                icon={Gauge}
                type="score"
                tooltip="How stable the strategy is across parameter variations. Higher = more robust"
              />
              <ValidationMetricCard
                label="Risk of Ruin"
                value={validationResults.results?.risk_of_ruin?.ruin_probability || 0}
                icon={AlertTriangle}
                type="ruin"
                tooltip="Probability of account ruin based on trade statistics and position sizing"
              />
              <ValidationMetricCard
                label="Slippage Impact"
                value={validationResults.results?.slippage?.profit_degradation || 0}
                icon={TrendingDown}
                type="drawdown"
                tooltip="Percentage of profit lost due to spread, slippage, and execution costs"
              />
              <ValidationMetricCard
                label="Monte Carlo Survival"
                value={validationResults.results?.risk_of_ruin?.survival_probability || 0}
                icon={Activity}
                type="survival"
                tooltip="Survival probability from Monte Carlo simulation"
              />
              <ValidationMetricCard
                label="Overfitting Risk"
                value={validationResults.results?.sensitivity?.overfitting_risk || 0}
                icon={Target}
                type="ruin"
                tooltip="Risk that strategy is over-optimized on historical data"
              />
            </div>

            {/* Detailed Results Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Bootstrap Results */}
              {validationResults.results?.bootstrap && (
                <div className="bg-[#0F0F10] border border-white/5 p-4 rounded-sm">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Shield className="w-4 h-4 text-blue-400" />
                      <h4 className="text-xs font-mono uppercase tracking-widest text-zinc-400">Bootstrap Analysis</h4>
                    </div>
                    <Badge variant="outline" className={cn(
                      'text-[10px]',
                      validationResults.results.bootstrap.is_robust ? 'text-emerald-400 border-emerald-500/40' : 'text-red-400 border-red-500/40'
                    )}>
                      {validationResults.results.bootstrap.grade}
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Survival Rate</span>
                      <span className="text-emerald-400">{validationResults.results.bootstrap.survival_rate}%</span>
                    </div>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Profit Probability</span>
                      <span className="text-zinc-300">{validationResults.results.bootstrap.profit_probability}%</span>
                    </div>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Mean Return</span>
                      <span className="text-zinc-300">{validationResults.results.bootstrap.mean_return_percent}%</span>
                    </div>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Score</span>
                      <span className="text-blue-400">{validationResults.results.bootstrap.score}/100</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Risk of Ruin Results */}
              {validationResults.results?.risk_of_ruin && (
                <div className="bg-[#0F0F10] border border-white/5 p-4 rounded-sm">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <h4 className="text-xs font-mono uppercase tracking-widest text-zinc-400">Risk of Ruin</h4>
                    </div>
                    <Badge variant="outline" className={cn(
                      'text-[10px]',
                      validationResults.results.risk_of_ruin.is_acceptable ? 'text-emerald-400 border-emerald-500/40' : 'text-red-400 border-red-500/40'
                    )}>
                      {validationResults.results.risk_of_ruin.risk_level}
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Ruin Probability</span>
                      <span className={validationResults.results.risk_of_ruin.ruin_probability < 5 ? 'text-emerald-400' : 'text-red-400'}>
                        {validationResults.results.risk_of_ruin.ruin_probability}%
                      </span>
                    </div>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Survival Probability</span>
                      <span className="text-zinc-300">{validationResults.results.risk_of_ruin.survival_probability}%</span>
                    </div>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Kelly Fraction</span>
                      <span className="text-zinc-300">{validationResults.results.risk_of_ruin.kelly_fraction}%</span>
                    </div>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Score</span>
                      <span className="text-amber-400">{validationResults.results.risk_of_ruin.score}/100</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Slippage Results */}
              {validationResults.results?.slippage && (
                <div className="bg-[#0F0F10] border border-white/5 p-4 rounded-sm">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <TrendingDown className="w-4 h-4 text-violet-400" />
                      <h4 className="text-xs font-mono uppercase tracking-widest text-zinc-400">Execution Impact</h4>
                    </div>
                    <Badge variant="outline" className={cn(
                      'text-[10px]',
                      validationResults.results.slippage.is_viable ? 'text-emerald-400 border-emerald-500/40' : 'text-red-400 border-red-500/40'
                    )}>
                      {validationResults.results.slippage.impact_level}
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Profit Degradation</span>
                      <span className={validationResults.results.slippage.profit_degradation < 20 ? 'text-emerald-400' : 'text-amber-400'}>
                        {validationResults.results.slippage.profit_degradation}%
                      </span>
                    </div>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Realistic PF</span>
                      <span className="text-zinc-300">{validationResults.results.slippage.realistic_pf}</span>
                    </div>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Is Viable</span>
                      <span className={validationResults.results.slippage.is_viable ? 'text-emerald-400' : 'text-red-400'}>
                        {validationResults.results.slippage.is_viable ? 'Yes' : 'No'}
                      </span>
                    </div>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-zinc-500">Score</span>
                      <span className="text-violet-400">{validationResults.results.slippage.score}/100</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Prop Score Breakdown */}
            <div className="bg-[#0F0F10] border border-white/5 p-4 rounded-sm">
              <PropScoreBreakdown metrics={validationResults.propScoreMetrics} />
            </div>

            {/* Recommendations */}
            {validationResults.recommendations && validationResults.recommendations.length > 0 && (
              <div className="bg-[#0F0F10] border border-white/5 p-4 rounded-sm">
                <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-3">Recommendations</h4>
                <ul className="space-y-2">
                  {validationResults.recommendations.map((rec, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-zinc-400 font-mono">
                      <span className="text-amber-500">•</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
