import React from 'react';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import {
  Shield, TrendingUp, AlertTriangle, XCircle, CheckCircle2,
  HelpCircle, Activity, Gauge, Target, Zap, BarChart3
} from 'lucide-react';

/**
 * Prop Score Calculation Weights
 * 25% Survival (Monte Carlo + Bootstrap)
 * 20% Drawdown safety
 * 15% Sensitivity robustness
 * 15% Walk-forward stability
 * 10% Profitability
 * 10% Challenge pass probability
 * 5% Consistency
 */
export function calculatePropScore(metrics) {
  const {
    bootstrapSurvival = 0,
    monteCarloSurvival = 0,
    maxDrawdown = 50,
    sensitivityScore = 0,
    walkForwardScore = 0,
    profitability = 0,
    challengePassProb = 0,
    consistencyScore = 0
  } = metrics;

  // 25% Survival (average of MC and Bootstrap)
  const avgSurvival = (bootstrapSurvival + monteCarloSurvival) / 2;
  const survivalScore = avgSurvival * 25;

  // 20% Drawdown safety (inverse - lower DD = higher score)
  const ddSafetyScore = Math.max(0, (1 - maxDrawdown / 50)) * 20;

  // 15% Sensitivity robustness
  const sensitivityPortion = (sensitivityScore / 100) * 15;

  // 15% Walk-forward stability
  const walkForwardPortion = (walkForwardScore / 100) * 15;

  // 10% Profitability
  const profitPortion = Math.min(10, (profitability / 100) * 10);

  // 10% Challenge pass probability
  const challengePortion = challengePassProb * 10;

  // 5% Consistency
  const consistencyPortion = (consistencyScore / 100) * 5;

  return Math.round(
    survivalScore + ddSafetyScore + sensitivityPortion + 
    walkForwardPortion + profitPortion + challengePortion + consistencyPortion
  );
}

/**
 * Get decision status based on Prop Score
 */
export function getDecisionStatus(propScore) {
  if (propScore >= 80) {
    return {
      status: 'READY FOR PROP',
      color: 'emerald',
      icon: CheckCircle2,
      description: 'Strategy meets all prop firm requirements'
    };
  } else if (propScore >= 60) {
    return {
      status: 'NEEDS OPTIMIZATION',
      color: 'amber',
      icon: AlertTriangle,
      description: 'Strategy has potential but needs improvements'
    };
  } else {
    return {
      status: 'REJECT',
      color: 'red',
      icon: XCircle,
      description: 'Strategy is too risky for prop trading'
    };
  }
}

/**
 * Get color class based on value and thresholds
 */
export function getStatusColor(value, type = 'percentage') {
  if (type === 'percentage' || type === 'survival') {
    if (value >= 80) return 'emerald';
    if (value >= 60) return 'amber';
    return 'red';
  }
  if (type === 'drawdown' || type === 'ruin') {
    if (value <= 10) return 'emerald';
    if (value <= 25) return 'amber';
    return 'red';
  }
  if (type === 'score') {
    if (value >= 70) return 'emerald';
    if (value >= 50) return 'amber';
    return 'red';
  }
  return 'zinc';
}

/**
 * Prop Score Badge Component
 */
export function PropScoreBadge({ score, size = 'md', showLabel = true }) {
  const decision = getDecisionStatus(score);
  const Icon = decision.icon;
  
  const sizeClasses = {
    sm: 'h-6 px-2 text-[10px]',
    md: 'h-8 px-3 text-xs',
    lg: 'h-10 px-4 text-sm'
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            className={cn(
              'font-mono font-bold uppercase tracking-wider cursor-help',
              sizeClasses[size],
              decision.color === 'emerald' && 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 hover:bg-emerald-500/30',
              decision.color === 'amber' && 'bg-amber-500/20 text-amber-400 border-amber-500/40 hover:bg-amber-500/30',
              decision.color === 'red' && 'bg-red-500/20 text-red-400 border-red-500/40 hover:bg-red-500/30'
            )}
          >
            <Icon className="w-3 h-3 mr-1" />
            {showLabel ? decision.status : `${score}`}
          </Badge>
        </TooltipTrigger>
        <TooltipContent className="bg-[#0F0F10] border-white/10">
          <p className="font-mono text-xs">{decision.description}</p>
          <p className="font-mono text-[10px] text-zinc-500 mt-1">Prop Score: {score}/100</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/**
 * Circular Prop Score Gauge
 */
export function PropScoreGauge({ score, size = 120 }) {
  const decision = getDecisionStatus(score);
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (score / 100) * circumference;
  
  const colorMap = {
    emerald: '#10b981',
    amber: '#f59e0b',
    red: '#ef4444'
  };

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        {/* Background circle */}
        <circle
          cx={size/2}
          cy={size/2}
          r="45"
          stroke="#27272a"
          strokeWidth="8"
          fill="transparent"
        />
        {/* Progress circle */}
        <circle
          cx={size/2}
          cy={size/2}
          r="45"
          stroke={colorMap[decision.color]}
          strokeWidth="8"
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn(
          'text-2xl font-bold font-mono',
          `text-${decision.color}-400`
        )} style={{ color: colorMap[decision.color] }}>
          {score}
        </span>
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Prop Score</span>
      </div>
    </div>
  );
}

/**
 * Validation Metric Card
 */
