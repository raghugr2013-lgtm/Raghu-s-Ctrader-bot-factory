import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  Loader2, CheckCircle2, XCircle, Clock, Zap, ChevronRight,
  ArrowLeft, Play, TrendingUp, Shield, Network, Target, DollarSign,
  BarChart3, Activity
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api/pipeline`;

const STAGE_ICONS = {
  initialization: Clock,
  generation: Zap,
  diversity_filter: Network,
  backtesting: BarChart3,
  validation: Shield,
  correlation_filter: Network,
  regime_adaptation: TrendingUp,
  portfolio_selection: Target,
  risk_allocation: DollarSign,
  capital_scaling: DollarSign,
  cbot_generation: Zap,
  monitoring_setup: Activity,
  retrain_scheduling: Clock,
  completed: CheckCircle2,
  failed: XCircle,
};

export default function PipelinePage() {
  const navigate = useNavigate();
  const [isRunning, setIsRunning] = useState(false);
  const [pipelineResult, setPipelineResult] = useState(null);
  
  const [config, setConfig] = useState({
    generation_mode: 'ai',  // Changed default to 'ai'
    templates: ['EMA_CROSSOVER', 'RSI_MEAN_REVERSION', 'MACD_TREND'],
    strategies_per_template: 10,
    symbol: 'EURUSD',
    timeframe: '1h',
    initial_balance: 10000,
    duration_days: 365,
    diversity_min_score: 60.0,
    correlation_max_threshold: 0.7,
    min_sharpe_ratio: 1.0,
    max_drawdown_pct: 20.0,
    min_win_rate: 50.0,
    portfolio_size: 5,
    max_risk_per_strategy: 2.0,
    max_portfolio_risk: 8.0,
    allocation_method: 'MAX_SHARPE',
    enable_regime_filter: true,
    enable_monitoring: true,
    enable_auto_retrain: true,
    retrain_threshold_days: 30,
  });

  const handleRunPipeline = async () => {
    setIsRunning(true);
    setPipelineResult(null);

    try {
      toast.info('Starting Master Pipeline...');
      
      const response = await axios.post(`${API}/master-run`, config);
      const data = response.data;

      setPipelineResult(data);

      if (data.success) {
        toast.success(`Pipeline completed! ${data.deployable_count} strategies ready to deploy.`);
      } else {
        toast.error(`Pipeline failed: ${data.error_message}`);
      }
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      toast.error(`Pipeline failed: ${detail}`);
      setPipelineResult({
        success: false,
        error_message: detail,
        stage_results: [],
      });
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-white overflow-y-auto">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#0A0A0B]/95 backdrop-blur-lg border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="p-2 hover:bg-white/5 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-2xl font-bold">Master Pipeline</h1>
                <p className="text-xs text-zinc-500 mt-1">
                  Complete AI trading strategy pipeline from generation to deployment
                </p>
              </div>
            </div>
            <Button
              onClick={handleRunPipeline}
              disabled={isRunning}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 font-mono uppercase tracking-wide"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Running Pipeline...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Run Full Pipeline
                </>
              )}
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Configuration Summary */}
        <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-6">
          <h2 className="text-lg font-bold mb-4">Pipeline Configuration</h2>
          
          {/* Generation Mode Selector */}
          <div className="mb-6">
            <label className="block text-sm text-zinc-500 mb-2">Generation Mode</label>
            <div className="flex gap-2">
              <button
                onClick={() => setConfig({...config, generation_mode: 'ai'})}
                className={`px-4 py-2 rounded-lg text-sm font-mono transition-all ${
                  config.generation_mode === 'ai'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white/5 text-zinc-400 hover:bg-white/10'
                }`}
              >
                🤖 AI (OpenAI)
              </button>
              <button
                onClick={() => setConfig({...config, generation_mode: 'factory'})}
                className={`px-4 py-2 rounded-lg text-sm font-mono transition-all ${
                  config.generation_mode === 'factory'
                    ? 'bg-purple-600 text-white'
                    : 'bg-white/5 text-zinc-400 hover:bg-white/10'
                }`}
              >
                🏭 Factory (Templates)
              </button>
              <button
                onClick={() => setConfig({...config, generation_mode: 'both'})}
                className={`px-4 py-2 rounded-lg text-sm font-mono transition-all ${
                  config.generation_mode === 'both'
                    ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                    : 'bg-white/5 text-zinc-400 hover:bg-white/10'
                }`}
              >
                ⚡ Both (Hybrid)
              </button>
            </div>
            <p className="text-xs text-zinc-500 mt-2">
              {config.generation_mode === 'ai' && '✓ Uses OpenAI API to generate diverse strategies with fallback to predefined templates'}
              {config.generation_mode === 'factory' && '✓ Uses template-based generation with genetic variations'}
              {config.generation_mode === 'both' && '✓ Combines AI-generated and template-based strategies for maximum diversity'}
            </p>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-zinc-500">Strategies</p>
              <p className="font-mono">{config.strategies_per_template * config.templates.length}</p>
            </div>
            <div>
              <p className="text-zinc-500">Templates</p>
              <p className="font-mono">{config.templates.length}</p>
            </div>
            <div>
              <p className="text-zinc-500">Portfolio Size</p>
              <p className="font-mono">{config.portfolio_size}</p>
            </div>
            <div>
              <p className="text-zinc-500">Initial Balance</p>
              <p className="font-mono">${config.initial_balance.toLocaleString()}</p>
            </div>
          </div>
        </div>

        {/* Pipeline Stages */}
        {pipelineResult && (
          <div className="space-y-4">
            {/* Stage Results */}
            <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-6">
              <h2 className="text-lg font-bold mb-4">Pipeline Stages</h2>
              <div className="space-y-2">
                {pipelineResult.stage_results && pipelineResult.stage_results.map((stage, idx) => {
                  const Icon = STAGE_ICONS[stage.stage] || Clock;
                  return (
                    <div
                      key={idx}
                      className={`flex items-center justify-between p-4 rounded-lg border ${
                        stage.success
                          ? 'bg-emerald-500/10 border-emerald-500/30'
                          : 'bg-red-500/10 border-red-500/30'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className={`w-5 h-5 ${stage.success ? 'text-emerald-400' : 'text-red-400'}`} />
                        <div>
                          <p className="font-mono text-sm uppercase tracking-wide">
                            {stage.stage.replace(/_/g, ' ')}
                          </p>
                          <p className="text-xs text-zinc-400 mt-1">{stage.message}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        {stage.success ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                        ) : (
                          <XCircle className="w-5 h-5 text-red-400" />
                        )}
                        <p className="text-xs text-zinc-500 mt-1">{stage.execution_time.toFixed(2)}s</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Pipeline Summary */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <MetricCard
                label="Generated"
                value={pipelineResult.generated_count}
                icon={Zap}
                color="blue"
              />
              <MetricCard
                label="Backtested"
                value={pipelineResult.backtested_count}
                icon={BarChart3}
                color="cyan"
              />
              <MetricCard
                label="Validated"
                value={pipelineResult.validated_count}
                icon={Shield}
                color="emerald"
              />
              <MetricCard
                label="Selected"
                value={pipelineResult.selected_count}
                icon={Target}
                color="purple"
              />
              <MetricCard
                label="Deployable"
                value={pipelineResult.deployable_count}
                icon={CheckCircle2}
                color="emerald"
              />
            </div>

            {/* Selected Strategies */}
            {pipelineResult.selected_portfolio && pipelineResult.selected_portfolio.length > 0 && (
              <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-6">
                <h2 className="text-lg font-bold mb-4">Selected Portfolio</h2>
                <div className="space-y-2">
                  {pipelineResult.selected_portfolio.map((strategy, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-4 bg-white/5 rounded-lg border border-white/10"
                    >
                      <div>
                        <p className="font-mono font-bold">{strategy.name}</p>
                        <p className="text-xs text-zinc-500">{strategy.template_id}</p>
                      </div>
                      <div className="flex items-center gap-6 text-sm">
                        <div>
                          <p className="text-zinc-500">Fitness</p>
                          <p className="font-mono">{strategy.fitness?.toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-zinc-500">Sharpe</p>
                          <p className="font-mono">{strategy.sharpe_ratio?.toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-zinc-500">Max DD</p>
                          <p className="font-mono">{strategy.max_drawdown_pct?.toFixed(1)}%</p>
                        </div>
                        <div>
                          <p className="text-zinc-500">Win Rate</p>
                          <p className="font-mono">{strategy.win_rate?.toFixed(1)}%</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Execution Time */}
            <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <p className="text-zinc-500">Total Execution Time</p>
                <p className="font-mono text-lg font-bold">{pipelineResult.total_execution_time?.toFixed(2)}s</p>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!isRunning && !pipelineResult && (
          <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-12 text-center">
            <Zap className="w-12 h-12 mx-auto mb-4 text-blue-500" />
            <h3 className="text-xl font-bold mb-2">Ready to Run Pipeline</h3>
            <p className="text-zinc-400 mb-6">
              Click "Run Full Pipeline" to start the complete trading strategy generation and optimization flow.
            </p>
            <div className="text-left max-w-2xl mx-auto space-y-2 text-sm text-zinc-500">
              <p className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-400" />
                Generation → Diversity Filter → Backtesting → Validation
              </p>
              <p className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-400" />
                Correlation Filter → Regime Adaptation → Portfolio Selection
              </p>
              <p className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-400" />
                Risk Allocation → Capital Scaling → cBot Generation
              </p>
              <p className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-400" />
                Monitoring Setup → Auto-Retrain Scheduling
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value, icon: Icon, color }) {
  const colorClasses = {
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
  };

  return (
    <div className={`p-4 rounded-lg border ${colorClasses[color]}`}>
      <div className="flex items-center justify-between mb-2">
        <Icon className={`w-5 h-5 ${colorClasses[color].split(' ')[0]}`} />
        <p className="text-2xl font-bold font-mono">{value || 0}</p>
      </div>
      <p className="text-xs uppercase tracking-wide text-zinc-400">{label}</p>
    </div>
  );
}
