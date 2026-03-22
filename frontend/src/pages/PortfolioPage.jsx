import { useState, useCallback, useMemo } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import {
  Loader2, ArrowLeft, Activity, PieChart as PieIcon, GitBranch,
  LineChart, Dices, BarChart3, Settings2, Gauge, CheckCircle2,
  AlertTriangle, XCircle, Shield
} from 'lucide-react';

import { PortfolioManager } from '@/components/portfolio/PortfolioManager';
import { CorrelationHeatmap } from '@/components/portfolio/CorrelationHeatmap';
import { AllocationChart } from '@/components/portfolio/AllocationChart';
import { EquityCurve } from '@/components/portfolio/EquityCurve';
import { MonteCarloViz } from '@/components/portfolio/MonteCarloViz';
import { ComparisonDashboard } from '@/components/portfolio/ComparisonDashboard';
import { PropScoreGauge, StatusBadge } from '@/components/validation/PropScore';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const SESSION_ID = 'portfolio_session_' + Date.now().toString(36);

// Calculate Portfolio Prop Score
function calculatePortfolioPropScore(portfolio) {
  if (!portfolio) return null;
  
  const bt = portfolio.backtest_result;
  const mc = portfolio.monte_carlo_result;
  const corr = portfolio.correlation_result;
  
  if (!bt) return null;
  
  // Scoring weights
  let score = 0;
  
  // 25% - Win rate (scaled 0-100)
  const winRate = bt.win_rate || 0;
  score += Math.min(25, (winRate / 100) * 25);
  
  // 20% - Profit factor (1.0-3.0 range)
  const pf = bt.profit_factor || 0;
  score += Math.min(20, ((pf - 1) / 2) * 20);
  
  // 20% - Drawdown safety (inverse, lower is better)
  const dd = bt.max_drawdown_percent || 50;
  score += Math.max(0, (1 - dd / 50)) * 20;
  
  // 15% - Monte Carlo survival
  const mcSurvival = mc?.metrics?.profit_probability || 50;
  score += (mcSurvival / 100) * 15;
  
  // 10% - Sharpe ratio (scaled, 0-3 range)
  const sharpe = bt.sharpe_ratio || 0;
  score += Math.min(10, (sharpe / 3) * 10);
  
  // 10% - Diversification (correlation bonus)
  const avgCorr = corr?.average_correlation != null ? Math.abs(corr.average_correlation) : 0.5;
  score += Math.max(0, (1 - avgCorr)) * 10;
  
  return Math.round(score);
}

// Get decision status based on score
function getPortfolioDecision(score, portfolio) {
  const bt = portfolio?.backtest_result;
  const mc = portfolio?.monte_carlo_result;
  
  // Check critical metrics
  const hasHighDrawdown = (bt?.max_drawdown_percent || 0) > 25;
  const hasLowPF = (bt?.profit_factor || 0) < 1.2;
  const hasHighRuin = (mc?.metrics?.ruin_probability || 0) > 20;
  
  if (score >= 75 && !hasHighDrawdown && !hasLowPF && !hasHighRuin) {
    return {
      status: 'READY',
      color: 'emerald',
      icon: CheckCircle2,
      description: 'Portfolio is robust and ready for live deployment'
    };
  } else if (score >= 50 || (!hasHighDrawdown && !hasHighRuin)) {
    return {
      status: 'OPTIMIZE',
      color: 'amber',
      icon: AlertTriangle,
      description: 'Portfolio shows potential but needs optimization'
    };
  } else {
    return {
      status: 'REJECT',
      color: 'red',
      icon: XCircle,
      description: 'Portfolio has critical weaknesses - reconfigure strategies'
    };
  }
}

