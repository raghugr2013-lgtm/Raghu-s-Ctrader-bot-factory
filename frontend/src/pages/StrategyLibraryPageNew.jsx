import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  ArrowLeft, RefreshCw, TrendingUp, TrendingDown, Award, 
  Calendar, Code, CheckCircle2, Rocket, Download, Filter,
  SortAsc, SortDesc, Search, ChevronDown
} from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function StrategyLibraryPage() {
  const navigate = useNavigate();
  
  // State
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStrategies, setSelectedStrategies] = useState(new Set());
  const [sortBy, setSortBy] = useState('score'); // score, return, sharpe, date
  const [sortDirection, setSortDirection] = useState('desc');
  const [filterDrawdown, setFilterDrawdown] = useState(100); // max drawdown %
  const [filterSource, setFilterSource] = useState('all'); // all, ai_generation, analyzer, discovery
  const [searchQuery, setSearchQuery] = useState('');
  const [deployedStrategy, setDeployedStrategy] = useState(null);
  const [deploying, setDeploying] = useState(false);

  // Fetch strategies from library
  const fetchLibrary = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/pipeline/library?sort_by=${sortBy}&limit=100`);
      setStrategies(response.data);
      
      // Fetch deployed strategy
      const deployedResp = await axios.get(`${API}/pipeline/deployed`);
      if (deployedResp.data) {
        setDeployedStrategy(deployedResp.data);
      }
    } catch (error) {
      console.error('Failed to fetch library:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLibrary();
  }, [sortBy]);

  // Filtered and sorted strategies
  const filteredStrategies = useMemo(() => {
    let result = [...strategies];

    // Filter by drawdown
    result = result.filter(s => s.max_drawdown <= filterDrawdown);

    // Filter by source
    if (filterSource !== 'all') {
      result = result.filter(s => s.entry_point === filterSource);
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(s => 
        s.name.toLowerCase().includes(query) ||
        s.description.toLowerCase().includes(query)
      );
    }

    // Sort
    result.sort((a, b) => {
      let aVal, bVal;
      
      switch(sortBy) {
        case 'score':
          aVal = a.overall_score;
          bVal = b.overall_score;
          break;
        case 'return':
          aVal = a.total_return;
          bVal = b.total_return;
          break;
        case 'sharpe':
          aVal = a.sharpe_ratio;
          bVal = b.sharpe_ratio;
          break;
        case 'date':
          aVal = new Date(a.created_at).getTime();
          bVal = new Date(b.created_at).getTime();
          break;
        default:
          aVal = a.overall_score;
          bVal = b.overall_score;
      }

      return sortDirection === 'desc' ? bVal - aVal : aVal - bVal;
    });

    return result;
  }, [strategies, filterDrawdown, filterSource, searchQuery, sortBy, sortDirection]);

  // Selection handlers
  const toggleSelection = (strategyId) => {
    const newSelection = new Set(selectedStrategies);
    if (newSelection.has(strategyId)) {
      newSelection.delete(strategyId);
    } else {
      newSelection.add(strategyId);
    }
    setSelectedStrategies(newSelection);
  };

  const selectAll = () => {
    if (selectedStrategies.size === filteredStrategies.length) {
      setSelectedStrategies(new Set());
    } else {
      setSelectedStrategies(new Set(filteredStrategies.map(s => s.id)));
    }
  };

  // Deploy selected strategy
  const deploySelected = async () => {
    if (selectedStrategies.size !== 1) {
      alert('Please select exactly ONE strategy to deploy');
      return;
    }

    const strategyId = Array.from(selectedStrategies)[0];
    
    try {
      setDeploying(true);
      await axios.post(`${API}/pipeline/deploy/${strategyId}`);
      alert('Strategy deployed successfully!');
      
      // Refresh
      await fetchLibrary();
      setSelectedStrategies(new Set());
    } catch (error) {
      alert(`Deployment failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setDeploying(false);
    }
  };

  // Get entry point badge
  const getEntryBadge = (entryPoint) => {
    const badges = {
      ai_generation: { label: 'AI', color: 'bg-blue-500/20 text-blue-400 border-blue-500/40' },
      analyzer: { label: 'Analyzer', color: 'bg-purple-500/20 text-purple-400 border-purple-500/40' },
      discovery: { label: 'Discovery', color: 'bg-green-500/20 text-green-400 border-green-500/40' }
    };
    const badge = badges[entryPoint] || badges.ai_generation;
    return <Badge className={`text-[9px] px-1.5 py-0 font-mono ${badge.color}`}>{badge.label}</Badge>;
  };

  // Get score color
  const getScoreColor = (score) => {
    if (score >= 90) return 'text-emerald-400';
    if (score >= 80) return 'text-green-400';
    if (score >= 70) return 'text-yellow-400';
    if (score >= 60) return 'text-orange-400';
    return 'text-red-400';
  };

  return (
    <div className="min-h-screen bg-[#050505] p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/')} 
              className="text-zinc-500 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-extrabold uppercase tracking-tight text-white" style={{ fontFamily: 'Barlow Condensed, sans-serif' }}>
                STRATEGY LIBRARY
              </h1>
              <p className="text-xs text-zinc-500 uppercase tracking-widest mt-0.5 font-mono">
                Validated & Tested Strategies
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              onClick={fetchLibrary}
              disabled={loading}
              className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-mono uppercase text-[10px] h-8 px-3"
            >
              <RefreshCw className={`w-3 h-3 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Deployed Strategy Banner */}
        {deployedStrategy && (
          <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-sm p-3 mb-4">
            <div className="flex items-center gap-2">
              <Rocket className="w-4 h-4 text-emerald-400" />
              <span className="text-sm font-mono text-emerald-400">
                Currently Deployed: <strong>{deployedStrategy.name}</strong>
              </span>
              <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/40 text-[9px]">
                Score: {deployedStrategy.overall_score}
              </Badge>
            </div>
          </div>
        )}

        {/* Filters & Search */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-sm p-4 mb-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 w-3.5 h-3.5 text-zinc-500" />
              <input
                type="text"
                placeholder="Search strategies..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#18181B] border border-white/5 rounded pl-8 pr-3 py-2 text-xs text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-blue-500/50"
              />
            </div>

            {/* Sort By */}
            <div>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full bg-[#18181B] border border-white/5 rounded px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-blue-500/50"
              >
                <option value="score">Sort by Score</option>
                <option value="return">Sort by Return</option>
                <option value="sharpe">Sort by Sharpe</option>
                <option value="date">Sort by Date</option>
              </select>
            </div>

            {/* Max Drawdown Filter */}
            <div>
              <select
                value={filterDrawdown}
                onChange={(e) => setFilterDrawdown(Number(e.target.value))}
                className="w-full bg-[#18181B] border border-white/5 rounded px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-blue-500/50"
              >
                <option value="100">All Drawdowns</option>
                <option value="10">Max DD &lt; 10%</option>
                <option value="15">Max DD &lt; 15%</option>
                <option value="20">Max DD &lt; 20%</option>
              </select>
            </div>

            {/* Source Filter */}
            <div>
              <select
                value={filterSource}
                onChange={(e) => setFilterSource(e.target.value)}
                className="w-full bg-[#18181B] border border-white/5 rounded px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-blue-500/50"
              >
                <option value="all">All Sources</option>
                <option value="ai_generation">AI Generated</option>
                <option value="analyzer">Analyzed</option>
                <option value="discovery">Discovered</option>
              </select>
            </div>
          </div>

          {/* Results Count */}
          <div className="mt-3 flex items-center justify-between">
            <span className="text-xs text-zinc-500 font-mono">
              {filteredStrategies.length} strategies found
            </span>
            
            {selectedStrategies.size > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-zinc-400 font-mono">
                  {selectedStrategies.size} selected
                </span>
                <Button
                  onClick={deploySelected}
                  disabled={deploying || selectedStrategies.size !== 1}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono uppercase text-[10px] h-7 px-3"
                >
                  <Rocket className="w-3 h-3 mr-1" />
                  Deploy Selected
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Strategy Table */}
        <div className="bg-[#0A0A0A] border border-white/5 rounded-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <RefreshCw className="w-8 h-8 text-zinc-600 animate-spin" />
            </div>
          ) : filteredStrategies.length === 0 ? (
            <div className="text-center py-20">
              <Code className="w-12 h-12 text-zinc-700 mx-auto mb-3" />
              <p className="text-zinc-500 font-mono text-sm">No strategies found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead className="bg-[#18181B] border-b border-white/5">
                  <tr>
                    <th className="px-3 py-2 text-left">
                      <input
                        type="checkbox"
                        checked={selectedStrategies.size === filteredStrategies.length}
                        onChange={selectAll}
                        className="rounded bg-zinc-800 border-zinc-700"
                      />
                    </th>
                    <th className="px-3 py-2 text-left text-zinc-500 uppercase">Rank</th>
                    <th className="px-3 py-2 text-left text-zinc-500 uppercase">Name</th>
                    <th className="px-3 py-2 text-left text-zinc-500 uppercase">Source</th>
                    <th className="px-3 py-2 text-right text-zinc-500 uppercase">Score</th>
                    <th className="px-3 py-2 text-right text-zinc-500 uppercase">Return</th>
                    <th className="px-3 py-2 text-right text-zinc-500 uppercase">Sharpe</th>
                    <th className="px-3 py-2 text-right text-zinc-500 uppercase">Drawdown</th>
                    <th className="px-3 py-2 text-right text-zinc-500 uppercase">Win Rate</th>
                    <th className="px-3 py-2 text-right text-zinc-500 uppercase">Date</th>
                    <th className="px-3 py-2 text-center text-zinc-500 uppercase">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStrategies.map((strategy, idx) => (
                    <tr 
                      key={strategy.id}
                      className="border-b border-white/5 last:border-0 hover:bg-white/5 transition-colors"
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={selectedStrategies.has(strategy.id)}
                          onChange={() => toggleSelection(strategy.id)}
                          className="rounded bg-zinc-800 border-zinc-700"
                        />
                      </td>
                      <td className="px-3 py-2">
                        {strategy.rank === 1 ? (
                          <Award className="w-4 h-4 text-yellow-400" />
                        ) : (
                          <span className="text-zinc-500">#{strategy.rank || idx + 1}</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <div>
                          <div className="text-zinc-200 font-semibold">{strategy.name}</div>
                          {strategy.description && (
                            <div className="text-[10px] text-zinc-500 mt-0.5">{strategy.description}</div>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        {getEntryBadge(strategy.entry_point)}
                      </td>
                      <td className={`px-3 py-2 text-right font-bold ${getScoreColor(strategy.overall_score)}`}>
                        {strategy.overall_score.toFixed(1)}
                      </td>
                      <td className={`px-3 py-2 text-right ${strategy.total_return >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {strategy.total_return >= 0 ? '+' : ''}{strategy.total_return.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 text-right text-zinc-300">
                        {strategy.sharpe_ratio.toFixed(2)}
                      </td>
                      <td className={`px-3 py-2 text-right ${
                        strategy.max_drawdown < 10 ? 'text-emerald-400' :
                        strategy.max_drawdown < 20 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {strategy.max_drawdown.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 text-right text-zinc-300">
                        {strategy.win_rate.toFixed(0)}%
                      </td>
                      <td className="px-3 py-2 text-right text-zinc-500">
                        {new Date(strategy.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {strategy.deployed ? (
                          <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/40 text-[8px]">
                            DEPLOYED
                          </Badge>
                        ) : (
                          <Badge className="bg-zinc-800 text-zinc-500 border-zinc-700 text-[8px]">
                            STORED
                          </Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
