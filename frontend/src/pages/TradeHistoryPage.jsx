// TradeHistoryPage - Real API Connected v2
import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  ArrowLeft, Search, Download,
  TrendingUp, TrendingDown, RefreshCw
} from 'lucide-react';
import { formatDateTime } from '@/lib/dateUtils';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Transform API trade to component format
function transformTradeData(apiTrade) {
  return {
    id: apiTrade.id || apiTrade._id || `trade_${Date.now()}_${Math.random()}`,
    botId: apiTrade.bot_id,
    botName: apiTrade.bot_name,
    symbol: apiTrade.symbol,
    direction: apiTrade.direction?.toLowerCase() || 'buy',
    entryTime: apiTrade.timestamp_entry,
    exitTime: apiTrade.timestamp_exit,
    entryPrice: apiTrade.entry_price,
    exitPrice: apiTrade.exit_price,
    lotSize: apiTrade.lot_size,
    stopLoss: apiTrade.stop_loss,
    takeProfit: apiTrade.take_profit,
    profitLoss: apiTrade.pnl || 0,
    profitLossPips: apiTrade.pips || 0,
    reason: apiTrade.reason,
    closeReason: apiTrade.close_reason,
    result: apiTrade.result,
    mode: apiTrade.mode,
  };
}

const SYMBOLS = ['All', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'XAUUSD'];
const DIRECTIONS = ['All', 'buy', 'sell'];
const RESULTS = ['All', 'profit', 'loss'];
const MODES = ['All', 'forward_test', 'live', 'backtest'];

