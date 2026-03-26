import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  PropScoreBadge,
  StatusBadge,
  calculatePropScore,
  getDecisionStatus,
  getStatusColor
} from '@/components/validation/PropScore';
import {
  Trophy, Filter, Search, TrendingUp, TrendingDown,
  Shield, Activity, Gauge, AlertTriangle, ChevronUp, ChevronDown,
  Clock, BarChart3, Zap, Target, SortAsc, SortDesc
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

/**
 * Strategy Card for Leaderboard
 */
function StrategyCard({ strategy, rank, onSelect }) {
  const decision = getDecisionStatus(strategy.propScore);
  const isTop3 = rank <= 3;
  
  const rankColors = {
    1: 'from-amber-500/20 to-amber-500/5 border-amber-500/40',
    2: 'from-zinc-400/20 to-zinc-400/5 border-zinc-400/40',
    3: 'from-amber-700/20 to-amber-700/5 border-amber-700/40'
  };

  return (
    <div 
      className={cn(
        'bg-gradient-to-br border rounded-sm p-4 cursor-pointer transition-all hover:scale-[1.02]',
        isTop3 ? rankColors[rank] : 'from-[#0F0F10] to-[#0A0A0A] border-white/5 hover:border-white/10'
      )}
      onClick={() => onSelect && onSelect(strategy)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center font-bold font-mono text-sm',
            rank === 1 && 'bg-amber-500/20 text-amber-400',
            rank === 2 && 'bg-zinc-400/20 text-zinc-300',
            rank === 3 && 'bg-amber-700/20 text-amber-600',
            rank > 3 && 'bg-zinc-800 text-zinc-500'
          )}>
            {rank <= 3 ? <Trophy className="w-4 h-4" /> : `#${rank}`}
          </div>
          <div>
            <h4 className="text-sm font-bold text-zinc-200 uppercase tracking-wide">
              {strategy.name || `Strategy ${strategy.id?.slice(-6)}`}
            </h4>
            <p className="text-[10px] text-zinc-500 font-mono">
              {strategy.market || 'EURUSD'} • {strategy.timeframe || 'H1'}
            </p>
          </div>
        </div>
        <PropScoreBadge score={strategy.propScore} size="sm" showLabel={false} />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="text-center">
          <p className="text-[10px] text-zinc-500 uppercase">Survival</p>
          <p className={cn('text-sm font-bold font-mono', 
            strategy.bootstrapSurvival >= 80 ? 'text-emerald-400' : 
            strategy.bootstrapSurvival >= 60 ? 'text-amber-400' : 'text-red-400'
          )}>
            {strategy.bootstrapSurvival?.toFixed(0) || 0}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-zinc-500 uppercase">Ruin Risk</p>
          <p className={cn('text-sm font-bold font-mono',
            strategy.riskOfRuin <= 5 ? 'text-emerald-400' :
            strategy.riskOfRuin <= 15 ? 'text-amber-400' : 'text-red-400'
          )}>
            {strategy.riskOfRuin?.toFixed(1) || 0}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-[10px] text-zinc-500 uppercase">Max DD</p>
          <p className={cn('text-sm font-bold font-mono',
            strategy.maxDrawdown <= 10 ? 'text-emerald-400' :
            strategy.maxDrawdown <= 20 ? 'text-amber-400' : 'text-red-400'
          )}>
            {strategy.maxDrawdown?.toFixed(1) || 0}%
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-white/5">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[9px] text-zinc-500 border-zinc-700">
            {strategy.strategyType || 'Trend'}
          </Badge>
          {strategy.propReady && (
            <Badge variant="outline" className="text-[9px] text-emerald-400 border-emerald-500/40 bg-emerald-500/10">
              PROP READY
            </Badge>
          )}
        </div>
        <span className="text-[10px] text-zinc-600 font-mono">
          {strategy.totalTrades || 0} trades
        </span>
      </div>
    </div>
  );
}

/**
 * Leaderboard Table Row
 */
