import { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { 
  Settings, Save, RotateCcw, Filter, Zap, BarChart3, Shield,
  Loader2, Check, AlertTriangle, Info
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Input component for config values
function ConfigInput({ label, value, onChange, type = 'number', min, max, step = 0.1, description, unit }) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-mono text-zinc-400 flex items-center gap-2">
        {label}
        {unit && <span className="text-zinc-600">({unit})</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(type === 'number' ? parseFloat(e.target.value) : e.target.value)}
        min={min}
        max={max}
        step={step}
        className="w-full px-3 py-2 bg-[#0F0F10] border border-white/10 rounded text-sm text-zinc-200 font-mono focus:border-purple-500/50 focus:outline-none"
      />
      {description && <p className="text-[10px] text-zinc-600">{description}</p>}
    </div>
  );
}

// Section component
function ConfigSection({ title, icon: Icon, children, color = 'purple' }) {
  const colors = {
    purple: 'border-purple-500/30 bg-purple-950/10',
    emerald: 'border-emerald-500/30 bg-emerald-950/10',
    amber: 'border-amber-500/30 bg-amber-950/10',
    blue: 'border-blue-500/30 bg-blue-950/10'
  };
  
  return (
    <div className={`border rounded-lg p-4 ${colors[color]}`}>
      <div className="flex items-center gap-2 mb-4">
        <Icon className={`w-4 h-4 text-${color}-400`} />
        <h3 className="text-sm font-bold text-zinc-200 uppercase tracking-wider">{title}</h3>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {children}
      </div>
    </div>
  );
}

