import { useState, useEffect } from 'react';
import { CheckCircle2, Circle, Loader2, AlertTriangle, Play, Rocket, Eye, Target, Cpu, Shield, BarChart3, Activity, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

// Pipeline Step Component
export function PipelineStep({ step, isActive, isCompleted, isError, onClick, disabled }) {
  const getStepIcon = () => {
    if (isError) return <AlertTriangle className="w-4 h-4 text-red-400" />;
    if (isCompleted) return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    if (isActive) return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
    return <Circle className="w-4 h-4 text-zinc-600" />;
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-3 p-3 rounded-lg border transition-all w-full text-left ${
        isActive ? 'bg-blue-950/30 border-blue-500/50 shadow-lg shadow-blue-500/10' :
        isCompleted ? 'bg-emerald-950/20 border-emerald-500/30' :
        isError ? 'bg-red-950/20 border-red-500/30' :
        'bg-[#0F0F10] border-white/5 hover:border-white/20'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
      data-testid={`pipeline-step-${step.id}`}
    >
      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
        isActive ? 'bg-blue-600/30' :
        isCompleted ? 'bg-emerald-600/30' :
        isError ? 'bg-red-600/30' :
        'bg-zinc-800'
      }`}>
        {getStepIcon()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-mono uppercase tracking-wider ${
            isActive ? 'text-blue-400' :
            isCompleted ? 'text-emerald-400' :
            isError ? 'text-red-400' :
            'text-zinc-400'
          }`}>
            Step {step.number}
          </span>
          {isCompleted && <Badge variant="outline" className="text-[8px] h-4 border-emerald-500/40 text-emerald-400">Done</Badge>}
        </div>
        <p className="text-sm font-medium text-zinc-200 truncate">{step.title}</p>
        <p className="text-[10px] text-zinc-500 truncate">{step.description}</p>
      </div>
      {step.icon && <step.icon className={`w-5 h-5 ${
        isActive ? 'text-blue-400' :
        isCompleted ? 'text-emerald-400' :
        'text-zinc-600'
      }`} />}
    </button>
  );
}

// Main Pipeline Tracker Component
export function PipelineTracker({ 
  currentStep, 
  completedSteps, 
  pipelineStatus,
  onStepClick,
  selectedStrategy,
  generatedBot
}) {
  const steps = [
    { id: 'generate', number: 1, title: 'Generate Strategies', description: 'Create validated trading strategies', icon: Rocket },
    { id: 'view', number: 2, title: 'View Top Strategies', description: 'Review ranked results', icon: Eye },
    { id: 'select', number: 3, title: 'Select Strategy', description: 'Choose best performer', icon: Target },
    { id: 'bot', number: 4, title: 'Generate cBot', description: 'Convert to executable code', icon: Cpu },
    { id: 'pipeline', number: 5, title: 'Run Pipeline', description: 'Auto validation sequence', icon: Activity },
  ];

  return (
    <div className="space-y-2" data-testid="pipeline-tracker">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-mono uppercase tracking-widest text-zinc-500">Pipeline Flow</h3>
        <Badge variant="outline" className={`text-[9px] ${
          currentStep === 'complete' ? 'border-emerald-500/40 text-emerald-400' :
          currentStep ? 'border-blue-500/40 text-blue-400' :
          'border-white/10 text-zinc-500'
        }`}>
          {currentStep === 'complete' ? 'Complete' : `Step ${steps.findIndex(s => s.id === currentStep) + 1 || 1} of 5`}
        </Badge>
      </div>
      
      <div className="space-y-1.5">
        {steps.map((step, idx) => (
          <PipelineStep
            key={step.id}
            step={step}
            isActive={currentStep === step.id}
            isCompleted={completedSteps.includes(step.id)}
            isError={pipelineStatus?.[step.id]?.error}
            onClick={() => onStepClick?.(step.id)}
            disabled={idx > 0 && !completedSteps.includes(steps[idx - 1].id)}
          />
        ))}
      </div>
    </div>
  );
}

