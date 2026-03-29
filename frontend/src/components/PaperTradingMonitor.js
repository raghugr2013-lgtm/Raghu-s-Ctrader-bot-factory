import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Activity, TrendingUp, AlertCircle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function PaperTradingMonitor() {
  const [status, setStatus] = useState(null);
  const [trades, setTrades] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch paper trading status
  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/paper-trading/status`);
      setStatus(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch status');
      console.error('Status fetch error:', err);
    }
  };

  // Fetch trade history
  const fetchTrades = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/paper-trading/trades`);
      setTrades(response.data);
    } catch (err) {
      console.error('Trades fetch error:', err);
    }
  };

  // Initial fetch and polling
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchStatus(), fetchTrades()]);
      setLoading(false);
    };

    loadData();

    // Poll every 10 seconds
    const interval = setInterval(() => {
      fetchStatus();
      fetchTrades();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading paper trading data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="w-5 h-5 text-red-600" />
          <span className="font-semibold text-red-900">Error</span>
        </div>
        <p className="text-sm text-red-700">{error}</p>
        <button
          onClick={() => {
            setError(null);
            fetchStatus();
            fetchTrades();
          }}
          className="mt-3 text-sm text-red-600 hover:text-red-800 underline"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Status Indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-lg ${status?.running ? 'bg-green-100' : 'bg-gray-100'}`}>
            <Activity className={`w-6 h-6 ${status?.running ? 'text-green-600' : 'text-gray-600'}`} />
          </div>
          <div>
            <h3 className="text-xl font-bold text-gray-900">Paper Trading Monitor</h3>
            <p className="text-sm text-gray-600">
              {status?.running ? (
                <span className="text-green-600 font-medium">● Live Trading</span>
              ) : (
                <span className="text-gray-500">● System Stopped</span>
              )}
            </p>
          </div>
        </div>
        <div className="text-xs text-gray-500">
          Updates every 10s
        </div>
      </div>

      {/* A. Live Performance Metrics */}
      <div className="bg-white rounded-lg shadow p-6">
        <h4 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4" />
          Live Performance
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {/* Current Equity */}
          <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 mb-1">Current Equity</div>
            <div className="text-2xl font-bold text-gray-900">
              ${status?.total_equity?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Initial: ${status?.portfolio_details?.initial_capital?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
            </div>
          </div>

          {/* Total PnL */}
          <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 mb-1">Total PnL</div>
            <div className={`text-2xl font-bold ${status?.current_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {status?.current_pnl >= 0 ? '+' : ''}${status?.current_pnl?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
            </div>
            <div className={`text-xs mt-1 ${status?.total_return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {status?.total_return_pct >= 0 ? '+' : ''}{status?.total_return_pct?.toFixed(2) || '0.00'}%
            </div>
          </div>

          {/* Drawdown */}
          <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 mb-1">Drawdown</div>
            <div className={`text-2xl font-bold ${status?.drawdown_pct > 10 ? 'text-red-600' : 'text-gray-900'}`}>
              {status?.drawdown_pct?.toFixed(2) || '0.00'}%
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Max: 15%
            </div>
          </div>

          {/* Total Trades */}
          <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 mb-1">Total Trades</div>
            <div className="text-2xl font-bold text-gray-900">
              {status?.total_trades || 0}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Open: {status?.portfolio_details?.open_positions || 0}
            </div>
          </div>
        </div>
      </div>

      {/* C. System Status */}
      <div className="bg-white rounded-lg shadow p-6">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">System Status</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Trading Status */}
          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Trading Engine</span>
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                status?.running ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
              }`}>
                {status?.running ? '● Running' : '○ Stopped'}
              </span>
            </div>
            <div className="text-xs text-gray-500">
              {status?.running ? 'Monitoring markets on H1 candles' : 'System inactive'}
            </div>
          </div>

          {/* Risk Controls */}
          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Risk Controls</span>
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                status?.risk_status?.trading_enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}>
                {status?.risk_status?.trading_enabled ? '✓ Active' : '✗ Triggered'}
              </span>
            </div>
            {status?.risk_status?.stop_reason ? (
              <div className="text-xs text-red-600 font-medium">
                {status.risk_status.stop_reason}
              </div>
            ) : (
              <div className="text-xs text-gray-500">
                DD Margin: {status?.risk_status?.drawdown_margin_pct?.toFixed(1)}% | 
                Daily Loss Margin: {status?.risk_status?.daily_loss_margin_pct?.toFixed(1)}%
              </div>
            )}
          </div>
        </div>

        {/* Open Positions */}
        {status?.portfolio_details?.open_positions > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h5 className="text-xs font-semibold text-gray-700 mb-2">Open Positions</h5>
            <div className="space-y-2">
              {Object.entries(status.portfolio_details.positions || {}).map(([symbol, pos]) => (
                <div key={symbol} className="bg-gray-50 p-3 rounded border border-gray-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium text-gray-900">{symbol}</span>
                      <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                        pos.signal === 'LONG' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {pos.signal}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium text-gray-900">
                        ${pos.current_price?.toFixed(2)}
                      </div>
                      <div className="text-xs text-gray-500">
                        Entry: ${pos.entry_price?.toFixed(2)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* B. Trade History */}
      <div className="bg-white rounded-lg shadow p-6">
        <h4 className="text-sm font-semibold text-gray-700 mb-4">Trade History (Last 10)</h4>
        
        {trades.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p className="text-sm">No trades executed yet</p>
            <p className="text-xs mt-1">Waiting for EMA crossover signals</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-600">Timestamp</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-600">Symbol</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-600">Signal</th>
                  <th className="text-right py-2 px-3 text-xs font-semibold text-gray-600">Entry</th>
                  <th className="text-right py-2 px-3 text-xs font-semibold text-gray-600">Exit</th>
                  <th className="text-right py-2 px-3 text-xs font-semibold text-gray-600">PnL</th>
                </tr>
              </thead>
              <tbody>
                {trades.slice(0, 10).map((trade, idx) => {
                  const pnl = trade.pnl || 0;
                  const timestamp = new Date(trade.timestamp);
                  
                  return (
                    <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-2 px-3 text-xs text-gray-600">
                        {timestamp.toLocaleDateString()} {timestamp.toLocaleTimeString()}
                      </td>
                      <td className="py-2 px-3 text-xs font-medium text-gray-900">
                        {trade.symbol}
                      </td>
                      <td className="py-2 px-3">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          trade.signal === 'LONG' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {trade.signal}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-xs text-right text-gray-900">
                        ${trade.entry_price?.toFixed(2)}
                      </td>
                      <td className="py-2 px-3 text-xs text-right text-gray-900">
                        ${trade.exit_price?.toFixed(2)}
                      </td>
                      <td className={`py-2 px-3 text-xs text-right font-medium ${
                        pnl >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Info Note */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-xs text-blue-700">
        <p>
          <strong>Note:</strong> Paper trading engine checks markets every hour on H1 candle close. 
          Signals are generated using EMA 10/150 crossover strategy. Risk controls automatically stop trading 
          if drawdown exceeds 15% or daily loss exceeds 2%.
        </p>
      </div>
    </div>
  );
}

export default PaperTradingMonitor;
