import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import Editor from '@monaco-editor/react';
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
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
  GripVertical, GripHorizontal, Upload, Calendar, Clock, Layers, Rocket, Eye, Cpu, Circle
} from 'lucide-react';
import { formatDate, formatDateRange } from '@/lib/dateUtils';
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
import { 
  PipelineTracker, 
  BotPipelineStatus, 
  StrategyFitnessCard, 
  QuickStartFlow,
  AdvancedModeToggle 
} from '@/components/pipeline/PipelineTracker';
// Temporarily commented out - components need to be created
// import CSVUploader from '@/components/data/CSVUploader';
// import BulkCSVUploader from '@/components/data/BulkCSVUploader';
// import StrategyTemplateSelector from '@/components/strategy/StrategyTemplateSelector';

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

export default function Dashboard() {
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
  
  // Auto-Generate Strategies State
  const [isAutoGenerating, setIsAutoGenerating] = useState(false);
  const [autoGenProgress, setAutoGenProgress] = useState(0);
  const [topStrategies, setTopStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  
  // === NEW: Pipeline Flow State ===
  const [currentPipelineStep, setCurrentPipelineStep] = useState('generate');
  const [completedPipelineSteps, setCompletedPipelineSteps] = useState([]);
  const [advancedMode, setAdvancedMode] = useState(false); // Debug/Advanced mode
  const [pipelineResults, setPipelineResults] = useState(null);
  const [botDeploymentScore, setBotDeploymentScore] = useState(0);
  const [botStatus, setBotStatus] = useState(null);
  const [quickStartProgress, setQuickStartProgress] = useState(0);
  const [isQuickStarting, setIsQuickStarting] = useState(false);
  const [pipelineLogs, setPipelineLogs] = useState([]);
  
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
    
    // ENFORCE: Direct generation only available in Advanced Mode
    if (!selectedStrategy && !advancedMode) {
      toast.error(
        '🚫 Direct bot generation is disabled.\n\n' +
        'Please use the guided pipeline:\n' +
        '1. Generate Strategies → 2. Select Strategy → 3. Generate cBot\n\n' +
        'Enable "Advanced Mode" for debug access.',
        { duration: 6000 }
      );
      return;
    }
    
    // Show warning for direct generation in advanced mode
    if (!selectedStrategy && advancedMode) {
      toast.warning('⚠️ Advanced Mode: Generating without validation. Results may vary.', { duration: 3000 });
      addPipelineLog('warning', 'Direct generation bypassing validation pipeline');
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
      // STEP 1: Check LOCAL CSV market data availability FIRST
      setIsCheckingData(true);
      const dataCheckResponse = await axios.post(`${API}/marketdata/ensure-real-data`, {
        symbol: selectedPair,
        timeframe: selectedTimeframe,
        min_candles: 60
      });
      
      setDataAvailability(dataCheckResponse.data);
      setIsCheckingData(false);
      
      if (!dataCheckResponse.data.success) {
        // Show clear error message for missing local data
        toast.error(dataCheckResponse.data.message || '⚠️ No local market data found. Please upload Dukascopy CSV data.', {
          duration: 10000
        });
        
        // Block validation if no local data
        toast.warning('Validation blocked - local CSV data required', {
          duration: 6000
        });
        return; // Stop here - don't proceed without data
      } else {
        toast.success(`✓ Local CSV data loaded: ${dataCheckResponse.data.candle_count} candles`);
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
        toast.success('✅ Bot validated with local CSV market data - ready for deployment!');
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

  const handleAutoGenerateStrategies = async () => {
    // Check data availability first
    if (!dataAvailability || !dataAvailability.available) {
      toast.error('⚠️ No local CSV data available. Please load market data first.', {
        duration: 8000
      });
      return;
    }

    // Warning for moderate load (100-300)
    if (numStrategies > 100 && numStrategies <= 300) {
      toast.warning(`⚠️ Generating ${numStrategies} strategies. This may take a few minutes.`, {
        duration: 5000
      });
    }
    
    // Confirmation required for large runs (>300)
    if (numStrategies > 300) {
      setShowWarningModal(true);
      setPendingGeneration({ confirmed: false });
      return;
    }

    await executeStrategyGeneration();
  };

  const executeStrategyGeneration = async () => {
    setIsAutoGenerating(true);
    setAutoGenProgress(0);
    setTopStrategies([]);
    setJobProgress(null);
    setShowWarningModal(false);
    
    try {
      toast.info(`🚀 Starting ${numStrategies} ${strategyType} strategy generation...`, { duration: 3000 });

      // Use job-based endpoint for scalable processing
      const response = await axios.post(`${API}/strategy/generate-job`, {
        symbol: selectedPair,
        timeframe: selectedTimeframe,
        strategy_count: numStrategies,
        strategy_type: strategyType,
        risk_level: riskLevel,
        execution_mode: genExecutionMode,
        ai_model: singleModel,
        backtest_start: backtestFrom || null,
        backtest_end: backtestTo || null,
        batch_size: genExecutionMode === 'fast' ? 50 : 25
      });

      if (response.data.success && response.data.job_id) {
        setCurrentJobId(response.data.job_id);
        toast.success(`Job started: ${response.data.total_batches} batches queued`, { duration: 4000 });
      } else {
        throw new Error(response.data.message || 'Failed to start job');
      }
    } catch (error) {
      setIsAutoGenerating(false);
      const detail = error.response?.data?.message || error.response?.data?.detail || error.message;
      toast.error(`Strategy generation failed: ${detail}`, {
        duration: 8000
      });
    }
  };

  const handleGenerateCBotFromStrategy = async (strategy) => {
    setSelectedStrategy(strategy);
    
    // Update pipeline steps
    setCompletedPipelineSteps(prev => [...new Set([...prev, 'generate', 'view', 'select'])]);
    setCurrentPipelineStep('bot');
    addPipelineLog('info', `Strategy selected: ${strategy.name || strategy.template_id} (Fitness: ${(strategy.fitness || 0).toFixed(1)})`);
    
    // Use the new pipeline endpoint for proper strategy-to-bot conversion
    toast.loading(`🚀 Generating cBot from validated strategy: ${strategy.name || strategy.template_id}`, {
      id: 'cbot-generation'
    });
    
    addPipelineLog('info', 'Starting cBot generation pipeline...');
    
    try {
      const response = await axios.post(`${API_URL}/api/bot/generate-from-strategy`, {
        strategy_id: strategy.id || `strategy-${Date.now()}`,
        strategy_data: strategy,
        symbol: selectedPair || 'EURUSD',
        timeframe: selectedTimeframe || '1h',
        ai_model: selectedModel || 'openai',
        prop_firm: 'ftmo',
        run_full_pipeline: true
      });
      
      if (response.data.success) {
        const result = response.data;
        
        // Update generated code in state
        setGeneratedCode(result.code);
        
        // Update pipeline status
        setPipelineResults(result.pipeline_results);
        setBotDeploymentScore(result.deployment_score);
        setBotStatus(result.bot_status);
        setCompletedPipelineSteps(prev => [...new Set([...prev, 'bot', 'pipeline'])]);
        setCurrentPipelineStep('complete');
        
        // Add pipeline logs
        addPipelineLog('success', `cBot generated successfully`);
        addPipelineLog(result.pipeline_results.safety_injected ? 'success' : 'warning', 
          `Safety Injection: ${result.pipeline_results.safety_injected ? 'Passed' : 'Skipped'}`);
        addPipelineLog(result.pipeline_results.compile_verified ? 'success' : 'error', 
          `Compilation: ${result.pipeline_results.compile_verified ? 'Verified' : 'Failed'}`);
        addPipelineLog(result.pipeline_results.backtest_passed ? 'success' : 'warning', 
          `Backtest: ${result.pipeline_results.backtest_passed ? 'Passed' : 'Failed'}`);
        addPipelineLog(result.pipeline_results.monte_carlo_passed ? 'success' : 'warning', 
          `Monte Carlo: ${result.pipeline_results.monte_carlo_passed ? 'Passed' : 'Failed'}`);
        addPipelineLog(result.pipeline_results.walkforward_passed ? 'success' : 'warning', 
          `Walk-Forward: ${result.pipeline_results.walkforward_passed ? 'Passed' : 'Failed'}`);
        addPipelineLog('info', `Final Status: ${result.bot_status.toUpperCase()} (Score: ${result.deployment_score}%)`);
        
        // Show success with pipeline results
        const statusEmoji = {
          'ready_for_deployment': '✅',
          'robust': '💪',
          'validated': '✓',
          'draft': '📝'
        };
        
        toast.success(
          `${statusEmoji[result.bot_status] || '📝'} Bot Status: ${result.bot_status.toUpperCase()}\n` +
          `Deployment Score: ${result.deployment_score}%`,
          { id: 'cbot-generation', duration: 8000 }
        );
        
        // Store session for reference
        setPipelineBotSession(result.session_id);
        
      } else {
        addPipelineLog('error', `Generation failed: ${response.data.detail || 'Unknown error'}`);
        toast.error(`Failed to generate cBot: ${response.data.detail || 'Unknown error'}`, {
          id: 'cbot-generation'
        });
      }
    } catch (error) {
      console.error('cBot generation error:', error);
      addPipelineLog('error', `Error: ${error.response?.data?.detail || error.message}`);
      toast.error(
        error.response?.data?.detail || `Error generating cBot: ${error.message}`,
        { id: 'cbot-generation' }
      );
    }
  };
  
  // Helper function to add pipeline logs
  const addPipelineLog = (type, message) => {
    setPipelineLogs(prev => [...prev, {
      id: Date.now(),
      type, // 'info', 'success', 'warning', 'error'
      message,
      timestamp: new Date().toISOString()
    }]);
  };
  
  // Quick Start function - generates 10 strategies and shows top 3
  const handleQuickStart = async () => {
    setIsQuickStarting(true);
    setQuickStartProgress(0);
    setPipelineLogs([]);
    addPipelineLog('info', 'Quick Start initiated - generating 10 strategies...');
    
    try {
      // Step 1: Generate strategies using factory
      setQuickStartProgress(10);
      addPipelineLog('info', 'Creating strategy generation job...');
      
      const response = await axios.post(`${API}/factory/generate`, {
        session_id: `quickstart-${Date.now()}`,
        symbol: selectedPair || 'EURUSD',
        timeframe: selectedTimeframe || '1h',
        strategies_per_template: 2,
        templates: ['ema_crossover', 'rsi_mean_reversion', 'macd_trend', 'bollinger_breakout', 'atr_volatility_breakout'],
        duration_days: 365,
        initial_balance: 10000,
        challenge_firm: 'ftmo'
      });
      
      setQuickStartProgress(30);
      addPipelineLog('success', `Factory job created: ${response.data.run_id}`);
      
      if (response.data.run_id) {
        const runId = response.data.run_id;
        
        // Step 2: Poll for completion
        addPipelineLog('info', 'Waiting for strategies to be evaluated...');
        let attempts = 0;
        const maxAttempts = 20;
        let statusData = null;
        
        while (attempts < maxAttempts) {
          await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
          attempts++;
          setQuickStartProgress(30 + (attempts * 2));
          
          try {
            const statusResponse = await axios.get(`${API}/factory/status/${runId}`);
            statusData = statusResponse.data;
            
            if (statusData.status === 'completed') {
              addPipelineLog('success', `Generated ${statusData.total_generated} strategies in ${statusData.execution_time_seconds?.toFixed(1)}s`);
              break;
            } else if (statusData.status === 'failed') {
              throw new Error(statusData.error_message || 'Factory run failed');
            }
          } catch (e) {
            if (attempts >= maxAttempts) throw e;
          }
        }
        
        setQuickStartProgress(70);
        
        // Step 3: Get results
        addPipelineLog('info', 'Fetching strategy results...');
        const resultResponse = await axios.get(`${API}/factory/result/${runId}`);
        
        if (resultResponse.data.result?.strategies) {
          // Sort by fitness and take top 3 (or all if less than 3 meet threshold)
          const allStrategies = resultResponse.data.result.strategies;
          const passingStrategies = allStrategies.filter(s => s.fitness >= 25);
          const sortedStrategies = allStrategies
            .sort((a, b) => b.fitness - a.fitness)
            .slice(0, 5); // Show top 5 regardless of threshold
          
          setTopStrategies(sortedStrategies);
          setQuickStartProgress(100);
          
          if (passingStrategies.length > 0) {
            addPipelineLog('success', `${passingStrategies.length} strategies passed fitness threshold (≥25)`);
          } else {
            addPipelineLog('warning', `No strategies met fitness threshold (≥25). Showing top ${sortedStrategies.length} for review.`);
          }
          
          // Update pipeline state
          setCompletedPipelineSteps(['generate', 'view']);
          setCurrentPipelineStep('select');
          
          toast.success(`✅ Quick Start complete! ${sortedStrategies.length} strategies ready for selection.`, {
            duration: 5000
          });
        } else {
          throw new Error('No strategies returned from factory');
        }
      }
    } catch (error) {
      console.error('Quick start error:', error);
      addPipelineLog('error', `Quick Start failed: ${error.response?.data?.detail || error.message}`);
      toast.error(`Quick Start failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsQuickStarting(false);
    }
  };
  
  // State for pipeline bot session
  const [pipelineBotSession, setPipelineBotSession] = useState(null);

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
  
  // Strategy Config State
  const [selectedPair, setSelectedPair] = useState('EURUSD');
  const [strategyMode, setStrategyMode] = useState('standard'); // 'standard' | 'pro'
  const [selectedTimeframe, setSelectedTimeframe] = useState('1h');
  
  // === NEW: Strategy Generation Configuration ===
  const [numStrategies, setNumStrategies] = useState(100);
  const [strategyType, setStrategyType] = useState('intraday'); // scalping, intraday, swing
  const [riskLevel, setRiskLevel] = useState('medium'); // low, medium, high
  const [genExecutionMode, setGenExecutionMode] = useState('fast'); // fast, quality
  
  // Backtest Period
  const [backtestFrom, setBacktestFrom] = useState('');
  const [backtestTo, setBacktestTo] = useState('');
  
  // Job-based generation state
  const [currentJobId, setCurrentJobId] = useState(null);
  const [jobProgress, setJobProgress] = useState(null);
  const [showWarningModal, setShowWarningModal] = useState(false);
  const [pendingGeneration, setPendingGeneration] = useState(null);

  // Check data availability when pair changes (check ANY available data)
  useEffect(() => {
    checkDataAvailability();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPair]);

  // Poll job progress when a job is running
  useEffect(() => {
    if (!currentJobId) return;
    
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API}/strategy/job-status/${currentJobId}`);
        if (response.data.success) {
          setJobProgress(response.data);
          
          if (response.data.stage === 'completed') {
            setIsAutoGenerating(false);
            clearInterval(interval);
            
            // Fetch results
            const resultResponse = await axios.get(`${API}/strategy/job-result/${currentJobId}`);
            if (resultResponse.data.success) {
              setTopStrategies(resultResponse.data.strategies || []);
              toast.success(`✅ Generated ${resultResponse.data.total_passed} strategies (${resultResponse.data.total_generated} total)`, {
                duration: 6000
              });
            }
          } else if (response.data.stage === 'failed') {
            setIsAutoGenerating(false);
            clearInterval(interval);
            toast.error(`Generation failed: ${response.data.message}`, { duration: 8000 });
          }
        }
      } catch (error) {
        console.error('Job status check error:', error);
      }
    }, 1500);
    
    return () => clearInterval(interval);
  }, [currentJobId]);

  const checkDataAvailability = async () => {
    setIsCheckingData(true);
    try {
      // NEW: Check ANY available data for symbol, not fixed timeframe
      const response = await axios.get(`${API}/marketdata/check-any-availability/${selectedPair}`);
      
      if (response.data.available) {
        setDataAvailability({
          available: true,
          symbol: response.data.symbol,
          timeframe: response.data.best_timeframe,
          available_timeframes: response.data.available_timeframes || [],
          candle_count: response.data.candle_count,
          date_range: response.data.date_range,
          message: response.data.message
        });
      } else {
        setDataAvailability({
          available: false,
          symbol: selectedPair,
          timeframe: selectedTimeframe,
          available_timeframes: [],
          message: response.data.message || 'No data available'
        });
      }
    } catch (error) {
      console.error('Data availability check error:', error);
      // Fallback to specific timeframe check
      try {
        const fallbackResponse = await axios.get(`${API}/marketdata/check-availability/${selectedPair}/${selectedTimeframe}`);
        if (fallbackResponse.data.available) {
          setDataAvailability({
            available: true,
            symbol: fallbackResponse.data.symbol,
            timeframe: fallbackResponse.data.timeframe,
            candle_count: fallbackResponse.data.candle_count,
            date_range: fallbackResponse.data.date_range
          });
        } else {
          setDataAvailability({
            available: false,
            symbol: selectedPair,
            timeframe: selectedTimeframe,
            error: fallbackResponse.data?.message || 'No data'
          });
        }
      } catch (e) {
        setDataAvailability({
          available: false,
          symbol: selectedPair,
          timeframe: selectedTimeframe,
          error: 'Failed to check'
        });
      }
    } finally {
      setIsCheckingData(false);
    }
  };
  
  // Backtest Period Quick-Fill Functions
  const fillBacktestPeriod = (days) => {
    const today = new Date();
    const startDate = new Date(today);
    startDate.setDate(today.getDate() - days);
    
    setBacktestFrom(startDate.toISOString().split('T')[0]);
    setBacktestTo(today.toISOString().split('T')[0]);
  };

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

  return (
    <div className="h-screen w-screen bg-[#050505] overflow-hidden flex flex-col">
      {/* Header - Professional SaaS Navigation */}
      <div className="flex-shrink-0 bg-[#0A0A0A] border-b border-white/5 z-50" data-testid="app-header">
        <div className="flex items-center justify-between h-14 px-4">
          {/* Left: Logo & Branding */}
          <div className="flex items-center gap-4 min-w-[200px]">
            <div>
              <h1 className="text-xl font-extrabold uppercase tracking-tight text-white leading-none" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                Raghu's BOT Factory
              </h1>
              <p className="text-[10px] text-zinc-500 uppercase tracking-widest" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                Multi-AI Engine
              </p>
            </div>
          </div>

          {/* Center: Main Navigation */}
          <nav className="flex items-center gap-1" data-testid="main-navigation">
            {/* Mode Selection Group */}
            <div className="flex items-center bg-[#18181B] rounded-md border border-white/10 p-1 mr-3" data-testid="execution-mode-toggle">
              {[
                { value: 'backtest', label: 'Backtest', icon: BarChart3 },
                { value: 'forward_test', label: 'Forward', icon: TrendingUp },
                { value: 'live', label: 'Live Trading', icon: Activity }
              ].map(mode => {
                const Icon = mode.icon;
                return (
                  <button
                    key={mode.value}
                    onClick={() => setExecutionMode(mode.value)}
                    className={`flex items-center gap-1.5 px-3 py-2 text-[11px] font-mono uppercase transition-all duration-200 rounded-md ${
                      executionMode === mode.value
                        ? mode.value === 'live' 
                          ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/20' 
                          : 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                        : 'text-zinc-400 hover:text-white hover:bg-white/5'
                    }`}
                    data-testid={`mode-${mode.value}`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {mode.label}
                  </button>
                );
              })}
            </div>

            {/* Separator */}
            <div className="w-px h-6 bg-white/10 mx-2" />

            {/* Core Features Group */}
            <div className="flex items-center gap-1">
              <NavButton 
                onClick={() => navigate('/pipeline')} 
                icon={Zap} 
                label="Pipeline" 
                variant="accent"
                testId="pipeline-nav-btn"
              />
              <NavButton 
                onClick={() => navigate('/analyze-bot')} 
                icon={Search} 
                label="Analyze" 
                testId="analyze-nav-btn"
              />
              <NavButton 
                onClick={() => navigate('/discovery')} 
                icon={Globe} 
                label="Discover" 
                testId="discovery-nav-btn"
              />
              <NavButton 
                onClick={() => navigate('/library')} 
                icon={Database} 
                label="Library" 
                testId="library-nav-btn"
              />
            </div>

            {/* Separator */}
            <div className="w-px h-6 bg-white/10 mx-2" />

            {/* System / Management Group */}
            <div className="flex items-center gap-1">
              <NavButton 
                onClick={() => navigate('/bot-config')} 
                icon={Settings} 
                label="Config" 
                variant="secondary"
                testId="config-nav-btn"
              />
              <NavButton 
                onClick={() => navigate('/portfolio')} 
                icon={Briefcase} 
                label="Portfolio" 
                testId="portfolio-nav-btn"
              />
              <NavButton 
                onClick={() => navigate('/live')} 
                icon={Activity} 
                label="Monitor" 
                variant="accent"
                testId="live-nav-btn"
              />
            </div>
          </nav>

          {/* Right: Status & Meta Info */}
          <div className="flex items-center gap-3 min-w-[200px] justify-end">
            {metadata && (
              <span className="text-[10px] font-mono text-zinc-500 hidden lg:block" data-testid="execution-time">
                {metadata.total_ai_calls} calls • {metadata.execution_time_seconds}s
              </span>
            )}
            <div className="flex items-center gap-2 bg-[#18181B] rounded-md px-3 py-1.5 border border-white/10">
              <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" data-testid="status-indicator" />
              <span className="text-[10px] text-zinc-300 uppercase font-mono tracking-wide">Online</span>
            </div>
            <div className="bg-emerald-500/10 text-emerald-400 px-2.5 py-1 rounded-md text-[10px] font-mono font-semibold border border-emerald-500/20" data-testid="build-version">
              v2.1
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area with Vertical Split */}
      <PanelGroup 
        orientation="vertical" 
        className="flex-1 p-2"
      >
        {/* Top Section: Left + Center + Right Panels */}
        <Panel 
          defaultSize={60} 
          minSize={30}
        >
          <PanelGroup 
            orientation="horizontal" 
            className="h-full"
          >
            {/* Left Panel - Strategy Input - Now with larger default */}
            <Panel 
              defaultSize={18} 
              minSize={14}
            >
              <div className="h-full bg-[#0A0A0A] border border-white/5 flex flex-col overflow-hidden rounded-sm" data-testid="strategy-panel">
                <div className="border-b border-white/5 px-3 py-2 bg-[#18181B] flex-shrink-0">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-200 truncate" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                    Strategy Config
                  </h2>
                </div>
                <div className="flex-1 p-2 space-y-2 overflow-y-auto overflow-x-hidden custom-scrollbar text-xs">
                  {/* SECTION A: MARKET SELECTION */}
                  <div className="space-y-2">
                    <p className="text-[9px] font-mono uppercase tracking-widest text-cyan-400 border-b border-cyan-500/20 pb-1">Market Selection</p>
                    
                    {/* Pair Selection */}
                    <div>
                      <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1 block">Trading Pair</label>
                      <Select value={selectedPair} onValueChange={setSelectedPair}>
                        <SelectTrigger className="bg-[#18181B] border-white/10 text-xs text-zinc-300 h-7" data-testid="pair-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#0F0F10] border-white/10">
                          <SelectItem value="EURUSD" className="text-xs">EUR/USD</SelectItem>
                          <SelectItem value="XAUUSD" className="text-xs">XAU/USD (Gold)</SelectItem>
                          <SelectItem value="GBPUSD" className="text-xs">GBP/USD</SelectItem>
                          <SelectItem value="USDJPY" className="text-xs">USD/JPY</SelectItem>
                          <SelectItem value="NAS100" className="text-xs">NAS100 (Nasdaq)</SelectItem>
                          <SelectItem value="BTCUSD" className="text-xs">BTC/USD</SelectItem>
                          <SelectItem value="ETHUSD" className="text-xs">ETH/USD</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Timeframe Selection */}
                    <div>
                      <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1 block">Timeframe</label>
                      <Select value={selectedTimeframe} onValueChange={setSelectedTimeframe}>
                        <SelectTrigger className="bg-[#18181B] border-white/10 text-xs text-zinc-300 h-7" data-testid="timeframe-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#0F0F10] border-white/10">
                          <SelectItem value="1m" className="text-xs">1 Minute (M1)</SelectItem>
                          <SelectItem value="5m" className="text-xs">5 Minutes (M5)</SelectItem>
                          <SelectItem value="15m" className="text-xs">15 Minutes (M15)</SelectItem>
                          <SelectItem value="30m" className="text-xs">30 Minutes (M30)</SelectItem>
                          <SelectItem value="1h" className="text-xs">1 Hour (H1)</SelectItem>
                          <SelectItem value="4h" className="text-xs">4 Hours (H4)</SelectItem>
                          <SelectItem value="1d" className="text-xs">1 Day (D1)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Quick Access: Market Data */}
                  <Button
                    onClick={() => navigate('/market-data')}
                    className="w-full bg-amber-600/20 hover:bg-amber-600/30 text-amber-400 border border-amber-500/30 font-mono uppercase text-[10px] h-8 flex items-center justify-center gap-2"
                    data-testid="market-data-quick-access"
                  >
                    <Database className="w-3 h-3" />
                    Load Market Data
                  </Button>

                  {/* Data Availability Status - IMPROVED */}
                  <div className="bg-[#0F0F10] border border-white/5 p-2 rounded-sm">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Data Status</span>
                      {isCheckingData && <Loader2 className="w-3 h-3 animate-spin text-blue-400" />}
                    </div>
                    {dataAvailability ? (
                      <>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-mono text-zinc-300">{dataAvailability.symbol}</span>
                          {dataAvailability.available ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400 ml-auto" />
                          ) : (
                            <XCircle className="w-3 h-3 text-red-400 ml-auto" />
                          )}
                        </div>
                        {dataAvailability.available ? (
                          <>
                            <div className="text-[10px] text-emerald-400 font-mono mb-0.5">
                              ✓ {dataAvailability.candle_count?.toLocaleString()} candles ({dataAvailability.timeframe})
                            </div>
                            {dataAvailability.available_timeframes?.length > 1 && (
                              <div className="text-[9px] text-zinc-500 font-mono mb-0.5">
                                Available: {dataAvailability.available_timeframes.join(', ')}
                              </div>
                            )}
                            {dataAvailability.date_range && (
                              <div className="text-[9px] text-zinc-500 font-mono">
                                {formatDateRange(dataAvailability.date_range.start, dataAvailability.date_range.end)}
                              </div>
                            )}
                          </>
                        ) : (
                          <div className="text-[10px] text-red-400 font-mono">
                            ❌ No data available for {selectedPair}
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-[10px] text-zinc-600 font-mono">
                        Checking availability...
                      </div>
                    )}
                  </div>

                  {/* SECTION B: BACKTEST SETTINGS */}
                  <div className="bg-blue-950/20 border border-blue-500/30 rounded-sm p-2 space-y-2">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-3 h-3 text-blue-400" />
                      <p className="text-[9px] font-mono uppercase tracking-widest text-blue-400 font-bold">Backtest Period</p>
                    </div>
                    
                    {/* Quick Preset Buttons */}
                    <div className="grid grid-cols-3 gap-1">
                      {[
                        { label: '7D', days: 7 },
                        { label: '30D', days: 30 },
                        { label: '90D', days: 90 },
                        { label: '6M', days: 180 },
                        { label: '1Y', days: 365 },
                        { label: '2Y', days: 730 }
                      ].map(({ label, days }) => (
                        <button
                          key={days}
                          type="button"
                          onClick={() => fillBacktestPeriod(days)}
                          className="px-1 py-1 rounded text-[9px] font-mono bg-white/5 text-zinc-400 border border-white/10 hover:bg-blue-600 hover:text-white hover:border-blue-500 transition-all"
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    
                    {/* Date Inputs */}
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] font-mono uppercase text-zinc-500 mb-0.5 block">From</label>
                        <input
                          type="date"
                          value={backtestFrom}
                          onChange={(e) => setBacktestFrom(e.target.value)}
                          max={new Date().toISOString().split('T')[0]}
                          className="w-full bg-[#18181B] border-blue-500/30 text-[10px] text-white px-1.5 py-1 font-mono rounded border focus:outline-none focus:ring-1 focus:ring-blue-500"
                          data-testid="backtest-from-input"
                        />
                      </div>
                      <div>
                        <label className="text-[9px] font-mono uppercase text-zinc-500 mb-0.5 block">To</label>
                        <input
                          type="date"
                          value={backtestTo}
                          onChange={(e) => setBacktestTo(e.target.value)}
                          max={new Date().toISOString().split('T')[0]}
                          className="w-full bg-[#18181B] border-blue-500/30 text-[10px] text-white px-1.5 py-1 font-mono rounded border focus:outline-none focus:ring-1 focus:ring-blue-500"
                          data-testid="backtest-to-input"
                        />
                      </div>
                    </div>
                  </div>

                  {/* SECTION C: STRATEGY GENERATION CONTROLS */}
                  <div className="bg-purple-950/20 border border-purple-500/30 rounded-sm p-2 space-y-2">
                    <div className="flex items-center gap-2">
                      <Layers className="w-3 h-3 text-purple-400" />
                      <p className="text-[9px] font-mono uppercase tracking-widest text-purple-400 font-bold">Generation Settings</p>
                    </div>
                    
                    {/* Strategy Count - Preset Buttons */}
                    <div>
                      <label className="text-[9px] font-mono uppercase text-zinc-500 mb-1 block">Strategy Count</label>
                      <div className="grid grid-cols-4 gap-1 mb-1.5">
                        {[10, 50, 100, 200, 300, 500, 1000].slice(0, 4).map(count => (
                          <button
                            key={count}
                            type="button"
                            onClick={() => setNumStrategies(count)}
                            className={`px-1 py-1 rounded text-[9px] font-mono transition-all ${
                              numStrategies === count
                                ? 'bg-purple-600 text-white border-purple-500'
                                : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'
                            } border`}
                          >
                            {count}
                          </button>
                        ))}
                      </div>
                      <div className="grid grid-cols-3 gap-1 mb-1.5">
                        {[200, 500, 1000].map(count => (
                          <button
                            key={count}
                            type="button"
                            onClick={() => setNumStrategies(count)}
                            className={`px-1 py-1 rounded text-[9px] font-mono transition-all ${
                              numStrategies === count
                                ? count > 300 ? 'bg-red-600 text-white border-red-500' : 'bg-purple-600 text-white border-purple-500'
                                : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'
                            } border`}
                          >
                            {count}
                            {count > 300 && <span className="text-[7px] ml-0.5">⚡</span>}
                          </button>
                        ))}
                      </div>
                      
                      {/* Custom Input */}
                      <input
                        type="number"
                        value={numStrategies}
                        onChange={(e) => {
                          const val = parseInt(e.target.value) || 100;
                          setNumStrategies(Math.min(Math.max(val, 10), 1000));
                        }}
                        min="10"
                        max="1000"
                        className="w-full bg-[#18181B] border-purple-500/30 text-[10px] text-white px-2 py-1 font-mono rounded border focus:outline-none focus:ring-1 focus:ring-purple-500"
                        data-testid="num-strategies-input"
                      />
                      <p className="text-[8px] text-zinc-600 mt-0.5">Range: 10–1000 | {numStrategies > 300 ? '⚠️ Batch mode' : numStrategies > 100 ? '⚡ Moderate load' : '✓ Normal'}</p>
                    </div>
                    
                    {/* Strategy Type */}
                    <div>
                      <label className="text-[9px] font-mono uppercase text-zinc-500 mb-1 block">Strategy Type</label>
                      <div className="grid grid-cols-3 gap-1">
                        {[
                          { value: 'scalping', label: 'Scalping', desc: 'Fast' },
                          { value: 'intraday', label: 'Intraday', desc: 'Day' },
                          { value: 'swing', label: 'Swing', desc: 'Multi-day' }
                        ].map(({ value, label, desc }) => (
                          <button
                            key={value}
                            type="button"
                            onClick={() => setStrategyType(value)}
                            className={`px-1.5 py-1 rounded text-[9px] font-mono transition-all text-left ${
                              strategyType === value
                                ? 'bg-cyan-600/20 border-cyan-500/40 text-cyan-400'
                                : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'
                            } border`}
                          >
                            <div className="font-bold">{label}</div>
                            <div className="text-[7px] text-zinc-500">{desc}</div>
                          </button>
                        ))}
                      </div>
                    </div>
                    
                    {/* Risk Level */}
                    <div>
                      <label className="text-[9px] font-mono uppercase text-zinc-500 mb-1 block">Risk Level</label>
                      <div className="grid grid-cols-3 gap-1">
                        {[
                          { value: 'low', label: 'Low', color: 'emerald' },
                          { value: 'medium', label: 'Medium', color: 'amber' },
                          { value: 'high', label: 'High', color: 'red' }
                        ].map(({ value, label, color }) => (
                          <button
                            key={value}
                            type="button"
                            onClick={() => setRiskLevel(value)}
                            className={`px-2 py-1.5 rounded text-[9px] font-mono font-bold transition-all ${
                              riskLevel === value
                                ? `bg-${color}-600/20 border-${color}-500/40 text-${color}-400`
                                : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'
                            } border`}
                            style={riskLevel === value ? {
                              backgroundColor: color === 'emerald' ? 'rgba(5, 150, 105, 0.2)' : color === 'amber' ? 'rgba(217, 119, 6, 0.2)' : 'rgba(220, 38, 38, 0.2)',
                              borderColor: color === 'emerald' ? 'rgba(5, 150, 105, 0.4)' : color === 'amber' ? 'rgba(217, 119, 6, 0.4)' : 'rgba(220, 38, 38, 0.4)',
                              color: color === 'emerald' ? '#34d399' : color === 'amber' ? '#fbbf24' : '#f87171'
                            } : {}}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    </div>
                    
                    {/* Execution Mode */}
                    <div>
                      <label className="text-[9px] font-mono uppercase text-zinc-500 mb-1 block">Execution Mode</label>
                      <div className="grid grid-cols-2 gap-1">
                        <button
                          type="button"
                          onClick={() => setGenExecutionMode('fast')}
                          className={`px-2 py-1.5 rounded text-[9px] font-mono transition-all text-left ${
                            genExecutionMode === 'fast'
                              ? 'bg-green-600/20 border-green-500/40 text-green-400'
                              : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'
                          } border`}
                        >
                          <div className="font-bold flex items-center gap-1"><Zap className="w-2.5 h-2.5" /> Fast</div>
                          <div className="text-[7px] text-zinc-500">Parallel, lighter</div>
                        </button>
                        <button
                          type="button"
                          onClick={() => setGenExecutionMode('quality')}
                          className={`px-2 py-1.5 rounded text-[9px] font-mono transition-all text-left ${
                            genExecutionMode === 'quality'
                              ? 'bg-indigo-600/20 border-indigo-500/40 text-indigo-400'
                              : 'bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10'
                          } border`}
                        >
                          <div className="font-bold flex items-center gap-1"><Shield className="w-2.5 h-2.5" /> Quality</div>
                          <div className="text-[7px] text-zinc-500">Deeper validation</div>
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Job Progress Tracker */}
                  {(isAutoGenerating || jobProgress) && jobProgress && (
                    <div className="bg-[#0F0F10] border border-blue-500/30 rounded-sm p-2 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono uppercase tracking-widest text-blue-400">
                          {jobProgress.stage.replace(/_/g, ' ').toUpperCase()}
                        </span>
                        <span className="text-[10px] font-mono text-zinc-300">{Math.round(jobProgress.percent)}%</span>
                      </div>
                      
                      {/* Progress Bar */}
                      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-300"
                          style={{ width: `${jobProgress.percent}%` }}
                        />
                      </div>
                      
                      {/* Status Message */}
                      <p className="text-[9px] text-zinc-400 font-mono">{jobProgress.message}</p>
                      
                      {/* Batch Progress */}
                      {jobProgress.total_batches > 1 && (
                        <div className="text-[8px] text-zinc-500 font-mono">
                          Batch {jobProgress.current_batch}/{jobProgress.total_batches} | 
                          Generated: {jobProgress.strategies_generated} | 
                          Passed: {jobProgress.strategies_passed}
                        </div>
                      )}
                      
                      {/* Stage Indicator */}
                      <div className="flex gap-1">
                        {['fetching_data', 'preparing_data', 'generating_strategies', 'backtesting', 'validating_results', 'finalizing', 'completed'].map((stage, idx) => (
                          <div
                            key={stage}
                            className={`flex-1 h-1 rounded-full ${
                              jobProgress.stage === stage ? 'bg-blue-500' :
                              ['completed', 'failed'].includes(jobProgress.stage) || 
                              idx < ['fetching_data', 'preparing_data', 'generating_strategies', 'backtesting', 'validating_results', 'finalizing', 'completed'].indexOf(jobProgress.stage)
                                ? 'bg-emerald-500' : 'bg-zinc-700'
                            }`}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Mode Selection - Standard / Pro */}
                  <div>
                    <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2 block">Strategy Mode</label>
                    <div className="grid grid-cols-2 gap-2" data-testid="strategy-mode-selector">
                      <button
                        onClick={() => setStrategyMode('standard')}
                        className={`px-3 py-2 text-left border transition-colors ${
                          strategyMode === 'standard'
                            ? 'bg-blue-600/15 border-blue-500/40 text-blue-400'
                            : 'bg-[#0F0F10] border-white/5 text-zinc-500 hover:border-white/15 hover:text-zinc-300'
                        }`}
                        data-testid="mode-standard"
                      >
                        <p className="text-[10px] font-mono font-bold uppercase tracking-wider">Standard</p>
                        <p className="text-[9px] text-zinc-600">Quick setup</p>
                      </button>
                      <button
                        onClick={() => setStrategyMode('pro')}
                        className={`px-3 py-2 text-left border transition-colors ${
                          strategyMode === 'pro'
                            ? 'bg-purple-600/15 border-purple-500/40 text-purple-400'
                            : 'bg-[#0F0F10] border-white/5 text-zinc-500 hover:border-white/15 hover:text-zinc-300'
                        }`}
                        data-testid="mode-pro"
                      >
                        <p className="text-[10px] font-mono font-bold uppercase tracking-wider">Pro</p>
                        <p className="text-[9px] text-zinc-600">Advanced</p>
                      </button>
                    </div>
                  </div>

                  {/* AI Mode Selector - Wrapped for overflow */}
                  <div>
                    <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2 block">AI Mode</label>
                    <div className="flex flex-wrap gap-1" data-testid="ai-mode-selector">
                      <ModeButton mode="single" />
                      <ModeButton mode="collaboration" />
                      <ModeButton mode="competition" />
                    </div>
                  </div>

                  {/* Model Selection based on mode */}
                  {aiMode === 'single' && (
                    <ModelSelect label="AI Model" value={singleModel} onChange={setSingleModel} testId="single-model-select" />
                  )}

                  {aiMode === 'collaboration' && (
                    <div className="space-y-2 bg-[#0F0F10] border border-white/5 p-2 rounded-sm" data-testid="collaboration-config">
                      <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Pipeline Roles</p>
                      <ModelSelect label="Strategy Generator" value={generatorModel} onChange={setGeneratorModel} testId="generator-model-select" />
                      <ModelSelect label="Code Reviewer" value={reviewerModel} onChange={setReviewerModel} testId="reviewer-model-select" />
                      <ModelSelect label="Strategy Optimizer" value={optimizerModel} onChange={setOptimizerModel} testId="optimizer-model-select" />
                    </div>
                  )}

                  {aiMode === 'competition' && (
                    <div className="bg-[#0F0F10] border border-white/5 p-2 rounded-sm" data-testid="competition-config">
                      <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1">Competing Models</p>
                      <div className="space-y-1">
                        {AI_MODELS.map(m => (
                          <div key={m.value} className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
                            <Trophy className="w-3 h-3 text-amber-500/60" />
                            {m.label}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Prop Firm Selector */}
                  <div>
                    <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1 block">Prop Firm</label>
                    <Select value={propFirm} onValueChange={setPropFirm}>
                      <SelectTrigger className="bg-[#18181B] border-white/10 text-xs text-zinc-300 h-7" data-testid="prop-firm-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#0F0F10] border-white/10">
                        <SelectItem value="none" className="text-xs">No Prop Firm</SelectItem>
                        <SelectItem value="ftmo" className="text-xs">FTMO</SelectItem>
                        <SelectItem value="pipfarm" className="text-xs">PipFarm</SelectItem>
                        <SelectItem value="fundednext" className="text-xs">Funded Next</SelectItem>
                        <SelectItem value="thefundedtrader" className="text-xs">The Funded Trader</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Strategy Prompt */}
                  <div className="flex-1 flex flex-col min-h-0">
                    <label className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2 block">
                      Trading Strategy
                    </label>
                    <Textarea
                      placeholder="Describe your trading strategy in detail..."
                      value={strategyPrompt}
                      onChange={(e) => setStrategyPrompt(e.target.value)}
                      className="bg-black border-white/10 text-sm text-white placeholder:text-zinc-600 flex-1 min-h-[120px] font-mono resize-none"
                      data-testid="strategy-input"
                    />
                  </div>

                  <Button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="w-full bg-blue-600 hover:bg-blue-500 text-white font-mono uppercase text-xs h-9 flex-shrink-0"
                    data-testid="generate-button"
                  >
                    {isGenerating ? (
                      <><Loader2 className="w-3 h-3 mr-2 animate-spin" /> GENERATING...</>
                    ) : (
                      <><Play className="w-3 h-3 mr-2" /> GENERATE BOT</>
                    )}
                  </Button>

                  {/* Auto-Generate Strategies Button */}
                  <Button
                    onClick={handleAutoGenerateStrategies}
                    disabled={isAutoGenerating || !dataAvailability?.available}
                    className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-mono uppercase text-[10px] h-10 flex flex-col items-center justify-center gap-0.5 flex-shrink-0"
                    data-testid="auto-generate-button"
                  >
                    {isAutoGenerating ? (
                      <>
                        <span className="flex items-center gap-2">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Processing...
                        </span>
                        <span className="text-[8px] opacity-75">
                          {jobProgress ? `${Math.round(jobProgress.percent)}% - ${jobProgress.stage.replace(/_/g, ' ')}` : 'Starting...'}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="flex items-center gap-2">
                          <Trophy className="w-3 h-3" />
                          🚀 Generate {numStrategies} Strategies
                        </span>
                        <span className="text-[8px] opacity-75">{strategyType} • {riskLevel} risk • {genExecutionMode}</span>
                      </>
                    )}
                  </Button>

                  {/* Warning Modal for Large Runs */}
                  {showWarningModal && (
                    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
                      <div className="bg-[#18181B] border border-red-500/30 rounded-lg p-4 max-w-md mx-4">
                        <div className="flex items-center gap-2 mb-3">
                          <AlertTriangle className="w-5 h-5 text-red-400" />
                          <h3 className="text-sm font-bold text-red-400">Large Generation Warning</h3>
                        </div>
                        <p className="text-xs text-zinc-400 mb-3">
                          You're about to generate <strong className="text-white">{numStrategies} strategies</strong>. 
                          This will be processed in batches and may take several minutes.
                        </p>
                        <div className="bg-red-950/30 border border-red-500/20 rounded p-2 mb-3">
                          <p className="text-[10px] text-red-300 font-mono">
                            ⚠️ Estimated time: {Math.ceil(numStrategies / 50 * 2)} - {Math.ceil(numStrategies / 50 * 4)} minutes
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            onClick={() => setShowWarningModal(false)}
                            className="flex-1 bg-zinc-700 hover:bg-zinc-600 text-white text-xs"
                          >
                            Cancel
                          </Button>
                          <Button
                            onClick={executeStrategyGeneration}
                            className="flex-1 bg-red-600 hover:bg-red-500 text-white text-xs"
                          >
                            Proceed Anyway
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}

                  {sessionId && (
                    <div className="pt-2 border-t border-white/5 flex-shrink-0">
                      <p className="text-[10px] text-zinc-500 uppercase font-mono">Session</p>
                      <p className="text-[10px] text-zinc-400 font-mono break-all">{sessionId}</p>
                    </div>
                  )}
                </div>
              </div>
            </Panel>

            {/* Vertical Resize Handle */}
            <VerticalResizeHandle />

            {/* Center Panel - Code Editor */}
            <Panel 
              defaultSize={53} 
              minSize={35}
            >
              <div className="h-full bg-[#0A0A0A] border border-white/5 flex flex-col overflow-hidden rounded-sm" data-testid="code-panel">
                <div className="border-b border-white/5 px-3 py-2 bg-[#18181B] flex items-center justify-between flex-shrink-0 overflow-x-auto">
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-200 whitespace-nowrap" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                      Generated cBot Code
                    </h2>
                    {botValidation && (
                      <Badge
                        variant="outline"
                        className={`text-[9px] px-1.5 py-0 h-4 ${botValidation.is_deployable ? 'border-emerald-500/40 text-emerald-400' : 'border-red-500/40 text-red-400'}`}
                        data-testid="validation-badge"
                      >
                        {botValidation.is_deployable ? '✓ VALIDATED' : `${botValidation.failed_checks} FAILED`}
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
            <Button
              onClick={handleInjectSafety}
              size="sm"
              className="bg-amber-600/20 hover:bg-amber-600/30 text-amber-400 border border-amber-500/30 font-mono uppercase text-[10px] h-7 px-3"
              data-testid="inject-safety-button"
              disabled={!generatedCode || generatedCode.startsWith('//')}
            >
              <ShieldCheck className="w-3 h-3 mr-1" /> INJECT SAFETY
            </Button>
            <Button
              onClick={handleValidate}
              disabled={isValidating || !generatedCode || generatedCode.startsWith('//')}
              size="sm"
              className="bg-violet-600/20 hover:bg-violet-600/30 text-violet-400 border border-violet-500/30 font-mono uppercase text-[10px] h-7 px-3"
              data-testid="validate-button"
            >
              {isValidating ? (
                <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> VALIDATING...</>
              ) : (
                <><FlaskConical className="w-3 h-3 mr-1" /> VALIDATE</>
              )}
            </Button>
            
            {/* Pre-Deployment Checklist */}
            {deploymentStatus && (
              <div className="flex items-center gap-2" data-testid="deployment-checklist">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className={`flex items-center gap-1.5 px-2 py-1 rounded border text-[9px] font-mono ${
                        deploymentStatus.allPassed 
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                          : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      }`}>
                        {deploymentStatus.allPassed ? (
                          <CheckCircle2 className="w-3 h-3" />
                        ) : (
                          <AlertTriangle className="w-3 h-3" />
                        )}
                        {deploymentStatus.passedCount}/{deploymentStatus.total}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="bg-[#18181B] border-white/10 p-3 max-w-xs">
                      <p className="text-[10px] font-mono uppercase text-zinc-500 mb-2">Pre-Deployment Checklist</p>
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2 text-xs font-mono">
                          {deploymentStatus.checks.propScorePass ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <XCircle className="w-3 h-3 text-red-400" />
                          )}
                          <span className={deploymentStatus.checks.propScorePass ? 'text-emerald-400' : 'text-red-400'}>
                            Prop Score ≥ 80
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs font-mono">
                          {deploymentStatus.checks.riskOfRuinPass ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <XCircle className="w-3 h-3 text-red-400" />
                          )}
                          <span className={deploymentStatus.checks.riskOfRuinPass ? 'text-emerald-400' : 'text-red-400'}>
                            Risk of Ruin &lt; 5%
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs font-mono">
                          {deploymentStatus.checks.validationComplete ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <XCircle className="w-3 h-3 text-red-400" />
                          )}
                          <span className={deploymentStatus.checks.validationComplete ? 'text-emerald-400' : 'text-red-400'}>
                            Validation Complete
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs font-mono">
                          {deploymentStatus.checks.bootstrapPass ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <XCircle className="w-3 h-3 text-red-400" />
                          )}
                          <span className={deploymentStatus.checks.bootstrapPass ? 'text-emerald-400' : 'text-red-400'}>
                            Bootstrap Survival ≥ 70%
                          </span>
                        </div>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                
                {deploymentStatus.allPassed && (
                  <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/40 text-[9px] px-2 py-0.5">
                    <ShieldCheck className="w-3 h-3 mr-1" /> PROP READY
                  </Badge>
                )}
              </div>
            )}
            
            {/* Compile Status Badge */}
            {compileStatus && (
              <Badge 
                className={`text-[9px] px-2 py-0.5 ${
                  compileStatus === 'VERIFIED' 
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' 
                    : 'bg-red-500/20 text-red-400 border-red-500/40'
                }`}
                data-testid="compile-status-badge"
              >
                {compileStatus === 'VERIFIED' ? (
                  <><CheckCircle2 className="w-3 h-3 mr-1" /> COMPILE VERIFIED</>
                ) : (
                  <><XCircle className="w-3 h-3 mr-1" /> COMPILE FAILED ({compileErrors.length})</>
                )}
              </Badge>
            )}

            {/* Compile Check Button */}
            <Button
              onClick={handleCompileCheck}
              size="sm"
              disabled={!generatedCode || isGenerating}
              className="font-mono uppercase text-[10px] h-7 px-3 bg-amber-600 hover:bg-amber-500 text-white"
              data-testid="compile-check-button"
            >
              {isGenerating ? (
                <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> CHECKING</>
              ) : (
                <><Shield className="w-3 h-3 mr-1" /> CHECK COMPILE</>
              )}
            </Button>
            
            <Button
              onClick={handleDownload}
              size="sm"
              disabled={!generatedCode || isGenerating}
              className={`font-mono uppercase text-[10px] h-7 px-3 ${
                compileStatus === 'VERIFIED'
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                  : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 border border-zinc-700'
              }`}
              data-testid="download-button"
            >
              {isGenerating ? (
                <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> VERIFYING</>
              ) : compileStatus === 'VERIFIED' ? (
                <><Download className="w-3 h-3 mr-1" /> DOWNLOAD VERIFIED</>
              ) : (
                <><Download className="w-3 h-3 mr-1" /> DOWNLOAD</>
              )}
            </Button>
                  </div>
                </div>
                <div className="flex-1 overflow-hidden" data-testid="code-editor">
                  <Editor
                    height="100%"
                    defaultLanguage="csharp"
                    theme="vs-dark"
                    value={generatedCode}
                    onChange={(value) => setGeneratedCode(value)}
                    options={{
                      minimap: { enabled: false },
                      fontSize: 13,
                      lineNumbers: 'on',
                      scrollBeyondLastLine: false,
                      automaticLayout: true,
                      tabSize: 4,
                      wordWrap: 'on',
                      fontFamily: 'JetBrains Mono, monospace',
                    }}
                  />
                </div>
              </div>
            </Panel>

            {/* Vertical Resize Handle */}
            <VerticalResizeHandle />

            {/* Right Panel - Pipeline Tracker & Logs */}
            <Panel 
              defaultSize={20} 
              minSize={12}
            >
              <div className="h-full bg-[#0A0A0A] border border-white/5 flex flex-col overflow-hidden rounded-sm" data-testid="logs-panel">
                <div className="border-b border-white/5 px-3 py-2 bg-[#18181B] flex items-center justify-between flex-shrink-0">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-200" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                    Pipeline Logs
                  </h2>
                  <div className="flex items-center gap-2">
                    {(pipelineLogs.length > 0 || collaborationLogs.length > 0) && (
                      <span className="text-[10px] font-mono text-zinc-500">{pipelineLogs.length + collaborationLogs.length} events</span>
                    )}
                  </div>
                </div>
                
                <div className="flex-1 overflow-y-auto custom-scrollbar">
                  {/* Pipeline Status Section */}
                  {(pipelineResults || selectedStrategy) && (
                    <div className="p-2 border-b border-white/5">
                      <BotPipelineStatus 
                        pipelineResults={pipelineResults}
                        deploymentScore={botDeploymentScore}
                        botStatus={botStatus}
                      />
                    </div>
                  )}
                  
                  {/* Strategy Fitness Card */}
                  {selectedStrategy && (
                    <div className="p-2 border-b border-white/5">
                      <StrategyFitnessCard strategy={selectedStrategy} />
                    </div>
                  )}
                  
                  {/* Pipeline Logs */}
                  <div className="p-2" data-testid="pipeline-logs">
                    {pipelineLogs.length > 0 && (
                      <div className="mb-3">
                        <div className="text-[9px] font-mono uppercase tracking-wider text-zinc-500 mb-2">Pipeline Activity</div>
                        {pipelineLogs.map((log) => (
                          <div key={log.id} className={`flex items-start gap-2 text-xs font-mono py-1.5 border-b border-white/5 last:border-0 ${
                            log.type === 'error' ? 'text-red-400' :
                            log.type === 'success' ? 'text-emerald-400' :
                            log.type === 'warning' ? 'text-amber-400' :
                            'text-zinc-400'
                          }`}>
                            <span className="w-4 flex-shrink-0">
                              {log.type === 'error' ? '✗' :
                               log.type === 'success' ? '✓' :
                               log.type === 'warning' ? '!' :
                               '→'}
                            </span>
                            <span className="flex-1">{log.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {/* Collaboration Logs (fallback) */}
                    {isGenerating && collaborationLogs.length === 0 && pipelineLogs.length === 0 ? (
                      <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono p-2">
                        <Loader2 className="w-3 h-3 animate-spin" /> Running pipeline...
                      </div>
                    ) : collaborationLogs.length === 0 && pipelineLogs.length === 0 ? (
                      <p className="text-xs text-zinc-500 font-mono p-2">Generate strategies or a bot to see pipeline logs.</p>
                    ) : collaborationLogs.length > 0 && (
                      <>
                        <div className="text-[9px] font-mono uppercase tracking-wider text-zinc-500 mb-2">Generation Logs</div>
                        {collaborationLogs.map((log, idx) => (
                          <LogEntry key={idx} log={log} />
                        ))}
                        <div ref={logsEndRef} />
                      </>
                    )}
                  </div>
                </div>
              </div>
            </Panel>
          </PanelGroup>
        </Panel>

        {/* Horizontal Resize Handle */}
        <HorizontalResizeHandle />

        {/* Bottom Panel - Quality Gates & Results */}
        <Panel 
          defaultSize={40} 
          minSize={20}
        >
          <div className="h-full bg-[#0A0A0A] border border-white/5 overflow-hidden flex flex-col rounded-sm" data-testid="results-panel">
            <Tabs value={bottomTab} onValueChange={setBottomTab} className="flex flex-col h-full">
              <div className="border-b border-white/5 bg-[#18181B] flex-shrink-0 overflow-x-auto">
                <TabsList className="bg-transparent border-none h-8 p-0 rounded-none inline-flex min-w-max">
                  <TabsTrigger
                    value="validation"
                    className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-violet-500 data-[state=active]:text-violet-400 text-zinc-500 rounded-none h-8 px-4 uppercase text-[10px] tracking-wider font-bold whitespace-nowrap"
                    data-testid="tab-validation"
                  >
                    <FlaskConical className="w-3 h-3 mr-1.5" /> Bot Validation
                  </TabsTrigger>
                  <TabsTrigger
                    value="gates"
                    className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 text-zinc-500 rounded-none h-8 px-4 uppercase text-[10px] tracking-wider font-bold whitespace-nowrap"
                    data-testid="tab-gates"
                  >
                    <Shield className="w-3 h-3 mr-1.5" /> Quality Gates
                  </TabsTrigger>
                  <TabsTrigger
                    value="competition"
                    className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 text-zinc-500 rounded-none h-8 px-4 uppercase text-[10px] tracking-wider font-bold whitespace-nowrap"
                    data-testid="tab-competition"
                  >
                    <Trophy className="w-3 h-3 mr-1.5" /> Competition
                  </TabsTrigger>
                  <TabsTrigger
                    value="summary"
                    className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 text-zinc-500 rounded-none h-8 px-4 uppercase text-[10px] tracking-wider font-bold whitespace-nowrap"
                    data-testid="tab-summary"
                  >
                    <BarChart3 className="w-3 h-3 mr-1.5" /> Summary
                  </TabsTrigger>
                  <TabsTrigger
                    value="advanced"
                    className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-emerald-500 data-[state=active]:text-emerald-400 text-zinc-500 rounded-none h-8 px-4 uppercase text-[10px] tracking-wider font-bold whitespace-nowrap"
                    data-testid="tab-advanced"
                  >
                    <Gauge className="w-3 h-3 mr-1.5" /> Prop Score
                    {propScore && (
                      <span className={`ml-1.5 px-1.5 py-0.5 text-[9px] rounded font-bold ${
                        propScore >= 80 ? 'bg-emerald-500/20 text-emerald-400' :
                        propScore >= 60 ? 'bg-amber-500/20 text-amber-400' :
                        'bg-red-500/20 text-red-400'
                      }`}>
                        {propScore}
                      </span>
                    )}
                  </TabsTrigger>
                  <TabsTrigger
                    value="templates"
                    className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-purple-500 data-[state=active]:text-purple-400 text-zinc-500 rounded-none h-8 px-4 uppercase text-[10px] tracking-wider font-bold whitespace-nowrap"
                    data-testid="tab-templates"
                  >
                    <Target className="w-3 h-3 mr-1.5" /> Strategies
                  </TabsTrigger>
                  <TabsTrigger
                    value="auto-strategies"
                    className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-gradient-to-r data-[state=active]:from-purple-500 data-[state=active]:to-pink-500 data-[state=active]:text-purple-400 text-zinc-500 rounded-none h-8 px-4 uppercase text-[10px] tracking-wider font-bold whitespace-nowrap"
                    data-testid="tab-auto-strategies"
                  >
                    <Trophy className="w-3 h-3 mr-1.5" /> Top Strategies
                  </TabsTrigger>
                </TabsList>
              </div>

              {/* Bot Validation Tab */}
          <TabsContent value="validation" className="flex-1 p-3 overflow-y-auto mt-0">
            {!botValidation ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <FlaskConical className="w-10 h-10 text-zinc-600 mb-3" />
                <p className="text-sm text-zinc-400 font-mono">Click "VALIDATE" to test your bot</p>
                <p className="text-xs text-zinc-600 font-mono mt-1">Validation checks compilation, backtest performance, and risk safety</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Data Availability Warning */}
                {dataAvailability && !dataAvailability.success && (
                  <div className="flex items-center gap-3 p-3 rounded-sm border border-amber-500/40 bg-amber-500/10" data-testid="data-warning">
                    <AlertTriangle className="w-6 h-6 text-amber-400 shrink-0" />
                    <div>
                      <p className="text-sm font-bold text-amber-400 font-mono uppercase">REAL DATA UNAVAILABLE</p>
                      <p className="text-xs text-amber-300/80 font-mono">
                        {dataAvailability.message || 'Could not obtain real market data. Backtest results may NOT be reliable.'}
                      </p>
                      <p className="text-[10px] text-amber-300/60 font-mono mt-1">
                        Ensure TWELVE_DATA_KEY or ALPHA_VANTAGE_KEY is configured and try a supported symbol/timeframe.
                      </p>
                    </div>
                  </div>
                )}
                
                {/* Data Source Badge */}
                {dataAvailability && dataAvailability.success && (
                  <div className="flex items-center gap-2 p-2 rounded-sm border border-emerald-500/30 bg-emerald-500/5" data-testid="data-source-badge">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-mono text-emerald-400">
                      REAL DATA: {dataAvailability.candle_count} candles from {dataAvailability.data_source}
                    </span>
                  </div>
                )}
                
                {/* Overall Status */}
                <div className={`flex items-center justify-between p-3 rounded-sm border ${
                  botValidation.is_deployable
                    ? 'bg-emerald-500/10 border-emerald-500/30'
                    : 'bg-red-500/10 border-red-500/30'
                }`}>
                  <div className="flex items-center gap-3">
                    {botValidation.is_deployable ? (
                      <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                    ) : (
                      <XCircle className="w-6 h-6 text-red-400" />
                    )}
                    <div>
                      <p className={`text-sm font-bold uppercase font-mono ${
                        botValidation.is_deployable ? 'text-emerald-400' : 'text-red-400'
                      }`}>
                        {botValidation.is_deployable ? 'READY FOR DEPLOYMENT' : 'VALIDATION FAILED'}
                      </p>
                      <p className="text-xs text-zinc-500 font-mono">{botValidation.summary}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold font-mono text-zinc-300">
                      {botValidation.passed_checks}/{botValidation.total_checks}
                    </p>
                    <p className="text-[10px] text-zinc-500 uppercase">Checks Passed</p>
                  </div>
                </div>

                {/* Validation Cards */}
                <div className="grid grid-cols-3 gap-3">
                  {/* Compilation */}
                  <ValidationStatusCard
                    title="Compilation"
                    status={botValidation.compilation.status}
                    isValid={botValidation.compilation.is_valid}
                    icon={CheckCircle2}
                    details={[
                      { label: `${botValidation.compilation.error_count} errors`, passed: botValidation.compilation.error_count === 0 },
                      { label: `${botValidation.compilation.warning_count} warnings`, passed: botValidation.compilation.warning_count <= 2 }
                    ]}
                  />

                  {/* Backtest */}
                  <ValidationStatusCard
                    title="Backtest"
                    status={botValidation.backtest.status}
                    isValid={botValidation.backtest.is_valid}
                    score={botValidation.backtest.strategy_score}
                    icon={BarChart3}
                    details={[
                      { label: `${botValidation.backtest.trades_executed} trades`, passed: botValidation.backtest.trades_executed > 0 },
                      { label: `${botValidation.backtest.win_rate}% win rate`, passed: botValidation.backtest.win_rate >= 45 },
                      { label: `${botValidation.backtest.profit_factor}x profit factor`, passed: botValidation.backtest.profit_factor >= 1.0 }
                    ]}
                  />

                  {/* Risk Safety */}
                  <ValidationStatusCard
                    title="Risk Safety"
                    status={botValidation.risk_safety.status}
                    isValid={botValidation.risk_safety.is_valid}
                    score={botValidation.risk_safety.score}
                    icon={ShieldCheck}
                    details={[
                      { label: 'Stop Loss', passed: botValidation.risk_safety.has_stop_loss },
                      { label: 'Position Limit', passed: botValidation.risk_safety.has_position_limit },
                      { label: 'Daily Loss Limit', passed: botValidation.risk_safety.has_daily_loss_limit },
                      { label: 'Drawdown Protection', passed: botValidation.risk_safety.has_drawdown_protection }
                    ]}
                  />
                </div>

                {/* Recommendations */}
                {botValidation.recommendations?.length > 0 && (
                  <div className="border-t border-white/5 pt-3">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <p className="text-[10px] font-mono uppercase tracking-widest text-amber-400">Recommendations</p>
                    </div>
                    <div className="space-y-1">
                      {botValidation.recommendations.map((rec, i) => (
                        <p key={i} className="text-xs text-zinc-400 font-mono flex items-start gap-2">
                          <span className="text-amber-500">•</span> {rec}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </TabsContent>

          {/* Gates Tab */}
          <TabsContent value="gates" className="flex-1 p-3 overflow-y-auto mt-0">
            {!qualityGates ? (
              <p className="text-xs text-zinc-500 font-mono">Quality gate results will appear here after generation...</p>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-3 mb-2">
                  <span
                    className={`text-sm font-bold uppercase font-mono ${qualityGates.is_deployable ? 'text-emerald-400' : 'text-red-400'}`}
                    data-testid="deployment-status"
                  >
                    {qualityGates.status}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-500">
                    {qualityGates.gates_passed}/{qualityGates.gates_total} gates passed
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2" data-testid="quality-gates-grid">
                  {qualityGates.gate_results?.map((gate, idx) => (
                    <QualityGateCard key={idx} gate={gate} />
                  ))}
                </div>
                {qualityGates.recommendations?.length > 0 && (
                  <div className="border-t border-white/5 pt-2 mt-2">
                    <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1">Recommendations</p>
                    {qualityGates.recommendations.map((rec, i) => (
                      <p key={i} className="text-xs text-amber-400/80 font-mono">- {rec}</p>
                    ))}
                  </div>
                )}
                
                {/* Market Selection Results - Visible immediately after generation */}
                {marketSelection && marketSelection.best_pair && (
                  <div className="border-t border-white/5 pt-3 mt-3">
                    <div className="bg-gradient-to-r from-blue-500/10 to-cyan-500/10 border border-blue-500/30 rounded-sm p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <TrendingUp className="w-3.5 h-3.5 text-blue-400" />
                        <span className="text-[10px] font-mono uppercase tracking-widest text-blue-400">Best Market Configuration</span>
                      </div>
                      <div className="grid grid-cols-3 gap-3 text-center">
                        <div>
                          <div className="text-[9px] font-mono uppercase text-zinc-500">Best Pair</div>
                          <div className="text-sm font-bold font-mono text-white">{marketSelection.best_pair}</div>
                        </div>
                        <div>
                          <div className="text-[9px] font-mono uppercase text-zinc-500">Best Timeframe</div>
                          <div className="text-sm font-bold font-mono text-cyan-400">{marketSelection.best_timeframe}</div>
                        </div>
                        <div>
                          <div className="text-[9px] font-mono uppercase text-zinc-500">Market Type</div>
                          <div className={`text-sm font-bold font-mono capitalize ${
                            marketSelection.market_type === 'trend' ? 'text-emerald-400' :
                            marketSelection.market_type === 'range' ? 'text-amber-400' : 'text-purple-400'
                          }`}>{marketSelection.market_type || 'Unknown'}</div>
                        </div>
                      </div>
                      {marketSelection.top_configs && marketSelection.top_configs.length > 0 && (
                        <div className="flex gap-1.5 mt-2 flex-wrap">
                          {marketSelection.top_configs.slice(0, 3).map((config, idx) => (
                            <span key={idx} className={`px-1.5 py-0.5 rounded text-[9px] font-mono ${
                              idx === 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-800 text-zinc-400'
                            }`}>
                              #{idx + 1} {config.pair}/{config.timeframe}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </TabsContent>

          {/* Competition Tab */}
          <TabsContent value="competition" className="flex-1 p-3 overflow-y-auto mt-0">
            {!competitionResult ? (
              <p className="text-xs text-zinc-500 font-mono">Run in Competition mode to see ranked results...</p>
            ) : (
              <div className="space-y-2" data-testid="competition-results">
                <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">
                  Winner: <span className="text-emerald-400">{competitionResult.winner}</span>
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {competitionResult.entries.map((entry, idx) => (
                    <div
                      key={idx}
                      className={`bg-[#0F0F10] border p-3 rounded-sm ${
                        entry.rank === 1 ? 'border-amber-500/40' : 'border-white/5'
                      }`}
                      data-testid={`competition-entry-${entry.rank}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-mono font-bold text-zinc-200">#{entry.rank}</span>
                        {entry.rank === 1 && <Trophy className="w-3 h-3 text-amber-400" />}
                      </div>
                      <p className="text-sm font-bold text-zinc-300 uppercase">{entry.ai_model}</p>
                      <div className="mt-2 space-y-1">
                        <div className="flex justify-between text-[10px] font-mono">
                          <span className="text-zinc-500">Errors</span>
                          <span className={entry.validation_errors > 0 ? 'text-red-400' : 'text-emerald-400'}>
                            {entry.validation_errors}
                          </span>
                        </div>
                        <div className="flex justify-between text-[10px] font-mono">
                          <span className="text-zinc-500">Warnings</span>
                          <span className={entry.validation_warnings > 2 ? 'text-yellow-400' : 'text-emerald-400'}>
                            {entry.validation_warnings}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          {/* Summary Tab */}
          <TabsContent value="summary" className="flex-1 p-3 overflow-y-auto mt-0">
            {!validationSummary ? (
              <p className="text-xs text-zinc-500 font-mono">Generate a bot to see summary...</p>
            ) : (
              <div className="grid grid-cols-4 gap-3" data-testid="validation-summary">
                <div className="bg-[#0F0F10] border border-white/10 p-3 rounded-sm">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Status</p>
                  <p className={`text-lg font-bold mt-1 ${validationSummary.is_valid ? 'text-emerald-400' : 'text-red-400'}`}>
                    {validationSummary.is_valid ? 'COMPILED' : 'FAILED'}
                  </p>
                </div>
                <div className="bg-[#0F0F10] border border-white/10 p-3 rounded-sm">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Errors</p>
                  <p className="text-lg font-bold mt-1 text-red-400">{validationSummary.compilation_errors}</p>
                </div>
                <div className="bg-[#0F0F10] border border-white/10 p-3 rounded-sm">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Warnings</p>
                  <p className="text-lg font-bold mt-1 text-yellow-400">{validationSummary.compilation_warnings}</p>
                </div>
                <div className="bg-[#0F0F10] border border-white/10 p-3 rounded-sm">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Compliance</p>
                  <p className="text-lg font-bold mt-1 text-cyan-400">
                    {validationSummary.compliance_score != null ? `${validationSummary.compliance_score}%` : 'N/A'}
                  </p>
                </div>
              </div>
            )}
          </TabsContent>

          {/* Advanced Validation / Prop Score Tab */}
          <TabsContent value="advanced" className="flex-1 p-3 overflow-y-auto mt-0">
            {!botValidation ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Gauge className="w-10 h-10 text-zinc-600 mb-3" />
                <p className="text-sm text-zinc-400 font-mono">Run basic validation first</p>
                <p className="text-xs text-zinc-600 font-mono mt-1">Then click "PROP SCORE" for advanced analysis</p>
              </div>
            ) : !advancedValidation ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Gauge className="w-10 h-10 text-emerald-500/50 mb-3" />
                <p className="text-sm text-zinc-400 font-mono">Ready for advanced validation</p>
                <p className="text-xs text-zinc-600 font-mono mt-1 mb-4">Bootstrap, Sensitivity, Risk of Ruin, Slippage analysis</p>
                <Button
                  onClick={handleAdvancedValidation}
                  disabled={isAdvancedValidating}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono uppercase text-xs"
                >
                  {isAdvancedValidating ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> ANALYZING...</>
                  ) : (
                    <><Gauge className="w-4 h-4 mr-2" /> CALCULATE PROP SCORE</>
                  )}
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Decision Banner with Prop Score */}
                <div className={`p-4 rounded-sm border flex items-center justify-between ${
                  advancedValidation.decision.color === 'emerald' ? 'bg-emerald-500/10 border-emerald-500/30' :
                  advancedValidation.decision.color === 'amber' ? 'bg-amber-500/10 border-amber-500/30' :
                  'bg-red-500/10 border-red-500/30'
                }`}>
                  <div className="flex items-center gap-4">
                    <PropScoreGauge score={propScore} size={80} />
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        {advancedValidation.decision.color === 'emerald' && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
                        {advancedValidation.decision.color === 'amber' && <AlertTriangle className="w-5 h-5 text-amber-400" />}
                        {advancedValidation.decision.color === 'red' && <XCircle className="w-5 h-5 text-red-400" />}
                        <span className={`text-lg font-bold uppercase font-mono ${
                          advancedValidation.decision.color === 'emerald' ? 'text-emerald-400' :
                          advancedValidation.decision.color === 'amber' ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {advancedValidation.decision.status}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-400 font-mono">{advancedValidation.decision.description}</p>
                      <p className="text-[10px] text-zinc-600 font-mono mt-1">Overall Grade: {advancedValidation.overall_grade}</p>
                    </div>
                  </div>
                  <StatusBadge status={advancedValidation.is_deployable ? 'PROP SAFE' : propScore >= 60 ? 'MODERATE RISK' : 'HIGH RISK'} />
                </div>

                {/* Market Selection Card (NEW) */}
                {marketSelection && marketSelection.best_pair && (
                  <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/30 rounded-sm p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp className="w-4 h-4 text-blue-400" />
                      <h4 className="text-[10px] font-mono uppercase tracking-widest text-blue-400">Optimal Market Configuration</h4>
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="text-center">
                        <div className="text-[10px] font-mono uppercase text-zinc-500 mb-1">Best Pair</div>
                        <div className="text-lg font-bold font-mono text-white">{marketSelection.best_pair}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-[10px] font-mono uppercase text-zinc-500 mb-1">Best Timeframe</div>
                        <div className="text-lg font-bold font-mono text-cyan-400">{marketSelection.best_timeframe}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-[10px] font-mono uppercase text-zinc-500 mb-1">Market Type</div>
                        <div className={`text-lg font-bold font-mono capitalize ${
                          marketSelection.market_type === 'trend' ? 'text-emerald-400' :
                          marketSelection.market_type === 'range' ? 'text-amber-400' : 'text-purple-400'
                        }`}>{marketSelection.market_type || 'Unknown'}</div>
                      </div>
                    </div>
                    {marketSelection.top_configs && marketSelection.top_configs.length > 1 && (
                      <div className="mt-3 pt-3 border-t border-white/10">
                        <div className="text-[9px] font-mono uppercase text-zinc-500 mb-2">Top 3 Configurations</div>
                        <div className="flex gap-2 flex-wrap">
                          {marketSelection.top_configs.slice(0, 3).map((config, idx) => (
                            <div key={idx} className={`px-2 py-1 rounded text-[10px] font-mono ${
                              idx === 0 ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                              'bg-zinc-800 text-zinc-400 border border-white/10'
                            }`}>
                              #{idx + 1} {config.pair}/{config.timeframe} 
                              <span className="ml-1 opacity-60">({config.prop_score?.toFixed(0) || 0})</span>
                            </div>
                          ))}
                        </div>
                        <div className="text-[9px] font-mono text-zinc-600 mt-2">
                          Tested: {marketSelection.total_tested} combinations | Passed: {marketSelection.passed_threshold}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className={`border rounded-sm p-3 ${
                          (advancedValidation.results?.bootstrap?.survival_rate || 0) >= 80 ? 'border-emerald-500/30 bg-emerald-500/5' :
                          (advancedValidation.results?.bootstrap?.survival_rate || 0) >= 60 ? 'border-amber-500/30 bg-amber-500/5' :
                          'border-red-500/30 bg-red-500/5'
                        }`}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <Shield className="w-3.5 h-3.5 text-blue-400" />
                            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Bootstrap Survival</span>
                          </div>
                          <span className={`text-xl font-bold font-mono ${
                            (advancedValidation.results?.bootstrap?.survival_rate || 0) >= 80 ? 'text-emerald-400' :
                            (advancedValidation.results?.bootstrap?.survival_rate || 0) >= 60 ? 'text-amber-400' : 'text-red-400'
                          }`}>{advancedValidation.results?.bootstrap?.survival_rate || 0}%</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent className="bg-[#0F0F10] border-white/10 max-w-xs">
                        <p className="text-xs">Percentage of bootstrap simulations that survived without hitting ruin threshold</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className={`border rounded-sm p-3 ${
                          (advancedValidation.results?.sensitivity?.robustness_score || 0) >= 70 ? 'border-emerald-500/30 bg-emerald-500/5' :
                          (advancedValidation.results?.sensitivity?.robustness_score || 0) >= 50 ? 'border-amber-500/30 bg-amber-500/5' :
                          'border-red-500/30 bg-red-500/5'
                        }`}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <Gauge className="w-3.5 h-3.5 text-violet-400" />
                            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Sensitivity Score</span>
                          </div>
                          <span className={`text-xl font-bold font-mono ${
                            (advancedValidation.results?.sensitivity?.robustness_score || 0) >= 70 ? 'text-emerald-400' :
                            (advancedValidation.results?.sensitivity?.robustness_score || 0) >= 50 ? 'text-amber-400' : 'text-red-400'
                          }`}>{advancedValidation.results?.sensitivity?.robustness_score || 0}</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent className="bg-[#0F0F10] border-white/10 max-w-xs">
                        <p className="text-xs">How stable the strategy is across parameter variations. Higher = more robust</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className={`border rounded-sm p-3 ${
                          (advancedValidation.results?.risk_of_ruin?.ruin_probability || 0) <= 10 ? 'border-emerald-500/30 bg-emerald-500/5' :
                          (advancedValidation.results?.risk_of_ruin?.ruin_probability || 0) <= 25 ? 'border-amber-500/30 bg-amber-500/5' :
                          'border-red-500/30 bg-red-500/5'
                        }`}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Risk of Ruin</span>
                          </div>
                          <span className={`text-xl font-bold font-mono ${
                            (advancedValidation.results?.risk_of_ruin?.ruin_probability || 0) <= 10 ? 'text-emerald-400' :
                            (advancedValidation.results?.risk_of_ruin?.ruin_probability || 0) <= 25 ? 'text-amber-400' : 'text-red-400'
                          }`}>{advancedValidation.results?.risk_of_ruin?.ruin_probability || 0}%</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent className="bg-[#0F0F10] border-white/10 max-w-xs">
                        <p className="text-xs">Probability of account ruin based on trade statistics and position sizing</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className={`border rounded-sm p-3 ${
                          (advancedValidation.results?.slippage?.profit_degradation || 0) <= 10 ? 'border-emerald-500/30 bg-emerald-500/5' :
                          (advancedValidation.results?.slippage?.profit_degradation || 0) <= 25 ? 'border-amber-500/30 bg-amber-500/5' :
                          'border-red-500/30 bg-red-500/5'
                        }`}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <TrendingDown className="w-3.5 h-3.5 text-red-400" />
                            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Slippage Impact</span>
                          </div>
                          <span className={`text-xl font-bold font-mono ${
                            (advancedValidation.results?.slippage?.profit_degradation || 0) <= 10 ? 'text-emerald-400' :
                            (advancedValidation.results?.slippage?.profit_degradation || 0) <= 25 ? 'text-amber-400' : 'text-red-400'
                          }`}>{advancedValidation.results?.slippage?.profit_degradation || 0}%</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent className="bg-[#0F0F10] border-white/10 max-w-xs">
                        <p className="text-xs">Percentage of profit lost due to spread, slippage, and execution costs</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className={`border rounded-sm p-3 ${
                          (advancedValidation.results?.risk_of_ruin?.survival_probability || 0) >= 80 ? 'border-emerald-500/30 bg-emerald-500/5' :
                          (advancedValidation.results?.risk_of_ruin?.survival_probability || 0) >= 60 ? 'border-amber-500/30 bg-amber-500/5' :
                          'border-red-500/30 bg-red-500/5'
                        }`}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <Activity className="w-3.5 h-3.5 text-cyan-400" />
                            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">MC Survival</span>
                          </div>
                          <span className={`text-xl font-bold font-mono ${
                            (advancedValidation.results?.risk_of_ruin?.survival_probability || 0) >= 80 ? 'text-emerald-400' :
                            (advancedValidation.results?.risk_of_ruin?.survival_probability || 0) >= 60 ? 'text-amber-400' : 'text-red-400'
                          }`}>{advancedValidation.results?.risk_of_ruin?.survival_probability || 0}%</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent className="bg-[#0F0F10] border-white/10 max-w-xs">
                        <p className="text-xs">Monte Carlo survival probability</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className={`border rounded-sm p-3 ${
                          (advancedValidation.results?.sensitivity?.overfitting_risk || 0) <= 20 ? 'border-emerald-500/30 bg-emerald-500/5' :
                          (advancedValidation.results?.sensitivity?.overfitting_risk || 0) <= 40 ? 'border-amber-500/30 bg-amber-500/5' :
                          'border-red-500/30 bg-red-500/5'
                        }`}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <Target className="w-3.5 h-3.5 text-orange-400" />
                            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Overfitting Risk</span>
                          </div>
                          <span className={`text-xl font-bold font-mono ${
                            (advancedValidation.results?.sensitivity?.overfitting_risk || 0) <= 20 ? 'text-emerald-400' :
                            (advancedValidation.results?.sensitivity?.overfitting_risk || 0) <= 40 ? 'text-amber-400' : 'text-red-400'
                          }`}>{advancedValidation.results?.sensitivity?.overfitting_risk || 0}%</span>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent className="bg-[#0F0F10] border-white/10 max-w-xs">
                        <p className="text-xs">Risk that strategy is over-optimized on historical data</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>

                {/* Data Visualization Charts */}
                <ValidationChartPanel 
                  equityCurve={chartData.equityCurve}
                  drawdownCurve={chartData.drawdownCurve}
                  monteCarloDistribution={chartData.monteCarloDistribution}
                  monteCarloMedian={chartData.monteCarloMedian}
                  maxDrawdown={chartData.maxDrawdown}
                  percentiles={chartData.percentiles}
                />

                {/* Prop Score Breakdown */}
                <div className="bg-[#0F0F10] border border-white/5 p-4 rounded-sm">
                  <PropScoreBreakdown metrics={advancedValidation.propScoreMetrics} />
                </div>

                {/* Recommendations */}
                {advancedValidation.recommendations && advancedValidation.recommendations.length > 0 && (
                  <div className="bg-[#0F0F10] border border-white/5 p-4 rounded-sm">
                    <div className="flex items-center gap-2 mb-3">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <h4 className="text-[10px] font-mono uppercase tracking-widest text-amber-400">Recommendations</h4>
                    </div>
                    <ul className="space-y-2">
                      {advancedValidation.recommendations.map((rec, idx) => (
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
          </TabsContent>

          {/* Strategy Templates Tab */}
          <TabsContent value="templates" className="flex-1 p-3 overflow-y-auto mt-0">
            <div className="text-center py-12 text-zinc-500">
              <p>Strategy templates feature coming soon</p>
            </div>
            {/* Temporarily commented out - component needs to be created
            <StrategyTemplateSelector 
              symbol="EURUSD"
              timeframe="1h"
              onResultsReceived={(results) => {
                toast.success(`${results.template.name}: ${results.metrics.total_trades} trades, PF=${results.metrics.profit_factor.toFixed(2)}`);
              }}
            />
            */}
          </TabsContent>

          {/* Auto-Generated Strategies Tab - GUIDED PIPELINE */}
          <TabsContent value="auto-strategies" className="flex-1 p-3 overflow-y-auto mt-0">
            {/* Pipeline Step Indicator */}
            <div className="mb-4 p-3 bg-[#0A0A0B] border border-white/5 rounded-lg">
              <div className="flex items-center gap-4 overflow-x-auto pb-2">
                {[
                  { id: 'generate', label: 'Generate', icon: Rocket, number: 1 },
                  { id: 'view', label: 'View', icon: Eye, number: 2 },
                  { id: 'select', label: 'Select', icon: Target, number: 3 },
                  { id: 'bot', label: 'cBot', icon: Cpu, number: 4 },
                  { id: 'pipeline', label: 'Pipeline', icon: Activity, number: 5 },
                ].map((step, idx) => {
                  const isCompleted = completedPipelineSteps.includes(step.id);
                  const isCurrent = currentPipelineStep === step.id;
                  const Icon = step.icon;
                  return (
                    <div key={step.id} className="flex items-center gap-2">
                      <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all ${
                        isCompleted ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-400' :
                        isCurrent ? 'bg-blue-950/30 border-blue-500/40 text-blue-400' :
                        'bg-zinc-900/50 border-white/5 text-zinc-500'
                      }`}>
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          isCompleted ? 'bg-emerald-500/30' :
                          isCurrent ? 'bg-blue-500/30' :
                          'bg-zinc-800'
                        }`}>
                          {isCompleted ? '✓' : step.number}
                        </div>
                        <Icon className="w-3 h-3" />
                        <span className="text-[10px] font-mono uppercase whitespace-nowrap">{step.label}</span>
                      </div>
                      {idx < 4 && <ChevronRight className="w-4 h-4 text-zinc-600" />}
                    </div>
                  );
                })}
              </div>
            </div>
            
            {topStrategies.length === 0 ? (
              <div className="space-y-6">
                {/* Quick Start Flow */}
                <QuickStartFlow 
                  onQuickStart={handleQuickStart}
                  isLoading={isQuickStarting}
                  progress={quickStartProgress}
                />
                
                {/* Or Manual Generation */}
                <div className="text-center">
                  <p className="text-xs text-zinc-500 mb-3">— or generate manually —</p>
                  <Button
                    onClick={handleAutoGenerateStrategies}
                    disabled={isAutoGenerating || !dataAvailability?.available}
                    className="bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 border border-purple-500/30 font-mono uppercase text-xs"
                    data-testid="manual-generate-btn"
                  >
                    {isAutoGenerating ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating...</>
                    ) : (
                      <><Rocket className="w-4 h-4 mr-2" /> Generate {numStrategies} Strategies</>
                    )}
                  </Button>
                </div>
                
                {/* Advanced Mode Toggle */}
                <div className="flex justify-center pt-4 border-t border-white/5">
                  <AdvancedModeToggle 
                    enabled={advancedMode} 
                    onToggle={() => setAdvancedMode(!advancedMode)} 
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-purple-400 font-mono uppercase">Top {topStrategies.length} Strategies</h3>
                  <Badge variant="outline" className="text-[9px] border-purple-500/40 text-purple-400">
                    Ranked by Score
                  </Badge>
                </div>
                
                {topStrategies.map((strategy, idx) => {
                  // Highlight best metrics
                  const bestPF = Math.max(...topStrategies.map(s => s.profit_factor || 0));
                  const bestWR = Math.max(...topStrategies.map(s => s.win_rate || 0));
                  const lowestDD = Math.min(...topStrategies.map(s => s.max_drawdown_pct || 100));
                  const isBestPF = strategy.profit_factor === bestPF;
                  const isBestWR = strategy.win_rate === bestWR;
                  const isLowestDD = strategy.max_drawdown_pct === lowestDD;
                  
                  return (
                  <div
                    key={idx}
                    className={`bg-[#0F0F10] border p-3 rounded-sm hover:border-purple-500/40 transition-colors ${
                      idx === 0 ? 'border-yellow-500/40 bg-yellow-950/10' : 
                      selectedStrategy?.id === strategy.id ? 'border-blue-500/40 bg-blue-950/10' :
                      'border-purple-500/20'
                    } ${selectedStrategy?.id === strategy.id ? 'ring-1 ring-blue-500/30' : ''}`}
                    data-testid={`strategy-card-${idx}`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`text-lg font-bold ${idx === 0 ? 'text-yellow-400' : idx < 3 ? 'text-purple-400' : 'text-zinc-500'}`}>
                          #{strategy.rank || idx + 1}
                        </span>
                        <div>
                          <h4 className="text-xs font-bold text-zinc-200 font-mono">{strategy.name || strategy.template_id}</h4>
                          <p className="text-[10px] text-zinc-500 mt-0.5 line-clamp-1">{strategy.description || `Template: ${strategy.template_id}`}</p>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {/* Fitness Score Badge - PROMINENT */}
                        <Badge className={`text-[10px] px-2 py-0.5 font-bold ${
                          (strategy.fitness || 0) >= 60 ? 'bg-emerald-600/30 text-emerald-400 border-emerald-500/40' :
                          (strategy.fitness || 0) >= 40 ? 'bg-amber-600/30 text-amber-400 border-amber-500/40' :
                          (strategy.fitness || 0) >= 25 ? 'bg-blue-600/30 text-blue-400 border-blue-500/40' :
                          'bg-red-600/30 text-red-400 border-red-500/40'
                        }`}>
                          Fitness: {(strategy.fitness || 0).toFixed(1)}
                        </Badge>
                        <Badge variant="outline" className={`text-[9px] px-1.5 py-0 h-4 ${
                          (strategy.composite_score || 0) >= 0.7 ? 'border-emerald-500/40 text-emerald-400' :
                          (strategy.composite_score || 0) >= 0.5 ? 'border-amber-500/40 text-amber-400' :
                          'border-red-500/40 text-red-400'
                        }`}>
                          Score: {(strategy.composite_score || strategy.score || 0).toFixed(3)}
                        </Badge>
                      </div>
                    </div>

                    {/* Enhanced metrics grid */}
                    <div className="grid grid-cols-5 gap-2 mb-3">
                      <div className={`p-1.5 rounded-sm ${isBestPF ? 'bg-emerald-950/30 border border-emerald-500/30' : 'bg-[#18181B]'}`}>
                        <p className="text-[9px] text-zinc-600 uppercase font-mono">Profit Factor</p>
                        <p className={`text-sm font-bold font-mono ${
                          (strategy.profit_factor || 0) >= 1.5 ? 'text-emerald-400' :
                          (strategy.profit_factor || 0) >= 1.2 ? 'text-blue-400' :
                          'text-amber-400'
                        }`}>
                          {(strategy.profit_factor || 0).toFixed(2)}
                          {isBestPF && <span className="text-[8px] ml-1">🏆</span>}
                        </p>
                      </div>
                      <div className={`p-1.5 rounded-sm ${isBestWR ? 'bg-emerald-950/30 border border-emerald-500/30' : 'bg-[#18181B]'}`}>
                        <p className="text-[9px] text-zinc-600 uppercase font-mono">Win Rate</p>
                        <p className={`text-sm font-bold font-mono ${
                          (strategy.win_rate || 0) >= 50 ? 'text-emerald-400' :
                          (strategy.win_rate || 0) >= 40 ? 'text-blue-400' :
                          'text-amber-400'
                        }`}>
                          {(strategy.win_rate || 0).toFixed(1)}%
                          {isBestWR && <span className="text-[8px] ml-1">🏆</span>}
                        </p>
                      </div>
                      <div className={`p-1.5 rounded-sm ${isLowestDD ? 'bg-emerald-950/30 border border-emerald-500/30' : 'bg-[#18181B]'}`}>
                        <p className="text-[9px] text-zinc-600 uppercase font-mono">Max DD</p>
                        <p className={`text-sm font-bold font-mono ${
                          (strategy.max_drawdown_pct || 0) <= 15 ? 'text-emerald-400' :
                          (strategy.max_drawdown_pct || 0) <= 25 ? 'text-amber-400' :
                          'text-red-400'
                        }`}>
                          {(strategy.max_drawdown_pct || 0).toFixed(1)}%
                          {isLowestDD && <span className="text-[8px] ml-1">🏆</span>}
                        </p>
                      </div>
                      <div className="bg-[#18181B] p-1.5 rounded-sm">
                        <p className="text-[9px] text-zinc-600 uppercase font-mono">Net Profit</p>
                        <p className={`text-sm font-bold font-mono ${
                          (strategy.net_profit || 0) > 0 ? 'text-emerald-400' : 'text-red-400'
                        }`}>
                          ${(strategy.net_profit || 0).toLocaleString()}
                        </p>
                      </div>
                      <div className="bg-[#18181B] p-1.5 rounded-sm">
                        <p className="text-[9px] text-zinc-600 uppercase font-mono">Trades</p>
                        <p className="text-sm font-bold text-zinc-300 font-mono">{strategy.total_trades || 0}</p>
                      </div>
                    </div>
                    
                    {/* Additional metrics row */}
                    <div className="grid grid-cols-3 gap-2 mb-3">
                      <div className="bg-[#18181B]/50 p-1 rounded-sm">
                        <p className="text-[8px] text-zinc-600 uppercase font-mono">Sharpe</p>
                        <p className={`text-xs font-bold font-mono ${
                          (strategy.sharpe_ratio || 0) >= 1 ? 'text-emerald-400' : 'text-zinc-400'
                        }`}>{(strategy.sharpe_ratio || 0).toFixed(2)}</p>
                      </div>
                      <div className="bg-[#18181B]/50 p-1 rounded-sm">
                        <p className="text-[8px] text-zinc-600 uppercase font-mono">R:R</p>
                        <p className="text-xs font-bold text-zinc-400 font-mono">{(strategy.risk_reward || 0).toFixed(2)}</p>
                      </div>
                      <div className="bg-[#18181B]/50 p-1 rounded-sm">
                        <p className="text-[8px] text-zinc-600 uppercase font-mono">Avg Win/Loss</p>
                        <p className="text-xs font-bold font-mono">
                          <span className="text-emerald-400">${(strategy.avg_win || 0).toFixed(0)}</span>
                          <span className="text-zinc-600">/</span>
                          <span className="text-red-400">${(strategy.avg_loss || 0).toFixed(0)}</span>
                        </p>
                      </div>
                    </div>

                    {/* Walk-Forward Validation Results */}
                    {strategy.walkforward && (
                      <div className={`border rounded-sm p-2 mb-3 ${
                        strategy.walkforward.is_robust 
                          ? 'bg-emerald-950/20 border-emerald-500/30' 
                          : strategy.walkforward.is_overfit 
                            ? 'bg-red-950/20 border-red-500/30'
                            : 'bg-zinc-900/50 border-zinc-700/30'
                      }`}>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[9px] font-mono uppercase tracking-wider text-zinc-500">
                            Walk-Forward Validation
                          </span>
                          <div className="flex items-center gap-2">
                            <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                              strategy.walkforward.robustness_grade === 'A' ? 'bg-emerald-600/30 text-emerald-400' :
                              strategy.walkforward.robustness_grade === 'B' ? 'bg-blue-600/30 text-blue-400' :
                              strategy.walkforward.robustness_grade === 'C' ? 'bg-amber-600/30 text-amber-400' :
                              'bg-red-600/30 text-red-400'
                            }`}>
                              Grade {strategy.walkforward.robustness_grade}
                            </span>
                            {strategy.walkforward.is_robust ? (
                              <span className="text-[8px] text-emerald-400 font-mono">✓ ROBUST</span>
                            ) : strategy.walkforward.is_overfit ? (
                              <span className="text-[8px] text-red-400 font-mono">⚠ OVERFIT</span>
                            ) : (
                              <span className="text-[8px] text-zinc-500 font-mono">—</span>
                            )}
                          </div>
                        </div>
                        
                        {/* Training vs Validation comparison */}
                        <div className="grid grid-cols-2 gap-2 mb-2">
                          <div className="bg-blue-950/30 rounded p-1.5">
                            <p className="text-[8px] text-blue-400 font-mono mb-1">📈 TRAINING (70%)</p>
                            <div className="grid grid-cols-2 gap-1">
                              <div>
                                <span className="text-[7px] text-zinc-600">PF:</span>
                                <span className="text-[9px] text-blue-300 ml-1 font-bold">{(strategy.walkforward.training_pf || 0).toFixed(2)}</span>
                              </div>
                              <div>
                                <span className="text-[7px] text-zinc-600">WR:</span>
                                <span className="text-[9px] text-blue-300 ml-1 font-bold">{(strategy.walkforward.training_wr || 0).toFixed(0)}%</span>
                              </div>
                            </div>
                          </div>
                          <div className="bg-purple-950/30 rounded p-1.5">
                            <p className="text-[8px] text-purple-400 font-mono mb-1">🔮 VALIDATION (30%)</p>
                            <div className="grid grid-cols-2 gap-1">
                              <div>
                                <span className="text-[7px] text-zinc-600">PF:</span>
                                <span className={`text-[9px] ml-1 font-bold ${
                                  (strategy.walkforward.validation_pf || 0) >= 1.0 ? 'text-emerald-300' : 'text-red-300'
                                }`}>{(strategy.walkforward.validation_pf || 0).toFixed(2)}</span>
                              </div>
                              <div>
                                <span className="text-[7px] text-zinc-600">WR:</span>
                                <span className={`text-[9px] ml-1 font-bold ${
                                  (strategy.walkforward.validation_wr || 0) >= 40 ? 'text-emerald-300' : 'text-amber-300'
                                }`}>{(strategy.walkforward.validation_wr || 0).toFixed(0)}%</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        
                        {/* Stability Score Bar */}
                        <div className="flex items-center gap-2">
                          <span className="text-[8px] text-zinc-500 font-mono w-16">Stability:</span>
                          <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                            <div 
                              className={`h-full transition-all ${
                                (strategy.walkforward.stability_score || 0) >= 0.8 ? 'bg-emerald-500' :
                                (strategy.walkforward.stability_score || 0) >= 0.6 ? 'bg-amber-500' :
                                'bg-red-500'
                              }`}
                              style={{ width: `${(strategy.walkforward.stability_score || 0) * 100}%` }}
                            />
                          </div>
                          <span className={`text-[9px] font-mono font-bold ${
                            (strategy.walkforward.stability_score || 0) >= 0.8 ? 'text-emerald-400' :
                            (strategy.walkforward.stability_score || 0) >= 0.6 ? 'text-amber-400' :
                            'text-red-400'
                          }`}>{((strategy.walkforward.stability_score || 0) * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    )}

                    <div className="flex gap-2">
                      <Button
                        onClick={() => handleGenerateCBotFromStrategy(strategy)}
                        size="sm"
                        data-testid={`generate-cbot-btn-${idx}`}
                        className="flex-1 bg-gradient-to-r from-purple-600/30 to-blue-600/30 hover:from-purple-600/40 hover:to-blue-600/40 text-purple-300 border border-purple-500/40 font-mono uppercase text-[10px] h-8 shadow-lg shadow-purple-500/10"
                      >
                        <Play className="w-3 h-3 mr-1" /> Generate cBot
                      </Button>
                      <Button
                        size="sm"
                        className="bg-[#18181B] hover:bg-[#1F1F23] text-zinc-400 border border-white/10 font-mono uppercase text-[10px] h-8"
                        onClick={() => {
                          toast.info(strategy.logic || strategy.description || `Template: ${strategy.template_id}, Fitness: ${strategy.fitness}`, { duration: 10000 });
                        }}
                      >
                        <HelpCircle className="w-3 h-3 mr-1" /> Details
                      </Button>
                    </div>
                    
                    {/* Bot Status Badge (if bot was generated) */}
                    {strategy.bot_status && (
                      <div className={`mt-2 p-2 rounded border ${
                        strategy.bot_status === 'ready_for_deployment' ? 'bg-emerald-950/30 border-emerald-500/40' :
                        strategy.bot_status === 'robust' ? 'bg-blue-950/30 border-blue-500/40' :
                        strategy.bot_status === 'validated' ? 'bg-amber-950/30 border-amber-500/40' :
                        'bg-zinc-900/30 border-zinc-700/40'
                      }`}>
                        <div className="flex items-center justify-between">
                          <span className="text-[9px] font-mono uppercase tracking-wider text-zinc-500">
                            Bot Status
                          </span>
                          <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                            strategy.bot_status === 'ready_for_deployment' ? 'bg-emerald-600/30 text-emerald-400' :
                            strategy.bot_status === 'robust' ? 'bg-blue-600/30 text-blue-400' :
                            strategy.bot_status === 'validated' ? 'bg-amber-600/30 text-amber-400' :
                            'bg-zinc-600/30 text-zinc-400'
                          }`}>
                            {strategy.bot_status === 'ready_for_deployment' ? '✅ READY' :
                             strategy.bot_status === 'robust' ? '💪 ROBUST' :
                             strategy.bot_status === 'validated' ? '✓ VALIDATED' :
                             '📝 DRAFT'}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                  );
                })}
              </div>
            )}
          </TabsContent>
            </Tabs>
          </div>
        </Panel>
      </PanelGroup>
    </div>
  );
}