// Bot Pipeline Status Tracker (for step 5)
export function BotPipelineStatus({ pipelineResults, deploymentScore, botStatus }) {
  const stages = [
    { id: 'strategy_selected', label: 'Strategy Selected', key: 'strategy_selected' },
    { id: 'cbot_generated', label: 'cBot Generated', key: 'cbot_generated' },
    { id: 'safety_injected', label: 'Safety Injected', key: 'safety_injected' },
    { id: 'compiled', label: 'Compiled', key: 'compile_verified' },
    { id: 'monte_carlo', label: 'Monte Carlo', key: 'monte_carlo_passed' },
    { id: 'walkforward', label: 'Walk Forward', key: 'walkforward_passed' },
    { id: 'ready', label: 'Ready', key: 'is_ready' },
  ];

  const getStageStatus = (stage) => {
    if (stage.key === 'strategy_selected' || stage.key === 'cbot_generated') {
      return pipelineResults ? 'completed' : 'pending';
    }
    if (stage.key === 'is_ready') {
      return botStatus === 'ready_for_deployment' ? 'completed' : 'pending';
    }
    if (!pipelineResults) return 'pending';
    return pipelineResults[stage.key] ? 'completed' : 'pending';
  };

  return (
    <div className="bg-[#0A0A0B] border border-white/5 rounded-lg p-4" data-testid="bot-pipeline-status">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-xs font-mono uppercase tracking-widest text-zinc-500">Bot Pipeline Status</h4>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">Score:</span>
          <span className={`text-sm font-bold font-mono ${
            deploymentScore >= 80 ? 'text-emerald-400' :
            deploymentScore >= 60 ? 'text-amber-400' :
            'text-red-400'
          }`}>{deploymentScore || 0}%</span>
        </div>
      </div>
      
      <div className="space-y-2">
        {stages.map((stage, idx) => {
          const status = getStageStatus(stage);
          return (
            <div key={stage.id} className="flex items-center gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono ${
                status === 'completed' ? 'bg-emerald-600/30 text-emerald-400' :
                status === 'running' ? 'bg-blue-600/30 text-blue-400' :
                'bg-zinc-800 text-zinc-600'
              }`}>
                {status === 'completed' ? '✓' : status === 'running' ? <Loader2 className="w-3 h-3 animate-spin" /> : idx + 1}
              </div>
              <span className={`text-xs font-mono ${
                status === 'completed' ? 'text-emerald-400' :
                status === 'running' ? 'text-blue-400' :
                'text-zinc-500'
              }`}>{stage.label}</span>
              {status === 'completed' && <CheckCircle2 className="w-3 h-3 text-emerald-400 ml-auto" />}
              {status === 'running' && <Loader2 className="w-3 h-3 text-blue-400 ml-auto animate-spin" />}
            </div>
          );
        })}
      </div>
      
      {/* Progress Bar */}
      <div className="mt-4">
        <Progress value={deploymentScore || 0} className="h-1.5" />
      </div>
      
      {/* Status Badge */}
      {botStatus && (
        <div className="mt-3 flex justify-center">
          <Badge className={`text-xs font-mono uppercase ${
            botStatus === 'ready_for_deployment' ? 'bg-emerald-600/30 text-emerald-400 border-emerald-500/40' :
            botStatus === 'robust' ? 'bg-blue-600/30 text-blue-400 border-blue-500/40' :
            botStatus === 'validated' ? 'bg-amber-600/30 text-amber-400 border-amber-500/40' :
            'bg-zinc-600/30 text-zinc-400 border-zinc-500/40'
          }`}>
            {botStatus === 'ready_for_deployment' ? '✅ Ready for Deployment' :
             botStatus === 'robust' ? '💪 Robust' :
             botStatus === 'validated' ? '✓ Validated' :
             '📝 Draft'}
          </Badge>
        </div>
      )}
    </div>
  );
}

// Strategy Fitness Card Component
export function StrategyFitnessCard({ strategy }) {
  if (!strategy) return null;

  const fitnessComponents = [
    { 
      id: 'pf', 
      label: 'Profit Factor', 
      value: strategy.profit_factor || 0, 
      format: (v) => v.toFixed(2),
      threshold: 1.5,
      weight: '25%',
      description: 'Gross profit / gross loss ratio',
      icon: BarChart3
    },
    { 
      id: 'dd', 
      label: 'Max Drawdown', 
      value: strategy.max_drawdown_pct || 0, 
      format: (v) => `${v.toFixed(1)}%`,
      threshold: 15,
      isLowerBetter: true,
      weight: '25%',
      description: 'Peak to trough decline',
      icon: Activity
    },
    { 
      id: 'sharpe', 
      label: 'Sharpe Ratio', 
      value: strategy.sharpe_ratio || 0, 
      format: (v) => v.toFixed(2),
      threshold: 1.0,
      weight: '25%',
      description: 'Risk-adjusted return',
      icon: Zap
    },
    { 
      id: 'stability', 
      label: 'Stability', 
      value: (strategy.walkforward?.stability_score || strategy.monte_carlo_score / 100 || 0.5) * 100, 
      format: (v) => `${v.toFixed(0)}%`,
      threshold: 60,
      weight: '25%',
      description: 'Walk-forward consistency',
      icon: Shield
    },
  ];

  const isPassing = (comp) => {
    if (comp.isLowerBetter) {
      return comp.value <= comp.threshold;
    }
    return comp.value >= comp.threshold;
  };

  return (
    <div className="bg-[#0A0A0B] border border-white/5 rounded-lg p-4" data-testid="strategy-fitness-card">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-xs font-mono uppercase tracking-widest text-zinc-500">Strategy Fitness Breakdown</h4>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">Total:</span>
          <span className={`text-lg font-bold font-mono ${
            (strategy.fitness || 0) >= 60 ? 'text-emerald-400' :
            (strategy.fitness || 0) >= 40 ? 'text-amber-400' :
            'text-red-400'
          }`}>{(strategy.fitness || 0).toFixed(1)}</span>
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-3">
        {fitnessComponents.map((comp) => {
          const Icon = comp.icon;
          const passing = isPassing(comp);
          return (
            <div key={comp.id} className={`p-3 rounded-lg border ${
              passing ? 'bg-emerald-950/20 border-emerald-500/20' : 'bg-red-950/20 border-red-500/20'
            }`}>
              <div className="flex items-center gap-2 mb-1">
                <Icon className={`w-3 h-3 ${passing ? 'text-emerald-400' : 'text-red-400'}`} />
                <span className="text-[10px] font-mono uppercase text-zinc-400">{comp.label}</span>
                <span className="text-[8px] text-zinc-600 ml-auto">({comp.weight})</span>
              </div>
              <p className={`text-lg font-bold font-mono ${passing ? 'text-emerald-400' : 'text-red-400'}`}>
                {comp.format(comp.value)}
              </p>
              <p className="text-[9px] text-zinc-600 mt-0.5">{comp.description}</p>
              <p className="text-[8px] text-zinc-500 mt-1">
                Target: {comp.isLowerBetter ? '≤' : '≥'} {comp.threshold}{comp.id === 'dd' || comp.id === 'stability' ? '%' : ''}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Quick Start Component
export function QuickStartFlow({ onQuickStart, isLoading, progress }) {
  return (
    <div className="bg-gradient-to-br from-purple-950/30 to-blue-950/30 border border-purple-500/20 rounded-lg p-6 text-center" data-testid="quick-start-flow">
      <Rocket className="w-12 h-12 text-purple-400 mx-auto mb-4" />
      <h3 className="text-lg font-bold text-zinc-200 mb-2">Quick Start</h3>
      <p className="text-sm text-zinc-400 mb-4 max-w-md mx-auto">
        Automatically generate 10 validated strategies, apply filtering, and show the top 3 performers for you to select.
      </p>
      
      {isLoading ? (
        <div className="space-y-3">
          <div className="flex items-center justify-center gap-2 text-purple-400">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm font-mono">Generating strategies...</span>
          </div>
          <Progress value={progress} className="h-2 max-w-xs mx-auto" />
          <p className="text-xs text-zinc-500">{progress}% complete</p>
        </div>
      ) : (
        <Button
          onClick={onQuickStart}
          className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-mono uppercase tracking-wider"
          data-testid="quick-start-btn"
        >
          <Zap className="w-4 h-4 mr-2" />
          Quick Start
        </Button>
      )}
      
      <div className="mt-4 flex items-center justify-center gap-4 text-xs text-zinc-500">
        <span>10 strategies</span>
        <span>•</span>
        <span>Auto-filtered</span>
        <span>•</span>
        <span>Top 3 shown</span>
      </div>
    </div>
  );
}

// Advanced Mode Toggle
export function AdvancedModeToggle({ enabled, onToggle }) {
  return (
    <div className="flex items-center gap-2 p-2 bg-[#0A0A0B] border border-white/5 rounded-lg">
      <button
        onClick={onToggle}
        className={`relative w-10 h-5 rounded-full transition-colors ${
          enabled ? 'bg-amber-600' : 'bg-zinc-700'
        }`}
        data-testid="advanced-mode-toggle"
      >
        <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
          enabled ? 'translate-x-5' : 'translate-x-0.5'
        }`} />
      </button>
      <span className="text-xs font-mono text-zinc-400">
        Advanced Mode {enabled && <span className="text-amber-400">(Debug)</span>}
      </span>
    </div>
  );
}

export default PipelineTracker;
