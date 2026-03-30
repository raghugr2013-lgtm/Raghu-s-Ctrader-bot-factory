import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import {
  Loader2, ArrowLeft, Globe, Github, Star, GitFork,
  CheckCircle2, XCircle, AlertTriangle, Zap, TrendingUp,
  Search, Database, RefreshCw, ExternalLink, Sparkles,
  ArrowRight, BarChart3, Shield, Target
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function StatusBadge({ status }) {
  if (status === 'approved') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        <CheckCircle2 className="w-3 h-3" />
        Approved
      </span>
    );
  }
  if (status === 'rejected') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-red-500/10 text-red-400 border border-red-500/20">
        <XCircle className="w-3 h-3" />
        Rejected
      </span>
    );
  }
  if (status === 'conditional') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
        <AlertTriangle className="w-3 h-3" />
        Conditional
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-zinc-500/10 text-zinc-400 border border-zinc-500/20">
      {status}
    </span>
  );
}

function GradeBadge({ grade }) {
  const styles = {
    'A+': 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white shadow-lg shadow-emerald-500/25',
    'A': 'bg-gradient-to-r from-emerald-500/80 to-teal-500/80 text-white',
    'B': 'bg-gradient-to-r from-cyan-500/80 to-blue-500/80 text-white',
    'C': 'bg-gradient-to-r from-amber-500/80 to-orange-500/80 text-white',
    'D': 'bg-gradient-to-r from-orange-500/80 to-red-500/80 text-white',
    'F': 'bg-gradient-to-r from-red-500/80 to-rose-500/80 text-white',
  };
  return (
    <span className={`inline-flex items-center justify-center w-10 h-10 rounded-xl text-sm font-bold ${styles[grade] || styles['C']}`}>
      {grade}
    </span>
  );
}

