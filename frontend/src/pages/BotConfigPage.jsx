import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { toast } from 'sonner';
import {
  ArrowLeft, Shield, AlertTriangle, CheckCircle2, Lock,
  DollarSign, Percent, TrendingDown, BarChart3, Zap,
  Calculator, Settings2, Save, ArrowRight
} from 'lucide-react';

const DEFAULT_CONFIG = {
  accountSize: 10000,
  riskPerTrade: 1.0,
  maxDailyDrawdown: 5.0,
  maxTotalDrawdown: 10.0,
  maxTradesPerDay: 5,
  lotSizeMode: 'percent_risk', // 'fixed' | 'percent_risk'
  fixedLotSize: 0.1,
  maxConcurrentTrades: 3,
  tradeCooldownMinutes: 15,
};

// Store config in localStorage for persistence
const STORAGE_KEY = 'bot_risk_config';

export default function BotConfigPage() {
  const navigate = useNavigate();
  const [config, setConfig] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : DEFAULT_CONFIG;
  });
  const [isLocked, setIsLocked] = useState(false);

  // Calculate derived values
  const calculations = useMemo(() => {
    const { accountSize, riskPerTrade, maxDailyDrawdown, maxTotalDrawdown, maxTradesPerDay, lotSizeMode, fixedLotSize } = config;
    
    // Risk-based lot size calculation (assuming 100:1 leverage, 10 pips SL)
    const riskAmount = accountSize * (riskPerTrade / 100);
    const pipValue = 10; // USD per pip for 1 standard lot
    const stopLossPips = 20; // Default SL assumption
    const calculatedLotSize = lotSizeMode === 'percent_risk' 
      ? (riskAmount / (stopLossPips * pipValue)).toFixed(2)
      : fixedLotSize;
    
    // Daily risk exposure
    const maxDailyRisk = accountSize * (maxDailyDrawdown / 100);
    const maxTotalRisk = accountSize * (maxTotalDrawdown / 100);
    const estimatedDailyRisk = Math.min(riskAmount * maxTradesPerDay, maxDailyRisk);
    const maxExposure = parseFloat(calculatedLotSize) * maxTradesPerDay;
    
    return {
      calculatedLotSize: parseFloat(calculatedLotSize),
      riskAmount,
      maxDailyRisk,
      maxTotalRisk,
      estimatedDailyRisk,
      maxExposure,
    };
  }, [config]);

  // Validation checks
  const validationStatus = useMemo(() => {
    const issues = [];
    const { riskPerTrade, maxDailyDrawdown, maxTotalDrawdown, maxTradesPerDay } = config;
    
    if (riskPerTrade > 2) issues.push('Risk per trade > 2% is aggressive');
    if (maxDailyDrawdown > 5) issues.push('Daily DD > 5% is risky for prop firms');
    if (maxTotalDrawdown > 10) issues.push('Total DD > 10% may fail prop challenges');
    if (maxTradesPerDay > 10) issues.push('Too many trades per day increases risk');
    if (riskPerTrade * maxTradesPerDay > maxDailyDrawdown) {
      issues.push('Risk per trade × max trades exceeds daily DD limit');
    }
    
    return {
      isValid: issues.length === 0,
      issues,
      isPropSafe: riskPerTrade <= 1 && maxDailyDrawdown <= 5 && maxTotalDrawdown <= 10,
    };
  }, [config]);

  const handleSave = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    setIsLocked(true);
    toast.success('Risk configuration saved and locked');
  };

  const handleUnlock = () => {
    setIsLocked(false);
    toast.info('Configuration unlocked for editing');
  };

  const handleProceed = () => {
    if (!isLocked) {
      toast.error('Please save and lock configuration first');
      return;
    }
    navigate('/');
  };

  const updateConfig = (key, value) => {
    if (isLocked) return;
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="min-h-screen bg-[#050505] p-4" data-testid="bot-config-page">
      {/* Header */}
      <div className="max-w-4xl mx-auto mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate('/')} className="text-zinc-500 hover:text-white transition-colors" data-testid="back-btn">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-extrabold uppercase tracking-tight text-white" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                BOT RISK CONFIGURATION
              </h1>
              <p className="text-xs text-zinc-500 uppercase tracking-widest mt-0.5 font-mono">
                Set risk parameters before generation
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {isLocked ? (
              <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/40 font-mono text-xs px-3 py-1" data-testid="risk-locked-badge">
                <Lock className="w-3 h-3 mr-1.5" /> RISK LOCKED
              </Badge>
            ) : (
              <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/40 font-mono text-xs px-3 py-1">
                <AlertTriangle className="w-3 h-3 mr-1.5" /> UNLOCKED
              </Badge>
            )}
          </div>
        </div>

        {/* Validation Status Banner */}
        <div className={`p-4 rounded-sm border mb-6 ${
          validationStatus.isPropSafe ? 'bg-emerald-500/10 border-emerald-500/30' :
          validationStatus.isValid ? 'bg-amber-500/10 border-amber-500/30' :
          'bg-red-500/10 border-red-500/30'
        }`} data-testid="validation-banner">
          <div className="flex items-center gap-3">
            {validationStatus.isPropSafe ? (
              <CheckCircle2 className="w-6 h-6 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-6 h-6 text-amber-400" />
            )}
            <div>
              <p className={`text-sm font-bold uppercase font-mono ${
                validationStatus.isPropSafe ? 'text-emerald-400' : 'text-amber-400'
              }`}>
                {validationStatus.isPropSafe ? 'PROP FIRM SAFE' : 'REVIEW SETTINGS'}
              </p>
              {validationStatus.issues.length > 0 && (
                <ul className="mt-1 space-y-0.5">
                  {validationStatus.issues.map((issue, i) => (
                    <li key={i} className="text-xs text-zinc-400 font-mono">• {issue}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto grid grid-cols-2 gap-6">
        {/* Left Column - Input Controls */}
        <div className="space-y-4">
          <div className="bg-[#0A0A0A] border border-white/5 p-4 rounded-sm">
            <h3 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-4 flex items-center gap-2">
              <DollarSign className="w-3.5 h-3.5" /> Account Settings
            </h3>
            
            {/* Account Size */}
            <div className="mb-4">
              <label className="text-xs text-zinc-400 font-mono mb-1.5 block">Account Size (USD)</label>
              <Input
                type="number"
                value={config.accountSize}
                onChange={(e) => updateConfig('accountSize', parseFloat(e.target.value) || 0)}
                disabled={isLocked}
                className="bg-black border-white/10 text-white font-mono h-9"
                data-testid="account-size-input"
              />
            </div>

            {/* Lot Size Mode */}
            <div className="mb-4">
              <label className="text-xs text-zinc-400 font-mono mb-1.5 block">Lot Size Mode</label>
              <div className="flex gap-2">
                <Button
                  onClick={() => updateConfig('lotSizeMode', 'percent_risk')}
                  disabled={isLocked}
                  className={`flex-1 h-8 text-xs font-mono uppercase ${
                    config.lotSizeMode === 'percent_risk'
                      ? 'bg-blue-600 text-white'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
                  }`}
                  data-testid="lot-mode-percent"
                >
                  <Percent className="w-3 h-3 mr-1" /> % Risk
                </Button>
                <Button
                  onClick={() => updateConfig('lotSizeMode', 'fixed')}
                  disabled={isLocked}
                  className={`flex-1 h-8 text-xs font-mono uppercase ${
                    config.lotSizeMode === 'fixed'
                      ? 'bg-blue-600 text-white'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
                  }`}
                  data-testid="lot-mode-fixed"
                >
                  Fixed Lot
                </Button>
              </div>
            </div>

            {config.lotSizeMode === 'fixed' && (
              <div className="mb-4">
                <label className="text-xs text-zinc-400 font-mono mb-1.5 block">Fixed Lot Size</label>
                <Input
                  type="number"
                  step="0.01"
                  value={config.fixedLotSize}
                  onChange={(e) => updateConfig('fixedLotSize', parseFloat(e.target.value) || 0.01)}
                  disabled={isLocked}
                  className="bg-black border-white/10 text-white font-mono h-9"
                  data-testid="fixed-lot-input"
                />
              </div>
            )}
          </div>

          <div className="bg-[#0A0A0A] border border-white/5 p-4 rounded-sm">
            <h3 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-4 flex items-center gap-2">
              <Shield className="w-3.5 h-3.5" /> Risk Controls
            </h3>

            {/* Risk Per Trade */}
            <div className="mb-4">
              <div className="flex justify-between mb-1.5">
                <label className="text-xs text-zinc-400 font-mono">Risk Per Trade</label>
                <span className="text-xs font-mono text-blue-400">{config.riskPerTrade}%</span>
              </div>
              <Slider
                value={[config.riskPerTrade]}
                onValueChange={([v]) => updateConfig('riskPerTrade', v)}
                min={0.1}
                max={5}
                step={0.1}
                disabled={isLocked}
                className="w-full"
                data-testid="risk-per-trade-slider"
              />
              <div className="flex justify-between mt-1 text-[9px] text-zinc-600 font-mono">
                <span>0.1%</span>
                <span className="text-emerald-500">1% SAFE</span>
                <span className="text-red-500">5% MAX</span>
              </div>
            </div>

            {/* Max Daily Drawdown */}
            <div className="mb-4">
              <div className="flex justify-between mb-1.5">
                <label className="text-xs text-zinc-400 font-mono">Max Daily Drawdown</label>
                <span className="text-xs font-mono text-amber-400">{config.maxDailyDrawdown}%</span>
              </div>
              <Slider
                value={[config.maxDailyDrawdown]}
                onValueChange={([v]) => updateConfig('maxDailyDrawdown', v)}
                min={1}
                max={10}
                step={0.5}
                disabled={isLocked}
                className="w-full"
                data-testid="max-daily-dd-slider"
              />
              <div className="flex justify-between mt-1 text-[9px] text-zinc-600 font-mono">
                <span>1%</span>
                <span className="text-emerald-500">5% PROP</span>
                <span className="text-red-500">10%</span>
              </div>
            </div>

            {/* Max Total Drawdown */}
            <div className="mb-4">
              <div className="flex justify-between mb-1.5">
                <label className="text-xs text-zinc-400 font-mono">Max Total Drawdown</label>
                <span className="text-xs font-mono text-red-400">{config.maxTotalDrawdown}%</span>
              </div>
              <Slider
                value={[config.maxTotalDrawdown]}
                onValueChange={([v]) => updateConfig('maxTotalDrawdown', v)}
                min={2}
                max={20}
                step={1}
                disabled={isLocked}
                className="w-full"
                data-testid="max-total-dd-slider"
              />
              <div className="flex justify-between mt-1 text-[9px] text-zinc-600 font-mono">
                <span>2%</span>
                <span className="text-emerald-500">10% PROP</span>
                <span className="text-red-500">20%</span>
              </div>
            </div>

            {/* Max Trades Per Day */}
            <div className="mb-4">
              <div className="flex justify-between mb-1.5">
                <label className="text-xs text-zinc-400 font-mono">Max Trades Per Day</label>
                <span className="text-xs font-mono text-zinc-300">{config.maxTradesPerDay}</span>
              </div>
              <Slider
                value={[config.maxTradesPerDay]}
                onValueChange={([v]) => updateConfig('maxTradesPerDay', v)}
                min={1}
                max={20}
                step={1}
                disabled={isLocked}
                className="w-full"
                data-testid="max-trades-slider"
              />
            </div>

            {/* Max Concurrent Trades */}
            <div className="mb-4">
              <div className="flex justify-between mb-1.5">
                <label className="text-xs text-zinc-400 font-mono">Max Concurrent Trades</label>
                <span className="text-xs font-mono text-zinc-300">{config.maxConcurrentTrades}</span>
              </div>
              <Slider
                value={[config.maxConcurrentTrades]}
                onValueChange={([v]) => updateConfig('maxConcurrentTrades', v)}
                min={1}
                max={10}
                step={1}
                disabled={isLocked}
                className="w-full"
                data-testid="max-concurrent-slider"
              />
            </div>

            {/* Trade Cooldown */}
            <div>
              <div className="flex justify-between mb-1.5">
                <label className="text-xs text-zinc-400 font-mono">Trade Cooldown (mins)</label>
                <span className="text-xs font-mono text-zinc-300">{config.tradeCooldownMinutes}</span>
              </div>
              <Slider
                value={[config.tradeCooldownMinutes]}
                onValueChange={([v]) => updateConfig('tradeCooldownMinutes', v)}
                min={0}
                max={60}
                step={5}
                disabled={isLocked}
                className="w-full"
                data-testid="cooldown-slider"
              />
            </div>
          </div>
        </div>

        {/* Right Column - Calculated Values & Actions */}
        <div className="space-y-4">
          <div className="bg-[#0A0A0A] border border-white/5 p-4 rounded-sm">
            <h3 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-4 flex items-center gap-2">
              <Calculator className="w-3.5 h-3.5" /> Calculated Values
            </h3>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-black/50 border border-white/5 p-3 rounded-sm" data-testid="calc-lot-size">
                <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Lot Size</p>
                <p className="text-xl font-bold font-mono text-blue-400">{calculations.calculatedLotSize}</p>
              </div>
              <div className="bg-black/50 border border-white/5 p-3 rounded-sm" data-testid="calc-risk-amount">
                <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Risk Amount</p>
                <p className="text-xl font-bold font-mono text-emerald-400">${calculations.riskAmount.toFixed(0)}</p>
              </div>
              <div className="bg-black/50 border border-white/5 p-3 rounded-sm" data-testid="calc-daily-risk">
                <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Est. Daily Risk</p>
                <p className="text-xl font-bold font-mono text-amber-400">${calculations.estimatedDailyRisk.toFixed(0)}</p>
              </div>
              <div className="bg-black/50 border border-white/5 p-3 rounded-sm" data-testid="calc-max-exposure">
                <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Max Exposure</p>
                <p className="text-xl font-bold font-mono text-zinc-300">{calculations.maxExposure.toFixed(2)} lots</p>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-white/5">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-zinc-500 font-mono">Max Daily Loss</span>
                <span className="text-sm font-mono text-red-400">${calculations.maxDailyRisk.toFixed(0)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-zinc-500 font-mono">Max Total Loss</span>
                <span className="text-sm font-mono text-red-400">${calculations.maxTotalRisk.toFixed(0)}</span>
              </div>
            </div>
          </div>

          {/* Risk Enforcement Preview */}
          <div className="bg-[#0A0A0A] border border-white/5 p-4 rounded-sm">
            <h3 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-4 flex items-center gap-2">
              <Shield className="w-3.5 h-3.5" /> Risk Enforcement (Auto-Injected)
            </h3>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-mono">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span className="text-zinc-300">Daily DD stop at {config.maxDailyDrawdown}%</span>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span className="text-zinc-300">Total DD kill switch at {config.maxTotalDrawdown}%</span>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span className="text-zinc-300">Max {config.maxConcurrentTrades} concurrent trades</span>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span className="text-zinc-300">{config.tradeCooldownMinutes}min cooldown between trades</span>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span className="text-zinc-300">Max {config.maxTradesPerDay} trades per day</span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="space-y-2">
            {!isLocked ? (
              <Button
                onClick={handleSave}
                className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-mono uppercase text-sm h-12"
                data-testid="save-config-btn"
              >
                <Lock className="w-4 h-4 mr-2" /> SAVE & LOCK CONFIGURATION
              </Button>
            ) : (
              <>
                <Button
                  onClick={handleProceed}
                  className="w-full bg-blue-600 hover:bg-blue-500 text-white font-mono uppercase text-sm h-12"
                  data-testid="proceed-btn"
                >
                  <ArrowRight className="w-4 h-4 mr-2" /> PROCEED TO BOT GENERATION
                </Button>
                <Button
                  onClick={handleUnlock}
                  variant="outline"
                  className="w-full border-zinc-700 text-zinc-400 font-mono uppercase text-xs h-9"
                  data-testid="unlock-btn"
                >
                  <Settings2 className="w-3 h-3 mr-2" /> Unlock to Edit
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
