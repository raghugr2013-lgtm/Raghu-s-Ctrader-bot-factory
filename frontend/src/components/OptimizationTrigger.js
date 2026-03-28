import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Play, StopCircle, Loader, CheckCircle, AlertCircle, TrendingUp } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function OptimizationTrigger() {
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [csvPath, setCsvPath] = useState('/app/trading_system/data/EURUSD_H1.csv');

  // Poll status while running
  useEffect(() => {
    if (!running) return;

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/optimization/status`);
        setStatus(response.data);

        // Check if finished
        if (!response.data.running) {
          setRunning(false);
          clearInterval(interval);
        }
      } catch (err) {
        console.error('Status poll error:', err);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [running]);

  const handleRunOptimization = async () => {
    setError(null);
    setResults(null);
    setRunning(true);
    setStatus({ running: true, elapsed_seconds: 0 });

    try {
      console.log('Starting optimization...');
      console.log('CSV path:', csvPath);

      const response = await axios.post(
        `${BACKEND_URL}/api/optimization/run`,
        {
          csv_path: csvPath,
          strategy: 'trend_following',
          phase: '2A'
        },
        {
          timeout: 310000 // 5 min + 10 sec buffer
        }
      );

      console.log('Optimization complete:', response.data);
      setResults(response.data);
      setRunning(false);
      
    } catch (err) {
      console.error('Optimization error:', err);
      setError(err.response?.data?.detail || err.message);
      setRunning(false);
    }
  };

  const handleCancel = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/optimization/cancel`);
      setRunning(false);
      setStatus(null);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-3 bg-blue-100 rounded-lg">
          <TrendingUp className="w-6 h-6 text-blue-600" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            Phase 2A Optimization
          </h2>
          <p className="text-sm text-gray-600">
            Automated strategy optimization engine
          </p>
        </div>
      </div>

      {/* CSV Path Input */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          CSV Data Path (Backend Server)
        </label>
        <input
          type="text"
          value={csvPath}
          onChange={(e) => setCsvPath(e.target.value)}
          disabled={running}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
          placeholder="/app/trading_system/data/EURUSD_H1.csv"
        />
        <p className="text-xs text-gray-500 mt-1">
          Path to CSV file accessible by backend server
        </p>
      </div>

      {/* Configuration Info */}
      <div className="bg-gray-50 border border-gray-200 rounded-md p-4 mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">
          Configuration:
        </h3>
        <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
          <div>• Strategy: Trend Following</div>
          <div>• Phase: 2A (Validation)</div>
          <div>• Variations: 8 combinations</div>
          <div>• Expected time: 5-10 seconds</div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3 mb-6">
        <button
          onClick={handleRunOptimization}
          disabled={running}
          className={`flex items-center gap-2 px-6 py-3 rounded-md font-medium transition-colors ${
            running
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700 shadow-md hover:shadow-lg'
          }`}
        >
          {running ? (
            <>
              <Loader className="w-5 h-5 animate-spin" />
              Running Optimization...
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              Run Optimization
            </>
          )}
        </button>

        {running && (
          <button
            onClick={handleCancel}
            className="flex items-center gap-2 px-6 py-3 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium"
          >
            <StopCircle className="w-5 h-5" />
            Cancel
          </button>
        )}
      </div>

      {/* Status Display */}
      {running && status && (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-6 animate-pulse">
          <div className="flex items-center gap-2 mb-2">
            <Loader className="w-5 h-5 animate-spin text-blue-600" />
            <span className="font-semibold text-blue-900">
              Optimization in Progress
            </span>
          </div>
          <p className="text-sm text-blue-700">
            Executing Python optimization script...
          </p>
          {status.elapsed_seconds !== null && (
            <p className="text-xs text-blue-600 mt-2">
              Elapsed: {status.elapsed_seconds?.toFixed(1)}s
            </p>
          )}
        </div>
      )}

      {/* Error Display */}
      {error && !running && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <span className="font-semibold text-red-900">Error</span>
          </div>
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={() => setError(null)}
            className="mt-3 text-sm text-red-600 hover:text-red-800 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Success Display */}
      {results && !running && !error && (
        <div className="bg-green-50 border border-green-200 rounded-md p-6">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-6 h-6 text-green-600" />
            <span className="text-lg font-semibold text-green-900">
              Optimization Complete!
            </span>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-white p-3 rounded border border-green-200">
              <div className="text-xs text-gray-600 mb-1">Total Strategies</div>
              <div className="text-2xl font-bold text-green-700">
                {results.total_strategies}
              </div>
            </div>
            
            <div className="bg-white p-3 rounded border border-green-200">
              <div className="text-xs text-gray-600 mb-1">Viable</div>
              <div className="text-2xl font-bold text-green-700">
                {results.viable_strategies}
              </div>
            </div>
            
            <div className="bg-white p-3 rounded border border-green-200">
              <div className="text-xs text-gray-600 mb-1">Best PF</div>
              <div className="text-2xl font-bold text-green-700">
                {results.best_profit_factor?.toFixed(2)}
              </div>
            </div>
            
            <div className="bg-white p-3 rounded border border-green-200">
              <div className="text-xs text-gray-600 mb-1">Time</div>
              <div className="text-2xl font-bold text-green-700">
                {results.execution_time_seconds?.toFixed(1)}s
              </div>
            </div>
          </div>

          {/* Top Strategies */}
          {results.results?.top_strategies && results.results.top_strategies.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">
                Top Strategies:
              </h4>
              <div className="space-y-2">
                {results.results.top_strategies.slice(0, 3).map((strategy, idx) => (
                  <div key={idx} className="bg-white p-3 rounded border border-green-200 text-sm">
                    <div className="flex justify-between items-center">
                      <span className="font-medium text-gray-900">
                        {idx + 1}. {strategy.variation_id}
                      </span>
                      <span className="text-green-700 font-semibold">
                        PF: {strategy.performance.profit_factor?.toFixed(2)}
                      </span>
                    </div>
                    <div className="text-xs text-gray-600 mt-1">
                      Score: {strategy.ranking_score?.toFixed(1)} | 
                      Trades: {strategy.performance.total_trades} | 
                      Return: {strategy.performance.return_pct?.toFixed(2)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-4 pt-4 border-t border-green-200">
            <a
              href="/discovery"
              className="text-sm text-green-700 hover:text-green-900 underline font-medium"
            >
              → View detailed results in Strategy Discovery
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export default OptimizationTrigger;