function LeaderboardRow({ strategy, rank, onSelect }) {
  const decision = getDecisionStatus(strategy.propScore);
  
  return (
    <tr 
      className="border-b border-white/5 hover:bg-white/[0.02] cursor-pointer transition-colors"
      onClick={() => onSelect && onSelect(strategy)}
    >
      <td className="px-4 py-3">
        <div className={cn(
          'w-6 h-6 rounded-full flex items-center justify-center font-bold font-mono text-xs',
          rank === 1 && 'bg-amber-500/20 text-amber-400',
          rank === 2 && 'bg-zinc-400/20 text-zinc-300',
          rank === 3 && 'bg-amber-700/20 text-amber-600',
          rank > 3 && 'bg-zinc-800 text-zinc-500'
        )}>
          {rank}
        </div>
      </td>
      <td className="px-4 py-3">
        <div>
          <p className="text-sm font-medium text-zinc-200">{strategy.name || `Strategy ${strategy.id?.slice(-6)}`}</p>
          <p className="text-[10px] text-zinc-500 font-mono">{strategy.market || 'EURUSD'} • {strategy.timeframe || 'H1'}</p>
        </div>
      </td>
      <td className="px-4 py-3 text-center">
        <div className={cn(
          'inline-flex items-center justify-center w-12 h-8 rounded font-bold font-mono text-sm',
          decision.color === 'emerald' && 'bg-emerald-500/20 text-emerald-400',
          decision.color === 'amber' && 'bg-amber-500/20 text-amber-400',
          decision.color === 'red' && 'bg-red-500/20 text-red-400'
        )}>
          {strategy.propScore}
        </div>
      </td>
      <td className="px-4 py-3 text-center">
        <span className={cn('text-sm font-mono',
          strategy.bootstrapSurvival >= 80 ? 'text-emerald-400' :
          strategy.bootstrapSurvival >= 60 ? 'text-amber-400' : 'text-red-400'
        )}>
          {strategy.bootstrapSurvival?.toFixed(0) || 0}%
        </span>
      </td>
      <td className="px-4 py-3 text-center">
        <span className={cn('text-sm font-mono',
          strategy.riskOfRuin <= 5 ? 'text-emerald-400' :
          strategy.riskOfRuin <= 15 ? 'text-amber-400' : 'text-red-400'
        )}>
          {strategy.riskOfRuin?.toFixed(1) || 0}%
        </span>
      </td>
      <td className="px-4 py-3 text-center">
        <span className={cn('text-sm font-mono',
          strategy.maxDrawdown <= 10 ? 'text-emerald-400' :
          strategy.maxDrawdown <= 20 ? 'text-amber-400' : 'text-red-400'
        )}>
          {strategy.maxDrawdown?.toFixed(1) || 0}%
        </span>
      </td>
      <td className="px-4 py-3 text-center">
        <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-700">
          {strategy.strategyType || 'Trend'}
        </Badge>
      </td>
      <td className="px-4 py-3 text-center">
        <StatusBadge status={strategy.propReady ? 'PROP SAFE' : strategy.propScore >= 60 ? 'NEEDS WORK' : 'HIGH RISK'} />
      </td>
    </tr>
  );
}

/**
 * Advanced Leaderboard Component
 */
