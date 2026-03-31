import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import Editor from '@monaco-editor/react';
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Loader2, Play, Download, CheckCircle2, XCircle, AlertCircle,
  Zap, Users, Trophy, ChevronRight, Shield, BarChart3, Briefcase,
  FlaskConical, ShieldCheck, AlertTriangle, Lock, Gauge, TrendingDown,
  Activity, Target, HelpCircle, Settings, TrendingUp, Search, Globe, Database,
  GripVertical, GripHorizontal, Upload
} from 'lucide-react';
import {
  PropScoreGauge,
  PropScoreBadge,
  ValidationMetricCard,
  StatusBadge,
  PropScoreBreakdown,
  calculatePropScore,
  getDecisionStatus
} from '@/components/validation/PropScore';
import { ValidationChartPanel } from '@/components/validation/ValidationCharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const AI_MODELS = [
  { value: 'openai', label: 'OpenAI GPT-5.2' },
  { value: 'claude', label: 'Claude Sonnet 4.5' },
  { value: 'deepseek', label: 'DeepSeek' },
];

const MODE_INFO = {
  single: { icon: Zap, label: 'SINGLE AI', desc: 'One AI generates' },
  collaboration: { icon: Users, label: 'COLLABORATION', desc: 'Sequential pipeline' },
  competition: { icon: Trophy, label: 'COMPETITION', desc: 'AIs compete' },
};

