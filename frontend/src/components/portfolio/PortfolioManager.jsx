import { useState, useCallback } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Plus, Trash2, Loader2, Briefcase, FolderPlus } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function PortfolioManager({ portfolio, setPortfolio, sessionId, onRefresh }) {
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [balance, setBalance] = useState('100000');
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  // Backtest seeding
  const [seeding, setSeeding] = useState(false);
  const [btName, setBtName] = useState('');
  const [btSymbol, setBtSymbol] = useState('EURUSD');
  const [btType, setBtType] = useState('trend_following');
  const [addingBt, setAddingBt] = useState(false);

  const createPortfolio = useCallback(async () => {
    if (!newName.trim()) { toast.error('Enter a portfolio name'); return; }
    setCreating(true);
    try {
      const res = await axios.post(`${API}/portfolio/create`, {
        session_id: sessionId,
        name: newName.trim(),
        description: newDesc.trim(),
        initial_balance: parseFloat(balance) || 100000,
      });
      toast.success(`Portfolio "${newName}" created`);
      setNewName(''); setNewDesc(''); setShowCreate(false);
      onRefresh(res.data.portfolio_id);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create portfolio');
    } finally { setCreating(false); }
  }, [newName, newDesc, balance, sessionId, onRefresh]);

  const seedAndAdd = useCallback(async () => {
    if (!portfolio || !btName.trim()) { toast.error('Enter a strategy name'); return; }
    setSeeding(true);
    try {
      // 1. Create a mock backtest
      const btRes = await axios.post(`${API}/backtest/simulate`, {
        session_id: sessionId,
        bot_name: btName.trim(),
        symbol: btSymbol,
        timeframe: '1h',
        duration_days: 90,
        initial_balance: 10000,
        strategy_type: btType,
      });
      // 2. Add to portfolio
      setAddingBt(true);
      await axios.post(`${API}/portfolio/${portfolio.id}/add-strategy`, {
        backtest_id: btRes.data.backtest_id,
        name: btName.trim(),
      });
      toast.success(`Strategy "${btName}" added`);
      setBtName('');
      onRefresh(portfolio.id);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to add strategy');
    } finally { setSeeding(false); setAddingBt(false); }
  }, [portfolio, btName, btSymbol, btType, sessionId, onRefresh]);

  const removeStrategy = useCallback(async (strategyId, name) => {
    if (!portfolio) return;
    try {
      await axios.delete(`${API}/portfolio/${portfolio.id}/strategy/${strategyId}`);
      toast.success(`Removed "${name}"`);
      onRefresh(portfolio.id);
    } catch (e) {
      toast.error('Failed to remove strategy');
    }
  }, [portfolio, onRefresh]);

  return (
    <div className="space-y-3" data-testid="portfolio-manager">
      {/* Create Portfolio */}
      {!portfolio ? (
        <div className="space-y-2">
          {!showCreate ? (
            <Button onClick={() => setShowCreate(true)} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-mono uppercase text-xs h-8" data-testid="show-create-btn">
              <FolderPlus className="w-3 h-3 mr-2" /> Create Portfolio
            </Button>
          ) : (
            <div className="space-y-2 bg-[#0F0F10] border border-white/5 p-3">
              <Input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Portfolio name" className="bg-black border-white/10 text-xs text-white h-7 font-mono" data-testid="portfolio-name-input" />
              <Input value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="Description (optional)" className="bg-black border-white/10 text-xs text-white h-7 font-mono" />
              <Input value={balance} onChange={e => setBalance(e.target.value)} placeholder="Initial balance" type="number" className="bg-black border-white/10 text-xs text-white h-7 font-mono" />
              <div className="flex gap-2">
                <Button onClick={createPortfolio} disabled={creating} className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-mono uppercase text-[10px] h-7" data-testid="create-portfolio-btn">
                  {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : 'CREATE'}
                </Button>
                <Button onClick={() => setShowCreate(false)} variant="ghost" className="text-zinc-500 font-mono uppercase text-[10px] h-7">Cancel</Button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Portfolio Info */}
          <div className="bg-[#0F0F10] border border-white/5 p-2">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <Briefcase className="w-3.5 h-3.5 text-blue-400" />
                <span className="text-xs font-bold text-zinc-200 uppercase" data-testid="portfolio-name">{portfolio.name}</span>
              </div>
              <Badge variant="outline" className="text-[9px] border-blue-500/30 text-blue-400 px-1.5 py-0 h-4">
                {portfolio.strategies?.length || 0} strategies
              </Badge>
            </div>
            <p className="text-[10px] text-zinc-500 font-mono">${(portfolio.initial_balance || 100000).toLocaleString()} initial</p>
          </div>

          {/* Strategies List */}
          <div className="space-y-1" data-testid="strategy-list">
            {(portfolio.strategies || []).map((s, i) => (
              <div key={s.strategy_id} className="flex items-center gap-2 bg-[#0F0F10] border border-white/5 px-2 py-1.5" data-testid={`strategy-item-${i}`}>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-mono font-bold text-zinc-300 truncate">{s.name}</p>
                  <div className="flex gap-3 text-[10px] text-zinc-500 font-mono mt-0.5">
                    <span>{s.symbol}</span>
                    <span>W:{s.win_rate?.toFixed(0)}%</span>
                    <span>PF:{s.profit_factor?.toFixed(1)}</span>
                    <span className="text-blue-400">{s.weight_percent?.toFixed(0)}%</span>
                  </div>
                </div>
                <button onClick={() => removeStrategy(s.strategy_id, s.name)} className="text-zinc-600 hover:text-red-400 transition-colors p-1" data-testid={`remove-strategy-${i}`}>
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>

          {/* Add Strategy */}
          <div className="bg-[#0F0F10] border border-white/5 p-2 space-y-1.5">
            <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Add Strategy</p>
            <Input value={btName} onChange={e => setBtName(e.target.value)} placeholder="Strategy name" className="bg-black border-white/10 text-xs text-white h-7 font-mono" data-testid="add-strategy-name" />
            <div className="flex gap-1.5">
              <select value={btSymbol} onChange={e => setBtSymbol(e.target.value)} className="flex-1 bg-black border border-white/10 text-xs text-zinc-300 h-7 px-2 font-mono rounded-sm" data-testid="add-strategy-symbol">
                <option value="EURUSD">EURUSD</option>
                <option value="GBPUSD">GBPUSD</option>
                <option value="USDJPY">USDJPY</option>
                <option value="AUDUSD">AUDUSD</option>
                <option value="XAUUSD">XAUUSD</option>
              </select>
              <select value={btType} onChange={e => setBtType(e.target.value)} className="flex-1 bg-black border border-white/10 text-xs text-zinc-300 h-7 px-2 font-mono rounded-sm" data-testid="add-strategy-type">
                <option value="trend_following">Trend</option>
                <option value="mean_reversion">Mean Rev</option>
                <option value="scalping">Scalp</option>
              </select>
            </div>
            <Button onClick={seedAndAdd} disabled={seeding} className="w-full bg-emerald-700 hover:bg-emerald-600 text-white font-mono uppercase text-[10px] h-7" data-testid="add-strategy-btn">
              {seeding ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Plus className="w-3 h-3 mr-1" />}
              {seeding ? (addingBt ? 'ADDING...' : 'BACKTESTING...') : 'ADD STRATEGY'}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
