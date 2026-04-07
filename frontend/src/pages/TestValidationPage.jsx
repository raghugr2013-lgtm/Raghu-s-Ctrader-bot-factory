import React from 'react';
import {
  PropScoreGauge,
  PropScoreBadge,
  ValidationMetricCard,
  StatusBadge,
  PropScoreBreakdown,
  calculatePropScore,
  getDecisionStatus
} from '@/components/validation/PropScore';
import {
  Shield, AlertTriangle, TrendingDown, Activity,
  Gauge, Target, CheckCircle2, XCircle, ChevronLeft
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';

// Mock data for testing - no backend dependency
const MOCK_VALIDATION_DATA = {
  propScore: 82,
  status: "READY FOR PROP",
  bootstrapSurvival: 93,
  monteCarloSurvival: 91,
  riskOfRuin: 3.5,
  maxDrawdown: 5.2,
  sensitivityScore: 78,
  overfittingRisk: 12,
  slippageImpact: 8.5,
  profitability: 72,
  walkForwardScore: 75,
  challengePassProb: 0.85,
  consistencyScore: 80,
  recommendations: [
    "Stable performance across bootstrap simulations",
    "Low drawdown - excellent risk management",
    "High survival probability - suitable for prop trading",
    "Consider increasing position size slightly given low risk"
  ]
};

export default function TestValidationPage() {
  const navigate = useNavigate();
  
  // Calculate prop score from mock metrics
  const propScoreMetrics = {
    bootstrapSurvival: MOCK_VALIDATION_DATA.bootstrapSurvival,
    monteCarloSurvival: MOCK_VALIDATION_DATA.monteCarloSurvival,
    maxDrawdown: MOCK_VALIDATION_DATA.maxDrawdown,
    sensitivityScore: MOCK_VALIDATION_DATA.sensitivityScore,
    walkForwardScore: MOCK_VALIDATION_DATA.walkForwardScore,
    profitability: MOCK_VALIDATION_DATA.profitability,
    challengePassProb: MOCK_VALIDATION_DATA.challengePassProb,
    consistencyScore: MOCK_VALIDATION_DATA.consistencyScore
  };
  
  const calculatedPropScore = calculatePropScore(propScoreMetrics);
  const decision = getDecisionStatus(calculatedPropScore);

  return (
    <div className="min-h-screen bg-[#050505] p-6">
      {/* Header with Version */}
      <div className="max-w-6xl mx-auto">
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
            <h1 className="text-2xl font-bold text-white">Validation Test Page</h1>
          </div>
          <div className="bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded text-xs font-mono font-bold">
            BUILD: v2.1-PROP-SCORE
          </div>
        </div>

        {/* Test Status Banner */}
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 mb-6">
          <p className="text-blue-400 font-mono text-sm">
            ✓ This is a test page with MOCK DATA - no backend required
          </p>
          <p className="text-blue-300/70 font-mono text-xs mt-1">
            If you can see this page with all components below, the frontend deployment is working correctly.
          </p>
        </div>

        {/* Decision Banner with Prop Score */}
        <div className={`p-6 rounded-lg border mb-6 ${
          decision.color === 'emerald' ? 'bg-emerald-500/10 border-emerald-500/30' :
          decision.color === 'amber' ? 'bg-amber-500/10 border-amber-500/30' :
          'bg-red-500/10 border-red-500/30'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <PropScoreGauge score={calculatedPropScore} size={120} />
              <div>
                <div className="flex items-center gap-2 mb-2">
                  {decision.color === 'emerald' && <CheckCircle2 className="w-6 h-6 text-emerald-400" />}
                  {decision.color === 'amber' && <AlertTriangle className="w-6 h-6 text-amber-400" />}
                  {decision.color === 'red' && <XCircle className="w-6 h-6 text-red-400" />}
                  <span className={`text-2xl font-bold uppercase font-mono ${
                    decision.color === 'emerald' ? 'text-emerald-400' :
                    decision.color === 'amber' ? 'text-amber-400' : 'text-red-400'
                  }`}>
                    {decision.status}
                  </span>
                </div>
                <p className="text-sm text-zinc-400 font-mono">{decision.description}</p>
                <p className="text-xs text-zinc-600 font-mono mt-2">
                  Calculated Prop Score: {calculatedPropScore} | Mock Score: {MOCK_VALIDATION_DATA.propScore}
                </p>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <StatusBadge status="PROP SAFE" />
              <PropScoreBadge score={calculatedPropScore} size="lg" />
            </div>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
          <ValidationMetricCard
            label="Bootstrap Survival"
            value={MOCK_VALIDATION_DATA.bootstrapSurvival}
            icon={Shield}
            type="survival"
            tooltip="Percentage of bootstrap simulations that survived"
          />
          <ValidationMetricCard
            label="Sensitivity Score"
            value={MOCK_VALIDATION_DATA.sensitivityScore}
            icon={Gauge}
            type="score"
            tooltip="Parameter stability score"
          />
          <ValidationMetricCard
            label="Risk of Ruin"
            value={MOCK_VALIDATION_DATA.riskOfRuin}
            icon={AlertTriangle}
            type="ruin"
            tooltip="Probability of account ruin"
          />
          <ValidationMetricCard
            label="Slippage Impact"
            value={MOCK_VALIDATION_DATA.slippageImpact}
            icon={TrendingDown}
            type="drawdown"
            tooltip="Profit lost to execution costs"
          />
          <ValidationMetricCard
            label="MC Survival"
            value={MOCK_VALIDATION_DATA.monteCarloSurvival}
            icon={Activity}
            type="survival"
            tooltip="Monte Carlo survival probability"
          />
          <ValidationMetricCard
            label="Overfitting Risk"
            value={MOCK_VALIDATION_DATA.overfittingRisk}
            icon={Target}
            type="ruin"
            tooltip="Risk of curve-fitting"
          />
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Prop Score Breakdown */}
          <div className="bg-[#0A0A0A] border border-white/5 p-6 rounded-lg">
            <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-300 mb-4">Prop Score Breakdown</h3>
            <PropScoreBreakdown metrics={propScoreMetrics} />
          </div>

          {/* Recommendations */}
          <div className="bg-[#0A0A0A] border border-white/5 p-6 rounded-lg">
            <div className="flex items-center gap-2 mb-4">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-300">Analysis Results</h3>
            </div>
            <ul className="space-y-3">
              {MOCK_VALIDATION_DATA.recommendations.map((rec, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-zinc-400 font-mono">
                  <span className="text-emerald-500 mt-0.5">✓</span>
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Debug Panel */}
        <div className="mt-6 bg-[#0A0A0A] border border-white/5 p-6 rounded-lg">
          <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-300 mb-4">Debug Information</h3>
          <pre className="bg-black/50 p-4 rounded text-xs font-mono text-zinc-400 overflow-auto">
{JSON.stringify({
  mockData: MOCK_VALIDATION_DATA,
  calculatedPropScore,
  propScoreMetrics,
  decision: {
    status: decision.status,
    color: decision.color,
    description: decision.description
  }
}, null, 2)}
          </pre>
        </div>

        {/* Component Status Checklist */}
        <div className="mt-6 bg-[#0A0A0A] border border-white/5 p-6 rounded-lg">
          <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-300 mb-4">Component Rendering Status</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-zinc-400">PropScoreGauge</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-zinc-400">PropScoreBadge</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-zinc-400">ValidationMetricCard</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-zinc-400">StatusBadge</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-zinc-400">PropScoreBreakdown</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-zinc-400">calculatePropScore()</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-zinc-400">getDecisionStatus()</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-zinc-400">Color Coding</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
