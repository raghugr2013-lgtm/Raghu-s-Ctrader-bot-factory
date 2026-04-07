import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import {
  Loader2, ArrowLeft, Database, Star, ExternalLink, Copy,
  CheckCircle2, XCircle, AlertTriangle, TrendingUp, TrendingDown,
  Shield, BarChart3, Code2, Eye, Download, RefreshCw, Search,
  ArrowUpDown, ChevronUp, ChevronDown, Gauge, Target, Zap,
  LayoutGrid, List, Sparkles, ArrowRight, Play
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function GradeBadge({ grade, size = 'default' }) {
  const styles = {
    'A+': 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white shadow-lg shadow-emerald-500/25',
    'A': 'bg-gradient-to-r from-emerald-500/80 to-teal-500/80 text-white',
    'B': 'bg-gradient-to-r from-cyan-500/80 to-blue-500/80 text-white',
    'C': 'bg-gradient-to-r from-amber-500/80 to-orange-500/80 text-white',
    'D': 'bg-gradient-to-r from-orange-500/80 to-red-500/80 text-white',
    'F': 'bg-gradient-to-r from-red-500/80 to-rose-500/80 text-white',
  };
  const sizeClass = size === 'large' ? 'w-14 h-14 text-xl' : 'w-10 h-10 text-sm';
  return (
    <span className={`inline-flex items-center justify-center rounded-xl font-bold ${sizeClass} ${styles[grade] || styles['C']}`}>
      {grade}
    </span>
  );
}

function MetricPill({ value, suffix = '', label, good = null }) {
  let colorClass = 'text-zinc-300';
  if (good !== null) {
    colorClass = good ? 'text-emerald-400' : 'text-red-400';
  }
  return (
    <div className="text-center px-3 py-2 rounded-xl bg-[#0B0F14]">
      <p className={`text-lg font-bold ${colorClass}`}>
        {value !== undefined && value !== null ? `${typeof value === 'number' ? value.toFixed(2) : value}${suffix}` : 'N/A'}
      </p>
      <p className="text-[9px] text-zinc-500 uppercase tracking-wider">{label}</p>
    </div>
  );
}

function StrategyCard({ strategy, onView, onCopy }) {
  const score = strategy.score || {};
  const source = strategy.source || {};
  const metadata = strategy.metadata || {};
  
  return (
    <div className="group relative bg-[#111827] border border-[#1F2937] rounded-2xl p-5 transition-all duration-300 hover:border-cyan-500/40 hover:-translate-y-1 hover:shadow-xl hover:shadow-cyan-500/5">
      {/* Hover gradient */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-cyan-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      
      <div className="relative">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0 pr-4">
            <h3 className="text-base font-semibold text-white truncate mb-1">
              {strategy.strategy_name || 'Unknown Strategy'}
            </h3>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] capitalize border-[#1F2937] text-zinc-400">
                {metadata.category?.replace('_', ' ') || 'Unknown'}
              </Badge>
              {source.stars > 0 && (
                <span className="flex items-center gap-1 text-xs text-zinc-500">
                  <Star className="w-3 h-3 text-amber-400" />
                  {source.stars}
                </span>
              )}
            </div>
          </div>
          <GradeBadge grade={score.grade} />
        </div>
        
        {/* Score highlight */}
        <div className="mb-4 pb-4 border-b border-[#1F2937]">
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
              {score.total_score?.toFixed(1) || 'N/A'}
            </span>
            <span className="text-sm text-zinc-500">/100</span>
          </div>
          <p className="text-xs text-zinc-500 mt-1">Total Score</p>
        </div>
        
        {/* Metrics */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          <MetricPill 
            value={score.max_drawdown} 
            suffix="%" 
            label="Max DD"
            good={score.max_drawdown < 6}
          />
          <MetricPill 
            value={score.risk_of_ruin} 
            suffix="%" 
            label="RoR"
            good={score.risk_of_ruin < 5}
          />
          <MetricPill 
            value={score.prop_score?.toFixed(0)} 
            label="Prop"
          />
        </div>
        
        {/* Actions */}
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onView(strategy._id)}
            className="flex-1 h-9 bg-[#0B0F14] hover:bg-cyan-500/10 text-zinc-300 hover:text-cyan-400 border border-[#1F2937] hover:border-cyan-500/30 transition-all"
          >
            <Eye className="w-4 h-4 mr-2" />
            View
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onCopy(strategy._id)}
            className="flex-1 h-9 bg-[#0B0F14] hover:bg-violet-500/10 text-zinc-300 hover:text-violet-400 border border-[#1F2937] hover:border-violet-500/30 transition-all"
          >
            <Code2 className="w-4 h-4 mr-2" />
            Copy Bot
          </Button>
        </div>
      </div>
    </div>
  );
}

function StrategyDetailModal({ strategy, isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [isCopying, setIsCopying] = useState(false);

  if (!strategy) return null;

  const score = strategy.score || {};
  const source = strategy.source || {};
  const metadata = strategy.metadata || {};
  const improvedStrategy = strategy.improved_strategy || {};
  const generatedBot = strategy.generated_bot || {};

  const copyCode = async (code, label) => {
    setIsCopying(true);
    try {
      await navigator.clipboard.writeText(code);
      toast.success(`${label} copied to clipboard!`);
    } catch (err) {
      toast.error('Failed to copy code');
    } finally {
      setIsCopying(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden bg-[#0B0F14] border-[#1F2937]">
        <DialogHeader className="pb-4 border-b border-[#1F2937]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <GradeBadge grade={score.grade} size="large" />
              <div>
                <DialogTitle className="text-xl text-white">{strategy.strategy_name}</DialogTitle>
                <p className="text-sm text-zinc-500 mt-1">{source.repo_full_name || 'Manual submission'}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
                {score.total_score?.toFixed(1)}
              </p>
              <p className="text-xs text-zinc-500">Total Score</p>
            </div>
          </div>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 overflow-hidden">
          <TabsList className="bg-[#111827] border border-[#1F2937] p-1">
            <TabsTrigger value="overview" className="text-xs data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-400">Overview</TabsTrigger>
            <TabsTrigger value="strategy" className="text-xs data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-400">Strategy</TabsTrigger>
            <TabsTrigger value="code" className="text-xs data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-400">Generated Bot</TabsTrigger>
            <TabsTrigger value="original" className="text-xs data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-400">Original Code</TabsTrigger>
          </TabsList>

          <div className="overflow-y-auto max-h-[55vh] mt-4 pr-2">
            <TabsContent value="overview" className="mt-0 space-y-4">
              {/* Score Grid */}
              <div className="grid grid-cols-5 gap-3">
                {[
                  { value: score.total_score?.toFixed(1), label: 'Total', color: 'cyan' },
                  { value: score.prop_score?.toFixed(0), label: 'Prop', color: 'emerald' },
                  { value: `${score.max_drawdown?.toFixed(1)}%`, label: 'Max DD', color: score.max_drawdown < 6 ? 'emerald' : 'red' },
                  { value: `${score.risk_of_ruin?.toFixed(2)}%`, label: 'RoR', color: score.risk_of_ruin < 5 ? 'emerald' : 'red' },
                  { value: score.stability_score?.toFixed(0), label: 'Stability', color: 'violet' },
                ].map((item, idx) => (
                  <div key={idx} className={`rounded-xl bg-[#111827] border border-[#1F2937] p-4 text-center`}>
                    <p className={`text-2xl font-bold text-${item.color}-400`}>{item.value}</p>
                    <p className="text-[10px] text-zinc-500 uppercase mt-1">{item.label}</p>
                  </div>
                ))}
              </div>

              {/* Source Info */}
              <div className="rounded-xl bg-[#111827] border border-[#1F2937] p-4">
                <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Source</h4>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white">{source.repo_full_name || 'N/A'}</p>
                    <p className="text-xs text-zinc-500 mt-1">{source.description || 'No description'}</p>
                  </div>
                  <div className="flex items-center gap-4">
                    {source.stars !== undefined && (
                      <div className="flex items-center gap-1.5 text-sm text-zinc-400">
                        <Star className="w-4 h-4 text-amber-400" />
                        {source.stars}
                      </div>
                    )}
                    {source.source_url && (
                      <a
                        href={source.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-sm text-cyan-400 hover:text-cyan-300"
                      >
                        <ExternalLink className="w-4 h-4" />
                        GitHub
                      </a>
                    )}
                  </div>
                </div>
              </div>

              {/* Approval Reasons */}
              {score.approval_reasons?.length > 0 && (
                <div className="rounded-xl bg-emerald-500/5 border border-emerald-500/20 p-4">
                  <h4 className="text-xs font-medium text-emerald-400 uppercase tracking-wider mb-3">Approval Criteria Met</h4>
                  <div className="space-y-2">
                    {score.approval_reasons.map((reason, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-sm text-emerald-300">
                        <CheckCircle2 className="w-4 h-4 shrink-0" />
                        {reason}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {score.recommendations?.length > 0 && (
                <div className="rounded-xl bg-amber-500/5 border border-amber-500/20 p-4">
                  <h4 className="text-xs font-medium text-amber-400 uppercase tracking-wider mb-3">Recommendations</h4>
                  <div className="space-y-2">
                    {score.recommendations.map((rec, idx) => (
                      <div key={idx} className="flex items-start gap-2 text-sm text-amber-300/80">
                        <Sparkles className="w-4 h-4 mt-0.5 shrink-0" />
                        {rec}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="strategy" className="mt-0 space-y-4">
              {/* Risk Config */}
              {improvedStrategy.risk_config && (
                <div className="rounded-xl bg-[#111827] border border-[#1F2937] p-4">
                  <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-4">Risk Configuration</h4>
                  <div className="grid grid-cols-4 gap-4">
                    {[
                      { label: 'Stop Loss', value: `${improvedStrategy.risk_config.stop_loss_value} pips` },
                      { label: 'Take Profit', value: `${improvedStrategy.risk_config.take_profit_value} pips` },
                      { label: 'Position Sizing', value: improvedStrategy.risk_config.position_sizing?.replace('_', ' ') },
                      { label: 'Trailing Stop', value: improvedStrategy.risk_config.trailing_stop ? 'Enabled' : 'Disabled' },
                    ].map((item, idx) => (
                      <div key={idx}>
                        <p className="text-[10px] text-zinc-500 uppercase">{item.label}</p>
                        <p className="text-sm text-white capitalize mt-1">{item.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Indicators */}
              {improvedStrategy.indicators?.length > 0 && (
                <div className="rounded-xl bg-[#111827] border border-[#1F2937] p-4">
                  <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Indicators</h4>
                  <div className="space-y-2">
                    {improvedStrategy.indicators.map((ind, idx) => (
                      <div key={idx} className="flex items-center justify-between bg-[#0B0F14] rounded-lg px-4 py-3">
                        <span className="text-sm text-white">{ind.display_name || ind.type}</span>
                        <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/20">{ind.role}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Filters */}
              {improvedStrategy.filters?.length > 0 && (
                <div className="rounded-xl bg-[#111827] border border-[#1F2937] p-4">
                  <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">Filters</h4>
                  <div className="space-y-2">
                    {improvedStrategy.filters.map((filter, idx) => (
                      <div key={idx} className="flex items-center justify-between bg-[#0B0F14] rounded-lg px-4 py-3">
                        <span className="text-sm text-white">{filter.name}</span>
                        <Badge className="bg-violet-500/10 text-violet-400 border-violet-500/20">{filter.type}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="code" className="mt-0">
              {generatedBot?.code ? (
                <div className="rounded-xl bg-[#111827] border border-[#1F2937] overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-[#1F2937]">
                    <span className="text-sm text-zinc-400">Generated Optimized Bot</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyCode(generatedBot.code, 'Generated bot code')}
                      disabled={isCopying}
                      className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
                    >
                      <Copy className="w-4 h-4 mr-2" />
                      Copy Code
                    </Button>
                  </div>
                  <pre className="p-4 text-xs text-zinc-300 overflow-x-auto max-h-80 font-mono bg-[#0B0F14]">
                    {generatedBot.code}
                  </pre>
                </div>
              ) : (
                <div className="rounded-xl bg-[#111827] border border-[#1F2937] p-12 text-center">
                  <Code2 className="w-12 h-12 mx-auto mb-4 text-zinc-700" />
                  <p className="text-sm text-zinc-500">No generated bot available</p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="original" className="mt-0">
              {strategy.original_code ? (
                <div className="rounded-xl bg-[#111827] border border-[#1F2937] overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-[#1F2937]">
                    <span className="text-sm text-zinc-400">Original Source Code</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyCode(strategy.original_code, 'Original code')}
                      disabled={isCopying}
                      className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
                    >
                      <Copy className="w-4 h-4 mr-2" />
                      Copy Code
                    </Button>
                  </div>
                  <pre className="p-4 text-xs text-zinc-300 overflow-x-auto max-h-80 font-mono bg-[#0B0F14]">
                    {strategy.original_code}
                  </pre>
                </div>
              ) : (
                <div className="rounded-xl bg-[#111827] border border-[#1F2937] p-12 text-center">
                  <Code2 className="w-12 h-12 mx-auto mb-4 text-zinc-700" />
                  <p className="text-sm text-zinc-500">Original code not available</p>
                </div>
              )}
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

export default function StrategyLibraryPage() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [strategies, setStrategies] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [viewMode, setViewMode] = useState('grid');
  
  // Filters
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [sortBy, setSortBy] = useState('score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [limit, setLimit] = useState(20);

  const fetchStrategies = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({ limit: limit.toString() });
      if (categoryFilter !== 'all') {
        params.append('category', categoryFilter);
      }
      
      const response = await axios.get(`${API}/discovery/top-strategies?${params}`);
      let data = response.data.strategies || [];
      
      data.sort((a, b) => {
        let aVal, bVal;
        if (sortBy === 'score') {
          aVal = a.score?.total_score || 0;
          bVal = b.score?.total_score || 0;
        } else if (sortBy === 'drawdown') {
          aVal = a.score?.max_drawdown || 100;
          bVal = b.score?.max_drawdown || 100;
        } else if (sortBy === 'ror') {
          aVal = a.score?.risk_of_ruin || 100;
          bVal = b.score?.risk_of_ruin || 100;
        } else if (sortBy === 'prop') {
          aVal = a.score?.prop_score || 0;
          bVal = b.score?.prop_score || 0;
        }
        return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
      });
      
      setStrategies(data);
    } catch (error) {
      toast.error('Failed to load strategies');
    } finally {
      setIsLoading(false);
    }
  }, [categoryFilter, sortBy, sortOrder, limit]);

  const fetchStatistics = async () => {
    try {
      const response = await axios.get(`${API}/discovery/statistics`);
      setStatistics(response.data.statistics);
    } catch (error) {
      console.error('Failed to load statistics');
    }
  };

  useEffect(() => {
    fetchStrategies();
    fetchStatistics();
  }, [fetchStrategies]);

  const viewStrategy = async (strategyId) => {
    try {
      const response = await axios.get(`${API}/discovery/strategy/${strategyId}`);
      setSelectedStrategy(response.data.strategy);
      setDetailModalOpen(true);
    } catch (error) {
      toast.error('Failed to load strategy details');
    }
  };

  const copyGeneratedCode = async (strategyId) => {
    try {
      const response = await axios.get(`${API}/discovery/strategy/${strategyId}`);
      const code = response.data.strategy?.generated_bot?.code;
      if (code) {
        await navigator.clipboard.writeText(code);
        toast.success('Bot code copied to clipboard!');
      } else {
        toast.error('No generated code available');
      }
    } catch (error) {
      toast.error('Failed to copy code');
    }
  };

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return <ArrowUpDown className="w-3 h-3 opacity-30" />;
    return sortOrder === 'desc' 
      ? <ChevronDown className="w-3 h-3 text-cyan-400" />
      : <ChevronUp className="w-3 h-3 text-cyan-400" />;
  };

  return (
    <div className="min-h-screen bg-[#0B0F14]" data-testid="strategy-library-page">
      {/* Header */}
      <div className="sticky top-0 z-50 backdrop-blur-xl bg-[#0B0F14]/80 border-b border-[#1F2937]">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/')}
              className="text-zinc-400 hover:text-white hover:bg-white/5"
              data-testid="back-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Dashboard
            </Button>
            <div className="h-6 w-px bg-[#1F2937]" />
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
                <Database className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-semibold text-white">Strategy Library</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/discovery')}
              className="text-violet-400 hover:text-violet-300 hover:bg-violet-500/10"
            >
              <Search className="w-4 h-4 mr-2" />
              Discovery
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => { fetchStrategies(); fetchStatistics(); }}
              className="text-zinc-400 hover:text-white hover:bg-white/5"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Statistics */}
        {statistics && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            {[
              { value: statistics.total_approved, label: 'Approved', color: 'from-cyan-500/20 to-cyan-500/5 border-cyan-500/20', textColor: 'text-cyan-400', icon: CheckCircle2 },
              { value: statistics.total_rejected, label: 'Rejected', color: 'from-red-500/20 to-red-500/5 border-red-500/20', textColor: 'text-red-400', icon: XCircle },
              { value: statistics.average_score?.toFixed(1), label: 'Avg Score', color: 'from-emerald-500/20 to-emerald-500/5 border-emerald-500/20', textColor: 'text-emerald-400', icon: BarChart3 },
              { value: statistics.grades?.['A+'] || 0, label: 'A+ Grade', color: 'from-amber-500/20 to-amber-500/5 border-amber-500/20', textColor: 'text-amber-400', icon: Star },
              { value: statistics.grades?.['A'] || 0, label: 'A Grade', color: 'from-violet-500/20 to-violet-500/5 border-violet-500/20', textColor: 'text-violet-400', icon: Target },
            ].map((stat, idx) => (
              <div key={idx} className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${stat.color} border p-5`}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className={`text-3xl font-bold text-white`}>{stat.value}</p>
                    <p className="text-sm text-zinc-400 mt-1">{stat.label}</p>
                  </div>
                  <stat.icon className={`w-6 h-6 ${stat.textColor} opacity-60`} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Filters Bar */}
        <div className="flex items-center justify-between gap-4 mb-6 p-4 rounded-2xl bg-[#111827] border border-[#1F2937]">
          <div className="flex items-center gap-4">
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-48 bg-[#0B0F14] border-[#1F2937] text-white">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent className="bg-[#111827] border-[#1F2937]">
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="trend_following">Trend Following</SelectItem>
                <SelectItem value="mean_reversion">Mean Reversion</SelectItem>
                <SelectItem value="breakout">Breakout</SelectItem>
                <SelectItem value="scalping">Scalping</SelectItem>
              </SelectContent>
            </Select>
            
            <Select value={sortBy} onValueChange={(v) => setSortBy(v)}>
              <SelectTrigger className="w-40 bg-[#0B0F14] border-[#1F2937] text-white">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent className="bg-[#111827] border-[#1F2937]">
                <SelectItem value="score">Score</SelectItem>
                <SelectItem value="drawdown">Max DD</SelectItem>
                <SelectItem value="ror">Risk of Ruin</SelectItem>
                <SelectItem value="prop">Prop Score</SelectItem>
              </SelectContent>
            </Select>

            <Select value={limit.toString()} onValueChange={(v) => setLimit(parseInt(v))}>
              <SelectTrigger className="w-32 bg-[#0B0F14] border-[#1F2937] text-white">
                <SelectValue placeholder="Limit" />
              </SelectTrigger>
              <SelectContent className="bg-[#111827] border-[#1F2937]">
                <SelectItem value="10">10 results</SelectItem>
                <SelectItem value="20">20 results</SelectItem>
                <SelectItem value="50">50 results</SelectItem>
                <SelectItem value="100">100 results</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* View Toggle */}
          <div className="flex items-center gap-1 p-1 rounded-xl bg-[#0B0F14] border border-[#1F2937]">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg transition-all ${viewMode === 'grid' ? 'bg-cyan-500/20 text-cyan-400' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`p-2 rounded-lg transition-all ${viewMode === 'table' ? 'bg-cyan-500/20 text-cyan-400' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <Loader2 className="w-10 h-10 animate-spin text-cyan-500 mx-auto mb-4" />
              <p className="text-zinc-400">Loading strategies...</p>
            </div>
          </div>
        ) : strategies.length === 0 ? (
          <div className="rounded-2xl bg-[#111827] border border-[#1F2937] p-16 text-center">
            <div className="w-20 h-20 mx-auto mb-6 rounded-3xl bg-gradient-to-br from-zinc-800 to-zinc-900 flex items-center justify-center">
              <Database className="w-10 h-10 text-zinc-600" />
            </div>
            <h3 className="text-2xl font-semibold text-white mb-3">No Strategies Yet</h3>
            <p className="text-zinc-400 max-w-md mx-auto mb-6">
              Run the Discovery Engine to find and analyze trading bots from GitHub.
            </p>
            <Button
              onClick={() => navigate('/discovery')}
              className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-semibold shadow-lg shadow-violet-500/25"
            >
              <Search className="w-4 h-4 mr-2" />
              Go to Discovery
            </Button>
          </div>
        ) : viewMode === 'grid' ? (
          /* Grid View */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {strategies.map((strategy) => (
              <StrategyCard 
                key={strategy._id} 
                strategy={strategy} 
                onView={viewStrategy}
                onCopy={copyGeneratedCode}
              />
            ))}
          </div>
        ) : (
          /* Table View */
          <div className="rounded-2xl bg-[#111827] border border-[#1F2937] overflow-hidden">
            {/* Table Header */}
            <div className="grid grid-cols-12 gap-4 px-6 py-4 bg-[#0B0F14] border-b border-[#1F2937] text-xs font-medium uppercase text-zinc-500 tracking-wider">
              <div className="col-span-3">Strategy</div>
              <div className="col-span-1 flex items-center gap-1 cursor-pointer hover:text-zinc-300" onClick={() => toggleSort('score')}>
                Score <SortIcon field="score" />
              </div>
              <div className="col-span-1">Grade</div>
              <div className="col-span-1 flex items-center gap-1 cursor-pointer hover:text-zinc-300" onClick={() => toggleSort('drawdown')}>
                Max DD <SortIcon field="drawdown" />
              </div>
              <div className="col-span-1 flex items-center gap-1 cursor-pointer hover:text-zinc-300" onClick={() => toggleSort('ror')}>
                RoR <SortIcon field="ror" />
              </div>
              <div className="col-span-1 flex items-center gap-1 cursor-pointer hover:text-zinc-300" onClick={() => toggleSort('prop')}>
                Prop <SortIcon field="prop" />
              </div>
              <div className="col-span-1">Type</div>
              <div className="col-span-2 text-right">Actions</div>
            </div>

            {/* Table Body */}
            <div className="divide-y divide-[#1F2937]">
              {strategies.map((strategy) => {
                const score = strategy.score || {};
                const source = strategy.source || {};
                const metadata = strategy.metadata || {};
                
                return (
                  <div 
                    key={strategy._id} 
                    className="grid grid-cols-12 gap-4 px-6 py-4 hover:bg-white/[0.02] transition-colors items-center"
                  >
                    <div className="col-span-3">
                      <p className="text-sm text-white font-medium truncate">{strategy.strategy_name}</p>
                      <p className="text-xs text-zinc-500 truncate">{source.repo_full_name || 'N/A'}</p>
                    </div>
                    <div className="col-span-1">
                      <span className="text-lg font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
                        {score.total_score?.toFixed(1)}
                      </span>
                    </div>
                    <div className="col-span-1">
                      <GradeBadge grade={score.grade} />
                    </div>
                    <div className="col-span-1">
                      <span className={`font-mono text-sm ${score.max_drawdown < 6 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {score.max_drawdown?.toFixed(1)}%
                      </span>
                    </div>
                    <div className="col-span-1">
                      <span className={`font-mono text-sm ${score.risk_of_ruin < 5 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {score.risk_of_ruin?.toFixed(2)}%
                      </span>
                    </div>
                    <div className="col-span-1">
                      <span className="font-mono text-sm text-zinc-300">{score.prop_score?.toFixed(0)}</span>
                    </div>
                    <div className="col-span-1">
                      <Badge className="text-[10px] capitalize bg-[#0B0F14] text-zinc-400 border-[#1F2937]">
                        {metadata.category?.replace('_', ' ') || 'N/A'}
                      </Badge>
                    </div>
                    <div className="col-span-2 flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => viewStrategy(strategy._id)}
                        className="h-8 px-3 text-xs text-zinc-400 hover:text-cyan-400 hover:bg-cyan-500/10"
                      >
                        <Eye className="w-3 h-3 mr-1" />
                        View
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyGeneratedCode(strategy._id)}
                        className="h-8 px-3 text-xs text-zinc-400 hover:text-violet-400 hover:bg-violet-500/10"
                      >
                        <Copy className="w-3 h-3 mr-1" />
                        Copy
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      <StrategyDetailModal
        strategy={selectedStrategy}
        isOpen={detailModalOpen}
        onClose={() => setDetailModalOpen(false)}
      />
    </div>
  );
}
