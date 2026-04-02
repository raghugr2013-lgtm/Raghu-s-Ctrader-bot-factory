import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import Editor from '@monaco-editor/react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import {
  Loader2, ArrowLeft, Search, Code2, Target, Shield, 
  TrendingUp, AlertTriangle, CheckCircle2, XCircle,
  Lightbulb, BarChart3, Gauge
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Sample cBot code for testing
const SAMPLE_CODE = `using System;
using cAlgo.API;
using cAlgo.API.Indicators;

[Robot(Name = "MA Crossover Bot", AccessRights = AccessRights.None)]
public class MACrossoverBot : Robot
{
    [Parameter("Fast MA Period", DefaultValue = 10)]
    public int FastPeriod { get; set; }
    
    [Parameter("Slow MA Period", DefaultValue = 20)]
    public int SlowPeriod { get; set; }
    
    [Parameter("Stop Loss", DefaultValue = 20)]
    public double StopLoss { get; set; }
    
    [Parameter("Take Profit", DefaultValue = 40)]
    public double TakeProfit { get; set; }
    
    private SimpleMovingAverage _fastMA;
    private SimpleMovingAverage _slowMA;
    
    protected override void OnStart()
    {
        _fastMA = Indicators.SimpleMovingAverage(Bars.ClosePrices, FastPeriod);
        _slowMA = Indicators.SimpleMovingAverage(Bars.ClosePrices, SlowPeriod);
    }
    
    protected override void OnBar()
    {
        if (_fastMA.Result.HasCrossedAbove(_slowMA.Result, 0))
        {
            ExecuteMarketOrder(TradeType.Buy, Symbol.Name, 10000, "MA Cross", StopLoss, TakeProfit);
        }
        
        if (_fastMA.Result.HasCrossedBelow(_slowMA.Result, 0))
        {
            ExecuteMarketOrder(TradeType.Sell, Symbol.Name, 10000, "MA Cross", StopLoss, TakeProfit);
        }
    }
}`;

function SectionCard({ title, icon: Icon, children, className = '' }) {
  return (
    <div className={`bg-[#0F0F10] border border-white/10 rounded-sm ${className}`}>
      <div className="flex items-center gap-2 px-4 py-2 border-b border-white/5 bg-[#18181B]">
        <Icon className="w-4 h-4 text-zinc-400" />
        <h3 className="text-sm font-mono uppercase tracking-wider text-zinc-300">{title}</h3>
      </div>
      <div className="p-4">
        {children}
      </div>
    </div>
  );
}

function IndicatorBadge({ indicator }) {
  return (
    <div className="bg-zinc-800 border border-zinc-700 rounded px-3 py-2">
      <div className="flex items-center gap-2 mb-1">
        <BarChart3 className="w-4 h-4 text-blue-400" />
        <span className="text-sm font-mono text-zinc-200">{indicator.name}</span>
      </div>
      {indicator.variable_name && (
        <p className="text-xs text-zinc-500 font-mono">var: {indicator.variable_name}</p>
      )}
      {indicator.parameters && Object.keys(indicator.parameters).length > 0 && (
        <div className="mt-1 text-xs text-zinc-400">
          {Object.entries(indicator.parameters).map(([key, val]) => (
            <span key={key} className="mr-2">{key}: <span className="text-cyan-400">{String(val)}</span></span>
          ))}
        </div>
      )}
    </div>
  );
}

