import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  Loader2, CheckCircle2, XCircle, Clock, Zap, ChevronRight,
  ArrowLeft, Play, TrendingUp, Shield, Network, Target, DollarSign,
  BarChart3, Download, Settings
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
  monitoring_setup: Clock,
  retrain_scheduling: Clock,
  completed: CheckCircle2,
  failed: XCircle,
};

export default function PipelinePage() {
  const navigate = useNavigate();
  const [isRunning, setIsRunning] = useState(false);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  // Progress tracking state (NEW)
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState(null);
  
  const [config, setConfig] = useState({
    // Core settings (always visible)
    generation_mode: 'factory',
    ai_provider: 'openai',
    symbol: 'EURUSD',
    timeframe: '1h',
    strategies_per_template: 10,
    portfolio_size: 5,
    
    // Backtest date range (NEW)
    backtest_from_date: '',  // YYYY-MM-DD
    backtest_to_date: '',    // YYYY-MM-DD
    
    // Account & Risk Configuration (NEW)
    account_size: 10000,      // Total account capital
    risk_per_trade: 1.0,      // Risk per trade in %
    
    // Advanced settings (collapsible)
    templates: ['ema_crossover', 'rsi_mean_reversion', 'macd_trend'],
    initial_balance: 10000,
    duration_days: 90,
    diversity_min_score: 60.0,
    correlation_max_threshold: 0.7,
    min_sharpe_ratio: 1.0,
    max_drawdown_pct: 20.0,
    min_win_rate: 50.0,
    max_risk_per_strategy: 2.0,
    max_portfolio_risk: 8.0,
    allocation_method: 'MAX_SHARPE',
    enable_regime_filter: true,
    enable_monitoring: false,
    enable_auto_retrain: false,
    retrain_threshold_days: 30,
  });

  const handleRunPipeline = async () => {
    setIsRunning(true);
    setPipelineResult(null);
    setProgress(null);

    try {
      toast.info('Starting Pipeline...');
      
      const response = await axios.post(`${API}/master-run`, config);
      const data = response.data;
      
      // Store job ID for progress tracking
      if (data.run_id) {
        setJobId(data.run_id);
        
        // Start polling for progress
        const progressInterval = setInterval(async () => {
          try {
            const progressRes = await axios.get(`${API}/progress/${data.run_id}`);
            if (progressRes.data.success) {
              setProgress(progressRes.data.progress);
              
              // Stop polling if completed or failed
              if (progressRes.data.progress.stage === 'completed' || 
                  progressRes.data.progress.stage === 'failed') {
                clearInterval(progressInterval);
              }
            }
          } catch (err) {
            console.error('Progress polling error:', err);
          }
        }, 2000); // Poll every 2 seconds
        
        // Store interval ID for cleanup
        window._progressInterval = progressInterval;
      }

      setPipelineResult(data);

      if (data.success) {
        toast.success(`Pipeline complete! ${data.deployable_count} strategies ready.`);
      } else {
        toast.error(`Pipeline failed: ${data.error_message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Pipeline error:', error);
      const errorDetail = error.response?.data?.detail;
      const errorMessage = typeof errorDetail === 'object' 
        ? errorDetail.message || JSON.stringify(errorDetail)
        : errorDetail || error.message;
      
      toast.error(`Pipeline failed: ${errorMessage}`);
      setPipelineResult({
        success: false,
        error_message: errorMessage,
        stage_results: [],
      });
    } finally {
      setIsRunning(false);
      
      // Cleanup progress interval
      if (window._progressInterval) {
        clearInterval(window._progressInterval);
        window._progressInterval = null;
      }
    }
  };

  const handleDownloadBots = async () => {
    if (!pipelineResult?.run_id) {
      toast.error('No run ID available');
      return;
    }

    try {
      toast.info('Preparing download...');
      
      // Create export
      const exportResponse = await axios.post(
        `${BACKEND_URL}/api/export/create/${pipelineResult.run_id}`,
        {
          strategies: pipelineResult.selected_portfolio || [],
          top_n: config.portfolio_size,
          pipeline_config: {
            symbol: config.symbol,
            timeframe: config.timeframe,
            initial_balance: config.initial_balance
          }
        }
      );

      if (exportResponse.data.success) {
        // Download the ZIP
        window.open(`${BACKEND_URL}/api/export/download/${pipelineResult.run_id}`, '_blank');
        toast.success('Download started!');
      }
    } catch (error) {
      console.error('Download error:', error);
      toast.error(`Download failed: ${error.message}`);
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
                <h1 className="text-2xl font-bold">Strategy Pipeline</h1>
                <p className="text-xs text-zinc-500 mt-1">
                  Generate, validate, and deploy cTrader bots
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
                  Running...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Run Pipeline
                </>
              )}
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Configuration Panel */}
        <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold">Configuration</h2>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm text-zinc-400 hover:text-white transition-colors"
            >
              <Settings className="w-4 h-4" />
              {showAdvanced ? 'Hide' : 'Show'} Advanced
            </button>
          </div>
          
          {/* Core Settings Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
            {/* Generation Mode */}
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Generation Mode</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setConfig({...config, generation_mode: 'factory'})}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-mono transition-all ${
                    config.generation_mode === 'factory'
                      ? 'bg-purple-600 text-white'
                      : 'bg-white/5 text-zinc-400 hover:bg-white/10'
                  }`}
                >
                  Factory
                </button>
                <button
                  onClick={() => setConfig({...config, generation_mode: 'ai'})}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-mono transition-all ${
                    config.generation_mode === 'ai'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white/5 text-zinc-400 hover:bg-white/10'
                  }`}
                >
                  AI
                </button>
              </div>
            </div>

            {/* AI Provider (shown when generation_mode is 'ai') */}
            {config.generation_mode === 'ai' && (
              <div>
                <label className="block text-sm text-zinc-400 mb-2">AI Provider</label>
                <select
                  value={config.ai_provider}
                  onChange={(e) => setConfig({...config, ai_provider: e.target.value})}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="openai">OpenAI</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                  <option value="hybrid">Hybrid (All 3)</option>
                </select>
              </div>
            )}

            {/* Timeframe */}
            <div>
              <label className="block text-sm text-zinc-400 mb-2">
                Timeframe
                <span className="block text-xs text-zinc-600 font-normal mt-0.5">Strategy execution timeframe (aggregated from 1m base data)</span>
              </label>
              <select
                value={config.timeframe}
                onChange={(e) => setConfig({...config, timeframe: e.target.value})}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="1m">1 Minute</option>
                <option value="5m">5 Minutes</option>
                <option value="15m">15 Minutes</option>
                <option value="30m">30 Minutes</option>
                <option value="1h">1 Hour</option>
                <option value="4h">4 Hours</option>
                <option value="1d">Daily</option>
              </select>
            </div>
            
            {/* Backtest From Date (NEW) */}
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Backtest From Date</label>
              <input
                type="date"
                value={config.backtest_from_date}
                onChange={(e) => setConfig({...config, backtest_from_date: e.target.value})}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Leave empty for auto"
              />
              <p className="text-xs text-zinc-600 mt-1">Optional: Custom start date</p>
            </div>
            
            {/* Backtest To Date (NEW) */}
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Backtest To Date</label>
              <input
                type="date"
                value={config.backtest_to_date}
                onChange={(e) => setConfig({...config, backtest_to_date: e.target.value})}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Leave empty for latest"
              />
              <p className="text-xs text-zinc-600 mt-1">Optional: Custom end date</p>
            </div>

            {/* Account Size (NEW) */}
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Account Size ($)</label>
              <input
                type="number"
                value={config.account_size}
                onChange={(e) => setConfig({...config, account_size: parseFloat(e.target.value) || 10000})}
                min="100"
                step="100"
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="10000"
              />
              <p className="text-xs text-zinc-600 mt-1">Total capital for portfolio</p>
            </div>
            
            {/* Risk per Trade (NEW) */}
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Risk per Trade (%)</label>
              <input
                type="number"
                value={config.risk_per_trade}
                onChange={(e) => setConfig({...config, risk_per_trade: parseFloat(e.target.value) || 1.0})}
                min="0.1"
                max="5.0"
                step="0.1"
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="1.0"
              />
              <p className="text-xs text-zinc-600 mt-1">Risk per trade (1% = conservative)</p>
            </div>


            {/* Symbol */}
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Symbol</label>
              <input
                type="text"
                value={config.symbol}
                onChange={(e) => setConfig({...config, symbol: e.target.value.toUpperCase()})}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="EURUSD"
              />
            </div>

            {/* Strategies Per Template */}
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Strategies to Generate</label>
              <input
                type="number"
                value={config.strategies_per_template}
                onChange={(e) => setConfig({...config, strategies_per_template: parseInt(e.target.value)})}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                min="1"
                max="50"
              />
            </div>

            {/* Portfolio Size */}
            <div>
              <label className="block text-sm text-zinc-400 mb-2">Portfolio Size</label>
              <input
                type="number"
                value={config.portfolio_size}
                onChange={(e) => setConfig({...config, portfolio_size: parseInt(e.target.value)})}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                min="1"
                max="10"
              />
            </div>
          </div>

          {/* Advanced Settings (Collapsible) */}
          {showAdvanced && (
            <div className="pt-6 border-t border-white/10 space-y-4">
              <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-wide">Advanced Settings</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Initial Balance</label>
                  <input
                    type="number"
                    value={config.initial_balance}
                    onChange={(e) => setConfig({...config, initial_balance: parseFloat(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm font-mono"
                  />
                </div>
                
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Backtest Days</label>
                  <input
                    type="number"
                    value={config.duration_days}
                    onChange={(e) => setConfig({...config, duration_days: parseInt(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm font-mono"
                  />
                </div>
                
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Min Sharpe Ratio</label>
                  <input
                    type="number"
                    step="0.1"
                    value={config.min_sharpe_ratio}
                    onChange={(e) => setConfig({...config, min_sharpe_ratio: parseFloat(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm font-mono"
                  />
                </div>
                
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Max Drawdown %</label>
                  <input
                    type="number"
                    step="0.1"
                    value={config.max_drawdown_pct}
                    onChange={(e) => setConfig({...config, max_drawdown_pct: parseFloat(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm font-mono"
                  />
                </div>
                
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Min Win Rate %</label>
                  <input
                    type="number"
                    step="0.1"
                    value={config.min_win_rate}
                    onChange={(e) => setConfig({...config, min_win_rate: parseFloat(e.target.value)})}
                    className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm font-mono"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Quick Info */}
          <div className="mt-6 pt-6 border-t border-white/10">
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-6">
                <div>
                  <span className="text-zinc-500">Mode:</span>
                  <span className="ml-2 font-mono text-white">
                    {config.generation_mode === 'factory' ? '🏭 Templates' : `🤖 ${config.ai_provider}`}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500">Market:</span>
                  <span className="ml-2 font-mono text-white">{config.symbol} @ {config.timeframe}</span>
                </div>
                <div>
                  <span className="text-zinc-500">Strategies:</span>
                  <span className="ml-2 font-mono text-white">
                    {config.strategies_per_template * config.templates.length} → {config.portfolio_size}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Progress Tracker (NEW) */}
        {isRunning && progress && (
          <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">Pipeline Progress</h2>
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                <span className="text-sm text-zinc-400">
                  {progress.current} / {progress.total} strategies
                </span>
              </div>
            </div>
            
            {/* Progress Bar */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-mono text-zinc-400 uppercase tracking-wide">
                  {progress.stage}
                </span>
                <span className="text-sm font-mono text-blue-400">
                  {progress.percent}%
                </span>
              </div>
              <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-blue-600 to-purple-600 h-full transition-all duration-300 ease-out"
                  style={{ width: `${progress.percent}%` }}
                />
              </div>
            </div>
            
            {/* Status Message */}
            <div className="flex items-center gap-2 p-3 bg-white/5 rounded-lg border border-white/10">
              <ChevronRight className="w-4 h-4 text-blue-400 shrink-0" />
              <p className="text-sm text-zinc-300">{progress.message}</p>
            </div>
            
            {/* Errors (if any) */}
            {progress.errors && progress.errors.length > 0 && (
              <div className="mt-4 space-y-2">
                {progress.errors.map((error, idx) => (
                  <div key={idx} className="flex items-start gap-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-400">
                    <XCircle className="w-3 h-3 shrink-0 mt-0.5" />
                    <span>{error}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Pipeline Results */}
        {pipelineResult && (
          <div className="space-y-6">
            {/* Summary Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <MetricCard label="Generated" value={pipelineResult.generated_count} icon={Zap} color="blue" />
              <MetricCard label="Backtested" value={pipelineResult.backtested_count} icon={BarChart3} color="cyan" />
              <MetricCard label="Validated" value={pipelineResult.validated_count} icon={Shield} color="emerald" />
              <MetricCard label="Selected" value={pipelineResult.selected_count} icon={Target} color="purple" />
              <MetricCard label="Deployable" value={pipelineResult.deployable_count} icon={CheckCircle2} color="emerald" />
            </div>

            {/* Stage Results */}
            <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-6">
              <h2 className="text-lg font-bold mb-4">Pipeline Stages</h2>
              <div className="space-y-2">
                {pipelineResult.stage_results?.map((stage, idx) => {
                  const Icon = STAGE_ICONS[stage.stage] || Clock;
                  return (
                    <div
                      key={idx}
                      className={`flex items-center justify-between p-3 rounded-lg border ${
                        stage.success
                          ? 'bg-emerald-500/10 border-emerald-500/30'
                          : 'bg-red-500/10 border-red-500/30'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className={`w-4 h-4 ${stage.success ? 'text-emerald-400' : 'text-red-400'}`} />
                        <div>
                          <p className="font-mono text-sm uppercase tracking-wide">
                            {stage.stage.replace(/_/g, ' ')}
                          </p>
                          <p className="text-xs text-zinc-400 mt-0.5">{stage.message}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <p className="text-xs text-zinc-500">{stage.execution_time?.toFixed(2)}s</p>
                        {stage.success ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <XCircle className="w-4 h-4 text-red-400" />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Selected Strategies */}
            {pipelineResult.selected_portfolio?.length > 0 && (
              <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-bold">Top Strategies</h2>
                  <Button
                    onClick={handleDownloadBots}
                    className="bg-emerald-600 hover:bg-emerald-700"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download Bots
                  </Button>
                </div>
                <div className="space-y-2">
                  {pipelineResult.selected_portfolio.map((strategy, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-4 bg-white/5 rounded-lg border border-white/10"
                    >
                      <div className="flex-1">
                        <p className="font-mono font-bold">#{idx + 1} {strategy.name}</p>
                        <p className="text-xs text-zinc-500">{strategy.template_id || 'N/A'}</p>
                        {/* Backtest Period (NEW) */}
                        {(config.backtest_from_date || config.backtest_to_date) && (
                          <div className="mt-2 flex items-center gap-4 text-xs text-zinc-400">
                            <div className="flex items-center gap-1">
                              <span className="text-zinc-600">Symbol:</span>
                              <span className="font-mono">{config.symbol}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <span className="text-zinc-600">Timeframe:</span>
                              <span className="font-mono">{config.timeframe}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <span className="text-zinc-600">Backtest:</span>
                              <span className="font-mono">
                                {config.backtest_from_date || 'Auto'} → {config.backtest_to_date || 'Latest'}
                              </span>
                            </div>
                          </div>
                        )}
                        {/* Capital Allocation (NEW) */}
                        {strategy.allocation && (
                          <div className="mt-2 flex items-center gap-4 text-xs">
                            <div className="flex items-center gap-1 text-emerald-400">
                              <DollarSign className="w-3 h-3" />
                              <span className="font-mono font-bold">${strategy.allocation.allocated_capital?.toLocaleString()}</span>
                              <span className="text-zinc-600">capital</span>
                            </div>
                            <div className="flex items-center gap-1 text-blue-400">
                              <span className="font-mono">${strategy.allocation.position_size?.toLocaleString()}</span>
                              <span className="text-zinc-600">position</span>
                            </div>
                            <div className="flex items-center gap-1 text-zinc-400">
                              <span className="font-mono">{strategy.allocation.weight_percent}%</span>
                              <span className="text-zinc-600">weight</span>
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-6 text-sm">
                        <div>
                          <p className="text-zinc-500 text-xs">Score</p>
                          <p className="font-mono">{strategy.composite_score?.toFixed(1) || strategy.fitness?.toFixed(2) || 'N/A'}</p>
                        </div>
                        <div>
                          <p className="text-zinc-500 text-xs">Sharpe</p>
                          <p className="font-mono">{strategy.sharpe_ratio?.toFixed(2) || 'N/A'}</p>
                        </div>
                        <div>
                          <p className="text-zinc-500 text-xs">Max DD</p>
                          <p className="font-mono">{strategy.max_drawdown_pct?.toFixed(1)}%</p>
                        </div>
                        <div>
                          <p className="text-zinc-500 text-xs">Win Rate</p>
                          <p className="font-mono">{strategy.win_rate?.toFixed(1)}%</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Execution Summary */}
            <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-zinc-500" />
                  <p className="text-zinc-400">Total Execution Time</p>
                </div>
                <p className="font-mono text-xl font-bold">{pipelineResult.total_execution_time?.toFixed(2)}s</p>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!isRunning && !pipelineResult && (
          <div className="bg-[#0F0F10] border border-white/10 rounded-lg p-12 text-center">
            <Zap className="w-12 h-12 mx-auto mb-4 text-blue-500" />
            <h3 className="text-xl font-bold mb-2">Ready to Generate Strategies</h3>
            <p className="text-zinc-400 mb-6">
              Configure your settings above and click "Run Pipeline" to start.
            </p>
            <div className="text-left max-w-2xl mx-auto space-y-2 text-sm text-zinc-500">
              <p className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-400" />
                1. Generate strategies using templates or AI
              </p>
              <p className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-400" />
                2. Backtest with real market data
              </p>
              <p className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-400" />
                3. Validate with Monte Carlo simulation
              </p>
              <p className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-400" />
                4. Select top performers for portfolio
              </p>
              <p className="flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-blue-400" />
                5. Generate and download cTrader bots
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
