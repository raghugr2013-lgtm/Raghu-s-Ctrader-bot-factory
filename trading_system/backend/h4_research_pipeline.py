"""
H4 Intraday Research Pipeline
Aggregates H1 candles → H4, then runs:
Factory → GA Optimization → Cross-market validation → Walk-forward testing
"""

import os, sys, json, time
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

from datetime import datetime, timedelta
from pymongo import MongoClient
from market_data_models import Candle, DataTimeframe
from real_backtester import RealBacktester
from backtest_calculator import performance_calculator, strategy_scorer
from backtest_mock_data import mock_generator
from optimizer_engine import GeneticOptimizer, FitnessEvaluator
from optimizer_models import OptimizationResult, ParamDef, ParamType

# --- Config ---
TIMEFRAME = "4h"
TF_ENUM = DataTimeframe.H4
TRAIN_RATIO = 0.70
PAIRS = ["EURUSD", "GBPUSD", "USDJPY"]
POP_SIZE = 30
NUM_GENS = 15
FACTORY_PER_TEMPLATE = 50
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


# ---------------------------------------------------------------------------
# H1 → H4 Aggregation
# ---------------------------------------------------------------------------

def aggregate_h1_to_h4(h1_candles):
    """
    Aggregate H1 candles into H4 candles.
    Groups by 4-hour blocks aligned to 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC.
    """
    if not h1_candles:
        return []

    # Group candles into 4-hour blocks
    blocks = {}
    for c in h1_candles:
        ts = c.timestamp
        # Align to 4-hour block start: floor hour to nearest multiple of 4
        block_hour = (ts.hour // 4) * 4
        block_start = ts.replace(hour=block_hour, minute=0, second=0, microsecond=0)
        key = (block_start.year, block_start.month, block_start.day, block_hour)
        if key not in blocks:
            blocks[key] = {"candles": [], "timestamp": block_start}
        blocks[key]["candles"].append(c)

    # Aggregate each block into a single H4 candle
    h4_candles = []
    for key in sorted(blocks.keys()):
        group = blocks[key]["candles"]
        # Sort by timestamp within block
        group.sort(key=lambda x: x.timestamp)

        h4 = Candle(
            timestamp=blocks[key]["timestamp"],
            open=group[0].open,
            high=max(c.high for c in group),
            low=min(c.low for c in group),
            close=group[-1].close,
            volume=sum(c.volume for c in group),
            symbol=group[0].symbol,
            timeframe=DataTimeframe.H4,
        )
        h4_candles.append(h4)

    h4_candles.sort(key=lambda c: c.timestamp)
    return h4_candles


def load_h1_candles(symbol):
    """Load H1 candles from MongoDB."""
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    docs = list(db.market_candles.find(
        {"symbol": symbol, "timeframe": "1h"}, {"_id": 0}
    ).sort("timestamp", 1))
    client.close()
    return [Candle(
        timestamp=d["timestamp"], open=d["open"], high=d["high"],
        low=d["low"], close=d["close"], volume=d.get("volume", 0),
        symbol=d["symbol"], timeframe=DataTimeframe.H1,
    ) for d in docs]


def store_h4_candles(h4_candles):
    """Store aggregated H4 candles in MongoDB (upsert)."""
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    stored = 0
    for c in h4_candles:
        db.market_candles.update_one(
            {"symbol": c.symbol, "timeframe": "4h", "timestamp": c.timestamp},
            {"$set": {
                "symbol": c.symbol, "timeframe": "4h",
                "timestamp": c.timestamp,
                "open": c.open, "high": c.high, "low": c.low,
                "close": c.close, "volume": c.volume,
                "provider": "aggregated_h1",
            }},
            upsert=True,
        )
        stored += 1
    client.close()
    return stored


def load_h4_candles(symbol):
    """Load H4 candles from MongoDB."""
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    docs = list(db.market_candles.find(
        {"symbol": symbol, "timeframe": "4h"}, {"_id": 0}
    ).sort("timestamp", 1))
    client.close()
    return [Candle(
        timestamp=d["timestamp"], open=d["open"], high=d["high"],
        low=d["low"], close=d["close"], volume=d.get("volume", 0),
        symbol=d["symbol"], timeframe=DataTimeframe.H4,
    ) for d in docs]


# ---------------------------------------------------------------------------
# Pipeline helpers (same as H1 pipeline)
# ---------------------------------------------------------------------------

def backtest_params(genes, candles):
    bt = RealBacktester()
    trades, equity, config = bt.run(TEMPLATE_ID, genes, candles, 10000.0)
    if not trades:
        return {"trades": 0, "net": 0, "sharpe": 0, "dd": 0, "wr": 0, "pf": 0, "ok": False}
    m = performance_calculator.calculate_metrics(trades, equity, config)
    return {"trades": len(trades), "net": m.net_profit, "sharpe": m.sharpe_ratio,
            "dd": m.max_drawdown_percent, "wr": m.win_rate, "pf": m.profit_factor,
            "ok": m.net_profit > 0}


def ga_optimize(candles, symbol):
    evaluator = FitnessEvaluator(
        strategy_type=STRATEGY_TYPE, symbol=symbol, timeframe=TIMEFRAME,
        duration_days=365, initial_balance=10000.0, challenge_firm="ftmo",
        weights=WEIGHTS, mock_generator=mock_generator,
        perf_calculator=performance_calculator, strategy_scorer=strategy_scorer,
        candles=candles, template_id=TEMPLATE_ID,
    )
    result = OptimizationResult(
        id=f"h4-{symbol}", session_id="h4-research",
        strategy_type=STRATEGY_TYPE, symbol=symbol, timeframe=TIMEFRAME,
        population_size=POP_SIZE, num_generations=NUM_GENS,
        initial_balance=10000.0, param_definitions=EMA_PARAMS,
        crossover_rate=0.85, mutation_rate=0.12, mutation_strength=0.15,
        elite_count=5, tournament_size=4, fitness_weights=WEIGHTS,
    )
    optimizer = GeneticOptimizer(
        param_defs=EMA_PARAMS, evaluator=evaluator,
        population_size=POP_SIZE, num_generations=NUM_GENS,
        crossover_rate=0.85, mutation_rate=0.12, mutation_strength=0.15,
        elite_count=5, tournament_size=4,
    )
    optimizer.run(result)
    return result.best_genome.genes, result.best_genome.fitness


# ===========================================================================
# MAIN PIPELINE
# ===========================================================================

print("=" * 100)
print("H4 RESEARCH PIPELINE — EMA Crossover (Aggregated from H1)")
print("=" * 100)

# Step 0: Aggregate H1 → H4
print("\nSTEP 0: Aggregating H1 candles → H4")
print("-" * 50)
all_candles = {}
for pair in PAIRS:
    h1 = load_h1_candles(pair)
    h4 = aggregate_h1_to_h4(h1)
    n_stored = store_h4_candles(h4)
    all_candles[pair] = h4
    print(f"  {pair}: {len(h1)} H1 → {len(h4)} H4 candles "
          f"({h4[0].timestamp.strftime('%Y-%m-%d')} to {h4[-1].timestamp.strftime('%Y-%m-%d')})")

# ===========================================================================
# PHASE 1: Factory Discovery
# ===========================================================================
print(f"\n{'='*100}")
print("PHASE 1: Factory Discovery (50 strategies per pair)")
print("=" * 100)

from factory_engine import STRATEGY_TEMPLATES, StrategyGenerator
from factory_models import TemplateId
from optimizer_models import StrategyGenome

for pair in PAIRS:
    candles = all_candles[pair]
    tmpl = STRATEGY_TEMPLATES[TemplateId.EMA_CROSSOVER]
    strategies = StrategyGenerator.generate(tmpl, FACTORY_PER_TEMPLATE)

    evaluator = FitnessEvaluator(
        strategy_type=tmpl.backtest_strategy_type, symbol=pair, timeframe=TIMEFRAME,
        duration_days=365, initial_balance=10000.0, challenge_firm="ftmo",
        weights=WEIGHTS, mock_generator=mock_generator,
        perf_calculator=performance_calculator, strategy_scorer=strategy_scorer,
        candles=candles, template_id=TEMPLATE_ID,
    )

    profitable = 0
    fitnesses = []
    for strat in strategies:
        genome = StrategyGenome(genes=strat.genes)
        evaluator.evaluate(genome)
        fitnesses.append(genome.fitness)
        if genome.net_profit > 0:
            profitable += 1

    avg_f = sum(fitnesses) / len(fitnesses)
    max_f = max(fitnesses)
    print(f"  {pair}: {profitable}/{len(strategies)} profitable ({profitable/len(strategies)*100:.0f}%), avg fitness={avg_f:.1f}, best={max_f:.1f}")

# ===========================================================================
# PHASE 2: GA Optimization (full data)
# ===========================================================================
print(f"\n{'='*100}")
print(f"PHASE 2: GA Optimization ({POP_SIZE} pop x {NUM_GENS} gen, full H4 data)")
print("=" * 100)

opt_params = {}
for pair in PAIRS:
    t0 = time.time()
    genes, fitness = ga_optimize(all_candles[pair], pair)
    elapsed = time.time() - t0
    opt_params[pair] = genes
    print(f"  {pair}: fitness={fitness:.2f} in {elapsed:.0f}s | fast={genes['fast_ma_period']:.0f} slow={genes['slow_ma_period']:.0f} atr={genes['atr_period']:.0f} SL={genes['stop_loss_atr_mult']:.2f} TP={genes['take_profit_atr_mult']:.2f} risk={genes['risk_per_trade_pct']:.2f}% ADX={genes['adx_threshold']:.1f}")

# ===========================================================================
# PHASE 3: Cross-Market Validation
# ===========================================================================
print(f"\n{'='*100}")
print("PHASE 3: Cross-Market Validation")
print("=" * 100)

cross_results = {}
for opt_pair in PAIRS:
    genes = opt_params[opt_pair]
    cross_results[opt_pair] = {}
    for test_pair in PAIRS:
        cross_results[opt_pair][test_pair] = backtest_params(genes, all_candles[test_pair])

for opt_pair in PAIRS:
    total = sum(cross_results[opt_pair][tp]["net"] for tp in PAIRS)
    cross = sum(1 for tp in PAIRS if cross_results[opt_pair][tp]["ok"])
    print(f"\n  Params from {opt_pair}: {cross}/3 profitable, total=${total:.2f}")
    for tp in PAIRS:
        r = cross_results[opt_pair][tp]
        m = " *HOME*" if tp == opt_pair else ""
        s = "PROFIT" if r["ok"] else "LOSS"
        print(f"    {tp}: {s:>6} Net=${r['net']:>10.2f} Sharpe={r['sharpe']:>7.2f} DD={r['dd']:>5.2f}% WR={r['wr']:>5.1f}% Trades={r['trades']}{m}")

# ===========================================================================
# PHASE 4: Walk-Forward Out-of-Sample
# ===========================================================================
print(f"\n{'='*100}")
print(f"PHASE 4: Walk-Forward Validation (70/30 split)")
print("=" * 100)

wf_results = {}
for pair in PAIRS:
    candles = all_candles[pair]
    split_idx = int(len(candles) * TRAIN_RATIO)
    train = candles[:split_idx]
    test = candles[split_idx:]

    print(f"\n  {pair}: Train={len(train)} candles, Test={len(test)} candles")
    print(f"    Training: {train[0].timestamp.strftime('%Y-%m-%d')} to {train[-1].timestamp.strftime('%Y-%m-%d')}")
    print(f"    Testing:  {test[0].timestamp.strftime('%Y-%m-%d')} to {test[-1].timestamp.strftime('%Y-%m-%d')}")

    t0 = time.time()
    genes, fitness = ga_optimize(train, pair)
    elapsed = time.time() - t0
    print(f"    GA done in {elapsed:.0f}s, fitness={fitness:.2f}")

    ins = backtest_params(genes, train)
    oos = backtest_params(genes, test)

    retention = (oos["net"] / ins["net"] * 100) if ins["net"] > 0 else 0
    wf_results[pair] = {"genes": genes, "in_sample": ins, "out_sample": oos, "retention": retention}

    print(f"    IN-SAMPLE:  Net=${ins['net']:>10.2f} Sharpe={ins['sharpe']:>7.2f} DD={ins['dd']:>5.2f}% WR={ins['wr']:>5.1f}% Trades={ins['trades']}")
    print(f"    OUT-SAMPLE: Net=${oos['net']:>10.2f} Sharpe={oos['sharpe']:>7.2f} DD={oos['dd']:>5.2f}% WR={oos['wr']:>5.1f}% Trades={oos['trades']}")
    print(f"    Retention:  {retention:.0f}%  {'PROFIT' if oos['ok'] else 'LOSS'}")

# ===========================================================================
# FINAL SUMMARY
# ===========================================================================
print(f"\n\n{'='*100}")
print("FINAL SUMMARY: H4 EMA CROSSOVER RESEARCH PIPELINE")
print("=" * 100)

# Cross-market
best_opt = max(PAIRS, key=lambda p: sum(cross_results[p][tp]["net"] for tp in PAIRS))
best_total = sum(cross_results[best_opt][tp]["net"] for tp in PAIRS)
best_cross = sum(1 for tp in PAIRS if cross_results[best_opt][tp]["ok"])
print(f"\nCross-Market: Best params from {best_opt} ({best_cross}/3 profitable, total=${best_total:.2f})")

# Walk-forward
oos_profitable = sum(1 for p in PAIRS if wf_results[p]["out_sample"]["ok"])
total_oos = sum(wf_results[p]["out_sample"]["net"] for p in PAIRS)
total_ins = sum(wf_results[p]["in_sample"]["net"] for p in PAIRS)
avg_retention = (total_oos / total_ins * 100) if total_ins > 0 else 0

print(f"\nWalk-Forward:")
print(f"  Out-of-sample profitable: {oos_profitable}/3 pairs")
print(f"  Total in-sample P&L:      ${total_ins:.2f}")
print(f"  Total out-of-sample P&L:  ${total_oos:.2f}")
print(f"  Avg retention:            {avg_retention:.0f}%")

# Compare with D1 and H1
print(f"\n--- TIMEFRAME COMPARISON (EMA Crossover) ---")
print(f"  D1 walk-forward:  3/3 OOS profitable, 42% retention, $1,531 OOS total")
print(f"  H1 walk-forward:  2/3 OOS profitable,  0% retention,   -$10 OOS total")
print(f"  H4 walk-forward:  {oos_profitable}/3 OOS profitable, {avg_retention:.0f}% retention, ${total_oos:.2f} OOS total")

if oos_profitable >= 2 and avg_retention > 20:
    verdict = "H4 PASS - EMA strategy is robust on 4-hour timeframe"
elif oos_profitable >= 2:
    verdict = "H4 MARGINAL - Profitable but weaker retention"
else:
    verdict = "H4 FAIL - Strategy does not transfer well to 4-hour"
print(f"\n  VERDICT: {verdict}")

# Save results
results = {
    "aggregation": {p: len(all_candles[p]) for p in PAIRS},
    "cross_market": {p: {tp: cross_results[p][tp] for tp in PAIRS} for p in PAIRS},
    "walk_forward": {p: {"in_sample": wf_results[p]["in_sample"],
                          "out_sample": wf_results[p]["out_sample"],
                          "retention": wf_results[p]["retention"]} for p in PAIRS},
    "opt_params": {p: opt_params[p] for p in PAIRS},
}
with open("/app/research/h4_validation_results.json", "w") as f:
    json.dump(results, f, default=str, indent=2)
print(f"\nResults saved to /app/research/h4_validation_results.json")
