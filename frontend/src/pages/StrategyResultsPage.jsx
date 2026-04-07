import { useState, useEffect } from 'react';
import { ArrowLeft, Download, TrendingUp, TrendingDown, Award, AlertTriangle } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Quality grade calculator
const getQualityGrade = (strategy) => {
  const { profit_factor = 0, sharpe_ratio = 0, max_drawdown_pct = 100, total_trades = 0, win_rate = 0 } = strategy;
  
  let score = 0;
  
  // Profit Factor (0-30 points)
  if (profit_factor >= 2.0) score += 30;
  else if (profit_factor >= 1.5) score += 20;
  else if (profit_factor >= 1.3) score += 15;
  else if (profit_factor >= 1.0) score += 5;
  
  // Sharpe Ratio (0-25 points)
  if (sharpe_ratio >= 2.5) score += 25;
  else if (sharpe_ratio >= 2.0) score += 20;
  else if (sharpe_ratio >= 1.5) score += 15;
  else if (sharpe_ratio >= 1.0) score += 5;
  
  // Max Drawdown (0-25 points)
  if (max_drawdown_pct <= 10) score += 25;
  else if (max_drawdown_pct <= 15) score += 20;
  else if (max_drawdown_pct <= 20) score += 15;
  else if (max_drawdown_pct <= 30) score += 5;
  
  // Total Trades (0-20 points)
  if (total_trades >= 100) score += 20;
  else if (total_trades >= 75) score += 15;
  else if (total_trades >= 50) score += 10;
  else if (total_trades >= 20) score += 5;
  
  // Grade assignment
  if (score >= 75) return { grade: 'A', label: 'Strong', color: 'bg-green-500' };
  if (score >= 55) return { grade: 'B', label: 'Medium', color: 'bg-blue-500' };
  if (score >= 35) return { grade: 'C', label: 'Weak', color: 'bg-yellow-500' };
  return { grade: 'F', label: 'Fail', color: 'bg-red-500' };
};