export default function Leaderboard({ 
  strategies: initialStrategies = [],
  onSelectStrategy,
  view = 'table'
}) {
  const [strategies, setStrategies] = useState(initialStrategies);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterMarket, setFilterMarket] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [filterPropReady, setFilterPropReady] = useState(false);
  const [sortBy, setSortBy] = useState('propScore');
  const [sortOrder, setSortOrder] = useState('desc');
  const [currentView, setCurrentView] = useState(view);

  // Process and enrich strategies with prop scores
  const enrichedStrategies = useMemo(() => {
    return strategies.map(s => {
      const propScore = s.propScore || calculatePropScore({
        bootstrapSurvival: s.bootstrapSurvival || s.survival_rate || 70,
        monteCarloSurvival: s.monteCarloSurvival || s.mc_survival || 70,
        maxDrawdown: s.maxDrawdown || s.max_drawdown || 15,
        sensitivityScore: s.sensitivityScore || s.sensitivity || 60,
        walkForwardScore: s.walkForwardScore || s.wf_score || 65,
        profitability: s.profitability || s.profit_probability || 60,
        challengePassProb: s.challengePassProb || s.pass_probability || 0.6,
        consistencyScore: s.consistencyScore || s.consistency || 70
      });
      
      return {
        ...s,
        propScore,
        propReady: propScore >= 80,
        decision: getDecisionStatus(propScore)
      };
    });
  }, [strategies]);

  // Filter and sort strategies
  const filteredStrategies = useMemo(() => {
    let result = [...enrichedStrategies];
    
    // Search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(s => 
        (s.name || '').toLowerCase().includes(term) ||
        (s.id || '').toLowerCase().includes(term) ||
        (s.market || '').toLowerCase().includes(term)
      );
    }
    
    // Market filter
    if (filterMarket !== 'all') {
      result = result.filter(s => (s.market || 'EURUSD') === filterMarket);
    }
    
    // Type filter
    if (filterType !== 'all') {
      result = result.filter(s => (s.strategyType || 'Trend') === filterType);
    }
    
    // Prop ready filter
    if (filterPropReady) {
      result = result.filter(s => s.propReady);
    }
    
    // Sort
    result.sort((a, b) => {
      const aVal = a[sortBy] || 0;
      const bVal = b[sortBy] || 0;
      return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
    });
    
    return result;
  }, [enrichedStrategies, searchTerm, filterMarket, filterType, filterPropReady, sortBy, sortOrder]);

  // Get unique markets and types for filters
  const markets = useMemo(() => {
    const set = new Set(enrichedStrategies.map(s => s.market || 'EURUSD'));
    return ['all', ...Array.from(set)];
  }, [enrichedStrategies]);

  const strategyTypes = useMemo(() => {
    const set = new Set(enrichedStrategies.map(s => s.strategyType || 'Trend'));
    return ['all', ...Array.from(set)];
  }, [enrichedStrategies]);

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return <SortAsc className="w-3 h-3 text-zinc-600" />;
    return sortOrder === 'desc' ? 
      <SortDesc className="w-3 h-3 text-violet-400" /> : 
      <SortAsc className="w-3 h-3 text-violet-400" />;
  };

  return (
    <div className="bg-[#0A0A0A] border border-white/5 rounded-sm overflow-hidden">
      {/* Header */}
      <div className="border-b border-white/5 px-4 py-3 bg-[#18181B] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Trophy className="w-5 h-5 text-amber-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Strategy Leaderboard</h3>
          <Badge variant="outline" className="text-[10px] text-zinc-500">
            {filteredStrategies.length} strategies
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            className={cn('h-7 px-2', currentView === 'cards' && 'bg-white/5')}
            onClick={() => setCurrentView('cards')}
          >
            <BarChart3 className="w-4 h-4" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className={cn('h-7 px-2', currentView === 'table' && 'bg-white/5')}
            onClick={() => setCurrentView('table')}
          >
            <Activity className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="border-b border-white/5 px-4 py-3 flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <Input
            placeholder="Search strategies..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-8 bg-[#0F0F10] border-white/10 text-sm"
          />
        </div>
        
        <Select value={filterMarket} onValueChange={setFilterMarket}>
          <SelectTrigger className="w-[130px] h-8 bg-[#0F0F10] border-white/10 text-xs">
            <SelectValue placeholder="Market" />
          </SelectTrigger>
          <SelectContent className="bg-[#0F0F10] border-white/10">
            {markets.map(m => (
              <SelectItem key={m} value={m} className="text-xs">
                {m === 'all' ? 'All Markets' : m}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-[130px] h-8 bg-[#0F0F10] border-white/10 text-xs">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent className="bg-[#0F0F10] border-white/10">
            {strategyTypes.map(t => (
              <SelectItem key={t} value={t} className="text-xs">
                {t === 'all' ? 'All Types' : t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          size="sm"
          variant={filterPropReady ? 'default' : 'outline'}
          className={cn(
            'h-8 text-[10px] uppercase font-mono',
            filterPropReady && 'bg-emerald-600 hover:bg-emerald-500'
          )}
          onClick={() => setFilterPropReady(!filterPropReady)}
        >
          <Shield className="w-3 h-3 mr-1" />
          Prop Ready Only
        </Button>
      </div>

      {/* Content */}
      <div className="p-4">
        {filteredStrategies.length === 0 ? (
          <div className="text-center py-12">
            <Trophy className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
            <p className="text-sm text-zinc-400 font-mono">No strategies found</p>
            <p className="text-xs text-zinc-600 font-mono mt-1">Try adjusting your filters</p>
          </div>
        ) : currentView === 'cards' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredStrategies.map((strategy, idx) => (
              <StrategyCard
                key={strategy.id || idx}
                strategy={strategy}
                rank={idx + 1}
                onSelect={onSelectStrategy}
              />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="px-4 py-2 text-left text-[10px] font-mono uppercase tracking-widest text-zinc-500 w-12">Rank</th>
                  <th className="px-4 py-2 text-left text-[10px] font-mono uppercase tracking-widest text-zinc-500">Strategy</th>
                  <th 
                    className="px-4 py-2 text-center text-[10px] font-mono uppercase tracking-widest text-zinc-500 cursor-pointer hover:text-zinc-300"
                    onClick={() => toggleSort('propScore')}
                  >
                    <div className="flex items-center justify-center gap-1">
                      Prop Score <SortIcon field="propScore" />
                    </div>
                  </th>
                  <th 
                    className="px-4 py-2 text-center text-[10px] font-mono uppercase tracking-widest text-zinc-500 cursor-pointer hover:text-zinc-300"
                    onClick={() => toggleSort('bootstrapSurvival')}
                  >
                    <div className="flex items-center justify-center gap-1">
                      Survival <SortIcon field="bootstrapSurvival" />
                    </div>
                  </th>
                  <th 
                    className="px-4 py-2 text-center text-[10px] font-mono uppercase tracking-widest text-zinc-500 cursor-pointer hover:text-zinc-300"
                    onClick={() => toggleSort('riskOfRuin')}
                  >
                    <div className="flex items-center justify-center gap-1">
                      Risk of Ruin <SortIcon field="riskOfRuin" />
                    </div>
                  </th>
                  <th 
                    className="px-4 py-2 text-center text-[10px] font-mono uppercase tracking-widest text-zinc-500 cursor-pointer hover:text-zinc-300"
                    onClick={() => toggleSort('maxDrawdown')}
                  >
                    <div className="flex items-center justify-center gap-1">
                      Max DD <SortIcon field="maxDrawdown" />
                    </div>
                  </th>
                  <th className="px-4 py-2 text-center text-[10px] font-mono uppercase tracking-widest text-zinc-500">Type</th>
                  <th className="px-4 py-2 text-center text-[10px] font-mono uppercase tracking-widest text-zinc-500">Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredStrategies.map((strategy, idx) => (
                  <LeaderboardRow
                    key={strategy.id || idx}
                    strategy={strategy}
                    rank={idx + 1}
                    onSelect={onSelectStrategy}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