export default function PortfolioPage({ onBack }) {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [runningAnalysis, setRunningAnalysis] = useState(null); // 'correlation' | 'backtest' | 'montecarlo'
  const [activeTab, setActiveTab] = useState('overview');
  const [sessionId] = useState(SESSION_ID);

  const loadPortfolio = useCallback(async (id) => {
    try {
      const res = await axios.get(`${API}/portfolio/${id}`);
      setPortfolio(res.data.portfolio);
    } catch (e) {
      toast.error('Failed to load portfolio');
    }
  }, []);

  const onRefresh = useCallback((id) => {
    loadPortfolio(id);
  }, [loadPortfolio]);

  // Analysis actions
  const runCorrelation = useCallback(async () => {
    if (!portfolio?.id) return;
    setRunningAnalysis('correlation');
    try {
      await axios.post(`${API}/portfolio/${portfolio.id}/analyze-correlation`);
      toast.success('Correlation analysis complete');
      loadPortfolio(portfolio.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Correlation analysis failed');
    } finally { setRunningAnalysis(null); }
  }, [portfolio, loadPortfolio]);

  const runBacktest = useCallback(async () => {
    if (!portfolio?.id) return;
    setRunningAnalysis('backtest');
    try {
      await axios.post(`${API}/portfolio/${portfolio.id}/backtest`, { session_id: sessionId });
      toast.success('Portfolio backtest complete');
      loadPortfolio(portfolio.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Backtest failed');
    } finally { setRunningAnalysis(null); }
  }, [portfolio, sessionId, loadPortfolio]);

  const runMonteCarlo = useCallback(async () => {
    if (!portfolio?.id) return;
    setRunningAnalysis('montecarlo');
    try {
      await axios.post(`${API}/portfolio/${portfolio.id}/monte-carlo`, {
        session_id: sessionId, num_simulations: 1000,
      });
      toast.success('Monte Carlo complete');
      loadPortfolio(portfolio.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Monte Carlo failed');
    } finally { setRunningAnalysis(null); }
  }, [portfolio, sessionId, loadPortfolio]);

  const runAll = useCallback(async () => {
    if (!portfolio?.id || (portfolio.strategies?.length || 0) < 1) return;
    setRunningAnalysis('all');
    try {
      if (portfolio.strategies.length >= 2) {
        await axios.post(`${API}/portfolio/${portfolio.id}/analyze-correlation`);
      }
      await axios.post(`${API}/portfolio/${portfolio.id}/backtest`, { session_id: sessionId });
      await axios.post(`${API}/portfolio/${portfolio.id}/monte-carlo`, {
        session_id: sessionId, num_simulations: 1000,
      });
      toast.success('Full analysis complete');
      loadPortfolio(portfolio.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Analysis failed');
    } finally { setRunningAnalysis(null); }
  }, [portfolio, sessionId, loadPortfolio]);

  const stratCount = portfolio?.strategies?.length || 0;

  // Calculate portfolio prop score and decision
  const portfolioPropScore = useMemo(() => calculatePortfolioPropScore(portfolio), [portfolio]);
  const portfolioDecision = useMemo(() => 
    portfolioPropScore ? getPortfolioDecision(portfolioPropScore, portfolio) : null
  , [portfolioPropScore, portfolio]);

  return (
    <div className="h-screen w-screen bg-[#050505] overflow-hidden grid grid-cols-12 grid-rows-[auto_1fr] gap-2 p-2" data-testid="portfolio-page">
      {/* Header */}
      <div className="col-span-12 bg-[#0A0A0A] border border-white/5 px-4 py-3 flex items-center justify-between" data-testid="portfolio-header">
        <div className="flex items-center gap-4">
          <button onClick={onBack} className="text-zinc-500 hover:text-white transition-colors" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-2xl font-extrabold uppercase tracking-tight text-white" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
              PORTFOLIO ENGINE
            </h1>
            <p className="text-xs text-zinc-500 uppercase tracking-widest mt-0.5" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
              Multi-Strategy Analysis & Optimization
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Portfolio Decision Engine */}
          {portfolioDecision && portfolioPropScore && (
            <div className={`flex items-center gap-2 px-3 py-1 rounded border ${
              portfolioDecision.color === 'emerald' ? 'bg-emerald-500/10 border-emerald-500/30' :
              portfolioDecision.color === 'amber' ? 'bg-amber-500/10 border-amber-500/30' :
              'bg-red-500/10 border-red-500/30'
            }`} data-testid="portfolio-decision">
              <portfolioDecision.icon className={`w-4 h-4 ${
                portfolioDecision.color === 'emerald' ? 'text-emerald-400' :
                portfolioDecision.color === 'amber' ? 'text-amber-400' : 'text-red-400'
              }`} />
              <span className={`text-xs font-mono font-bold uppercase ${
                portfolioDecision.color === 'emerald' ? 'text-emerald-400' :
                portfolioDecision.color === 'amber' ? 'text-amber-400' : 'text-red-400'
              }`}>{portfolioDecision.status}</span>
              <span className={`text-sm font-bold font-mono ${
                portfolioDecision.color === 'emerald' ? 'text-emerald-400' :
                portfolioDecision.color === 'amber' ? 'text-amber-400' : 'text-red-400'
              }`}>{portfolioPropScore}</span>
            </div>
          )}
          {portfolio && (
            <Button
              onClick={runAll}
              disabled={runningAnalysis || stratCount < 1}
              className="bg-blue-600 hover:bg-blue-500 text-white font-mono uppercase text-[10px] h-7 px-3"
              data-testid="run-all-btn"
            >
              {runningAnalysis === 'all' ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Activity className="w-3 h-3 mr-1" />}
              RUN FULL ANALYSIS
            </Button>
          )}
          <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs text-zinc-400 uppercase font-mono">ONLINE</span>
        </div>
      </div>

      {/* Left Panel - Portfolio Manager */}
      <div className="col-span-3 bg-[#0A0A0A] border border-white/5 flex flex-col overflow-hidden" data-testid="manager-panel">
        <div className="border-b border-white/5 px-3 py-2 bg-[#18181B]">
          <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-200" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
            Portfolio Manager
          </h2>
        </div>
        <div className="flex-1 p-3 overflow-y-auto">
          <PortfolioManager
            portfolio={portfolio}
            setPortfolio={setPortfolio}
            sessionId={sessionId}
            onRefresh={onRefresh}
          />

          {/* Analysis Buttons */}
          {portfolio && stratCount >= 1 && (
            <div className="mt-3 space-y-1.5 pt-3 border-t border-white/5">
              <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Analysis</p>
              <Button
                onClick={runCorrelation} disabled={runningAnalysis || stratCount < 2}
                className="w-full bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 font-mono uppercase text-[10px] h-7 justify-start"
                data-testid="run-correlation-btn"
              >
                {runningAnalysis === 'correlation' ? <Loader2 className="w-3 h-3 animate-spin mr-2" /> : <GitBranch className="w-3 h-3 mr-2" />}
                Correlation
              </Button>
              <Button
                onClick={runBacktest} disabled={runningAnalysis}
                className="w-full bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 font-mono uppercase text-[10px] h-7 justify-start"
                data-testid="run-backtest-btn"
              >
                {runningAnalysis === 'backtest' ? <Loader2 className="w-3 h-3 animate-spin mr-2" /> : <LineChart className="w-3 h-3 mr-2" />}
                Backtest
              </Button>
              <Button
                onClick={runMonteCarlo} disabled={runningAnalysis}
                className="w-full bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 font-mono uppercase text-[10px] h-7 justify-start"
                data-testid="run-mc-btn"
              >
                {runningAnalysis === 'montecarlo' ? <Loader2 className="w-3 h-3 animate-spin mr-2" /> : <Dices className="w-3 h-3 mr-2" />}
                Monte Carlo
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Right Panel - Tabbed Analysis */}
      <div className="col-span-9 bg-[#0A0A0A] border border-white/5 flex flex-col overflow-hidden" data-testid="analysis-panel">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-full">
          <div className="border-b border-white/5 bg-[#18181B]">
            <TabsList className="bg-transparent border-none h-9 p-0 rounded-none w-full justify-start">
              <TabsTrigger value="overview" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 text-zinc-500 rounded-none h-9 px-4 uppercase text-[10px] tracking-wider font-bold" data-testid="tab-overview">
                <BarChart3 className="w-3 h-3 mr-1.5" /> Overview
              </TabsTrigger>
              <TabsTrigger value="correlation" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 text-zinc-500 rounded-none h-9 px-4 uppercase text-[10px] tracking-wider font-bold" data-testid="tab-correlation">
                <GitBranch className="w-3 h-3 mr-1.5" /> Correlation
              </TabsTrigger>
              <TabsTrigger value="equity" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 text-zinc-500 rounded-none h-9 px-4 uppercase text-[10px] tracking-wider font-bold" data-testid="tab-equity">
                <LineChart className="w-3 h-3 mr-1.5" /> Equity
              </TabsTrigger>
              <TabsTrigger value="montecarlo" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 text-zinc-500 rounded-none h-9 px-4 uppercase text-[10px] tracking-wider font-bold" data-testid="tab-montecarlo">
                <Dices className="w-3 h-3 mr-1.5" /> Monte Carlo
              </TabsTrigger>
              <TabsTrigger value="compare" className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 text-zinc-500 rounded-none h-9 px-4 uppercase text-[10px] tracking-wider font-bold" data-testid="tab-compare">
                <Settings2 className="w-3 h-3 mr-1.5" /> Compare
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Overview Tab */}
          <TabsContent value="overview" className="flex-1 p-4 overflow-y-auto mt-0">
            {!portfolio ? (
              <div className="flex items-center justify-center h-full text-sm text-zinc-500 font-mono" data-testid="overview-empty">
                Create a portfolio to begin
              </div>
            ) : (
              <div className="space-y-4 h-full" data-testid="overview-content">
                {/* Decision Engine Banner */}
                {portfolioDecision && portfolioPropScore && (
                  <div className={`p-4 rounded-sm border flex items-center justify-between ${
                    portfolioDecision.color === 'emerald' ? 'bg-emerald-500/10 border-emerald-500/30' :
                    portfolioDecision.color === 'amber' ? 'bg-amber-500/10 border-amber-500/30' :
                    'bg-red-500/10 border-red-500/30'
                  }`} data-testid="decision-banner">
                    <div className="flex items-center gap-4">
                      <PropScoreGauge score={portfolioPropScore} size={80} />
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <portfolioDecision.icon className={`w-5 h-5 ${
                            portfolioDecision.color === 'emerald' ? 'text-emerald-400' :
                            portfolioDecision.color === 'amber' ? 'text-amber-400' : 'text-red-400'
                          }`} />
                          <span className={`text-lg font-bold uppercase font-mono ${
                            portfolioDecision.color === 'emerald' ? 'text-emerald-400' :
                            portfolioDecision.color === 'amber' ? 'text-amber-400' : 'text-red-400'
                          }`}>{portfolioDecision.status}</span>
                        </div>
                        <p className="text-xs text-zinc-400 font-mono">{portfolioDecision.description}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div>
                        <p className="text-[10px] text-zinc-500 font-mono uppercase">Win Rate</p>
                        <p className="text-lg font-bold font-mono text-zinc-200">{(portfolio.backtest_result?.win_rate || 0).toFixed(1)}%</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-zinc-500 font-mono uppercase">Profit Factor</p>
                        <p className="text-lg font-bold font-mono text-zinc-200">{(portfolio.backtest_result?.profit_factor || 0).toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-zinc-500 font-mono uppercase">Max DD</p>
                        <p className="text-lg font-bold font-mono text-red-400">{(portfolio.backtest_result?.max_drawdown_percent || 0).toFixed(1)}%</p>
                      </div>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-3 gap-4 flex-1">
                  {/* Allocation */}
                  <div className="bg-[#0A0A0A] border border-white/5 flex flex-col overflow-hidden">
                    <div className="border-b border-white/5 px-3 py-1.5 bg-[#18181B] flex items-center gap-2">
                      <PieIcon className="w-3 h-3 text-blue-400" />
                      <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-zinc-400">Allocation</span>
                    </div>
                    <div className="flex-1 p-2 min-h-0">
                      <AllocationChart strategies={portfolio.strategies} allocationResult={portfolio.allocation_result} />
                    </div>
                  </div>

                  {/* Equity mini */}
                  <div className="col-span-2 bg-[#0A0A0A] border border-white/5 flex flex-col overflow-hidden">
                    <div className="border-b border-white/5 px-3 py-1.5 bg-[#18181B] flex items-center gap-2">
                      <LineChart className="w-3 h-3 text-blue-400" />
                      <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-zinc-400">Portfolio Performance</span>
                      {portfolio.backtest_result?.grade && (
                        <Badge variant="outline" className={`ml-auto text-[9px] px-1.5 py-0 h-4 ${portfolio.backtest_result.is_deployable ? 'border-emerald-500/30 text-emerald-400' : 'border-red-500/30 text-red-400'}`}>
                          Grade {portfolio.backtest_result.grade}
                        </Badge>
                      )}
                    </div>
                    <div className="flex-1 p-2 min-h-0">
                      <EquityCurve backtestResult={portfolio.backtest_result} />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </TabsContent>

          {/* Correlation Tab */}
          <TabsContent value="correlation" className="flex-1 p-4 overflow-y-auto mt-0">
            <CorrelationHeatmap correlationResult={portfolio?.correlation_result} strategies={portfolio?.strategies} />
          </TabsContent>

          {/* Equity Tab */}
          <TabsContent value="equity" className="flex-1 p-4 overflow-y-auto mt-0">
            <EquityCurve backtestResult={portfolio?.backtest_result} />
          </TabsContent>

          {/* Monte Carlo Tab */}
          <TabsContent value="montecarlo" className="flex-1 p-4 overflow-y-auto mt-0">
            <MonteCarloViz mcResult={portfolio?.monte_carlo_result} />
          </TabsContent>

          {/* Compare Tab */}
          <TabsContent value="compare" className="flex-1 p-4 overflow-y-auto mt-0">
            <ComparisonDashboard portfolio={portfolio} onRefresh={onRefresh} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