export function StrategyConfigPanel() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [originalConfig, setOriginalConfig] = useState(null);

  // Load config on mount
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/api/config`);
      if (response.data.success) {
        setConfig(response.data.config);
        setOriginalConfig(JSON.stringify(response.data.config));
      }
    } catch (error) {
      toast.error('Failed to load configuration');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    try {
      setSaving(true);
      const response = await axios.post(`${API_URL}/api/config/update`, config);
      if (response.data.success) {
        toast.success('Configuration saved successfully');
        setOriginalConfig(JSON.stringify(config));
        setHasChanges(false);
      }
    } catch (error) {
      toast.error('Failed to save configuration');
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const resetConfig = async () => {
    if (!window.confirm('Reset all settings to defaults? This cannot be undone.')) return;
    
    try {
      setSaving(true);
      const response = await axios.post(`${API_URL}/api/config/reset`);
      if (response.data.success) {
        setConfig(response.data.config);
        setOriginalConfig(JSON.stringify(response.data.config));
        setHasChanges(false);
        toast.success('Configuration reset to defaults');
      }
    } catch (error) {
      toast.error('Failed to reset configuration');
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const updateValue = (section, key, value) => {
    setConfig(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }));
    setHasChanges(JSON.stringify({ ...config, [section]: { ...config[section], [key]: value } }) !== originalConfig);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
      </div>
    );
  }

  if (!config) {
    return (
      <div className="text-center text-zinc-500 py-8">
        Failed to load configuration
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="strategy-config-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings className="w-5 h-5 text-purple-400" />
          <h2 className="text-lg font-bold text-zinc-200">Strategy Configuration</h2>
          {hasChanges && (
            <Badge className="bg-amber-600/30 text-amber-400 border-amber-500/40 text-[10px]">
              Unsaved Changes
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={resetConfig}
            disabled={saving}
            variant="outline"
            size="sm"
            className="text-zinc-400 border-white/10 hover:bg-white/5"
          >
            <RotateCcw className="w-3 h-3 mr-1" />
            Reset
          </Button>
          <Button
            onClick={saveConfig}
            disabled={saving || !hasChanges}
            size="sm"
            className="bg-purple-600 hover:bg-purple-500 text-white"
          >
            {saving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
            Save
          </Button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-3 p-3 bg-blue-950/20 border border-blue-500/20 rounded-lg">
        <Info className="w-4 h-4 text-blue-400 mt-0.5" />
        <div className="text-xs text-zinc-400">
          <p className="font-medium text-blue-400 mb-1">Dynamic Configuration</p>
          <p>Changes apply immediately to new strategy generations. No restart required.</p>
        </div>
      </div>

      {/* Filter Section */}
      <ConfigSection title="Quality Filters" icon={Filter} color="purple">
        <ConfigInput
          label="Min Profit Factor"
          value={config.filters.min_profit_factor}
          onChange={(v) => updateValue('filters', 'min_profit_factor', v)}
          min={1.0}
          max={3.0}
          step={0.05}
          description="Minimum PF to pass filter (1.2 recommended)"
        />
        <ConfigInput
          label="Max Drawdown"
          value={config.filters.max_drawdown_pct}
          onChange={(v) => updateValue('filters', 'max_drawdown_pct', v)}
          min={5}
          max={50}
          step={1}
          unit="%"
          description="Maximum allowed drawdown"
        />
        <ConfigInput
          label="Min Stability"
          value={config.filters.min_stability_pct}
          onChange={(v) => updateValue('filters', 'min_stability_pct', v)}
          min={0}
          max={100}
          step={5}
          unit="%"
          description="Minimum stability score"
        />
        <ConfigInput
          label="Min Trades"
          value={config.filters.min_trades}
          onChange={(v) => updateValue('filters', 'min_trades', Math.round(v))}
          min={10}
          max={500}
          step={10}
          description="Minimum number of trades"
        />
        <ConfigInput
          label="Min Sharpe Ratio"
          value={config.filters.min_sharpe_ratio}
          onChange={(v) => updateValue('filters', 'min_sharpe_ratio', v)}
          min={-2}
          max={3}
          step={0.1}
          description="Minimum Sharpe ratio"
        />
        <ConfigInput
          label="Min Win Rate"
          value={config.filters.min_win_rate}
          onChange={(v) => updateValue('filters', 'min_win_rate', v)}
          min={10}
          max={80}
          step={5}
          unit="%"
          description="Minimum win rate"
        />
      </ConfigSection>

      {/* Generation Section */}
      <ConfigSection title="Generation Settings" icon={Zap} color="emerald">
        <ConfigInput
          label="Default Strategy Count"
          value={config.generation.default_strategy_count}
          onChange={(v) => updateValue('generation', 'default_strategy_count', Math.round(v))}
          min={10}
          max={500}
          step={10}
          description="Strategies per generation run"
        />
        <ConfigInput
          label="Batch Size"
          value={config.generation.batch_size}
          onChange={(v) => updateValue('generation', 'batch_size', Math.round(v))}
          min={5}
          max={50}
          step={5}
          description="Parallel batch size"
        />
        <ConfigInput
          label="Max Retries"
          value={config.generation.max_retries}
          onChange={(v) => updateValue('generation', 'max_retries', Math.round(v))}
          min={1}
          max={10}
          step={1}
          description="Retries if no strategies pass"
        />
        <ConfigInput
          label="Strategies Per Retry"
          value={config.generation.strategies_per_retry}
          onChange={(v) => updateValue('generation', 'strategies_per_retry', Math.round(v))}
          min={10}
          max={100}
          step={5}
          description="Additional strategies on retry"
        />
        <ConfigInput
          label="Min Data Years"
          value={config.generation.min_data_years}
          onChange={(v) => updateValue('generation', 'min_data_years', v)}
          min={0.5}
          max={10}
          step={0.5}
          unit="years"
          description="Minimum data required"
        />
        <ConfigInput
          label="Default Duration"
          value={config.generation.default_duration_days}
          onChange={(v) => updateValue('generation', 'default_duration_days', Math.round(v))}
          min={365}
          max={3650}
          step={365}
          unit="days"
          description="Backtest period"
        />
      </ConfigSection>

      {/* Scoring Section */}
      <ConfigSection title="Scoring Weights" icon={BarChart3} color="amber">
        <ConfigInput
          label="Profit Factor Weight"
          value={config.scoring.profit_factor_weight}
          onChange={(v) => updateValue('scoring', 'profit_factor_weight', v)}
          min={0}
          max={1}
          step={0.05}
          description="Weight in fitness score"
        />
        <ConfigInput
          label="Drawdown Weight"
          value={config.scoring.drawdown_weight}
          onChange={(v) => updateValue('scoring', 'drawdown_weight', v)}
          min={0}
          max={1}
          step={0.05}
          description="DD penalty weight"
        />
        <ConfigInput
          label="Sharpe Weight"
          value={config.scoring.sharpe_weight}
          onChange={(v) => updateValue('scoring', 'sharpe_weight', v)}
          min={0}
          max={1}
          step={0.05}
          description="Risk-adjusted weight"
        />
        <ConfigInput
          label="Monte Carlo Weight"
          value={config.scoring.monte_carlo_weight}
          onChange={(v) => updateValue('scoring', 'monte_carlo_weight', v)}
          min={0}
          max={1}
          step={0.05}
          description="MC simulation weight"
        />
      </ConfigSection>

      {/* Safety Section */}
      <ConfigSection title="Safety Rules" icon={Shield} color="blue">
        <ConfigInput
          label="Max Daily Loss"
          value={config.safety.max_daily_loss_pct}
          onChange={(v) => updateValue('safety', 'max_daily_loss_pct', v)}
          min={1}
          max={10}
          step={0.5}
          unit="%"
          description="Daily loss limit"
        />
        <ConfigInput
          label="Max Total Loss"
          value={config.safety.max_total_loss_pct}
          onChange={(v) => updateValue('safety', 'max_total_loss_pct', v)}
          min={5}
          max={20}
          step={1}
          unit="%"
          description="Total loss limit"
        />
        <ConfigInput
          label="Max Position Size"
          value={config.safety.max_position_size_pct}
          onChange={(v) => updateValue('safety', 'max_position_size_pct', v)}
          min={0.5}
          max={10}
          step={0.5}
          unit="%"
          description="Per trade risk"
        />
        <div className="col-span-2 flex gap-4">
          <label className="flex items-center gap-2 text-xs text-zinc-400">
            <input
              type="checkbox"
              checked={config.safety.require_stop_loss}
              onChange={(e) => updateValue('safety', 'require_stop_loss', e.target.checked)}
              className="w-4 h-4 rounded border-white/20 bg-[#0F0F10]"
            />
            Require Stop Loss
          </label>
          <label className="flex items-center gap-2 text-xs text-zinc-400">
            <input
              type="checkbox"
              checked={config.safety.require_take_profit}
              onChange={(e) => updateValue('safety', 'require_take_profit', e.target.checked)}
              className="w-4 h-4 rounded border-white/20 bg-[#0F0F10]"
            />
            Require Take Profit
          </label>
        </div>
      </ConfigSection>

      {/* Metadata */}
      <div className="text-[10px] text-zinc-600 font-mono flex justify-between">
        <span>Version: {config.version}</span>
        <span>Last updated: {new Date(config.last_updated).toLocaleString()} by {config.updated_by}</span>
      </div>
    </div>
  );
}

export default StrategyConfigPanel;