export default function TradeHistoryPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const botIdFilter = searchParams.get('bot');

  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [apiSummary, setApiSummary] = useState(null);

  const [filters, setFilters] = useState({
    search: '',
    symbol: 'All',
    direction: 'All',
    result: 'All',
    mode: 'All',
    botId: botIdFilter || '',
  });

  // Fetch trades from API
  const fetchTrades = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filters.botId) params.append('bot_id', filters.botId);
      if (filters.symbol !== 'All') params.append('symbol', filters.symbol);
      if (filters.direction !== 'All') params.append('direction', filters.direction);
      if (filters.result !== 'All') params.append('result', filters.result);
      if (filters.mode !== 'All') params.append('mode', filters.mode);
      params.append('limit', '500');

      const response = await axios.get(`${API}/trades?${params.toString()}`);
      
      if (response.data.success) {
        const transformedTrades = response.data.trades.map(transformTradeData);
        setTrades(transformedTrades);
        setApiSummary(response.data.summary);
      }
    } catch (error) {
      console.error('Failed to fetch trades:', error);
      toast.error('Failed to load trade history');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filters.botId, filters.symbol, filters.direction, filters.result, filters.mode]);

  useEffect(() => {
    fetchTrades();
  }, [fetchTrades]);

  // Client-side filtering for search (API handles the rest)
  const filteredTrades = useMemo(() => {
    if (!filters.search) return trades;
    return trades.filter(trade => 
      trade.botName?.toLowerCase().includes(filters.search.toLowerCase())
    );
  }, [trades, filters.search]);

  // Calculate summary stats from API or local data
  const summary = useMemo(() => {
    if (apiSummary) {
      return {
        totalTrades: apiSummary.total_trades || 0,
        winningTrades: apiSummary.wins || 0,
        losingTrades: apiSummary.losses || 0,
        totalPnL: apiSummary.total_pnl || 0,
        winRate: apiSummary.win_rate || 0,
        profitFactor: apiSummary.profit_factor || 0,
        avgWin: apiSummary.avg_win || 0,
        avgLoss: apiSummary.avg_loss || 0,
      };
    }

    // Fallback to local calculation
    const totalTrades = filteredTrades.length;
    const winningTrades = filteredTrades.filter(t => (t.profitLoss || 0) > 0).length;
    const losingTrades = filteredTrades.filter(t => (t.profitLoss || 0) < 0).length;
    const totalPnL = filteredTrades.reduce((sum, t) => sum + (t.profitLoss || 0), 0);
    const totalPips = filteredTrades.reduce((sum, t) => sum + (t.profitLossPips || 0), 0);
    const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;
    const avgWin = winningTrades > 0 
      ? filteredTrades.filter(t => (t.profitLoss || 0) > 0).reduce((sum, t) => sum + (t.profitLoss || 0), 0) / winningTrades 
      : 0;
    const avgLoss = losingTrades > 0
      ? Math.abs(filteredTrades.filter(t => (t.profitLoss || 0) < 0).reduce((sum, t) => sum + (t.profitLoss || 0), 0)) / losingTrades
      : 0;
    const profitFactor = avgLoss > 0 && losingTrades > 0 ? (avgWin * winningTrades) / (avgLoss * losingTrades) : avgWin > 0 ? 999 : 0;

    return { totalTrades, winningTrades, losingTrades, totalPnL, totalPips, winRate, avgWin, avgLoss, profitFactor };
  }, [apiSummary, filteredTrades]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchTrades();
    toast.success('Trade history refreshed');
  };

  const handleExport = () => {
    const csv = [
      ['ID', 'Bot', 'Symbol', 'Direction', 'Mode', 'Entry Time', 'Exit Time', 'Entry Price', 'Exit Price', 'Lot Size', 'P/L', 'Pips', 'Reason', 'Close Reason'].join(','),
      ...filteredTrades.map(t => [
        t.id, 
        `"${t.botName || ''}"`, 
        t.symbol, 
        t.direction, 
        t.mode,
        t.entryTime, 
        t.exitTime || '', 
        t.entryPrice, 
        t.exitPrice || '', 
        t.lotSize, 
        t.profitLoss || 0, 
        t.profitLossPips || 0, 
        `"${t.reason || ''}"`, 
        `"${t.closeReason || ''}"`
      ].join(','))
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trade_history_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    toast.success('CSV exported successfully');
  };

  return (
    <div className="min-h-screen bg-[#050505] p-4" data-testid="trade-history-page">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate('/live')} className="text-zinc-500 hover:text-white transition-colors" data-testid="back-btn">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-extrabold uppercase tracking-tight text-white" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                TRADE HISTORY
              </h1>
              <p className="text-xs text-zinc-500 uppercase tracking-widest mt-0.5 font-mono">
                Complete trade log & analysis
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={handleRefresh}
              disabled={refreshing}
              className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-mono uppercase text-[10px] h-8 px-3"
              data-testid="refresh-btn"
            >
              <RefreshCw className={`w-3 h-3 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
            </Button>
            <Button
              onClick={handleExport}
              disabled={filteredTrades.length === 0}
              className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-mono uppercase text-[10px] h-8 px-3"
              data-testid="export-btn"
            >
              <Download className="w-3 h-3 mr-1.5" /> Export CSV
            </Button>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-8 gap-3 mb-6">
          <div className="bg-[#0A0A0A] border border-white/5 p-3 rounded-sm" data-testid="stat-total">
            <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Total Trades</p>
            <p className="text-xl font-bold font-mono text-zinc-200">{summary.totalTrades}</p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-3 rounded-sm" data-testid="stat-wins">
            <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Wins</p>
            <p className="text-xl font-bold font-mono text-emerald-400">{summary.winningTrades}</p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-3 rounded-sm" data-testid="stat-losses">
            <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Losses</p>
            <p className="text-xl font-bold font-mono text-red-400">{summary.losingTrades}</p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-3 rounded-sm" data-testid="stat-winrate">
            <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Win Rate</p>
            <p className={`text-xl font-bold font-mono ${summary.winRate >= 50 ? 'text-emerald-400' : 'text-amber-400'}`}>
              {summary.winRate.toFixed(1)}%
            </p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-3 rounded-sm" data-testid="stat-pnl">
            <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Total P&L</p>
            <p className={`text-xl font-bold font-mono ${summary.totalPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {summary.totalPnL >= 0 ? '+' : ''}${summary.totalPnL.toFixed(0)}
            </p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-3 rounded-sm" data-testid="stat-pips">
            <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Total Pips</p>
            <p className={`text-xl font-bold font-mono ${(summary.totalPips || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {(summary.totalPips || 0) >= 0 ? '+' : ''}{(summary.totalPips || 0).toFixed ? (summary.totalPips || 0).toFixed(0) : summary.totalPips || 0}
            </p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-3 rounded-sm" data-testid="stat-avg-win">
            <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Avg Win</p>
            <p className="text-xl font-bold font-mono text-emerald-400">${summary.avgWin.toFixed(0)}</p>
          </div>
          <div className="bg-[#0A0A0A] border border-white/5 p-3 rounded-sm" data-testid="stat-pf">
            <p className="text-[10px] text-zinc-500 font-mono uppercase mb-1">Profit Factor</p>
            <p className={`text-xl font-bold font-mono ${summary.profitFactor >= 1.5 ? 'text-emerald-400' : summary.profitFactor >= 1 ? 'text-amber-400' : 'text-red-400'}`}>
              {summary.profitFactor > 100 ? '99+' : summary.profitFactor.toFixed(2)}
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-[#0A0A0A] border border-white/5 p-4 rounded-sm mb-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  placeholder="Search by bot name..."
                  value={filters.search}
                  onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                  className="bg-black border-white/10 text-white font-mono text-xs h-8 pl-9"
                  data-testid="search-input"
                />
              </div>
            </div>
            <select
              value={filters.symbol}
              onChange={(e) => setFilters(prev => ({ ...prev, symbol: e.target.value }))}
              className="bg-black border border-white/10 text-zinc-300 text-xs h-8 px-3 font-mono rounded-sm"
              data-testid="symbol-filter"
            >
              {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select
              value={filters.direction}
              onChange={(e) => setFilters(prev => ({ ...prev, direction: e.target.value }))}
              className="bg-black border border-white/10 text-zinc-300 text-xs h-8 px-3 font-mono rounded-sm"
              data-testid="direction-filter"
            >
              {DIRECTIONS.map(d => <option key={d} value={d}>{d === 'All' ? 'All Directions' : d.toUpperCase()}</option>)}
            </select>
            <select
              value={filters.result}
              onChange={(e) => setFilters(prev => ({ ...prev, result: e.target.value }))}
              className="bg-black border border-white/10 text-zinc-300 text-xs h-8 px-3 font-mono rounded-sm"
              data-testid="result-filter"
            >
              {RESULTS.map(r => <option key={r} value={r}>{r === 'All' ? 'All Results' : r === 'profit' ? 'Profits Only' : 'Losses Only'}</option>)}
            </select>
            <select
              value={filters.mode}
              onChange={(e) => setFilters(prev => ({ ...prev, mode: e.target.value }))}
              className="bg-black border border-white/10 text-zinc-300 text-xs h-8 px-3 font-mono rounded-sm"
              data-testid="mode-filter"
            >
              {MODES.map(m => <option key={m} value={m}>{m === 'All' ? 'All Modes' : m === 'forward_test' ? 'Forward Test' : m.charAt(0).toUpperCase() + m.slice(1)}</option>)}
            </select>
            {filters.botId && (
              <Button
                onClick={() => setFilters(prev => ({ ...prev, botId: '' }))}
                variant="outline"
                className="border-zinc-700 text-zinc-400 font-mono text-[10px] h-8"
              >
                Clear Bot Filter
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Trade Table */}
      <div className="max-w-7xl mx-auto">
        <div className="bg-[#0A0A0A] border border-white/5 rounded-sm overflow-hidden">
          {loading ? (
            <div className="p-8 text-center">
              <RefreshCw className="w-8 h-8 text-zinc-600 mx-auto mb-3 animate-spin" />
              <p className="text-sm text-zinc-500 font-mono">Loading trades...</p>
            </div>
          ) : (
            <>
              <table className="w-full" data-testid="trades-table">
                <thead>
                  <tr className="bg-[#18181B] border-b border-white/5">
                    <th className="text-left px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">Bot</th>
                    <th className="text-left px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">Symbol</th>
                    <th className="text-left px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">Direction</th>
                    <th className="text-left px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">Mode</th>
                    <th className="text-left px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">Entry</th>
                    <th className="text-left px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">Exit</th>
                    <th className="text-left px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">Lot</th>
                    <th className="text-right px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">P/L</th>
                    <th className="text-right px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">Pips</th>
                    <th className="text-left px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">Close Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTrades.map((trade, i) => (
                    <tr 
                      key={trade.id} 
                      className={`border-b border-white/5 hover:bg-white/5 ${i % 2 === 0 ? 'bg-black/20' : ''}`}
                      data-testid={`trade-row-${trade.id}`}
                    >
                      <td className="px-4 py-3">
                        <p className="text-xs font-mono text-zinc-300">{trade.botName || 'Unknown'}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-mono text-zinc-400">{trade.symbol}</span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge className={`text-[9px] font-mono uppercase ${
                          trade.direction === 'buy' 
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' 
                            : 'bg-red-500/20 text-red-400 border-red-500/40'
                        }`}>
                          {trade.direction === 'buy' ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
                          {trade.direction}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge className={`text-[9px] font-mono uppercase ${
                          trade.mode === 'live' 
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' 
                            : trade.mode === 'forward_test'
                            ? 'bg-blue-500/20 text-blue-400 border-blue-500/40'
                            : 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40'
                        }`}>
                          {trade.mode === 'forward_test' ? 'FWD' : trade.mode?.toUpperCase() || 'N/A'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-xs font-mono text-zinc-400">{trade.entryPrice}</p>
                        <p className="text-[10px] font-mono text-zinc-600">
                          {trade.entryTime ? formatDateTime(trade.entryTime) : '-'}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-xs font-mono text-zinc-400">{trade.exitPrice || '-'}</p>
                        <p className="text-[10px] font-mono text-zinc-600">
                          {trade.exitTime ? formatDateTime(trade.exitTime) : '-'}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-mono text-zinc-400">{trade.lotSize}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={`text-sm font-bold font-mono ${(trade.profitLoss || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {(trade.profitLoss || 0) >= 0 ? '+' : ''}${(trade.profitLoss || 0).toFixed(2)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={`text-xs font-mono ${(trade.profitLossPips || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {(trade.profitLossPips || 0) >= 0 ? '+' : ''}{(trade.profitLossPips || 0).toFixed(1)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[10px] font-mono text-zinc-500">{trade.closeReason || trade.result || '-'}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredTrades.length === 0 && (
                <div className="p-8 text-center">
                  <p className="text-sm text-zinc-500 font-mono mb-2">No trades found</p>
                  <p className="text-xs text-zinc-600 font-mono">
                    {filters.botId ? 'Try clearing filters or check if the bot has recorded trades' : 'Trades will appear here once bots start executing'}
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