function EntrySignalCard({ signal }) {
  const isLong = signal.direction === 'long';
  return (
    <div className={`border rounded px-3 py-2 ${isLong ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
      <div className="flex items-center gap-2 mb-1">
        <Badge variant="outline" className={`text-[10px] ${isLong ? 'border-emerald-500/40 text-emerald-400' : 'border-red-500/40 text-red-400'}`}>
          {signal.direction.toUpperCase()}
        </Badge>
        <span className="text-xs text-zinc-400 font-mono">{signal.logic_type}</span>
      </div>
      <p className="text-xs text-zinc-300 font-mono break-all">{signal.condition_text}</p>
      {signal.indicators_used?.length > 0 && (
        <p className="text-[10px] text-zinc-500 mt-1">Uses: {signal.indicators_used.join(', ')}</p>
      )}
    </div>
  );
}

function RiskCard({ risk }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className={`p-3 rounded border ${risk.has_stop_loss ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
        <div className="flex items-center gap-2 mb-1">
          {risk.has_stop_loss ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
          <span className="text-xs font-mono text-zinc-300">Stop Loss</span>
        </div>
        <p className="text-lg font-bold text-zinc-200">
          {risk.stop_loss_pips ? `${risk.stop_loss_pips} pips` : 'None'}
        </p>
      </div>
      <div className={`p-3 rounded border ${risk.has_take_profit ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-amber-500/30 bg-amber-500/5'}`}>
        <div className="flex items-center gap-2 mb-1">
          {risk.has_take_profit ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-amber-400" />}
          <span className="text-xs font-mono text-zinc-300">Take Profit</span>
        </div>
        <p className="text-lg font-bold text-zinc-200">
          {risk.take_profit_pips ? `${risk.take_profit_pips} pips` : 'None'}
        </p>
      </div>
      <div className={`p-3 rounded border ${risk.has_trailing_stop ? 'border-cyan-500/30 bg-cyan-500/5' : 'border-zinc-500/30'}`}>
        <div className="flex items-center gap-2 mb-1">
          <TrendingUp className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono text-zinc-300">Trailing Stop</span>
        </div>
        <p className="text-sm text-zinc-200">
          {risk.has_trailing_stop ? (risk.trailing_stop_pips ? `${risk.trailing_stop_pips} pips` : 'Enabled') : 'Disabled'}
        </p>
      </div>
      <div className="p-3 rounded border border-zinc-500/30">
        <div className="flex items-center gap-2 mb-1">
          <Gauge className="w-4 h-4 text-violet-400" />
          <span className="text-xs font-mono text-zinc-300">Position Sizing</span>
        </div>
        <p className="text-sm text-zinc-200 capitalize">{risk.position_sizing}</p>
        {risk.lot_size && <p className="text-xs text-zinc-500">Lot: {risk.lot_size}</p>}
      </div>
    </div>
  );
}

function RecommendationCard({ recommendation, index }) {
  return (
    <div className="flex items-start gap-3 p-3 bg-amber-500/5 border border-amber-500/20 rounded">
      <Lightbulb className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
      <p className="text-sm text-zinc-300">{recommendation}</p>
    </div>
  );
}

export default function AnalyzeBotPage() {
  const navigate = useNavigate();
  const [code, setCode] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState('parsed');

  const handleAnalyze = async () => {
    if (!code.trim()) {
      toast.error('Please enter C# cBot code to analyze');
      return;
    }

    setIsAnalyzing(true);
    setResult(null);

    try {
      const response = await axios.post(`${API}/analyze-cbot`, { code });
      setResult(response.data);
      toast.success(`Analyzed: ${response.data.parsed?.bot_name || 'Bot'}`);
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      toast.error(`Analysis failed: ${detail}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const loadSample = () => {
    setCode(SAMPLE_CODE);
    toast.info('Sample MA Crossover bot loaded');
  };

  return (
    <div className="min-h-screen bg-[#09090B] text-zinc-100" data-testid="analyze-bot-page">
      {/* Header */}
      <div className="h-12 bg-[#0A0A0A] border-b border-white/5 flex items-center justify-between px-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/')}
            className="text-zinc-400 hover:text-zinc-200"
            data-testid="back-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
          <div className="h-6 w-px bg-zinc-700" />
          <h1 className="text-lg font-bold uppercase tracking-wider" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
            <Search className="w-5 h-5 inline mr-2 text-cyan-400" />
            C# cBot Analyzer
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] border-cyan-500/40 text-cyan-400">
            PHASE 1
          </Badge>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-2 gap-4 p-4 h-[calc(100vh-3rem)]">
        {/* Left Panel - Code Input */}
        <div className="flex flex-col bg-[#0A0A0A] border border-white/5 rounded-sm overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 bg-[#18181B]">
            <h2 className="text-sm font-mono uppercase tracking-wider text-zinc-300">
              <Code2 className="w-4 h-4 inline mr-2" />
              C# cBot Code
            </h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadSample}
              className="text-xs text-cyan-400 hover:text-cyan-300"
              data-testid="load-sample-btn"
            >
              Load Sample
            </Button>
          </div>
          
          <div className="flex-1 min-h-0">
            <Editor
              height="100%"
              defaultLanguage="csharp"
              theme="vs-dark"
              value={code}
              onChange={(value) => setCode(value || '')}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                wordWrap: 'on',
                automaticLayout: true,
              }}
              data-testid="code-editor"
            />
          </div>

          <div className="p-3 border-t border-white/5 bg-[#0F0F10]">
            <Button
              onClick={handleAnalyze}
              disabled={isAnalyzing || !code.trim()}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-mono uppercase tracking-wider"
              data-testid="analyze-btn"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4 mr-2" />
                  Analyze Bot
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Right Panel - Results */}
        <div className="flex flex-col bg-[#0A0A0A] border border-white/5 rounded-sm overflow-hidden">
          <div className="px-4 py-2 border-b border-white/5 bg-[#18181B]">
            <h2 className="text-sm font-mono uppercase tracking-wider text-zinc-300">
              <Target className="w-4 h-4 inline mr-2" />
              Analysis Results
            </h2>
          </div>

          {!result ? (
            <div className="flex-1 flex items-center justify-center text-zinc-500">
              <div className="text-center">
                <Search className="w-12 h-12 mx-auto mb-4 opacity-30" />
                <p className="text-sm font-mono">Paste C# code and click "Analyze Bot"</p>
                <p className="text-xs mt-2 text-zinc-600">Or load the sample bot to try it out</p>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Summary Header */}
              <div className="p-4 border-b border-white/5 bg-[#0F0F10]">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-lg font-bold text-zinc-100">{result.parsed?.bot_name || 'Unknown Bot'}</h3>
                  <Badge variant="outline" className="border-violet-500/40 text-violet-400 capitalize">
                    {result.strategy?.category?.replace('_', ' ') || 'Unknown'}
                  </Badge>
                </div>
                <p className="text-sm text-zinc-400">{result.message}</p>
                
                {/* Quick Stats */}
                <div className="grid grid-cols-4 gap-2 mt-3">
                  <div className="bg-zinc-800/50 rounded px-2 py-1 text-center">
                    <p className="text-lg font-bold text-blue-400">{result.parsed?.indicators?.length || 0}</p>
                    <p className="text-[10px] text-zinc-500 uppercase">Indicators</p>
                  </div>
                  <div className="bg-zinc-800/50 rounded px-2 py-1 text-center">
                    <p className="text-lg font-bold text-emerald-400">{result.parsed?.entry_conditions?.length || 0}</p>
                    <p className="text-[10px] text-zinc-500 uppercase">Signals</p>
                  </div>
                  <div className="bg-zinc-800/50 rounded px-2 py-1 text-center">
                    <p className="text-lg font-bold text-amber-400">{result.strategy?.analysis?.completeness?.score || 0}%</p>
                    <p className="text-[10px] text-zinc-500 uppercase">Complete</p>
                  </div>
                  <div className="bg-zinc-800/50 rounded px-2 py-1 text-center">
                    <p className="text-lg font-bold text-cyan-400">{result.strategy?.analysis?.risk_score?.score || 0}</p>
                    <p className="text-[10px] text-zinc-500 uppercase">Risk Score</p>
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
                <TabsList className="mx-4 mt-2 bg-zinc-800/50" data-testid="result-tabs">
                  <TabsTrigger value="parsed" className="text-xs font-mono">Parsed</TabsTrigger>
                  <TabsTrigger value="strategy" className="text-xs font-mono">Strategy</TabsTrigger>
                  <TabsTrigger value="recommendations" className="text-xs font-mono">Tips</TabsTrigger>
                </TabsList>

                <div className="flex-1 overflow-y-auto p-4">
                  <TabsContent value="parsed" className="mt-0 space-y-4" data-testid="parsed-tab">
                    {/* Indicators */}
                    <SectionCard title="Indicators" icon={BarChart3}>
                      {result.parsed?.indicators?.length > 0 ? (
                        <div className="grid gap-2">
                          {result.parsed.indicators.map((ind, idx) => (
                            <IndicatorBadge key={idx} indicator={ind} />
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-zinc-500">No indicators detected</p>
                      )}
                    </SectionCard>

                    {/* Entry Conditions */}
                    <SectionCard title="Entry Conditions" icon={Target}>
                      {result.parsed?.entry_conditions?.length > 0 ? (
                        <div className="space-y-2">
                          {result.parsed.entry_conditions.map((entry, idx) => (
                            <EntrySignalCard key={idx} signal={entry} />
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-zinc-500">No entry conditions detected</p>
                      )}
                    </SectionCard>

                    {/* Risk Management */}
                    <SectionCard title="Risk Management" icon={Shield}>
                      {result.parsed?.risk_management ? (
                        <RiskCard risk={result.parsed.risk_management} />
                      ) : (
                        <p className="text-sm text-zinc-500">No risk management detected</p>
                      )}
                    </SectionCard>

                    {/* Parameters */}
                    {result.parsed?.parameters && Object.keys(result.parsed.parameters).length > 0 && (
                      <SectionCard title="Parameters" icon={Code2}>
                        <div className="grid grid-cols-2 gap-2">
                          {Object.entries(result.parsed.parameters).map(([name, info]) => (
                            <div key={name} className="bg-zinc-800/50 rounded px-3 py-2">
                              <p className="text-xs font-mono text-zinc-300">{name}</p>
                              <p className="text-[10px] text-zinc-500">
                                Type: {info.type} | Default: <span className="text-cyan-400">{String(info.default)}</span>
                              </p>
                            </div>
                          ))}
                        </div>
                      </SectionCard>
                    )}
                  </TabsContent>

                  <TabsContent value="strategy" className="mt-0 space-y-4" data-testid="strategy-tab">
                    {/* Strategy Summary */}
                    <SectionCard title="Strategy Profile" icon={TrendingUp}>
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <p className="text-[10px] text-zinc-500 uppercase mb-1">Category</p>
                            <p className="text-sm text-zinc-200 capitalize">{result.strategy?.category?.replace('_', ' ')}</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-zinc-500 uppercase mb-1">Complexity</p>
                            <p className="text-sm text-zinc-200 capitalize">{result.strategy?.analysis?.complexity}</p>
                          </div>
                        </div>
                        <div>
                          <p className="text-[10px] text-zinc-500 uppercase mb-1">Description</p>
                          <p className="text-sm text-zinc-300">{result.strategy?.description}</p>
                        </div>
                      </div>
                    </SectionCard>

                    {/* Risk Assessment */}
                    <SectionCard title="Risk Assessment" icon={Shield}>
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-zinc-400">Risk Level</span>
                          <Badge 
                            variant="outline" 
                            className={`capitalize ${
                              result.strategy?.analysis?.risk_score?.level === 'low' 
                                ? 'border-emerald-500/40 text-emerald-400'
                                : result.strategy?.analysis?.risk_score?.level === 'medium'
                                ? 'border-amber-500/40 text-amber-400'
                                : 'border-red-500/40 text-red-400'
                            }`}
                          >
                            {result.strategy?.analysis?.risk_score?.level || 'Unknown'}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-zinc-400">Risk Score</span>
                          <span className="text-lg font-bold text-zinc-200">{result.strategy?.analysis?.risk_score?.score}/100</span>
                        </div>
                        {result.strategy?.analysis?.risk_score?.issues?.length > 0 && (
                          <div className="space-y-1 mt-2">
                            {result.strategy.analysis.risk_score.issues.map((issue, idx) => (
                              <div key={idx} className="flex items-start gap-2 text-xs text-amber-400">
                                <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                                <span>{issue}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </SectionCard>

                    {/* Completeness */}
                    <SectionCard title="Completeness Check" icon={Gauge}>
                      <div className="space-y-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-zinc-400">Overall</span>
                          <span className="text-lg font-bold text-zinc-200">
                            {result.strategy?.analysis?.completeness?.score}%
                          </span>
                        </div>
                        <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500"
                            style={{ width: `${result.strategy?.analysis?.completeness?.score || 0}%` }}
                          />
                        </div>
                        {result.strategy?.analysis?.completeness?.checks && (
                          <div className="grid grid-cols-2 gap-2 mt-3">
                            {Object.entries(result.strategy.analysis.completeness.checks).map(([check, passed]) => (
                              <div key={check} className="flex items-center gap-2 text-xs">
                                {passed ? (
                                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                ) : (
                                  <XCircle className="w-3 h-3 text-red-400" />
                                )}
                                <span className={passed ? 'text-zinc-300' : 'text-zinc-500'}>
                                  {check.replace(/_/g, ' ').replace('has ', '')}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </SectionCard>
                  </TabsContent>

                  <TabsContent value="recommendations" className="mt-0 space-y-3" data-testid="recommendations-tab">
                    {result.strategy?.analysis?.recommendations?.length > 0 ? (
                      result.strategy.analysis.recommendations.map((rec, idx) => (
                        <RecommendationCard key={idx} recommendation={rec} index={idx} />
                      ))
                    ) : (
                      <div className="text-center py-8 text-zinc-500">
                        <CheckCircle2 className="w-12 h-12 mx-auto mb-4 text-emerald-400" />
                        <p className="text-sm font-mono">No recommendations - strategy looks good!</p>
                      </div>
                    )}

                    {result.parsed?.warnings?.length > 0 && (
                      <SectionCard title="Parser Warnings" icon={AlertTriangle} className="mt-4">
                        <div className="space-y-2">
                          {result.parsed.warnings.map((warning, idx) => (
                            <div key={idx} className="flex items-start gap-2 text-xs text-amber-400">
                              <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                              <span>{warning}</span>
                            </div>
                          ))}
                        </div>
                      </SectionCard>
                    )}
                  </TabsContent>
                </div>
              </Tabs>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
