"""
Parameter Tuning for Enhanced Strategy

The initial enhanced version was TOO STRICT.
Need to find optimal balance between quality and quantity.
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timedelta

from market_data_service import init_market_data_service
from market_data_models import DataTimeframe
from backtest_models import BacktestConfig, Timeframe
from anti_chop_gradient_enhanced import run_anti_chop_gradient_enhanced_strategy
from test_eurusd_strategy import calculate_metrics
from validate_gradient_strategy import calculate_consistency_score, calculate_improvement_score

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


CONFIGS = [
    {
        "name": "Baseline Enhanced",
        "params": {
            "min_quality_score": 55,
            "require_rsi_momentum_alignment": True,
            "require_positive_ema_slope": True,
            "min_pullback_quality": 40,
            "take_profit_atr_mult": 4.8,
        }
    },
    {
        "name": "Lower Quality Threshold",
        "params": {
            "min_quality_score": 45,  # More lenient
            "require_rsi_momentum_alignment": True,
            "require_positive_ema_slope": True,
            "min_pullback_quality": 30,  # More lenient
            "take_profit_atr_mult": 4.8,
        }
    },
    {
        "name": "No RSI Momentum Requirement",
        "params": {
            "min_quality_score": 45,
            "require_rsi_momentum_alignment": False,  # Don't require
            "require_positive_ema_slope": True,
            "min_pullback_quality": 30,
            "take_profit_atr_mult": 4.8,
        }
    },
    {
        "name": "No EMA Slope Requirement",
        "params": {
            "min_quality_score": 45,
            "require_rsi_momentum_alignment": True,
            "require_positive_ema_slope": False,  # Don't require
            "min_pullback_quality": 30,
            "take_profit_atr_mult": 4.8,
        }
    },
    {
        "name": "Balanced (Lenient)",
        "params": {
            "min_quality_score": 40,
            "require_rsi_momentum_alignment": False,
            "require_positive_ema_slope": False,
            "min_pullback_quality": 25,
            "take_profit_atr_mult": 4.8,
        }
    },
    {
        "name": "Higher TP Only",
        "params": {
            "min_quality_score": 40,
            "require_rsi_momentum_alignment": False,
            "require_positive_ema_slope": False,
            "min_pullback_quality": 0,  # No pullback filter
            "take_profit_atr_mult": 5.2,  # Much higher
            "enable_quality_filter": False,  # Disable quality filter
        }
    },
]


async def run_tuning():
    """Tune enhanced strategy parameters"""
    
    print("=" * 80)
    print("ENHANCED STRATEGY - PARAMETER TUNING")
    print("Goal: Find optimal balance between quality filtering and trade frequency")
    print("=" * 80)
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Load data
    print("\n📊 Loading data...")
    candles = await market_data_service.get_candles(
        symbol="EURUSD",
        timeframe=DataTimeframe.H1,
        start_date=None,
        end_date=None,
        limit=10000
    )
    
    if not candles:
        print("❌ No cached data")
        client.close()
        return
    
    three_months_ago = datetime.now() - timedelta(days=90)
    candles = [c for c in candles if c.timestamp >= three_months_ago]
    
    print(f"✅ {len(candles)} candles loaded")
    
    # Config
    config = BacktestConfig(
        symbol="EURUSD",
        timeframe=Timeframe.H1,
        start_date=candles[0].timestamp,
        end_date=candles[-1].timestamp,
        initial_balance=10000.0,
        spread_pips=1.5,
        commission_per_lot=7.0,
        leverage=100,
    )
    
    # Base parameters
    base_params = {
        "base_risk_pct": 0.7,
        "stop_loss_atr_mult": 1.9,
        "min_confirmations": 2,
        "max_trades_per_day": 3,
        "gradient_full_threshold": 32,
        "gradient_high_threshold": 47,
        "gradient_medium_threshold": 62,
        "override_adx_threshold": 29,
    }
    
    results = []
    
    for config_def in CONFIGS:
        print(f"\n{'=' * 80}")
        print(f"TESTING: {config_def['name']}")
        print(f"{'=' * 80}")
        
        test_params = {**base_params, **config_def['params']}
        
        print(f"\n📋 Key Parameters:")
        print(f"   Min Quality Score: {test_params.get('min_quality_score', 'N/A')}")
        print(f"   RSI Momentum Required: {test_params.get('require_rsi_momentum_alignment', False)}")
        print(f"   EMA Slope Required: {test_params.get('require_positive_ema_slope', False)}")
        print(f"   Min Pullback Quality: {test_params.get('min_pullback_quality', 'N/A')}")
        print(f"   TP Multiplier: {test_params.get('take_profit_atr_mult', 4.3)}x")
        
        print(f"\n🚀 Running backtest...")
        trades, equity = run_anti_chop_gradient_enhanced_strategy(candles, config, test_params)
        
        metrics = calculate_metrics(trades, equity, config.initial_balance)
        consistency = calculate_consistency_score(trades, segments=3)
        score = calculate_improvement_score(
            metrics['profit_factor'],
            metrics['max_drawdown_pct'],
            consistency,
            metrics['total_trades']
        )
        
        # Check goals
        pf_goal = metrics['profit_factor'] > 1.5
        dd_goal = metrics['max_drawdown_pct'] < 6.0
        cons_goal = consistency > 50
        trades_goal = 25 <= metrics['total_trades'] <= 40
        
        goals_met = sum([pf_goal, dd_goal, cons_goal, trades_goal])
        
        result = {
            'name': config_def['name'],
            'trades': metrics['total_trades'],
            'pf': metrics['profit_factor'],
            'dd': metrics['max_drawdown_pct'],
            'consistency': consistency,
            'pnl': metrics['total_pnl'],
            'win_rate': metrics['win_rate'],
            'sharpe': metrics['sharpe_ratio'],
            'score': score,
            'goals_met': goals_met,
            'pf_goal': pf_goal,
        }
        results.append(result)
        
        print(f"\n📊 Results:")
        print(f"   Trades: {metrics['total_trades']} {'✅' if trades_goal else '❌'}")
        print(f"   Profit Factor: {metrics['profit_factor']:.2f} {'✅' if pf_goal else '❌'}")
        print(f"   Max DD: {metrics['max_drawdown_pct']:.2f}% {'✅' if dd_goal else '❌'}")
        print(f"   Consistency: {consistency:.1f}% {'✅' if cons_goal else '❌'}")
        print(f"   Net P&L: ${metrics['total_pnl']:.2f}")
        print(f"   Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   Score: {score:.1f}/100")
        print(f"   Goals Met: {goals_met}/4")
    
    # Comparison
    print(f"\n{'=' * 80}")
    print("TUNING RESULTS - COMPARISON")
    print(f"{'=' * 80}")
    
    print(f"\n{'Config':<30} {'Trades':<8} {'PF':<8} {'DD%':<8} {'P&L':<12} {'Score':<8} {'Goals':<8}")
    print("-" * 90)
    
    for r in results:
        pf_marker = "★" if r['pf_goal'] else ""
        print(f"{r['name']:<30} {r['trades']:<8} {r['pf']:<8.2f}{pf_marker:>1} {r['dd']:<8.2f} "
              f"${r['pnl']:<11.2f} {r['score']:<8.1f} {r['goals_met']}/4")
    
    # Best config
    print(f"\n{'=' * 80}")
    print("RECOMMENDATION")
    print(f"{'=' * 80}")
    
    best_pf = max(results, key=lambda x: x['pf'])
    best_score = max(results, key=lambda x: x['score'])
    
    print(f"\n🏆 Best Profit Factor: {best_pf['name']} (PF: {best_pf['pf']:.2f})")
    print(f"🏆 Best Overall Score: {best_score['name']} (Score: {best_score['score']:.1f})")
    
    if best_pf['pf'] > 1.5:
        print(f"\n✅ **TARGET ACHIEVED with {best_pf['name']}**")
        print(f"   Profit Factor: {best_pf['pf']:.2f} > 1.5 ✅")
        print(f"   Trades: {best_pf['trades']}")
        print(f"   P&L: ${best_pf['pnl']:.2f}")
        print(f"   Consistency: {best_pf['consistency']:.1f}%")
    else:
        print(f"\n⚠️  **Best Available: {best_pf['name']}**")
        print(f"   Profit Factor: {best_pf['pf']:.2f} (gap: {1.5 - best_pf['pf']:.2f})")
        print(f"   Trades: {best_pf['trades']}")
        print(f"   Suggestion: Entry quality alone may not be sufficient")
        print(f"              Consider hybrid approach or different market period")
    
    print(f"\n{'=' * 80}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(run_tuning())
