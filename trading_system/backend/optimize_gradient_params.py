"""
Parameter Optimization Test for Anti-Chop Gradient Strategy

Tests multiple parameter configurations to achieve:
- Profit Factor > 1.5
- Max Drawdown < 6%
- Consistency > 40%
- Trades: 30-50
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
from anti_chop_gradient import run_anti_chop_gradient_strategy
from test_eurusd_strategy import calculate_metrics
from validate_gradient_strategy import calculate_consistency_score, calculate_improvement_score

load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'ctrader_bot_factory')


# Parameter configurations to test
CONFIGS = [
    {
        "name": "Baseline",
        "params": {
            "gradient_full_threshold": 30,
            "gradient_high_threshold": 45,
            "gradient_medium_threshold": 60,
            "take_profit_atr_mult": 4.0,
            "override_adx_threshold": 30,
        }
    },
    {
        "name": "More Aggressive Gradient",
        "params": {
            "gradient_full_threshold": 35,  # Allow more 100% positions
            "gradient_high_threshold": 50,
            "gradient_medium_threshold": 65,
            "take_profit_atr_mult": 4.0,
            "override_adx_threshold": 30,
        }
    },
    {
        "name": "Higher Take Profit",
        "params": {
            "gradient_full_threshold": 30,
            "gradient_high_threshold": 45,
            "gradient_medium_threshold": 60,
            "take_profit_atr_mult": 4.5,  # Let winners run more
            "override_adx_threshold": 30,
        }
    },
    {
        "name": "Stronger Override",
        "params": {
            "gradient_full_threshold": 30,
            "gradient_high_threshold": 45,
            "gradient_medium_threshold": 60,
            "take_profit_atr_mult": 4.0,
            "override_adx_threshold": 28,  # Activate override more often
        }
    },
    {
        "name": "Combined Optimizations",
        "params": {
            "gradient_full_threshold": 35,
            "gradient_high_threshold": 50,
            "gradient_medium_threshold": 65,
            "take_profit_atr_mult": 4.5,
            "override_adx_threshold": 28,
        }
    },
    {
        "name": "Balanced",
        "params": {
            "gradient_full_threshold": 32,
            "gradient_high_threshold": 47,
            "gradient_medium_threshold": 62,
            "take_profit_atr_mult": 4.3,
            "override_adx_threshold": 29,
        }
    },
]


async def run_optimization():
    """Test multiple parameter configurations"""
    
    print("=" * 80)
    print("ANTI-CHOP GRADIENT - PARAMETER OPTIMIZATION")
    print("=" * 80)
    
    # Connect
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    market_data_service = init_market_data_service(db)
    
    # Load data
    print("\n📊 Loading EURUSD H1 data from MongoDB cache...")
    
    candles = await market_data_service.get_candles(
        symbol="EURUSD",
        timeframe=DataTimeframe.H1,
        start_date=None,
        end_date=None,
        limit=10000
    )
    
    if not candles:
        print("❌ No cached data found")
        client.close()
        return
    
    # Filter to last 3 months
    three_months_ago = datetime.now() - timedelta(days=90)
    candles = [c for c in candles if c.timestamp >= three_months_ago]
    
    print(f"✅ Loaded {len(candles)} candles")
    print(f"   Period: {candles[0].timestamp.strftime('%Y-%m-%d')} to {candles[-1].timestamp.strftime('%Y-%m-%d')}")
    
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
    
    # Base parameters (common across all configs)
    base_params = {
        "base_risk_pct": 0.7,
        "stop_loss_atr_mult": 1.9,
        "min_confirmations": 2,
        "max_trades_per_day": 3,
        "require_confirmation": True,
        "min_position_floor": 0.5,
        "enable_strong_signal_override": True,
        "override_min_signals": 3,
    }
    
    # Test all configurations
    results = []
    
    for config_def in CONFIGS:
        print(f"\n{'=' * 80}")
        print(f"TESTING: {config_def['name']}")
        print(f"{'=' * 80}")
        
        # Merge parameters
        test_params = {**base_params, **config_def['params']}
        
        # Print key parameters
        print(f"\n📋 Parameters:")
        print(f"   Gradient: <{test_params['gradient_full_threshold']}=100%, "
              f"<{test_params['gradient_high_threshold']}=80%, "
              f"<{test_params['gradient_medium_threshold']}=60%")
        print(f"   TP Mult: {test_params['take_profit_atr_mult']}x")
        print(f"   Override ADX: >{test_params['override_adx_threshold']}")
        
        # Run backtest
        print(f"\n🚀 Running backtest...")
        trades, equity = run_anti_chop_gradient_strategy(candles, config, test_params)
        
        # Calculate metrics
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
        cons_goal = consistency > 40
        trades_goal = 30 <= metrics['total_trades'] <= 50
        
        goals_met = sum([pf_goal, dd_goal, cons_goal, trades_goal])
        
        # Store results
        result = {
            'name': config_def['name'],
            'params': config_def['params'],
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
            'dd_goal': dd_goal,
            'cons_goal': cons_goal,
            'trades_goal': trades_goal,
        }
        results.append(result)
        
        # Print results
        print(f"\n📊 Results:")
        print(f"   Trades: {metrics['total_trades']} {'✅' if trades_goal else '❌'}")
        print(f"   Profit Factor: {metrics['profit_factor']:.2f} {'✅' if pf_goal else '❌'}")
        print(f"   Max DD: {metrics['max_drawdown_pct']:.2f}% {'✅' if dd_goal else '❌'}")
        print(f"   Consistency: {consistency:.1f}% {'✅' if cons_goal else '❌'}")
        print(f"   Net P&L: ${metrics['total_pnl']:.2f}")
        print(f"   Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   Sharpe: {metrics['sharpe_ratio']:.2f}")
        print(f"   Score: {score:.1f}/100")
        print(f"   Goals Met: {goals_met}/4")
    
    # Comparison Table
    print(f"\n{'=' * 80}")
    print("OPTIMIZATION RESULTS - COMPARISON")
    print(f"{'=' * 80}")
    
    print(f"\n{'Config':<25} {'Trades':<8} {'PF':<8} {'DD%':<8} {'Cons%':<8} {'P&L':<12} {'Score':<8} {'Goals':<8}")
    print("-" * 95)
    
    for r in results:
        pf_marker = "★" if r['pf_goal'] else ""
        print(f"{r['name']:<25} {r['trades']:<8} {r['pf']:<8.2f}{pf_marker:>1} {r['dd']:<8.2f} "
              f"{r['consistency']:<8.1f} ${r['pnl']:<11.2f} {r['score']:<8.1f} {r['goals_met']}/4")
    
    # Find best configuration
    print(f"\n{'=' * 80}")
    print("BEST CONFIGURATION BY METRIC")
    print(f"{'=' * 80}")
    
    best_pf = max(results, key=lambda x: x['pf'])
    best_score = max(results, key=lambda x: x['score'])
    best_pnl = max(results, key=lambda x: x['pnl'])
    best_goals = max(results, key=lambda x: x['goals_met'])
    
    print(f"\n🏆 Best Profit Factor: {best_pf['name']} (PF: {best_pf['pf']:.2f})")
    print(f"🏆 Best Overall Score: {best_score['name']} (Score: {best_score['score']:.1f})")
    print(f"🏆 Best Net P&L: {best_pnl['name']} (P&L: ${best_pnl['pnl']:.2f})")
    print(f"🏆 Most Goals Met: {best_goals['name']} ({best_goals['goals_met']}/4 goals)")
    
    # Recommendation
    print(f"\n{'=' * 80}")
    print("RECOMMENDATION")
    print(f"{'=' * 80}")
    
    configs_with_all_goals = [r for r in results if r['goals_met'] == 4]
    
    if configs_with_all_goals:
        winner = max(configs_with_all_goals, key=lambda x: x['score'])
        print(f"\n✅ **RECOMMENDED CONFIGURATION: {winner['name']}**")
        print(f"\n   All 4 goals achieved!")
        print(f"   - Profit Factor: {winner['pf']:.2f} (target: >1.5) ✅")
        print(f"   - Max Drawdown: {winner['dd']:.2f}% (target: <6%) ✅")
        print(f"   - Consistency: {winner['consistency']:.1f}% (target: >40%) ✅")
        print(f"   - Trades: {winner['trades']} (target: 30-50) ✅")
        print(f"   - Net P&L: ${winner['pnl']:.2f}")
        print(f"   - Overall Score: {winner['score']:.1f}/100")
        print(f"\n   Parameters:")
        for key, value in winner['params'].items():
            print(f"      {key}: {value}")
    else:
        # Find config closest to all goals
        winner = max(results, key=lambda x: (x['goals_met'], x['score']))
        print(f"\n⚠️  **BEST AVAILABLE CONFIGURATION: {winner['name']}**")
        print(f"\n   Goals met: {winner['goals_met']}/4")
        print(f"   - Profit Factor: {winner['pf']:.2f} (target: >1.5) {'✅' if winner['pf_goal'] else '❌'}")
        print(f"   - Max Drawdown: {winner['dd']:.2f}% (target: <6%) {'✅' if winner['dd_goal'] else '❌'}")
        print(f"   - Consistency: {winner['consistency']:.1f}% (target: >40%) {'✅' if winner['cons_goal'] else '❌'}")
        print(f"   - Trades: {winner['trades']} (target: 30-50) {'✅' if winner['trades_goal'] else '❌'}")
        print(f"   - Net P&L: ${winner['pnl']:.2f}")
        print(f"   - Overall Score: {winner['score']:.1f}/100")
        print(f"\n   Parameters:")
        for key, value in winner['params'].items():
            print(f"      {key}: {value}")
        
        print(f"\n   💡 Further optimization recommended to achieve all goals")
    
    print(f"\n{'=' * 80}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(run_optimization())
