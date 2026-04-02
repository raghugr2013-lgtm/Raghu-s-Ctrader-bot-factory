"""
Walk-Forward Out-of-Sample Validation
Split candles 70/30 → Optimize on training → Test on unseen data
"""

import os, sys, json, time
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

from pymongo import MongoClient
from market_data_models import Candle, DataTimeframe
from real_backtester import RealBacktester
from backtest_calculator import performance_calculator, strategy_scorer
from backtest_mock_data import mock_generator
from optimizer_engine import GeneticOptimizer, FitnessEvaluator
from optimizer_models import OptimizationResult, ParamDef, ParamType

# --- Config ---
TRAIN_RATIO = 0.70
PAIRS = ["EURUSD", "GBPUSD", "USDJPY"]
POP_SIZE = 50
NUM_GENS = 30
TEMPLATE_ID = "ema_crossover"
STRATEGY_TYPE = "trend_following"

EMA_PARAMS = [
    ParamDef(name="fast_ma_period", param_type=ParamType.INT, min_val=5, max_val=30, step=1),
    ParamDef(name="slow_ma_period", param_type=ParamType.INT, min_val=30, max_val=120, step=1),
    ParamDef(name="atr_period", param_type=ParamType.INT, min_val=10, max_val=25, step=1),
    ParamDef(name="stop_loss_atr_mult", param_type=ParamType.FLOAT, min_val=1.0, max_val=3.0),
    ParamDef(name="take_profit_atr_mult", param_type=ParamType.FLOAT, min_val=1.5, max_val=6.0),
    ParamDef(name="risk_per_trade_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=2.0),
    ParamDef(name="adx_threshold", param_type=ParamType.FLOAT, min_val=20.0, max_val=35.0),
]

WEIGHTS = {"sharpe": 0.30, "drawdown": 0.20, "monte_carlo": 0.15,
           "challenge": 0.15, "regime": 0.10, "profit_factor": 0.10}


def load_candles(symbol):
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    docs = list(db.market_candles.find(
        {"symbol": symbol, "timeframe": "1d"}, {"_id": 0}
    ).sort("timestamp", 1))
    client.close()
    return [Candle(
        timestamp=d["timestamp"], open=d["open"], high=d["high"],
        low=d["low"], close=d["close"], volume=d.get("volume", 0),
        symbol=d["symbol"], timeframe=DataTimeframe(d["timeframe"]),
    ) for d in docs]


def backtest_params(genes, candles):
    bt = RealBacktester()
    trades, equity, config = bt.run(TEMPLATE_ID, genes, candles, 10000.0)
    if not trades:
        return {"trades": 0, "net": 0, "sharpe": 0, "dd": 0, "wr": 0, "pf": 0, "profitable": False}
    m = performance_calculator.calculate_metrics(trades, equity, config)
    return {
        "trades": len(trades), "net": m.net_profit, "sharpe": m.sharpe_ratio,
        "dd": m.max_drawdown_percent, "wr": m.win_rate, "pf": m.profit_factor,
        "profitable": m.net_profit > 0,
    }


def run_pair(symbol):
    candles = load_candles(symbol)
    split_idx = int(len(candles) * TRAIN_RATIO)
    train = candles[:split_idx]
    test = candles[split_idx:]

    train_start = train[0].timestamp.strftime("%Y-%m-%d")
    train_end = train[-1].timestamp.strftime("%Y-%m-%d")
    test_start = test[0].timestamp.strftime("%Y-%m-%d")
    test_end = test[-1].timestamp.strftime("%Y-%m-%d")

    print(f"\n{'='*80}")
    print(f"  {symbol}: {len(candles)} total candles")
    print(f"  Training: {len(train)} candles ({train_start} to {train_end})")
    print(f"  Testing:  {len(test)} candles ({test_start} to {test_end})")
    print(f"{'='*80}")

    # GA optimize on training set
    print(f"  Running GA optimization on training set ({POP_SIZE} pop x {NUM_GENS} gen)...")
    t0 = time.time()

    evaluator = FitnessEvaluator(
        strategy_type=STRATEGY_TYPE, symbol=symbol, timeframe="1d",
        duration_days=365, initial_balance=10000.0, challenge_firm="ftmo",
        weights=WEIGHTS, mock_generator=mock_generator,
        perf_calculator=performance_calculator, strategy_scorer=strategy_scorer,
        candles=train, template_id=TEMPLATE_ID,
    )

    result = OptimizationResult(
        id=f"wf-{symbol}", session_id="walk-forward",
        strategy_type=STRATEGY_TYPE, symbol=symbol, timeframe="1d",
        population_size=POP_SIZE, num_generations=NUM_GENS,
        initial_balance=10000.0, param_definitions=EMA_PARAMS,
        crossover_rate=0.85, mutation_rate=0.12, mutation_strength=0.15,
        elite_count=5, tournament_size=4,
        fitness_weights=WEIGHTS,
    )

    optimizer = GeneticOptimizer(
        param_defs=EMA_PARAMS, evaluator=evaluator,
        population_size=POP_SIZE, num_generations=NUM_GENS,
        crossover_rate=0.85, mutation_rate=0.12, mutation_strength=0.15,
        elite_count=5, tournament_size=4,
    )

    optimizer.run(result)
    elapsed = time.time() - t0
    genes = result.best_genome.genes
    print(f"  Optimization complete in {elapsed:.1f}s")
    print(f"  Best genes: fast={genes['fast_ma_period']:.0f} slow={genes['slow_ma_period']:.0f} "
          f"atr={genes['atr_period']:.0f} SL={genes['stop_loss_atr_mult']:.2f} "
          f"TP={genes['take_profit_atr_mult']:.2f} risk={genes['risk_per_trade_pct']:.2f}% "
          f"ADX={genes['adx_threshold']:.1f}")

    # Backtest on training set (in-sample)
    in_sample = backtest_params(genes, train)
    # Backtest on test set (out-of-sample)
    out_sample = backtest_params(genes, test)

    return {
        "symbol": symbol,
        "train_candles": len(train), "test_candles": len(test),
        "train_period": f"{train_start} to {train_end}",
        "test_period": f"{test_start} to {test_end}",
        "genes": genes,
        "in_sample": in_sample,
        "out_sample": out_sample,
        "optimization_time": elapsed,
    }


# --- Main ---
print("=" * 80)
print("WALK-FORWARD OUT-OF-SAMPLE VALIDATION")
print(f"EMA Crossover | 70/30 split | {POP_SIZE} pop x {NUM_GENS} gen")
print("=" * 80)

all_results = {}
for pair in PAIRS:
    all_results[pair] = run_pair(pair)

# --- Report ---
print(f"\n\n{'='*100}")
print("RESULTS: IN-SAMPLE vs OUT-OF-SAMPLE")
print("=" * 100)
print(f"{'Pair':<10} {'':>5} {'Trades':>7} {'Net P&L':>10} {'Sharpe':>8} {'DD%':>7} {'WR%':>6} {'PF':>6} {'Profit?':>8}")
print("-" * 75)
for pair in PAIRS:
    r = all_results[pair]
    ins = r["in_sample"]
    oos = r["out_sample"]
    print(f"{pair:<10} {'TRAIN':>5} {ins['trades']:>7} {ins['net']:>10.2f} {ins['sharpe']:>8.2f} {ins['dd']:>6.2f}% {ins['wr']:>6.1f} {ins['pf']:>6.2f} {'YES' if ins['profitable'] else 'NO':>8}")
    print(f"{'':10} {'TEST':>5} {oos['trades']:>7} {oos['net']:>10.2f} {oos['sharpe']:>8.2f} {oos['dd']:>6.2f}% {oos['wr']:>6.1f} {oos['pf']:>6.2f} {'YES' if oos['profitable'] else 'NO':>8}")
    # Performance retention
    if ins['net'] != 0:
        retention = (oos['net'] / ins['net']) * 100 if ins['net'] > 0 else 0
    else:
        retention = 0
    print(f"{'':10} {'RETAIN':>5} {'':>7} {retention:>9.0f}%")
    print()

# Summary
print("=" * 100)
print("WALK-FORWARD SUMMARY")
print("=" * 100)
oos_profitable = sum(1 for p in PAIRS if all_results[p]["out_sample"]["profitable"])
total_oos_pnl = sum(all_results[p]["out_sample"]["net"] for p in PAIRS)
total_ins_pnl = sum(all_results[p]["in_sample"]["net"] for p in PAIRS)
avg_retention = (total_oos_pnl / total_ins_pnl * 100) if total_ins_pnl > 0 else 0

print(f"Out-of-sample profitable: {oos_profitable}/3 pairs")
print(f"Total in-sample P&L:      ${total_ins_pnl:.2f}")
print(f"Total out-of-sample P&L:  ${total_oos_pnl:.2f}")
print(f"Performance retention:    {avg_retention:.0f}%")
print()

if oos_profitable >= 2 and avg_retention > 30:
    print("VERDICT: PASS - Strategy shows robust out-of-sample performance")
    print("         Safe to proceed with H1/H4 timeframe testing")
elif oos_profitable >= 2:
    print("VERDICT: MARGINAL PASS - Profitable but with significant performance decay")
    print("         Proceed with caution on additional timeframes")
else:
    print("VERDICT: FAIL - Strategy does not generalize well to unseen data")
    print("         Further optimization or template refinement needed")

# Save for reference
with open("/tmp/walk_forward_results.json", "w") as f:
    json.dump(all_results, f, default=str)
print("\nDetailed results saved to /tmp/walk_forward_results.json")