function StatCard({ value, label, icon: Icon, color = 'cyan', delay = 0 }) {
  const colors = {
    cyan: 'from-cyan-500/20 to-cyan-500/5 border-cyan-500/20 text-cyan-400',
    emerald: 'from-emerald-500/20 to-emerald-500/5 border-emerald-500/20 text-emerald-400',
    red: 'from-red-500/20 to-red-500/5 border-red-500/20 text-red-400',
    amber: 'from-amber-500/20 to-amber-500/5 border-amber-500/20 text-amber-400',
  };
  
  return (
    <div 
      className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${colors[color]} border p-6 transition-all duration-300 hover:scale-[1.02]`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-4xl font-bold text-white mb-1">{value}</p>
          <p className="text-sm text-zinc-400 uppercase tracking-wider">{label}</p>
        </div>
        <Icon className={`w-8 h-8 opacity-50`} />
      </div>
    </div>
  );
}

function StrategyCard({ strategy }) {
  const score = strategy.score || {};
  const source = strategy.source || {};
  
  return (
    <div className="group relative bg-[#111827] border border-[#1F2937] rounded-2xl p-5 transition-all duration-300 hover:border-cyan-500/40 hover:-translate-y-1 hover:shadow-xl hover:shadow-cyan-500/5">
      {/* Gradient overlay on hover */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-cyan-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      
      <div className="relative">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-white truncate mb-1">
              {strategy.strategy_name || 'Unknown Strategy'}
            </h3>
            <p className="text-xs text-zinc-500 font-mono truncate">{source.repo_full_name || 'N/A'}</p>
          </div>
          <GradeBadge grade={score.grade || 'N/A'} />
        </div>
        
        {/* Score highlight */}
        <div className="flex items-center gap-3 mb-4 pb-4 border-b border-[#1F2937]">
          <div className="flex-1">
            <p className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
              {score.total_score?.toFixed(1) || 'N/A'}
            </p>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Total Score</p>
          </div>
          <StatusBadge status={score.status || strategy.status} />
        </div>
        
        {/* Metrics grid */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="text-center p-2 rounded-xl bg-[#0B0F14]">
            <p className={`text-lg font-bold ${score.max_drawdown < 6 ? 'text-emerald-400' : 'text-red-400'}`}>
              {score.max_drawdown?.toFixed(1) || 'N/A'}%
            </p>
            <p className="text-[9px] text-zinc-500 uppercase">Max DD</p>
          </div>
          <div className="text-center p-2 rounded-xl bg-[#0B0F14]">
            <p className={`text-lg font-bold ${score.risk_of_ruin < 5 ? 'text-emerald-400' : 'text-red-400'}`}>
              {score.risk_of_ruin?.toFixed(2) || 'N/A'}%
            </p>
            <p className="text-[9px] text-zinc-500 uppercase">Risk of Ruin</p>
          </div>
          <div className="text-center p-2 rounded-xl bg-[#0B0F14]">
            <p className="text-lg font-bold text-cyan-400">{score.prop_score?.toFixed(0) || 'N/A'}</p>
            <p className="text-[9px] text-zinc-500 uppercase">Prop Score</p>
          </div>
        </div>
        
        {/* Footer */}
        {source.stars !== undefined && (
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-1.5 text-zinc-500">
              <Star className="w-3.5 h-3.5 text-amber-400" />
              {source.stars} stars
            </span>
            {source.source_url && (
              <a 
                href={source.source_url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                <ExternalLink className="w-3 h-3" />
                Source
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function DiscoveryPage() {
  const navigate = useNavigate();
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [maxRepos, setMaxRepos] = useState(10);
  const [maxBotsPerRepo, setMaxBotsPerRepo] = useState(3);
  const [minStars, setMinStars] = useState(10);
  const [result, setResult] = useState(null);
  const [discoveryStatus, setDiscoveryStatus] = useState('');

  const pollJobStatus = async (jobId) => {
    const maxAttempts = 120; // Poll for up to 10 minutes (120 * 5 seconds)
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        const statusResponse = await axios.get(`${API}/discovery/status/${jobId}`);
        const jobData = statusResponse.data;

        // Update status message
        setDiscoveryStatus(jobData.message || 'Processing...');

        if (jobData.status === 'completed') {
          setResult({
            success: true,
            message: jobData.message,
            total_fetched: jobData.total_fetched,
            total_approved: jobData.total_approved,
            total_rejected: jobData.total_rejected,
            total_errors: jobData.total_errors,
            approved_strategies: jobData.approved_strategies,
            errors: jobData.errors,
            duration_seconds: jobData.duration_seconds
          });
          
          if (jobData.total_approved > 0) {
            toast.success(`Discovery complete! ${jobData.total_approved} strategies approved.`);
          } else {
            toast.info('Discovery complete. No strategies met approval criteria.');
          }
          return;
        } else if (jobData.status === 'failed') {
          toast.error(`Discovery failed: ${jobData.error || 'Unknown error'}`);
          setIsDiscovering(false);
          setDiscoveryStatus('');
          return;
        }

        // Still running or pending, wait and poll again
        await new Promise(resolve => setTimeout(resolve, 5000)); // Poll every 5 seconds
        attempts++;
      } catch (error) {
        console.error('Polling error:', error);
        await new Promise(resolve => setTimeout(resolve, 5000));
        attempts++;
      }
    }

    // Timeout
    toast.error('Discovery timed out. Please try again with fewer repositories.');
    setIsDiscovering(false);
    setDiscoveryStatus('');
  };

  const handleDiscover = async () => {
    setIsDiscovering(true);
    setResult(null);
    setDiscoveryStatus('Starting discovery...');

    try {
      // Start discovery job
      const response = await axios.post(`${API}/discovery/discover-bots`, {
        max_repos: maxRepos,
        max_bots_per_repo: maxBotsPerRepo,
        min_stars: minStars,
        generate_bots: true,
        save_to_db: true
      });
      
      const { job_id } = response.data;
      
      if (job_id) {
        toast.info('Discovery job started. Fetching results...');
        // Start polling for status
        await pollJobStatus(job_id);
      } else {
        toast.error('Failed to start discovery job');
      }
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      toast.error(`Discovery failed: ${detail}`);
    } finally {
      setIsDiscovering(false);
      setDiscoveryStatus('');
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0F14]" data-testid="discovery-page">
      {/* Header */}
      <div className="sticky top-0 z-50 backdrop-blur-xl bg-[#0B0F14]/80 border-b border-[#1F2937]">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/')}
              className="text-zinc-400 hover:text-white hover:bg-white/5"
              data-testid="back-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Dashboard
            </Button>
            <div className="h-6 w-px bg-[#1F2937]" />
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                <Globe className="w-4 h-4 text-white" />
              </div>
              <span className="text-lg font-semibold text-white">Discovery</span>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/library')}
            className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
          >
            <Database className="w-4 h-4 mr-2" />
            View Library
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Hero Section */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#111827] to-[#0B0F14] border border-[#1F2937] p-8 mb-8">
          {/* Background decoration */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-violet-500/10 to-transparent rounded-full blur-3xl" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-gradient-to-tr from-cyan-500/10 to-transparent rounded-full blur-3xl" />
          
          <div className="relative">
            <div className="flex items-start justify-between">
              <div className="max-w-2xl">
                <div className="flex items-center gap-3 mb-4">
                  <Sparkles className="w-5 h-5 text-violet-400" />
                  <span className="text-sm font-medium text-violet-400 uppercase tracking-wider">Bot Discovery Engine</span>
                </div>
                <h1 className="text-4xl font-bold text-white mb-3">
                  Find High-Quality Trading Bots
                </h1>
                <p className="text-lg text-zinc-400 mb-6">
                  Search GitHub for cTrader/cAlgo bots, analyze them automatically, and store only the best strategies.
                </p>
                
                {/* Search controls */}
                <div className="flex items-end gap-4 flex-wrap">
                  <div className="space-y-2">
                    <label className="text-xs text-zinc-500 uppercase tracking-wider">Max Repos</label>
                    <Input
                      type="number"
                      value={maxRepos}
                      onChange={(e) => setMaxRepos(Math.min(50, Math.max(1, parseInt(e.target.value) || 1)))}
                      min={1}
                      max={50}
                      className="w-24 bg-[#0B0F14] border-[#1F2937] text-white focus:border-cyan-500 focus:ring-cyan-500/20"
                      data-testid="max-repos-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs text-zinc-500 uppercase tracking-wider">Bots/Repo</label>
                    <Input
                      type="number"
                      value={maxBotsPerRepo}
                      onChange={(e) => setMaxBotsPerRepo(Math.min(10, Math.max(1, parseInt(e.target.value) || 1)))}
                      min={1}
                      max={10}
                      className="w-24 bg-[#0B0F14] border-[#1F2937] text-white focus:border-cyan-500 focus:ring-cyan-500/20"
                      data-testid="bots-per-repo-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs text-zinc-500 uppercase tracking-wider">Min Stars</label>
                    <Input
                      type="number"
                      value={minStars}
                      onChange={(e) => setMinStars(Math.max(0, parseInt(e.target.value) || 0))}
                      min={0}
                      className="w-24 bg-[#0B0F14] border-[#1F2937] text-white focus:border-cyan-500 focus:ring-cyan-500/20"
                      data-testid="min-stars-input"
                    />
                  </div>
                  <Button
                    onClick={handleDiscover}
                    disabled={isDiscovering}
                    className="h-10 px-6 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-semibold shadow-lg shadow-violet-500/25 transition-all duration-300 hover:shadow-violet-500/40 hover:scale-[1.02]"
                    data-testid="discover-btn"
                  >
                    {isDiscovering ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Discovering...
                      </>
                    ) : (
                      <>
                        <Search className="w-4 h-4 mr-2" />
                        Fetch Bots from GitHub
                      </>
                    )}
                  </Button>
                </div>
                
                {/* Status message during discovery */}
                {isDiscovering && discoveryStatus && (
                  <div className="mt-4 flex items-center gap-3 px-4 py-3 rounded-lg bg-violet-500/10 border border-violet-500/20">
                    <Loader2 className="w-4 h-4 text-violet-400 animate-spin flex-shrink-0" />
                    <p className="text-sm text-violet-300">{discoveryStatus}</p>
                  </div>
                )}
              </div>
              
              {/* GitHub icon decoration */}
              <div className="hidden lg:flex items-center justify-center w-32 h-32 rounded-3xl bg-gradient-to-br from-zinc-800 to-zinc-900 border border-[#1F2937]">
                <Github className="w-16 h-16 text-zinc-600" />
              </div>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {isDiscovering && (
          <div className="relative overflow-hidden rounded-2xl bg-[#111827] border border-violet-500/30 p-12 text-center mb-8">
            <div className="absolute inset-0 bg-gradient-to-r from-violet-500/5 via-purple-500/5 to-violet-500/5 animate-pulse" />
            <div className="relative">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-violet-500/20 to-purple-500/20 flex items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">Searching GitHub...</h3>
              <p className="text-zinc-400">Analyzing cTrader bots and scoring strategies</p>
              <p className="text-sm text-zinc-500 mt-2">This may take a few minutes</p>
            </div>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-8">
            {/* Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard 
                value={result.total_fetched} 
                label="Fetched" 
                icon={Search}
                color="cyan"
                delay={0}
              />
              <StatCard 
                value={result.total_approved} 
                label="Approved" 
                icon={CheckCircle2}
                color="emerald"
                delay={100}
              />
              <StatCard 
                value={result.total_rejected} 
                label="Rejected" 
                icon={XCircle}
                color="red"
                delay={200}
              />
              <StatCard 
                value={result.total_errors} 
                label="Errors" 
                icon={AlertTriangle}
                color="amber"
                delay={300}
              />
            </div>

            {/* Duration info */}
            <div className="flex items-center justify-center">
              <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#111827] border border-[#1F2937] text-sm text-zinc-400">
                <Zap className="w-4 h-4 text-amber-400" />
                Completed in {result.duration_seconds?.toFixed(1)} seconds
              </span>
            </div>

            {/* Approved Strategies */}
            {result.approved_strategies?.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-emerald-500/5 flex items-center justify-center">
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                      <h2 className="text-xl font-semibold text-white">Approved Strategies</h2>
                      <p className="text-sm text-zinc-500">{result.approved_strategies.length} strategies passed all criteria</p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigate('/library')}
                    className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
                  >
                    View All in Library
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {result.approved_strategies.map((strategy, idx) => (
                    <StrategyCard key={idx} strategy={strategy} />
                  ))}
                </div>
              </div>
            )}

            {/* Errors */}
            {result.errors?.length > 0 && (
              <div className="rounded-2xl bg-red-500/5 border border-red-500/20 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  <h3 className="text-lg font-semibold text-red-400">Errors ({result.errors.length})</h3>
                </div>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {result.errors.slice(0, 10).map((error, idx) => (
                    <p key={idx} className="text-sm text-red-300/80 font-mono bg-red-500/10 rounded-lg px-3 py-2">{error}</p>
                  ))}
                </div>
              </div>
            )}

            {/* No Approved Results */}
            {result.total_approved === 0 && result.total_fetched > 0 && (
              <div className="rounded-2xl bg-[#111827] border border-[#1F2937] p-12 text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-zinc-800 flex items-center justify-center">
                  <XCircle className="w-8 h-8 text-zinc-600" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">No Strategies Approved</h3>
                <p className="text-zinc-400 mb-4">None of the analyzed bots met our quality criteria.</p>
                <p className="text-sm text-zinc-500">Try lowering the minimum stars filter or increasing the search scope.</p>
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {!result && !isDiscovering && (
          <div className="rounded-2xl bg-[#111827] border border-[#1F2937] p-16 text-center">
            <div className="w-20 h-20 mx-auto mb-6 rounded-3xl bg-gradient-to-br from-zinc-800 to-zinc-900 flex items-center justify-center">
              <Globe className="w-10 h-10 text-zinc-600" />
            </div>
            <h3 className="text-2xl font-semibold text-white mb-3">Ready to Discover</h3>
            <p className="text-zinc-400 max-w-md mx-auto">
              Configure search parameters above and click "Fetch Bots from GitHub" to start discovering trading strategies.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