const StrategyResultsPage = () => {
  const [strategies, setStrategies] = useState([]);
  const [filteredStrategies, setFilteredStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState('fitness');
  const [gradeFilter, setGradeFilter] = useState('all');
  const [runInfo, setRunInfo] = useState(null);

  // Load latest factory run on mount
  useEffect(() => {
    loadLatestRun();
  }, []);

  // Apply filters and sorting
  useEffect(() => {
    let filtered = [...strategies];
    
    // Grade filter
    if (gradeFilter !== 'all') {
      filtered = filtered.filter(s => {
        const { grade } = getQualityGrade(s);
        return grade === gradeFilter;
      });
    }
    
    // Sort
    filtered.sort((a, b) => {
      if (sortBy === 'fitness') return (b.fitness || 0) - (a.fitness || 0);
      if (sortBy === 'profit_factor') return (b.profit_factor || 0) - (a.profit_factor || 0);
      if (sortBy === 'sharpe') return (b.sharpe_ratio || 0) - (a.sharpe_ratio || 0);
      if (sortBy === 'drawdown') return (a.max_drawdown_pct || 100) - (b.max_drawdown_pct || 100);
      return 0;
    });
    
    setFilteredStrategies(filtered);
  }, [strategies, sortBy, gradeFilter]);

  const loadLatestRun = async () => {
    setLoading(true);
    try {
      // For demo, load the test run we created
      const response = await axios.get(`${API}/factory/result/950ad4ff-b935-4b0b-ab94-d56257cd7bde`);
      if (response.data.success && response.data.result) {
        setRunInfo(response.data.result);
        setStrategies(response.data.result.strategies || []);
      }
    } catch (error) {
      console.error('Failed to load strategies:', error);
    } finally {
      setLoading(false);
    }
  };

  const downloadBot = async (strategyId) => {
    try {
      // Placeholder for bot generation
      alert(`Bot generation for strategy ${strategyId} will be implemented with correct API parameters`);
    } catch (error) {
      console.error('Failed to generate bot:', error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white p-8 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">Loading strategies...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-4 mb-4">
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => window.history.back()}
              className="text-gray-400 hover:text-white"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <h1 className="text-3xl font-bold">Strategy Results</h1>
          </div>
          
          {runInfo && (
            <Card className="bg-gray-900 border-gray-800 p-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-gray-400 text-sm">Symbol / Timeframe</p>
                  <p className="text-xl font-semibold">{runInfo.symbol} {runInfo.timeframe}</p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Total Generated</p>
                  <p className="text-xl font-semibold">{runInfo.total_generated}</p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Best Fitness</p>
                  <p className="text-xl font-semibold text-green-400">{runInfo.best_strategy?.fitness || 0}</p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Execution Time</p>
                  <p className="text-xl font-semibold">{runInfo.execution_time_seconds?.toFixed(2)}s</p>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Filters */}
        <div className="mb-6 flex gap-4">
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-48 bg-gray-900 border-gray-800">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="fitness">Fitness Score</SelectItem>
              <SelectItem value="profit_factor">Profit Factor</SelectItem>
              <SelectItem value="sharpe">Sharpe Ratio</SelectItem>
              <SelectItem value="drawdown">Drawdown (Low)</SelectItem>
            </SelectContent>
          </Select>

          <Select value={gradeFilter} onValueChange={setGradeFilter}>
            <SelectTrigger className="w-48 bg-gray-900 border-gray-800">
              <SelectValue placeholder="Filter by grade" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Grades</SelectItem>
              <SelectItem value="A">A - Strong</SelectItem>
              <SelectItem value="B">B - Medium</SelectItem>
              <SelectItem value="C">C - Weak</SelectItem>
            </SelectContent>
          </Select>

          <div className="ml-auto">
            <Badge variant="outline" className="text-gray-400">
              {filteredStrategies.length} strategies
            </Badge>
          </div>
        </div>

        {/* Strategies Table */}
        <Card className="bg-gray-900 border-gray-800">
          <Table>
            <TableHeader>
              <TableRow className="border-gray-800 hover:bg-gray-800/50">
                <TableHead className="text-gray-400">Grade</TableHead>
                <TableHead className="text-gray-400">Template</TableHead>
                <TableHead className="text-gray-400">Fitness</TableHead>
                <TableHead className="text-gray-400">Profit Factor</TableHead>
                <TableHead className="text-gray-400">Sharpe</TableHead>
                <TableHead className="text-gray-400">Drawdown</TableHead>
                <TableHead className="text-gray-400">Win Rate</TableHead>
                <TableHead className="text-gray-400">Trades</TableHead>
                <TableHead className="text-gray-400">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredStrategies.map((strategy) => {
                const { grade, label, color } = getQualityGrade(strategy);
                const isSelected = selectedStrategy?.id === strategy.id;
                
                return (
                  <TableRow 
                    key={strategy.id}
                    className={`border-gray-800 cursor-pointer hover:bg-gray-800/50 ${isSelected ? 'bg-gray-800' : ''}`}
                    onClick={() => setSelectedStrategy(strategy)}
                  >
                    <TableCell>
                      <Badge className={`${color} text-white`}>
                        {grade}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium">
                      {strategy.template_id?.replace(/_/g, ' ').toUpperCase() || 'Unknown'}
                    </TableCell>
                    <TableCell>
                      <span className="text-blue-400">{strategy.fitness?.toFixed(0) || 0}</span>
                    </TableCell>
                    <TableCell>
                      <span className={strategy.profit_factor >= 1.3 ? 'text-green-400' : 'text-red-400'}>
                        {strategy.profit_factor?.toFixed(2) || '0.00'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={strategy.sharpe_ratio >= 1.5 ? 'text-green-400' : 'text-yellow-400'}>
                        {strategy.sharpe_ratio?.toFixed(2) || '0.00'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={strategy.max_drawdown_pct <= 20 ? 'text-green-400' : 'text-red-400'}>
                        {strategy.max_drawdown_pct?.toFixed(1) || '0.0'}%
                      </span>
                    </TableCell>
                    <TableCell>
                      {strategy.win_rate?.toFixed(1) || '0.0'}%
                    </TableCell>
                    <TableCell>
                      <span className={strategy.total_trades >= 50 ? 'text-green-400' : 'text-yellow-400'}>
                        {strategy.total_trades || 0}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-blue-600 text-blue-400 hover:bg-blue-600/10"
                        onClick={(e) => {
                          e.stopPropagation();
                          downloadBot(strategy.id);
                        }}
                      >
                        <Download className="w-3 h-3 mr-1" />
                        Bot
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>

        {/* Strategy Detail Panel */}
        {selectedStrategy && (
          <Card className="mt-6 bg-gray-900 border-gray-800 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold">Strategy Details</h3>
              <Badge className={getQualityGrade(selectedStrategy).color + ' text-white text-lg px-3 py-1'}>
                Grade {getQualityGrade(selectedStrategy).grade}
              </Badge>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <p className="text-gray-400 text-sm mb-1">Template</p>
                <p className="text-lg font-semibold">{selectedStrategy.template_id?.replace(/_/g, ' ')}</p>
              </div>
              <div>
                <p className="text-gray-400 text-sm mb-1">Fitness Score</p>
                <p className="text-lg font-semibold text-blue-400">{selectedStrategy.fitness?.toFixed(0)}</p>
              </div>
              <div>
                <p className="text-gray-400 text-sm mb-1">Net Profit</p>
                <p className={`text-lg font-semibold ${selectedStrategy.net_profit > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  ${selectedStrategy.net_profit?.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-gray-400 text-sm mb-1">Monte Carlo Score</p>
                <p className="text-lg font-semibold text-purple-400">{selectedStrategy.monte_carlo_score}/100</p>
              </div>
            </div>

            <div className="mt-6 p-4 bg-gray-800 rounded-lg">
              <h4 className="text-sm font-semibold mb-3 text-gray-300">Parameters</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                {Object.entries(selectedStrategy.genes || {}).map(([key, value]) => (
                  <div key={key}>
                    <span className="text-gray-400">{key.replace(/_/g, ' ')}: </span>
                    <span className="text-white">{typeof value === 'number' ? value.toFixed(2) : value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Warnings for overfitting */}
            {(selectedStrategy.win_rate > 90 || selectedStrategy.max_drawdown_pct === 0 || selectedStrategy.total_trades < 50) && (
              <div className="mt-4 p-4 bg-yellow-900/20 border border-yellow-600/50 rounded-lg flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-yellow-400 mb-1">Overfitting Warning</p>
                  <ul className="text-sm text-gray-300 space-y-1">
                    {selectedStrategy.win_rate > 90 && <li>• Win rate over 90% - likely overfitted</li>}
                    {selectedStrategy.max_drawdown_pct === 0 && <li>• Zero drawdown - unrealistic</li>}
                    {selectedStrategy.total_trades < 50 && <li>• Less than 50 trades - insufficient data</li>}
                  </ul>
                  <p className="text-sm text-yellow-400 mt-2">⚠️ Not recommended for live trading</p>
                </div>
              </div>
            )}
          </Card>
        )}

        {filteredStrategies.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p>No strategies match the current filters</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default StrategyResultsPage;
