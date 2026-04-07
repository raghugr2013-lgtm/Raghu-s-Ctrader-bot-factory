import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import {
  ArrowLeft, Bell, BellOff, Send, AlertTriangle,
  TrendingUp, Bot, Settings2, Check, X, RefreshCw, Wifi
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AlertSettingsPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  
  const [config, setConfig] = useState({
    enabled: true,
    telegram_bot_token: '',
    telegram_chat_id: '',
    drawdown_warning_percent: 80,
    daily_profit_target_percent: 2,
    milestone_profits: [2, 5, 10],
    alert_on_drawdown_warning: true,
    alert_on_drawdown_breach: true,
    alert_on_profit_target: true,
    alert_on_milestone: true,
    alert_on_bot_start: true,
    alert_on_bot_stop: true,
    alert_on_trade: false,
  });

  const [tokenMasked, setTokenMasked] = useState('');

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API}/alerts/config`);
      if (response.data.success) {
        const cfg = response.data.config;
        setConfig(prev => ({
          ...prev,
          ...cfg,
          telegram_bot_token: '', // Don't show actual token
        }));
        setTokenMasked(cfg.telegram_bot_token_masked || '');
      }
    } catch (error) {
      console.error('Failed to fetch config:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updateData = { ...config };
      // Only send token if it was changed
      if (!updateData.telegram_bot_token) {
        delete updateData.telegram_bot_token;
      }
      
      await axios.post(`${API}/alerts/config`, updateData);
      toast.success('Alert settings saved');
      fetchConfig(); // Refresh to get masked token
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleTestTelegram = async () => {
    if (!config.telegram_bot_token && !tokenMasked) {
      toast.error('Please enter Telegram bot token');
      return;
    }
    if (!config.telegram_chat_id) {
      toast.error('Please enter Telegram chat ID');
      return;
    }

    setTesting(true);
    try {
      // If token wasn't changed, we need to first save then test
      if (!config.telegram_bot_token && tokenMasked) {
        // Token exists but wasn't modified - just test
        const response = await axios.post(`${API}/alerts/test-telegram`, {
          bot_token: "USE_SAVED", // Backend should use saved token
          chat_id: config.telegram_chat_id
        });
        toast.success('Test message sent to Telegram!');
      } else {
        const response = await axios.post(`${API}/alerts/test-telegram`, {
          bot_token: config.telegram_bot_token,
          chat_id: config.telegram_chat_id
        });
        toast.success('Test message sent to Telegram!');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to send test message');
    } finally {
      setTesting(false);
    }
  };

  const ToggleSwitch = ({ enabled, onChange, label, description }) => (
    <div className="flex items-center justify-between py-3 border-b border-white/5">
      <div>
        <p className="text-sm font-medium text-zinc-200">{label}</p>
        <p className="text-xs text-zinc-500">{description}</p>
      </div>
      <button
        onClick={() => onChange(!enabled)}
        className={`relative w-11 h-6 rounded-full transition-colors ${
          enabled ? 'bg-emerald-500' : 'bg-zinc-700'
        }`}
        data-testid={`toggle-${label.toLowerCase().replace(/\s/g, '-')}`}
      >
        <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
          enabled ? 'left-6' : 'left-1'
        }`} />
      </button>
    </div>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <RefreshCw className="w-8 h-8 text-zinc-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] p-4" data-testid="alert-settings-page">
      {/* Header */}
      <div className="max-w-2xl mx-auto mb-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate('/live')} className="text-zinc-500 hover:text-white transition-colors" data-testid="back-btn">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-extrabold uppercase tracking-tight text-white" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                ALERT SETTINGS
              </h1>
              <p className="text-xs text-zinc-500 uppercase tracking-widest mt-0.5 font-mono">
                Real-time notifications via Telegram
              </p>
            </div>
          </div>
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono uppercase text-[10px] h-9 px-4"
            data-testid="save-btn"
          >
            {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4 mr-1" />}
            Save Settings
          </Button>
        </div>

        {/* Master Toggle */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-sm p-4 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {config.enabled ? (
                <Bell className="w-6 h-6 text-emerald-400" />
              ) : (
                <BellOff className="w-6 h-6 text-zinc-500" />
              )}
              <div>
                <h2 className="text-lg font-bold text-white">Alerts {config.enabled ? 'Enabled' : 'Disabled'}</h2>
                <p className="text-xs text-zinc-500">Master switch for all notifications</p>
              </div>
            </div>
            <button
              onClick={() => setConfig(prev => ({ ...prev, enabled: !prev.enabled }))}
              className={`relative w-14 h-8 rounded-full transition-colors ${
                config.enabled ? 'bg-emerald-500' : 'bg-zinc-700'
              }`}
              data-testid="master-toggle"
            >
              <div className={`absolute top-1.5 w-5 h-5 rounded-full bg-white transition-transform ${
                config.enabled ? 'left-8' : 'left-1.5'
              }`} />
            </button>
          </div>
        </div>

        {/* Telegram Configuration */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-sm p-4 mb-4">
          <h3 className="text-sm font-bold text-zinc-200 mb-4 flex items-center gap-2">
            <Send className="w-4 h-4 text-blue-400" />
            Telegram Configuration
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-zinc-500 font-mono uppercase mb-1.5">Bot Token</label>
              <Input
                type="password"
                placeholder={tokenMasked || "Enter your Telegram bot token from @BotFather"}
                value={config.telegram_bot_token}
                onChange={(e) => setConfig(prev => ({ ...prev, telegram_bot_token: e.target.value }))}
                className="bg-black border-white/10 text-white font-mono text-sm h-10"
                data-testid="bot-token-input"
              />
              <p className="text-[10px] text-zinc-600 mt-1">Get from @BotFather on Telegram</p>
            </div>
            
            <div>
              <label className="block text-xs text-zinc-500 font-mono uppercase mb-1.5">Chat ID</label>
              <Input
                placeholder="Enter your Telegram chat ID"
                value={config.telegram_chat_id}
                onChange={(e) => setConfig(prev => ({ ...prev, telegram_chat_id: e.target.value }))}
                className="bg-black border-white/10 text-white font-mono text-sm h-10"
                data-testid="chat-id-input"
              />
              <p className="text-[10px] text-zinc-600 mt-1">Message @userinfobot to get your ID</p>
            </div>

            <Button
              onClick={handleTestTelegram}
              disabled={testing}
              className="bg-blue-600 hover:bg-blue-500 text-white font-mono uppercase text-[10px] h-9 px-4"
              data-testid="test-telegram-btn"
            >
              {testing ? <RefreshCw className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
              Send Test Message
            </Button>
          </div>
        </div>

        {/* Risk Alert Settings */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-sm p-4 mb-4">
          <h3 className="text-sm font-bold text-zinc-200 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Risk Alerts
          </h3>
          
          <div className="mb-4">
            <label className="block text-xs text-zinc-500 font-mono uppercase mb-1.5">
              Drawdown Warning Threshold (% of limit)
            </label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                value={config.drawdown_warning_percent}
                onChange={(e) => setConfig(prev => ({ ...prev, drawdown_warning_percent: parseFloat(e.target.value) || 0 }))}
                className="bg-black border-white/10 text-white font-mono text-sm h-10 w-24"
                min={50}
                max={100}
                data-testid="dd-threshold-input"
              />
              <span className="text-zinc-400 text-sm font-mono">%</span>
              <p className="text-xs text-zinc-500">Alert when DD reaches this % of your limit</p>
            </div>
          </div>

          <ToggleSwitch
            enabled={config.alert_on_drawdown_warning}
            onChange={(v) => setConfig(prev => ({ ...prev, alert_on_drawdown_warning: v }))}
            label="Drawdown Warning"
            description="Alert when approaching DD limit"
          />
          <ToggleSwitch
            enabled={config.alert_on_drawdown_breach}
            onChange={(v) => setConfig(prev => ({ ...prev, alert_on_drawdown_breach: v }))}
            label="Drawdown Breach"
            description="Alert when DD limit is breached (bot stopped)"
          />
        </div>

        {/* Profit Alert Settings */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-sm p-4 mb-4">
          <h3 className="text-sm font-bold text-zinc-200 mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            Profit Alerts
          </h3>
          
          <div className="mb-4">
            <label className="block text-xs text-zinc-500 font-mono uppercase mb-1.5">
              Daily Profit Target
            </label>
            <div className="flex items-center gap-3">
              <Input
                type="number"
                value={config.daily_profit_target_percent}
                onChange={(e) => setConfig(prev => ({ ...prev, daily_profit_target_percent: parseFloat(e.target.value) || 0 }))}
                className="bg-black border-white/10 text-white font-mono text-sm h-10 w-24"
                step={0.5}
                min={0}
                data-testid="profit-target-input"
              />
              <span className="text-zinc-400 text-sm font-mono">%</span>
              <p className="text-xs text-zinc-500">Alert when daily profit reaches this</p>
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-xs text-zinc-500 font-mono uppercase mb-1.5">
              Milestone Profits
            </label>
            <div className="flex items-center gap-2">
              {config.milestone_profits.map((m, i) => (
                <div key={i} className="flex items-center gap-1">
                  <Input
                    type="number"
                    value={m}
                    onChange={(e) => {
                      const newMilestones = [...config.milestone_profits];
                      newMilestones[i] = parseFloat(e.target.value) || 0;
                      setConfig(prev => ({ ...prev, milestone_profits: newMilestones }));
                    }}
                    className="bg-black border-white/10 text-white font-mono text-sm h-8 w-16"
                    step={1}
                    min={0}
                  />
                  <span className="text-zinc-500 text-xs">%</span>
                </div>
              ))}
            </div>
          </div>

          <ToggleSwitch
            enabled={config.alert_on_profit_target}
            onChange={(v) => setConfig(prev => ({ ...prev, alert_on_profit_target: v }))}
            label="Daily Target Reached"
            description="Alert when daily profit target is hit"
          />
          <ToggleSwitch
            enabled={config.alert_on_milestone}
            onChange={(v) => setConfig(prev => ({ ...prev, alert_on_milestone: v }))}
            label="Milestone Reached"
            description="Alert on profit milestones (2%, 5%, 10%)"
          />
        </div>

        {/* Bot Event Settings */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-sm p-4 mb-4">
          <h3 className="text-sm font-bold text-zinc-200 mb-4 flex items-center gap-2">
            <Bot className="w-4 h-4 text-blue-400" />
            Bot Events
          </h3>
          
          <ToggleSwitch
            enabled={config.alert_on_bot_start}
            onChange={(v) => setConfig(prev => ({ ...prev, alert_on_bot_start: v }))}
            label="Bot Started"
            description="Alert when a bot starts trading"
          />
          <ToggleSwitch
            enabled={config.alert_on_bot_stop}
            onChange={(v) => setConfig(prev => ({ ...prev, alert_on_bot_stop: v }))}
            label="Bot Stopped"
            description="Alert when a bot stops trading"
          />
          <ToggleSwitch
            enabled={config.alert_on_trade}
            onChange={(v) => setConfig(prev => ({ ...prev, alert_on_trade: v }))}
            label="Trade Notifications"
            description="Alert on every trade (can be noisy)"
          />
        </div>

        {/* Help Section */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-sm p-4">
          <h3 className="text-sm font-bold text-zinc-200 mb-3">Setup Instructions</h3>
          <ol className="text-xs text-zinc-400 space-y-2 font-mono">
            <li>1. Open Telegram and search for @BotFather</li>
            <li>2. Send /newbot and follow the instructions</li>
            <li>3. Copy the bot token and paste it above</li>
            <li>4. Search for @userinfobot and send /start</li>
            <li>5. Copy your chat ID and paste it above</li>
            <li>6. Click "Send Test Message" to verify</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
