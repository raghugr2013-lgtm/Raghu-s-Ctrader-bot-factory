"""
REGIME-ADAPTIVE TRADING SYSTEM

Master orchestrator that:
1. Detects market regime
2. Activates appropriate strategy
3. Combines results

Architecture:
- Trend-following for trending markets
- Mean-reversion for ranging markets
- Sits out when regime is unclear

Philosophy: Adapt to markets, don't fight them
"""

import logging
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

from market_data_models import Candle
from backtest_models import TradeRecord, EquityPoint, BacktestConfig
from market_regime_detector import detect_market_regime, MarketRegime, calculate_regime_statistics
from simple_trend_strategy import run_simple_trend_strategy
from simple_mean_reversion_strategy import run_simple_mean_reversion_strategy

logger = logging.getLogger(__name__)


def run_regime_adaptive_system(
    candles: List[Candle],
    config: BacktestConfig,
    params: Optional[Dict] = None
) -> Tuple[List[TradeRecord], List[EquityPoint], Dict]:
    """
    Regime-Adaptive Trading System
    
    Process:
    1. Detect regime for each candle
    2. Run trend strategy (collects signals for trending regimes)
    3. Run mean-reversion strategy (collects signals for ranging regimes)
    4. Merge and deduplicate trades
    5. Calculate combined equity curve
    
    Returns:
        (trades, equity_curve, statistics)
    """
    
    default_params = {
        # Regime detection
        "regime_lookback": 50,
        "min_regime_confidence": 0.4,  # REDUCED from 0.6 for more trade opportunities
        
        # Strategy selection
        "enable_trend_strategy": True,
        "enable_mean_reversion_strategy": True,
        
        # Global risk management
        "max_total_trades_per_day": 5,  # INCREASED from 3
        "max_concurrent_positions": 1,
        
        # Strategy-specific params can be passed as nested dicts
        "trend_params": {},
        "mean_reversion_params": {},
    }
    
    if params:
        default_params.update(params)
    p = default_params
    
    logger.info(f"="*80)
    logger.info(f"REGIME-ADAPTIVE TRADING SYSTEM")
    logger.info(f"="*80)
    logger.info(f"Strategies enabled:")
    logger.info(f"  - Trend-following: {p['enable_trend_strategy']}")
    logger.info(f"  - Mean-reversion: {p['enable_mean_reversion_strategy']}")
    logger.info(f"Risk limits:")
    logger.info(f"  - Max trades/day: {p['max_total_trades_per_day']}")
    logger.info(f"  - Max concurrent: {p['max_concurrent_positions']}")
    
    # === PHASE 1: DETECT REGIMES ===
    logger.info(f"\n📊 Phase 1: Detecting market regimes...")
    
    regimes = []
    for i in range(len(candles)):
        regime = detect_market_regime(candles, i, p["regime_lookback"])
        regimes.append(regime)
    
    # Calculate regime statistics
    regime_stats = calculate_regime_statistics(candles, p["regime_lookback"])
    
    logger.info(f"\n✅ Regime detection complete")
    logger.info(f"   Total periods analyzed: {regime_stats['total_periods']}")
    logger.info(f"\n   Trend Distribution:")
    logger.info(f"     Strong Uptrend: {regime_stats.get('strong_uptrend_pct', 0):.1f}%")
    logger.info(f"     Uptrend: {regime_stats.get('uptrend_pct', 0):.1f}%")
    logger.info(f"     Ranging: {regime_stats.get('ranging_pct', 0):.1f}%")
    logger.info(f"     Downtrend: {regime_stats.get('downtrend_pct', 0):.1f}%")
    logger.info(f"     Strong Downtrend: {regime_stats.get('strong_downtrend_pct', 0):.1f}%")
    logger.info(f"     Unclear: {regime_stats.get('unclear_pct', 0):.1f}%")
    logger.info(f"\n   Volatility Distribution:")
    logger.info(f"     High: {regime_stats.get('high_vol_pct', 0):.1f}%")
    logger.info(f"     Medium: {regime_stats.get('medium_vol_pct', 0):.1f}%")
    logger.info(f"     Low: {regime_stats.get('low_vol_pct', 0):.1f}%")
    
    # === PHASE 2: RUN INDIVIDUAL STRATEGIES ===
    
    all_trades = []
    strategy_results = {}
    
    # Trend-following strategy
    if p["enable_trend_strategy"]:
        logger.info(f"\n📈 Phase 2a: Running trend-following strategy...")
        trend_trades, trend_equity = run_simple_trend_strategy(
            candles, config, regimes, p["trend_params"]
        )
        strategy_results["trend"] = {
            "trades": trend_trades,
            "equity": trend_equity,
            "count": len(trend_trades)
        }
        all_trades.extend([(t, "trend") for t in trend_trades])
        logger.info(f"   Trend strategy: {len(trend_trades)} trades")
    
    # Mean-reversion strategy
    if p["enable_mean_reversion_strategy"]:
        logger.info(f"\n📉 Phase 2b: Running mean-reversion strategy...")
        mr_trades, mr_equity = run_simple_mean_reversion_strategy(
            candles, config, regimes, p["mean_reversion_params"]
        )
        strategy_results["mean_reversion"] = {
            "trades": mr_trades,
            "equity": mr_equity,
            "count": len(mr_trades)
        }
        all_trades.extend([(t, "mean_reversion") for t in mr_trades])
        logger.info(f"   Mean-reversion strategy: {len(mr_trades)} trades")
    
    # === PHASE 3: MERGE AND DEDUPLICATE ===
    logger.info(f"\n🔀 Phase 3: Merging strategies...")
    
    # Sort all trades by entry time
    all_trades.sort(key=lambda x: x[0].entry_time)
    
    # Apply global risk management (no overlapping trades)
    final_trades = []
    active_position = None
    trades_per_day = defaultdict(int)
    
    for trade, strategy_name in all_trades:
        day_key = trade.entry_time.date()
        
        # Check if we already have an active position
        if active_position is not None:
            # Check if current position has exited
            if trade.entry_time >= active_position.exit_time:
                active_position = None
            else:
                # Skip this trade - already in position
                continue
        
        # Check daily limit
        if trades_per_day[day_key] >= p["max_total_trades_per_day"]:
            continue
        
        # Accept trade
        trade.notes = f"Strategy: {strategy_name}"
        final_trades.append(trade)
        trades_per_day[day_key] += 1
        active_position = trade
    
    logger.info(f"   Total trades (deduplicated): {len(final_trades)}")
    
    # === PHASE 4: CALCULATE COMBINED EQUITY CURVE ===
    logger.info(f"\n💰 Phase 4: Calculating combined equity curve...")
    
    equity_curve = []
    balance = config.initial_balance
    peak_balance = balance
    
    # Sort trades chronologically
    final_trades.sort(key=lambda t: t.exit_time)
    
    trade_idx = 0
    for i, candle in enumerate(candles):
        # Apply completed trades
        while trade_idx < len(final_trades) and final_trades[trade_idx].exit_time <= candle.timestamp:
            balance += final_trades[trade_idx].profit_loss
            trade_idx += 1
        
        # Update peak
        if balance > peak_balance:
            peak_balance = balance
        
        drawdown = peak_balance - balance
        drawdown_pct = (drawdown / peak_balance * 100) if peak_balance > 0 else 0
        
        equity_curve.append(EquityPoint(
            timestamp=candle.timestamp,
            balance=balance,
            equity=balance,  # No unrealized P&L in combined system
            drawdown=drawdown,
            drawdown_percent=drawdown_pct,
        ))
    
    # === PHASE 5: CALCULATE STATISTICS ===
    
    # Trade distribution by strategy
    trade_by_strategy = defaultdict(int)
    pnl_by_strategy = defaultdict(float)
    
    for trade in final_trades:
        strategy = trade.notes.replace("Strategy: ", "") if trade.notes else "unknown"
        trade_by_strategy[strategy] += 1
        pnl_by_strategy[strategy] += trade.profit_loss
    
    statistics = {
        "regime_stats": regime_stats,
        "strategy_results": strategy_results,
        "trade_by_strategy": dict(trade_by_strategy),
        "pnl_by_strategy": dict(pnl_by_strategy),
        "total_trades": len(final_trades),
        "final_balance": balance,
        "return_pct": (balance / config.initial_balance - 1) * 100,
    }
    
    # === SUMMARY ===
    logger.info(f"\n{'='*80}")
    logger.info(f"REGIME-ADAPTIVE SYSTEM - SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"\nTotal trades: {len(final_trades)}")
    logger.info(f"Final balance: ${balance:.2f}")
    logger.info(f"Return: {statistics['return_pct']:.2f}%")
    
    logger.info(f"\nTrades by strategy:")
    for strategy, count in trade_by_strategy.items():
        pnl = pnl_by_strategy[strategy]
        logger.info(f"  {strategy}: {count} trades, ${pnl:.2f}")
    
    logger.info(f"\n✅ Regime-adaptive system complete")
    
    return final_trades, equity_curve, statistics