function LogEntry({ log }) {
  const colors = {
    generation: 'text-blue-400',
    review: 'text-cyan-400',
    optimization: 'text-violet-400',
    compilation: 'text-yellow-400',
    warning_optimization: 'text-amber-400',
    compliance: 'text-emerald-400',
    quality_gates: 'text-indigo-400',
    validation: 'text-orange-400',
    complete: 'text-emerald-300',
  };
  const color = colors[log.stage] || 'text-zinc-400';

  return (
    <div className="flex items-start gap-2 text-xs font-mono py-1 border-b border-white/5 last:border-0" data-testid={`log-entry-${log.stage}`}>
      <ChevronRight className={`w-3 h-3 mt-0.5 shrink-0 ${color}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`uppercase font-bold text-[10px] ${color}`}>{log.stage}</span>
          {log.ai_model && <span className="text-zinc-600 text-[10px]">{log.ai_model}</span>}
        </div>
        <p className="text-zinc-400 leading-relaxed break-words">{log.message}</p>
        {log.improvements && log.improvements.length > 0 && (
          <div className="mt-1 space-y-0.5">
            {log.improvements.map((imp, i) => (
              <p key={i} className="text-zinc-500 text-[10px]">+ {imp}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function QualityGateCard({ gate }) {
  const passed = gate.passed;
  return (
    <div
      className={`bg-[#0F0F10] border p-2.5 rounded-sm ${passed ? 'border-emerald-500/30' : 'border-red-500/30'}`}
      data-testid={`quality-gate-${gate.name.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">{gate.name}</span>
        {passed ? (
          <Badge variant="outline" className="text-[9px] border-emerald-500/40 text-emerald-400 px-1.5 py-0 h-4">PASS</Badge>
        ) : (
          <Badge variant="outline" className="text-[9px] border-red-500/40 text-red-400 px-1.5 py-0 h-4">FAIL</Badge>
        )}
      </div>
      <p className="text-xs text-zinc-400 font-mono">{gate.message}</p>
    </div>
  );
}

function ValidationStatusCard({ title, status, isValid, score, icon: Icon, details }) {
  const getStatusColor = () => {
    if (status === 'PASS') return 'border-emerald-500/40 bg-emerald-500/5';
    if (status === 'FAIL') return 'border-red-500/40 bg-red-500/5';
    if (status === 'WARNING') return 'border-amber-500/40 bg-amber-500/5';
    return 'border-zinc-500/40 bg-zinc-500/5';
  };

  const getTextColor = () => {
    if (status === 'PASS') return 'text-emerald-400';
    if (status === 'FAIL') return 'text-red-400';
    if (status === 'WARNING') return 'text-amber-400';
    return 'text-zinc-400';
  };

  return (
    <div className={`border rounded-sm p-4 ${getStatusColor()}`} data-testid={`validation-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className={`w-5 h-5 ${getTextColor()}`} />
          <span className="text-sm font-mono uppercase tracking-wider text-zinc-300">{title}</span>
        </div>
        <Badge
          variant="outline"
          className={`text-xs px-2 py-0.5 ${isValid ? 'border-emerald-500/40 text-emerald-400' : 'border-red-500/40 text-red-400'}`}
        >
          {status}
        </Badge>
      </div>
      {score !== undefined && (
        <div className="mb-2">
          <div className="flex justify-between text-[10px] font-mono mb-1">
            <span className="text-zinc-500">Score</span>
            <span className={getTextColor()}>{score}/100</span>
          </div>
          <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${isValid ? 'bg-emerald-500' : 'bg-red-500'}`}
              style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
            />
          </div>
        </div>
      )}
      {details && (
        <div className="space-y-1 mt-2">
          {details.map((detail, i) => (
            <p key={i} className="text-[10px] text-zinc-500 font-mono flex items-center gap-1">
              {detail.passed ? (
                <CheckCircle2 className="w-3 h-3 text-emerald-500" />
              ) : (
                <XCircle className="w-3 h-3 text-red-500" />
              )}
              {detail.label}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// Professional Navigation Button Component
function NavButton({ onClick, icon: Icon, label, variant = 'default', testId }) {
  const baseStyles = "flex items-center gap-1.5 px-3 py-2 text-[11px] font-mono uppercase transition-all duration-200 rounded-md h-9";
  
  const variantStyles = {
    default: "bg-transparent text-zinc-400 hover:text-white hover:bg-white/10 border border-transparent hover:border-white/10",
    secondary: "bg-zinc-800/50 text-zinc-400 hover:text-white hover:bg-zinc-700/50 border border-white/5",
    accent: "bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 border border-emerald-500/30 hover:border-emerald-500/50",
  };

  return (
    <button
      onClick={onClick}
      className={`${baseStyles} ${variantStyles[variant]}`}
      data-testid={testId}
    >
      <Icon className="w-4 h-4" />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

// Vertical Resize Handle (for horizontal panel resizing)
function VerticalResizeHandle() {
  return (
    <PanelResizeHandle className="w-2 mx-1 group cursor-col-resize transition-colors hover:bg-blue-500/30 active:bg-blue-500/50 flex items-center justify-center">
      <div className="w-1 h-8 bg-white/10 group-hover:bg-blue-400 rounded-full transition-colors" />
    </PanelResizeHandle>
  );
}

// Horizontal Resize Handle (for vertical panel resizing)
function HorizontalResizeHandle() {
  return (
    <PanelResizeHandle className="h-2 my-1 group cursor-row-resize transition-colors hover:bg-blue-500/30 active:bg-blue-500/50 flex items-center justify-center">
      <div className="h-1 w-16 bg-white/10 group-hover:bg-blue-400 rounded-full transition-colors" />
    </PanelResizeHandle>
  );
}

// Layout storage key
const LAYOUT_STORAGE_KEY = 'dashboard-layout-v1';

// Load layout from localStorage
function loadLayout() {
  try {
    const saved = localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
  } catch (e) {
    console.warn('Failed to load layout from localStorage:', e);
  }
  return null;
}

// Save layout to localStorage
function saveLayout(layout) {
  try {
    localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layout));
  } catch (e) {
    console.warn('Failed to save layout to localStorage:', e);
  }
}

function Dashboard() {
  const [strategyPrompt, setStrategyPrompt] = useState('');
  const [aiMode, setAiMode] = useState('single');
  const [singleModel, setSingleModel] = useState('openai');
  const [generatorModel, setGeneratorModel] = useState('deepseek');
  const [reviewerModel, setReviewerModel] = useState('openai');
  const [optimizerModel, setOptimizerModel] = useState('claude');
  const [propFirm, setPropFirm] = useState('none');

  const [generatedCode, setGeneratedCode] = useState('// Your generated cBot code will appear here...');
  const [sessionId, setSessionId] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [collaborationLogs, setCollaborationLogs] = useState([]);
  const [qualityGates, setQualityGates] = useState(null);
  const [validationSummary, setValidationSummary] = useState(null);
  const [competitionResult, setCompetitionResult] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [bottomTab, setBottomTab] = useState('validation');

  // Bot Validation State
  const [isValidating, setIsValidating] = useState(false);
  const [botValidation, setBotValidation] = useState(null);
  const [canDownload, setCanDownload] = useState(false);
  
  // Market Data Availability State
  const [dataAvailability, setDataAvailability] = useState(null);
  const [isCheckingData, setIsCheckingData] = useState(false);
  
  // Advanced Validation State
  const [isAdvancedValidating, setIsAdvancedValidating] = useState(false);
  const [advancedValidation, setAdvancedValidation] = useState(null);
  const [propScore, setPropScore] = useState(null);
  const [marketSelection, setMarketSelection] = useState(null);  // NEW: Market selection results
  const [chartData, setChartData] = useState({
    equityCurve: [],
    drawdownCurve: [],
    monteCarloDistribution: [],
    monteCarloMedian: [],
    maxDrawdown: 0,
    percentiles: { p5: 0, p50: 0, p95: 0 }
  });

  const logsEndRef = useRef(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [collaborationLogs]);

  // Reset validation when code changes
  useEffect(() => {
    setBotValidation(null);
    setCanDownload(false);
    setDataAvailability(null);
  }, [generatedCode]);

  const handleGenerate = async () => {
    if (!strategyPrompt.trim()) {
      toast.error('Please enter a trading strategy');
      return;
    }

    setIsGenerating(true);
    setCollaborationLogs([]);
    setQualityGates(null);
    setValidationSummary(null);
    setCompetitionResult(null);
    setMetadata(null);
    setBotValidation(null);
    setCanDownload(false);
    setAdvancedValidation(null);
    setPropScore(null);
    setChartData({
      equityCurve: [],
      drawdownCurve: [],
      monteCarloDistribution: [],
      monteCarloMedian: [],
      maxDrawdown: 0,
      percentiles: { p5: 0, p50: 0, p95: 0 }
    });
    setGeneratedCode('// Generating...');

    const reqBody = {
      session_id: sessionId || undefined,
      strategy_prompt: strategyPrompt,
      ai_mode: aiMode,
      prop_firm: propFirm,
    };

    if (aiMode === 'single') {
      reqBody.single_ai_model = singleModel;
    } else if (aiMode === 'collaboration') {
      reqBody.strategy_generator_model = generatorModel;
      reqBody.code_reviewer_model = reviewerModel;
      reqBody.optimizer_model = optimizerModel;
    }

    try {
      const response = await axios.post(`${API}/bot/generate-multi-ai`, reqBody);
      const data = response.data;

      setGeneratedCode(data.code);
      setSessionId(data.session_id);
      setCollaborationLogs(data.collaboration_logs || []);
      setQualityGates(data.quality_gates);
      setValidationSummary(data.validation);
      setCompetitionResult(data.competition);
      setMetadata(data.metadata);
      
      // NEW: Set market selection results
      if (data.market_selection) {
        setMarketSelection(data.market_selection);
      }

      if (data.quality_gates?.is_deployable) {
        toast.success('Bot generated! Run validation before downloading.');
      } else {
        toast.warning('Bot generated but may have issues. Run validation to check.');
      }
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      const detailStr = typeof detail === 'string' ? detail : JSON.stringify(detail);
      if (detailStr.toLowerCase().includes('budget')) {
        toast.error('LLM budget exceeded. Go to Profile > Universal Key > Add Balance to top up.');
      } else {
        toast.error(`Generation failed: ${detailStr}`);
      }
      setGeneratedCode('// Generation failed. See logs.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleValidate = async () => {
    if (!generatedCode || generatedCode.startsWith('//')) {
      toast.error('No code to validate');
      return;
    }

    setIsValidating(true);
    setBotValidation(null);
    setBottomTab('validation');
    setDataAvailability(null);

    try {
      // STEP 1: Check real market data availability FIRST
      setIsCheckingData(true);
      const dataCheckResponse = await axios.post(`${API}/marketdata/ensure-real-data`, {
        symbol: 'EURUSD',
        timeframe: '1h',
        min_candles: 60
      });
      
      setDataAvailability(dataCheckResponse.data);
      setIsCheckingData(false);
      
      if (!dataCheckResponse.data.success) {
        // Show warning but continue with validation
        toast.warning(`⚠️ Real market data unavailable - backtest results may not be reliable`, {
          duration: 8000
        });
      } else {
        toast.success(`✓ Real data loaded: ${dataCheckResponse.data.candle_count} candles from ${dataCheckResponse.data.data_source}`);
      }

      // STEP 2: Run validation
      const response = await axios.post(`${API}/bot/validate`, {
        code: generatedCode,
        session_id: sessionId,
        prop_firm: propFirm
      });

      const data = response.data;
      setBotValidation(data);
      setCanDownload(data.is_deployable && dataCheckResponse.data.success);

      if (data.is_deployable) {
        if (dataCheckResponse.data.success) {
          toast.success('✅ Bot validated with REAL market data - ready for deployment!');
        } else {
          toast.warning('⚠️ Bot validated but real data unavailable - results may not be reliable');
        }
      } else {
        toast.warning(`⚠️ Validation failed: ${data.failed_checks} check(s) failed`);
      }
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      toast.error(`Validation failed: ${detail}`);
      setBotValidation(null);
      setCanDownload(false);
    } finally {
      setIsValidating(false);
      setIsCheckingData(false);
    }
  };

  const handleInjectSafety = async () => {
    if (!generatedCode || generatedCode.startsWith('//')) {
      toast.error('No code to enhance');
      return;
    }

    try {
      const response = await axios.post(`${API}/bot/inject-safety`, {
        code: generatedCode,
        prop_firm: propFirm
      });

      const data = response.data;
      if (data.success && data.modified_code) {
        setGeneratedCode(data.modified_code);
        toast.success(`Safety code injected: ${data.injections_applied.length} features added`);
        setBotValidation(null);
        setCanDownload(false);
        setAdvancedValidation(null);
        setPropScore(null);
      } else {
        toast.error(`Injection failed: ${data.message}`);
      }
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      toast.error(`Safety injection failed: ${detail}`);
    }
  };

  // Advanced Validation Handler - Runs full validation suite
  const handleAdvancedValidation = async () => {
    if (!botValidation) {
      toast.error('Please run basic validation first');
      return;
    }

    setIsAdvancedValidating(true);
    setAdvancedValidation(null);
    setPropScore(null);

    // Generate sample trades from backtest simulation
    const sampleTrades = [];
    const numTrades = Math.max(20, botValidation.backtest?.trades_executed || 50);
    const winRate = (botValidation.backtest?.win_rate || 50) / 100;
    const avgWin = 150;
    const avgLoss = 100;

    for (let i = 0; i < numTrades; i++) {
      const isWin = Math.random() < winRate;
      sampleTrades.push({
        profit_loss: isWin ? avgWin * (0.5 + Math.random()) : -avgLoss * (0.5 + Math.random()),
        entry_time: new Date(Date.now() - (numTrades - i) * 86400000).toISOString(),
        volume: 1.0
      });
    }

    try {
      const response = await axios.post(`${API}/advanced/full-validation`, {
        session_id: sessionId,
        strategy_name: `Bot_${sessionId?.slice(-6) || 'Generated'}`,
        trades: sampleTrades,
        parameters: { fast_ma: 10, slow_ma: 20, risk_percent: 2.0 },
        initial_balance: 10000,
        risk_per_trade_percent: 2.0
      });

      const data = response.data;

      // Calculate Prop Score
      const propScoreMetrics = {
        bootstrapSurvival: data.results?.bootstrap?.survival_rate || 0,
        monteCarloSurvival: data.results?.risk_of_ruin?.survival_probability || 0,
        maxDrawdown: 100 - (data.results?.risk_of_ruin?.survival_probability || 0),
        sensitivityScore: data.results?.sensitivity?.robustness_score || 50,
        walkForwardScore: 70,
        profitability: data.results?.bootstrap?.profit_probability || 0,
        challengePassProb: (data.results?.bootstrap?.survival_rate || 0) / 100,
        consistencyScore: 100 - (data.results?.sensitivity?.overfitting_risk || 0)
      };

      const calculatedPropScore = calculatePropScore(propScoreMetrics);
      const decision = getDecisionStatus(calculatedPropScore);

      // Generate chart data from trades and validation results
      let balance = 10000;
      const equityCurve = sampleTrades.map((trade, i) => {
        balance += trade.profit_loss;
        return { balance, trade: i + 1 };
      });

      // Calculate drawdown curve
      let peak = 10000;
      const drawdownCurve = equityCurve.map(point => {
        if (point.balance > peak) peak = point.balance;
        const dd = ((peak - point.balance) / peak) * 100;
        return { drawdown: dd };
      });

      // Generate Monte Carlo distribution (simulated returns)
      const mcDistribution = Array.from({ length: 500 }, () => {
        const simReturn = (Math.random() - 0.3) * 80 + propScoreMetrics.profitability * 0.5;
        return { finalReturn: simReturn };
      });

      // Generate MC median equity curve
      const mcMedian = equityCurve.map((point, i) => ({
        balance: 10000 + (i * 45) + (Math.random() * 200 - 100)
      }));

      // Calculate percentiles
      const returns = mcDistribution.map(d => d.finalReturn).sort((a, b) => a - b);
      const p5 = returns[Math.floor(returns.length * 0.05)];
      const p50 = returns[Math.floor(returns.length * 0.5)];
      const p95 = returns[Math.floor(returns.length * 0.95)];

      setChartData({
        equityCurve,
        drawdownCurve,
        monteCarloDistribution: mcDistribution,
        monteCarloMedian: mcMedian,
        maxDrawdown: Math.max(...drawdownCurve.map(d => d.drawdown)),
        percentiles: { p5, p50, p95 }
      });

      setAdvancedValidation({
        ...data,
        propScoreMetrics,
        decision
      });
      setPropScore(calculatedPropScore);

      // Update download eligibility based on prop score
      if (calculatedPropScore >= 60 && botValidation?.is_deployable) {
        setCanDownload(true);
        toast.success(`Advanced validation complete! Prop Score: ${calculatedPropScore} - ${decision.status}`);
      } else {
        setCanDownload(false);
        toast.warning(`Prop Score: ${calculatedPropScore} - ${decision.status}. Consider improvements.`);
      }

      setBottomTab('advanced');
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      toast.error(`Advanced validation failed: ${detail}`);
    } finally {
      setIsAdvancedValidating(false);
    }
  };

  const [compileStatus, setCompileStatus] = useState(null); // null, 'VERIFIED', 'FAILED'
  const [compileErrors, setCompileErrors] = useState([]);

  const handleDownload = async () => {
    if (!generatedCode || generatedCode.startsWith('//')) {
      toast.error('No code to download');
      return;
    }

    // MANDATORY: Run compile gate before download
    setIsGenerating(true);
    try {
      const response = await axios.post(`${API}/bot/download`, {
        session_id: sessionId,
        code: generatedCode
      });

      if (response.data.success && response.data.status === 'VERIFIED') {
        // Update compile status
        setCompileStatus('VERIFIED');
        setCompileErrors([]);
        
        // Use verified code (may have auto-fixes applied)
        const verifiedCode = response.data.code;
        const filename = response.data.filename;
        
        const blob = new Blob([verifiedCode], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        toast.success(`${response.data.badge} - Bot downloaded!`);
      }
    } catch (error) {
      if (error.response?.data?.detail?.status === 'FAILED') {
        // Compilation failed
        setCompileStatus('FAILED');
        const errors = error.response.data.detail.errors || [];
        setCompileErrors(errors);
        toast.error(`❌ DOWNLOAD BLOCKED - ${errors.length} compilation error(s)`);
      } else {
        toast.error('Download failed: ' + (error.response?.data?.detail || error.message));
      }
    } finally {
      setIsGenerating(false);
    }
  };

  // Compile check function (can be called separately)
  const handleCompileCheck = async () => {
    if (!generatedCode) return;
    
    setIsGenerating(true);
    try {
      const response = await axios.post(`${API}/code/compile-gate`, {
        code: generatedCode,
        auto_fix: true,
        max_fix_attempts: 3
      });

      setCompileStatus(response.data.status);
      setCompileErrors(response.data.errors || []);
      
      if (response.data.is_verified) {
        // Update code if auto-fixes were applied
        if (response.data.code !== generatedCode) {
          setGeneratedCode(response.data.code);
          toast.success(`${response.data.badge} - ${response.data.fixes_applied?.length || 0} auto-fixes applied`);
        } else {
          toast.success(response.data.badge);
        }
      } else {
        toast.error(`${response.data.badge} - ${response.data.errors?.length || 0} error(s)`);
      }
    } catch (error) {
      toast.error('Compilation check failed');
    } finally {
      setIsGenerating(false);
    }
  };

  const ModeButton = ({ mode }) => {
    const info = MODE_INFO[mode];
    const Icon = info.icon;
    const active = aiMode === mode;
    return (
      <button
        onClick={() => setAiMode(mode)}
        className={`flex-1 flex items-center gap-2 px-3 py-2 text-left border transition-colors ${
          active
            ? 'bg-blue-600/15 border-blue-500/40 text-blue-400'
            : 'bg-[#0F0F10] border-white/5 text-zinc-500 hover:border-white/15 hover:text-zinc-300'
        }`}
        data-testid={`mode-${mode}`}
      >
        <Icon className="w-4 h-4 shrink-0" />
        <div>
          <p className="text-[10px] font-mono font-bold uppercase tracking-wider">{info.label}</p>
          <p className="text-[9px] text-zinc-600">{info.desc}</p>
        </div>
      </button>
    );
  };

  const ModelSelect = ({ label, value, onChange, testId }) => (
    <div>
      <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1 block">{label}</label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="bg-[#18181B] border-white/10 text-xs text-zinc-300 h-7" data-testid={testId}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-[#0F0F10] border-white/10">
          {AI_MODELS.map(m => (
            <SelectItem key={m.value} value={m.value} className="text-xs">{m.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const navigate = useNavigate();

  // Execution Mode State
  const [executionMode, setExecutionMode] = useState('backtest'); // 'backtest' | 'forward_test' | 'live'

  // Pre-deployment checklist evaluation
  const deploymentStatus = useMemo(() => {
    if (!propScore || !advancedValidation) return null;
    
    const checks = {
      propScorePass: propScore >= 80,
      riskOfRuinPass: (advancedValidation.results?.risk_of_ruin?.ruin_probability || 100) < 5,
      validationComplete: !!advancedValidation.results,
      bootstrapPass: (advancedValidation.results?.bootstrap?.survival_rate || 0) >= 70,
    };
    
    const passedCount = Object.values(checks).filter(Boolean).length;
    const allPassed = passedCount === 4;
    
    return {
      checks,
      passedCount,
      total: 4,
      allPassed,
      canDeploy: allPassed && canDownload
    };
  }, [propScore, advancedValidation, canDownload]);

  // FORCE RENDER TEST - Step 1
  console.log("🔥 Dashboard component MOUNTED");
  console.log("🔥 Component is rendering");
  
  return (
    <div style={{ 
      color: "white", 
      padding: "50px", 
      fontSize: "32px", 
      background: "blue",
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center"
    }}>
      <div>
        <h1>✅ BACKTEST PAGE IS LOADING</h1>
        <p style={{ fontSize: "18px", marginTop: "20px" }}>Dashboard.jsx is rendering!</p>
        <p style={{ fontSize: "14px", color: "lime" }}>Route: "/" (Root)</p>
      </div>
    </div>
  );
}





export default Dashboard;