export function ValidationMetricCard({ 
  label, 
  value, 
  unit = '%', 
  icon: Icon, 
  type = 'percentage',
  tooltip,
  size = 'md'
}) {
  const color = getStatusColor(value, type);
  
  const colorClasses = {
    emerald: 'border-emerald-500/30 bg-emerald-500/5',
    amber: 'border-amber-500/30 bg-amber-500/5',
    red: 'border-red-500/30 bg-red-500/5',
    zinc: 'border-zinc-500/30 bg-zinc-500/5'
  };

  const textClasses = {
    emerald: 'text-emerald-400',
    amber: 'text-amber-400',
    red: 'text-red-400',
    zinc: 'text-zinc-400'
  };

  const sizeClasses = {
    sm: 'p-2',
    md: 'p-3',
    lg: 'p-4'
  };

  const content = (
    <div className={cn(
      'border rounded-sm transition-colors',
      colorClasses[color],
      sizeClasses[size]
    )}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          {Icon && <Icon className={cn('w-3.5 h-3.5', textClasses[color])} />}
          <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
            {label}
          </span>
        </div>
        {tooltip && (
          <HelpCircle className="w-3 h-3 text-zinc-600 cursor-help" />
        )}
      </div>
      <div className="flex items-baseline gap-1">
        <span className={cn('text-xl font-bold font-mono', textClasses[color])}>
          {typeof value === 'number' ? value.toFixed(1) : value}
        </span>
        <span className="text-xs text-zinc-500">{unit}</span>
      </div>
    </div>
  );

  if (tooltip) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>{content}</TooltipTrigger>
          <TooltipContent className="bg-[#0F0F10] border-white/10 max-w-xs">
            <p className="text-xs">{tooltip}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return content;
}

/**
 * Status Badge with color coding
 */
export function StatusBadge({ status, variant = 'default' }) {
  const statusConfig = {
    'PROP SAFE': { color: 'emerald', icon: Shield },
    'HIGH RISK': { color: 'red', icon: AlertTriangle },
    'NOT DEPLOYABLE': { color: 'red', icon: XCircle },
    'MODERATE RISK': { color: 'amber', icon: AlertTriangle },
    'LOW RISK': { color: 'emerald', icon: CheckCircle2 },
    'READY': { color: 'emerald', icon: CheckCircle2 },
    'NEEDS WORK': { color: 'amber', icon: Activity },
    'REJECT': { color: 'red', icon: XCircle }
  };

  const config = statusConfig[status] || { color: 'zinc', icon: HelpCircle };
  const Icon = config.icon;

  return (
    <Badge
      variant="outline"
      className={cn(
        'font-mono text-[10px] uppercase tracking-wider',
        config.color === 'emerald' && 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10',
        config.color === 'amber' && 'border-amber-500/40 text-amber-400 bg-amber-500/10',
        config.color === 'red' && 'border-red-500/40 text-red-400 bg-red-500/10',
        config.color === 'zinc' && 'border-zinc-500/40 text-zinc-400 bg-zinc-500/10'
      )}
    >
      <Icon className="w-3 h-3 mr-1" />
      {status}
    </Badge>
  );
}

/**
 * Prop Score Breakdown Component
 */
export function PropScoreBreakdown({ metrics }) {
  const {
    bootstrapSurvival = 0,
    monteCarloSurvival = 0,
    maxDrawdown = 0,
    sensitivityScore = 0,
    walkForwardScore = 0,
    profitability = 0,
    challengePassProb = 0,
    consistencyScore = 0
  } = metrics;

  const breakdown = [
    { label: 'Survival (MC + Bootstrap)', weight: 25, value: ((bootstrapSurvival + monteCarloSurvival) / 2), icon: Shield },
    { label: 'Drawdown Safety', weight: 20, value: Math.max(0, (1 - maxDrawdown / 50)) * 100, icon: TrendingUp },
    { label: 'Sensitivity Robustness', weight: 15, value: sensitivityScore, icon: Gauge },
    { label: 'Walk-Forward Stability', weight: 15, value: walkForwardScore, icon: Activity },
    { label: 'Profitability', weight: 10, value: Math.min(100, profitability), icon: Target },
    { label: 'Challenge Pass Prob', weight: 10, value: challengePassProb * 100, icon: Zap },
    { label: 'Consistency', weight: 5, value: consistencyScore, icon: BarChart3 }
  ];

  return (
    <div className="space-y-2">
      <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-3">Score Breakdown</h4>
      {breakdown.map((item, idx) => {
        const contribution = (item.value / 100) * item.weight;
        const color = getStatusColor(item.value, 'percentage');
        const Icon = item.icon;
        
        return (
          <div key={idx} className="flex items-center gap-2">
            <Icon className={cn('w-3 h-3', `text-${color}-400`)} style={{ color: color === 'emerald' ? '#10b981' : color === 'amber' ? '#f59e0b' : '#ef4444' }} />
            <span className="text-[10px] text-zinc-400 flex-1 truncate">{item.label}</span>
            <span className="text-[10px] text-zinc-600 w-8 text-right">{item.weight}%</span>
            <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div 
                className="h-full rounded-full transition-all"
                style={{ 
                  width: `${item.value}%`,
                  backgroundColor: color === 'emerald' ? '#10b981' : color === 'amber' ? '#f59e0b' : '#ef4444'
                }}
              />
            </div>
            <span className="text-[10px] font-mono w-10 text-right" style={{ color: color === 'emerald' ? '#10b981' : color === 'amber' ? '#f59e0b' : '#ef4444' }}>
              +{contribution.toFixed(1)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default {
  calculatePropScore,
  getDecisionStatus,
  getStatusColor,
  PropScoreBadge,
  PropScoreGauge,
  ValidationMetricCard,
  StatusBadge,
  PropScoreBreakdown
};
