import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  AreaChart, Area, CartesianGrid
} from 'recharts';
import {
  ArrowLeft, Activity, TrendingUp, TrendingDown, DollarSign,
  AlertTriangle, CheckCircle2, XCircle, RefreshCw, Eye, Pause,
  Play, Settings2, BarChart3, Clock, Wifi, WifiOff, Zap
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const WS_URL = process.env.REACT_APP_BACKEND_URL?.replace('https://', 'wss://').replace('http://', 'ws://');

// Transform API response to component format
function transformBotData(apiBot) {
  return {
    id: apiBot.bot_id,
    name: apiBot.bot_name,
    symbol: apiBot.symbol,
    timeframe: apiBot.timeframe,
    status: apiBot.status?.toLowerCase() || 'stopped',
    initialBalance: apiBot.initial_balance,
    currentBalance: apiBot.current_balance,
    dailyPnL: apiBot.daily_pnl,
    dailyPnLPercent: apiBot.daily_pnl_percent,
    totalPnL: apiBot.total_pnl,
    totalPnLPercent: apiBot.total_pnl_percent,
    currentDrawdown: apiBot.current_drawdown,
    maxDrawdownLimit: apiBot.max_drawdown_limit,
    tradesToday: apiBot.trades_today,
    maxTradesPerDay: apiBot.max_trades_per_day,
    openTrades: apiBot.open_trades,
    winRate: apiBot.win_rate,
    lastTradeTime: apiBot.last_trade_time,
    mode: apiBot.mode,
    stopReason: apiBot.stop_reason,
  };
}

function BotCard({ bot, onToggle, onViewDetails }) {
  const statusConfig = {
    running: { icon: Play, color: 'emerald', label: 'RUNNING' },
    warning: { icon: AlertTriangle, color: 'amber', label: 'WARNING' },
    stopped: { icon: XCircle, color: 'red', label: 'STOPPED' },
    paused: { icon: Pause, color: 'blue', label: 'PAUSED' },
  };

  const status = statusConfig[bot.status] || statusConfig.stopped;
  const StatusIcon = status.icon;
  const ddProgress = (bot.currentDrawdown / bot.maxDrawdownLimit) * 100;
  const tradesProgress = (bot.tradesToday / bot.maxTradesPerDay) * 100;

  return (
    <div className={`bg-[#0A0A0A] border rounded-sm overflow-hidden ${
      bot.status === 'running' ? 'border-emerald-500/30' :
      bot.status === 'warning' ? 'border-amber-500/30' :
      'border-red-500/30'
    }`} data-testid={`bot-card-${bot.id}`}>
      {/* Header */}
      <div className="px-4 py-3 bg-[#18181B] border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full ${
            bot.status === 'running' ? 'bg-emerald-400 animate-pulse' :
            bot.status === 'warning' ? 'bg-amber-400 animate-pulse' :
            'bg-red-400'
          }`} />
          <div>
            <h3 className="text-sm font-bold text-zinc-200 font-mono">{bot.name}</h3>
            <p className="text-[10px] text-zinc-500 font-mono">{bot.symbol} · {bot.timeframe}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={`text-[9px] px-2 py-0.5 font-mono uppercase ${
            bot.mode === 'live' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' :
            'bg-blue-500/20 text-blue-400 border-blue-500/40'
          }`}>
            {bot.mode === 'live' ? 'LIVE' : 'FORWARD TEST'}
          </Badge>
          <Badge className={`text-[9px] px-2 py-0.5 font-mono uppercase`}
            style={{ 
              backgroundColor: status.color === 'emerald' ? 'rgba(16, 185, 129, 0.2)' : 
                              status.color === 'amber' ? 'rgba(245, 158, 11, 0.2)' : 
                              status.color === 'red' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(59, 130, 246, 0.2)',
              color: status.color === 'emerald' ? '#10b981' : 
                     status.color === 'amber' ? '#f59e0b' : 
                     status.color === 'red' ? '#ef4444' : '#3b82f6',
              borderColor: status.color === 'emerald' ? 'rgba(16, 185, 129, 0.4)' : 
                           status.color === 'amber' ? 'rgba(245, 158, 11, 0.4)' : 
                           status.color === 'red' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(59, 130, 246, 0.4)'
            }}
          >
            <StatusIcon className="w-3 h-3 mr-1" />
            {status.label}
          </Badge>
        </div>
      </div>

      {/* Stop Reason Alert */}
      {bot.stopReason && (
        <div className="px-4 py-2 bg-red-500/10 border-b border-red-500/20">
          <p className="text-xs text-red-400 font-mono flex items-center gap-2">
            <AlertTriangle className="w-3 h-3" />
            {bot.stopReason}
          </p>
        </div>
      )}

      {/* Main Stats Grid */}
      <div className="p-4 grid grid-cols-4 gap-3">
        {/* Balance */}
        <div>
          <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Balance</p>
          <p className="text-lg font-bold font-mono text-zinc-200" data-testid={`bot-balance-${bot.id}`}>
            ${bot.currentBalance.toLocaleString()}
          </p>
        </div>
        
        {/* Daily P&L */}
        <div>
          <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Daily P&L</p>
          <p className={`text-lg font-bold font-mono ${bot.dailyPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`} data-testid={`bot-daily-pnl-${bot.id}`}>
            {bot.dailyPnL >= 0 ? '+' : ''}{bot.dailyPnL.toFixed(0)}
            <span className="text-xs ml-1">({bot.dailyPnLPercent >= 0 ? '+' : ''}{bot.dailyPnLPercent.toFixed(2)}%)</span>
          </p>
        </div>

        {/* Drawdown */}
        <div>
          <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Drawdown</p>
          <p className={`text-lg font-bold font-mono ${
            bot.currentDrawdown >= bot.maxDrawdownLimit * 0.8 ? 'text-red-400' :
            bot.currentDrawdown >= bot.maxDrawdownLimit * 0.5 ? 'text-amber-400' :
            'text-zinc-300'
          }`} data-testid={`bot-drawdown-${bot.id}`}>
            {bot.currentDrawdown.toFixed(1)}%
            <span className="text-xs text-zinc-500 ml-1">/ {bot.maxDrawdownLimit}%</span>
          </p>
        </div>

        {/* Trades Today */}
        <div>
          <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Trades</p>
          <p className="text-lg font-bold font-mono text-zinc-300" data-testid={`bot-trades-${bot.id}`}>
            {bot.tradesToday}
            <span className="text-xs text-zinc-500 ml-1">/ {bot.maxTradesPerDay}</span>
          </p>
        </div>
      </div>

      {/* Progress Bars */}
      <div className="px-4 pb-3 space-y-2">
        {/* DD Progress */}
        <div>
          <div className="flex justify-between text-[9px] font-mono text-zinc-500 mb-1">
            <span>Drawdown Usage</span>
            <span>{ddProgress.toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all rounded-full ${
                ddProgress >= 80 ? 'bg-red-500' : ddProgress >= 50 ? 'bg-amber-500' : 'bg-emerald-500'
              }`}
              style={{ width: `${Math.min(100, ddProgress)}%` }}
            />
          </div>
        </div>

        {/* Trades Progress */}
        <div>
          <div className="flex justify-between text-[9px] font-mono text-zinc-500 mb-1">
            <span>Daily Trades</span>
            <span>{tradesProgress.toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-blue-500 transition-all rounded-full"
              style={{ width: `${Math.min(100, tradesProgress)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="px-4 py-3 bg-[#0F0F10] border-t border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
          <Clock className="w-3 h-3" />
          Last: {bot.lastTradeTime ? new Date(bot.lastTradeTime).toLocaleTimeString() : 'N/A'}
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => onViewDetails(bot)}
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-zinc-400 hover:text-white font-mono text-[10px]"
          >
            <Eye className="w-3 h-3 mr-1" /> Details
          </Button>
          <Button
            onClick={() => onToggle(bot)}
            size="sm"
            className={`h-7 px-3 font-mono text-[10px] uppercase ${
              bot.status === 'running' || bot.status === 'warning'
                ? 'bg-amber-600 hover:bg-amber-500 text-white'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white'
            }`}
          >
            {bot.status === 'running' || bot.status === 'warning' ? (
              <><Pause className="w-3 h-3 mr-1" /> Pause</>
            ) : (
              <><Play className="w-3 h-3 mr-1" /> Start</>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

// Real-time Equity Chart Component
function EquityCurveChart({ history }) {
  const chartData = useMemo(() => {
    if (!history || history.length === 0) return [];
    return history.slice(-50).map((point, idx) => ({
      time: new Date(point.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      balance: point.balance,
      idx
    }));
  }, [history]);

  if (chartData.length === 0) {
    return (
      <div className="h-40 flex items-center justify-center text-zinc-600 text-xs font-mono">
        No equity data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={160}>
      <AreaChart data={chartData}>
        <defs>
          <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
            <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis 
          dataKey="time" 
          tick={{ fill: '#71717a', fontSize: 9 }}
          axisLine={{ stroke: '#27272a' }}
          tickLine={false}
        />
        <YAxis 
          tick={{ fill: '#71717a', fontSize: 9 }}
          axisLine={{ stroke: '#27272a' }}
          tickLine={false}
          tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`}
          domain={['dataMin - 500', 'dataMax + 500']}
        />
        <Tooltip 
          contentStyle={{ 
            backgroundColor: '#18181b', 
            border: '1px solid #27272a',
            borderRadius: '4px',
            fontSize: '11px'
          }}
          formatter={(value) => [`$${value.toLocaleString()}`, 'Balance']}
        />
        <Area 
          type="monotone" 
          dataKey="balance" 
          stroke="#10b981" 
          strokeWidth={2}
          fill="url(#equityGradient)" 
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Daily PnL Chart Component
function DailyPnLChart({ history }) {
  const chartData = useMemo(() => {
    if (!history || history.length === 0) return [];
    return history.slice(-30).map((point, idx) => ({
      time: new Date(point.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      pnl: point.daily_pnl,
      idx
    }));
  }, [history]);

  if (chartData.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-zinc-600 text-xs font-mono">
        No P&L data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={120}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis 
          dataKey="time" 
          tick={{ fill: '#71717a', fontSize: 9 }}
          axisLine={{ stroke: '#27272a' }}
          tickLine={false}
        />
        <YAxis 
          tick={{ fill: '#71717a', fontSize: 9 }}
          axisLine={{ stroke: '#27272a' }}
          tickLine={false}
          tickFormatter={(v) => `$${v}`}
        />
        <Tooltip 
          contentStyle={{ 
            backgroundColor: '#18181b', 
            border: '1px solid #27272a',
            borderRadius: '4px',
            fontSize: '11px'
          }}
          formatter={(value) => [`$${value.toFixed(2)}`, 'Daily P&L']}
        />
        <Line 
          type="monotone" 
          dataKey="pnl" 
          stroke="#f59e0b" 
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function LiveDashboardPage() {
  // Force rebuild v3
  const navigate = useNavigate();
  const [bots, setBots] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);
  const [connectionQuality, setConnectionQuality] = useState('stable'); // stable, unstable, offline
  const [lastUpdate, setLastUpdate] = useState(null);
  const [allBotHistory, setAllBotHistory] = useState({});
  const [maxDDToday, setMaxDDToday] = useState(0);
  
  const wsRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const pollIntervalRef = useRef(null);
  const lastHeartbeat = useRef(Date.now());

  // Fetch bots from API
  const fetchBots = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/bots/status`);
      if (response.data.success) {
        const transformedBots = response.data.bots.map(transformBotData);
        setBots(transformedBots);
        setLastUpdate(new Date());
        
        // Calculate max DD today across all bots
        const maxDD = Math.max(...transformedBots.map(b => b.currentDrawdown || 0));
        setMaxDDToday(maxDD);
      }
    } catch (error) {
      console.error('Failed to fetch bots:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch bot history for charts
  const fetchBotHistory = useCallback(async (botId) => {
    try {
      const response = await axios.get(`${API}/bots/history/${botId}?hours=24`);
      if (response.data.success) {
        setAllBotHistory(prev => ({
          ...prev,
          [botId]: response.data.history
        }));
      }
    } catch (error) {
      console.error(`Failed to fetch history for ${botId}:`, error);
    }
  }, []);

  // Smart fallback polling - adjusts interval based on connection quality
  const setupSmartPolling = useCallback(() => {
    // Clear existing interval
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    // Determine polling interval based on connection quality
    let interval = 15000; // Default: 15 seconds
    if (connectionQuality === 'unstable') {
      interval = 10000; // Faster when unstable
    } else if (connectionQuality === 'offline') {
      interval = 5000; // Even faster when offline
    }

    pollIntervalRef.current = setInterval(() => {
      fetchBots();
      // Fetch history for all bots periodically
      bots.forEach(bot => fetchBotHistory(bot.id));
    }, interval);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [connectionQuality, fetchBots, bots, fetchBotHistory]);

  // WebSocket connection with auto-reconnect
  useEffect(() => {
    fetchBots();

    const connectWebSocket = () => {
      try {
        const ws = new WebSocket(`${WS_URL}/ws/bot-updates`);
        
        ws.onopen = () => {
          setWsConnected(true);
          setConnectionQuality('stable');
          reconnectAttempts.current = 0;
          console.log('[WS] Connected');
          lastHeartbeat.current = Date.now();
        };
        
        ws.onmessage = (event) => {
          lastHeartbeat.current = Date.now();
          const data = JSON.parse(event.data);
          
          if (data.type === 'BOT_STATUS_UPDATE' || data.type === 'bot_status_update') {
            setBots(prev => prev.map(bot => 
              bot.id === data.bot_id 
                ? { ...bot, 
                    status: data.status?.toLowerCase(), 
                    currentBalance: data.current_balance ?? bot.currentBalance,
                    dailyPnL: data.daily_pnl ?? bot.dailyPnL,
                    currentDrawdown: data.current_drawdown ?? bot.currentDrawdown,
                    tradesToday: data.trades_today ?? bot.tradesToday,
                    stopReason: data.stop_reason,
                  }
                : bot
            ));
            setLastUpdate(new Date());
            
            if (data.auto_stopped) {
              toast.error(`${data.bot_id} auto-stopped: ${data.stop_reason}`);
            }
          }
          
          if (data.type === 'DD_WARNING' || data.type === 'drawdown_update') {
            toast.warning(`DD Warning: ${data.bot_id} at ${data.current_drawdown}%`);
            // Update max DD
            setMaxDDToday(prev => Math.max(prev, data.current_drawdown || 0));
          }
          
          if (data.type === 'NEW_TRADE' || data.type === 'new_trade') {
            toast.info(`New trade: ${data.bot_id} ${data.direction || ''} ${data.symbol || ''}`);
            fetchBots(); // Refresh to get updated stats
          }

          if (data.type === 'DD_BREACH') {
            toast.error(`DD BREACH: ${data.bot_id} - ${data.reason}`, { duration: 10000 });
          }

          if (data.type === 'BOT_ALERT') {
            const toastFn = data.severity === 'critical' ? toast.error : 
                           data.severity === 'warning' ? toast.warning : toast.info;
            toastFn(`${data.alert_type}: ${data.message}`);
          }

          // Handle keepalive/pong
          if (data.type === 'keepalive' || data.type === 'pong' || data.type === 'connected') {
            lastHeartbeat.current = Date.now();
          }
        };
        
        ws.onclose = (event) => {
          setWsConnected(false);
          reconnectAttempts.current++;
          
          // Determine connection quality based on reconnect attempts
          if (reconnectAttempts.current > 3) {
            setConnectionQuality('offline');
          } else if (reconnectAttempts.current > 0) {
            setConnectionQuality('unstable');
          }
          
          // Exponential backoff with max 30 seconds
          const delay = Math.min(5000 * Math.pow(1.5, reconnectAttempts.current), 30000);
          console.log(`[WS] Disconnected, reconnecting in ${delay/1000}s...`);
          setTimeout(connectWebSocket, delay);
        };
        
        ws.onerror = (error) => {
          console.error('[WS] Error:', error);
          setConnectionQuality('unstable');
        };
        
        wsRef.current = ws;

        // Send ping every 25 seconds to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'ping' }));
          }
        }, 25000);

        // Check for stale connection (no heartbeat in 45 seconds)
        const healthCheck = setInterval(() => {
          const timeSinceHeartbeat = Date.now() - lastHeartbeat.current;
          if (timeSinceHeartbeat > 45000 && wsConnected) {
            console.log('[WS] Connection stale, reconnecting...');
            ws.close();
          }
        }, 10000);

        return () => {
          clearInterval(pingInterval);
          clearInterval(healthCheck);
        };
        
      } catch (error) {
        console.error('[WS] Connection failed:', error);
        setConnectionQuality('offline');
        setTimeout(connectWebSocket, 5000);
      }
    };
    
    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [fetchBots]);

  // Setup smart polling based on connection quality
  useEffect(() => {
    setupSmartPolling();
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [setupSmartPolling]);

  // Initial history fetch
  useEffect(() => {
    if (bots.length > 0 && Object.keys(allBotHistory).length === 0) {
      bots.forEach(bot => fetchBotHistory(bot.id));
    }
  }, [bots, allBotHistory, fetchBotHistory]);

  // Calculate aggregate stats
  const aggregateStats = useMemo(() => {
    if (bots.length === 0) {
      return { running: 0, warning: 0, stopped: 0, totalBalance: 0, totalDailyPnL: 0, totalPnL: 0, avgDrawdown: 0 };
    }
    
    const running = bots.filter(b => b.status === 'running').length;
    const warning = bots.filter(b => b.status === 'warning').length;
    const stopped = bots.filter(b => b.status === 'stopped' || b.status === 'paused' || b.status === 'error').length;
    
    const totalBalance = bots.reduce((sum, b) => sum + (b.currentBalance || 0), 0);
    const totalDailyPnL = bots.reduce((sum, b) => sum + (b.dailyPnL || 0), 0);
    const totalPnL = bots.reduce((sum, b) => sum + (b.totalPnL || 0), 0);
    const avgDrawdown = bots.reduce((sum, b) => sum + (b.currentDrawdown || 0), 0) / bots.length;
    
    return { running, warning, stopped, totalBalance, totalDailyPnL, totalPnL, avgDrawdown };
  }, [bots]);

  // Combine all bot histories for aggregate chart
  const aggregateHistory = useMemo(() => {
    const histories = Object.values(allBotHistory);
    if (histories.length === 0) return [];
    
    // Get the first bot's history as base timeline
    const baseHistory = histories[0] || [];
    return baseHistory.map((point, idx) => {
      let totalBalance = 0;
      let totalDailyPnL = 0;
      histories.forEach(hist => {
        if (hist[idx]) {
          totalBalance += hist[idx].balance || 0;
          totalDailyPnL += hist[idx].daily_pnl || 0;
        }
      });
      return {
        ...point,
        balance: totalBalance,
        daily_pnl: totalDailyPnL
      };
    });
  }, [allBotHistory]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchBots();
    bots.forEach(bot => fetchBotHistory(bot.id));
    setRefreshing(false);
    toast.success('Dashboard refreshed');
  };

  const handleToggleBot = async (bot) => {
    const action = bot.status === 'running' || bot.status === 'warning' ? 'pause' : 'start';
    try {
      const response = await axios.post(`${API}/bots/control/${bot.id}?action=${action}`);
      if (response.data.success) {
        setBots(prev => prev.map(b => {
          if (b.id === bot.id) {
            return { ...b, status: response.data.new_status.toLowerCase(), stopReason: null };
          }
          return b;
        }));
        toast.success(`${bot.name} ${action === 'start' ? 'started' : 'paused'}`);
      }
    } catch (error) {
      toast.error(`Failed to ${action} bot: ${error.message}`);
    }
  };

  const handleViewDetails = (bot) => {
    navigate(`/trade-history?bot=${bot.id}`);
  };

  // Connection status indicator
  const connectionStatusColor = wsConnected ? 
    (connectionQuality === 'stable' ? 'emerald' : 'amber') : 'red';
  const connectionStatusText = wsConnected ?
    (connectionQuality === 'stable' ? 'LIVE' : 'UNSTABLE') : 'OFFLINE';

  return (
    <div className="min-h-screen bg-[#050505] p-4" data-testid="live-dashboard-page">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate('/')} className="text-zinc-500 hover:text-white transition-colors" data-testid="back-btn">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-extrabold uppercase tracking-tight text-white" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                LIVE MONITORING
              </h1>
              <p className="text-xs text-zinc-500 uppercase tracking-widest mt-0.5 font-mono">
                Real-time bot status & performance
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* WebSocket Status */}
            <div className={`flex items-center gap-1.5 px-2 py-1 rounded text-[9px] font-mono ${
              connectionStatusColor === 'emerald' ? 'bg-emerald-500/20 text-emerald-400' :
              connectionStatusColor === 'amber' ? 'bg-amber-500/20 text-amber-400' :
              'bg-red-500/20 text-red-400'
            }`} data-testid="ws-status">
              {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {connectionStatusText}
              {lastUpdate && (
                <span className="ml-2 opacity-60">
                  {lastUpdate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              )}
            </div>
            <Button
              onClick={handleRefresh}
              disabled={refreshing}
              className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-mono uppercase text-[10px] h-8 px-3"
              data-testid="refresh-btn"
            >
              <RefreshCw className={`w-3 h-3 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              onClick={() => navigate('/settings/alerts')}
              className="bg-amber-600 hover:bg-amber-500 text-white font-mono uppercase text-[10px] h-8 px-3"
              data-testid="alert-settings-btn"
            >
              <AlertTriangle className="w-3 h-3 mr-1.5" />
              Alerts
            </Button>
            <Button
              onClick={() => navigate('/bot-config')}
              className="bg-blue-600 hover:bg-blue-500 text-white font-mono uppercase text-[10px] h-8 px-3"
              data-testid="add-bot-btn"
            >
              <Settings2 className="w-3 h-3 mr-1.5" />
              New Bot
            </Button>
          </div>
        </div>

        {/* Aggregate Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 mb-6">
          <div className="bg-[#0A0A0A] border border-white/5 p-2 rounded-sm" data-testid="stat-running">
            <div className="flex items-center gap-1.5 mb-0.5">
              <Play className="w-3 h-3 text-emerald-400" />
              <span className="text-[9px] text-zinc-500 font-mono uppercase">Running</span>
            </div>
            <p className="text-xl font-bold font-mono text-emerald-400">{aggregateStats.running}</p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-2 rounded-sm" data-testid="stat-warning">
            <div className="flex items-center gap-1.5 mb-0.5">
              <AlertTriangle className="w-3 h-3 text-amber-400" />
              <span className="text-[9px] text-zinc-500 font-mono uppercase">Warning</span>
            </div>
            <p className="text-xl font-bold font-mono text-amber-400">{aggregateStats.warning}</p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-2 rounded-sm" data-testid="stat-stopped">
            <div className="flex items-center gap-1.5 mb-0.5">
              <XCircle className="w-3 h-3 text-red-400" />
              <span className="text-[9px] text-zinc-500 font-mono uppercase">Stopped</span>
            </div>
            <p className="text-xl font-bold font-mono text-red-400">{aggregateStats.stopped}</p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-2 rounded-sm" data-testid="stat-balance">
            <div className="flex items-center gap-1.5 mb-0.5">
              <DollarSign className="w-3 h-3 text-zinc-400" />
              <span className="text-[9px] text-zinc-500 font-mono uppercase">Balance</span>
            </div>
            <p className="text-lg font-bold font-mono text-zinc-200">${(aggregateStats.totalBalance/1000).toFixed(0)}k</p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-2 rounded-sm" data-testid="stat-daily-pnl">
            <div className="flex items-center gap-1.5 mb-0.5">
              <BarChart3 className="w-3 h-3 text-zinc-400" />
              <span className="text-[9px] text-zinc-500 font-mono uppercase">Daily P&L</span>
            </div>
            <p className={`text-lg font-bold font-mono ${aggregateStats.totalDailyPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {aggregateStats.totalDailyPnL >= 0 ? '+' : ''}${aggregateStats.totalDailyPnL.toFixed(0)}
            </p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-2 rounded-sm" data-testid="stat-avg-dd">
            <div className="flex items-center gap-1.5 mb-0.5">
              <TrendingDown className="w-3 h-3 text-zinc-400" />
              <span className="text-[9px] text-zinc-500 font-mono uppercase">Avg DD</span>
            </div>
            <p className={`text-lg font-bold font-mono ${
              aggregateStats.avgDrawdown > 4 ? 'text-red-400' : 
              aggregateStats.avgDrawdown > 2 ? 'text-amber-400' : 'text-zinc-300'
            }`}>
              {aggregateStats.avgDrawdown.toFixed(1)}%
            </p>
          </div>
          <div className="bg-[#0A0A0A] border border-red-500/30 p-2 rounded-sm" data-testid="stat-max-dd-today">
            <div className="flex items-center gap-1.5 mb-0.5">
              <Zap className="w-3 h-3 text-red-400" />
              <span className="text-[9px] text-zinc-500 font-mono uppercase">Max DD</span>
            </div>
            <p className={`text-lg font-bold font-mono ${
              maxDDToday > 4 ? 'text-red-400' : 
              maxDDToday > 2 ? 'text-amber-400' : 'text-zinc-300'
            }`}>
              {maxDDToday.toFixed(1)}%
            </p>
          </div>
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          {/* Equity Curve Chart */}
          <div className="bg-[#0A0A0A] border border-white/5 p-4 rounded-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold text-zinc-400 font-mono uppercase flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                Real-Time Equity Curve
              </h3>
              <span className="text-[9px] text-zinc-600 font-mono">Last 24h</span>
            </div>
            <EquityCurveChart history={aggregateHistory} />
          </div>

          {/* Daily PnL Chart */}
          <div className="bg-[#0A0A0A] border border-white/5 p-4 rounded-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold text-zinc-400 font-mono uppercase flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-amber-400" />
                Daily P&L Trend
              </h3>
              <span className="text-[9px] text-zinc-600 font-mono">Last 24h</span>
            </div>
            <DailyPnLChart history={aggregateHistory} />
          </div>
        </div>
      </div>

      {/* Bot Cards Grid */}
      <div className="max-w-7xl mx-auto">
        {loading ? (
          <div className="bg-[#0A0A0A] border border-white/5 p-8 rounded-sm text-center">
            <RefreshCw className="w-12 h-12 text-zinc-600 mx-auto mb-4 animate-spin" />
            <p className="text-sm text-zinc-500 font-mono">Loading bot status...</p>
          </div>
        ) : bots.length === 0 ? (
          <div className="bg-[#0A0A0A] border border-white/5 p-8 rounded-sm text-center">
            <Activity className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <p className="text-sm text-zinc-500 font-mono mb-2">No bots registered</p>
            <p className="text-xs text-zinc-600 font-mono mb-4">
              Generate a bot from the dashboard and register it to start monitoring
            </p>
            <Button
              onClick={() => navigate('/')}
              className="mt-4 bg-blue-600 hover:bg-blue-500 text-white font-mono uppercase text-xs"
            >
              Go to Bot Builder
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="bot-cards-grid">
            {bots.map(bot => (
              <BotCard 
                key={bot.id} 
                bot={bot} 
                onToggle={handleToggleBot}
                onViewDetails={handleViewDetails}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
