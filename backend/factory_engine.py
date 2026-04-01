"""
Strategy Factory Engine
Generates strategies from predefined templates and evaluates them
through the existing backtest + fitness pipeline.
"""

import random
import logging
import time
from typing import List, Dict

from optimizer_models import ParamDef, ParamType, StrategyGenome
from optimizer_engine import FitnessEvaluator, GenomeFactory
from backtest_calculator import performance_calculator, strategy_scorer
from backtest_mock_data import mock_generator
from factory_models import (
    TemplateId,
    StrategyTemplate,
    GeneratedStrategy,
    FactoryRun,
    FactoryStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

STRATEGY_TEMPLATES: Dict[TemplateId, StrategyTemplate] = {
    TemplateId.EMA_CROSSOVER: StrategyTemplate(
        id=TemplateId.EMA_CROSSOVER,
        name="EMA Crossover",
        description="Enters on fast/slow EMA crossover with ATR-based stops. Classic trend-following approach.",
        backtest_strategy_type="trend_following",
        param_definitions=[
            ParamDef(name="fast_ma_period", param_type=ParamType.INT, min_val=5, max_val=30, step=1),
            ParamDef(name="slow_ma_period", param_type=ParamType.INT, min_val=30, max_val=120, step=1),
            ParamDef(name="atr_period", param_type=ParamType.INT, min_val=10, max_val=25, step=1),
            ParamDef(name="stop_loss_atr_mult", param_type=ParamType.FLOAT, min_val=1.0, max_val=3.0),
            ParamDef(name="take_profit_atr_mult", param_type=ParamType.FLOAT, min_val=1.5, max_val=6.0),
            ParamDef(name="risk_per_trade_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=2.0),
            ParamDef(name="adx_threshold", param_type=ParamType.FLOAT, min_val=20.0, max_val=35.0),
        ],
    ),
    TemplateId.RSI_MEAN_REVERSION: StrategyTemplate(
        id=TemplateId.RSI_MEAN_REVERSION,
        name="RSI Mean Reversion",
        description="Buys oversold / sells overbought RSI levels with Bollinger Band confirmation.",
        backtest_strategy_type="mean_reversion",
        param_definitions=[
            ParamDef(name="rsi_period", param_type=ParamType.INT, min_val=7, max_val=21, step=1),
            ParamDef(name="rsi_oversold", param_type=ParamType.FLOAT, min_val=20, max_val=35),
            ParamDef(name="rsi_overbought", param_type=ParamType.FLOAT, min_val=65, max_val=80),
            ParamDef(name="bb_period", param_type=ParamType.INT, min_val=14, max_val=30, step=1),
            ParamDef(name="bb_std", param_type=ParamType.FLOAT, min_val=1.5, max_val=3.0),
            ParamDef(name="stop_loss_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=2.0),
            ParamDef(name="take_profit_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=3.0),
            ParamDef(name="risk_per_trade_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=2.0),
        ],
    ),
    TemplateId.MACD_TREND: StrategyTemplate(
        id=TemplateId.MACD_TREND,
        name="MACD Trend Following",
        description="Uses MACD histogram crossover for trend entries with ADX filter and ATR stops.",
        backtest_strategy_type="trend_following",
        param_definitions=[
            ParamDef(name="fast_ma_period", param_type=ParamType.INT, min_val=8, max_val=20, step=1),
            ParamDef(name="slow_ma_period", param_type=ParamType.INT, min_val=20, max_val=50, step=1),
            ParamDef(name="atr_period", param_type=ParamType.INT, min_val=10, max_val=20, step=1),
            ParamDef(name="stop_loss_atr_mult", param_type=ParamType.FLOAT, min_val=1.0, max_val=3.5),
            ParamDef(name="take_profit_atr_mult", param_type=ParamType.FLOAT, min_val=2.0, max_val=7.0),
            ParamDef(name="risk_per_trade_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=2.5),
            ParamDef(name="adx_threshold", param_type=ParamType.FLOAT, min_val=18.0, max_val=35.0),
        ],
    ),
    TemplateId.BOLLINGER_BREAKOUT: StrategyTemplate(
        id=TemplateId.BOLLINGER_BREAKOUT,
        name="Bollinger Band Breakout",
        description="Enters on price breaking above/below Bollinger Bands with volume confirmation.",
        backtest_strategy_type="breakout",
        param_definitions=[
            ParamDef(name="bb_period", param_type=ParamType.INT, min_val=14, max_val=40, step=1),
            ParamDef(name="bb_std", param_type=ParamType.FLOAT, min_val=1.5, max_val=3.0),
            ParamDef(name="atr_period", param_type=ParamType.INT, min_val=10, max_val=25, step=1),
            ParamDef(name="stop_loss_atr_mult", param_type=ParamType.FLOAT, min_val=1.0, max_val=3.0),
            ParamDef(name="take_profit_atr_mult", param_type=ParamType.FLOAT, min_val=2.0, max_val=6.0),
            ParamDef(name="risk_per_trade_pct", param_type=ParamType.FLOAT, min_val=0.5, max_val=2.0),
            ParamDef(name="adx_threshold", param_type=ParamType.FLOAT, min_val=15.0, max_val=30.0),
        ],
    ),
    TemplateId.ATR_VOLATILITY_BREAKOUT: StrategyTemplate(
        id=TemplateId.ATR_VOLATILITY_BREAKOUT,
        name="ATR Volatility Breakout",
        description="Enters when price moves beyond N*ATR from recent close, targeting volatility expansion.",
        backtest_strategy_type="breakout",
        param_definitions=[
            ParamDef(name="atr_period", param_type=ParamType.INT, min_val=7, max_val=25, step=1),
            ParamDef(name="stop_loss_atr_mult", param_type=ParamType.FLOAT, min_val=0.8, max_val=2.5),
            ParamDef(name="take_profit_atr_mult", param_type=ParamType.FLOAT, min_val=2.0, max_val=8.0),
            ParamDef(name="risk_per_trade_pct", param_type=ParamType.FLOAT, min_val=0.3, max_val=2.0),
            ParamDef(name="adx_threshold", param_type=ParamType.FLOAT, min_val=15.0, max_val=35.0),
            ParamDef(name="fast_ma_period", param_type=ParamType.INT, min_val=5, max_val=20, step=1),
            ParamDef(name="slow_ma_period", param_type=ParamType.INT, min_val=20, max_val=80, step=1),
        ],
    ),
}


def get_all_templates() -> Dict[str, StrategyTemplate]:
    return STRATEGY_TEMPLATES


# ---------------------------------------------------------------------------
# Strategy Generator
# ---------------------------------------------------------------------------

class StrategyGenerator:
    """Generate random strategy instances from a template."""

    @staticmethod
    def generate(template: StrategyTemplate, count: int) -> List[GeneratedStrategy]:
        strategies = []
        factory = GenomeFactory(template.param_definitions)
        for _ in range(count):
            genome = factory.random_genome()
            strategies.append(
                GeneratedStrategy(
                    template_id=template.id,
                    genes=genome.genes,
                )
            )
        return strategies


# ---------------------------------------------------------------------------
# Factory Runner
# ---------------------------------------------------------------------------

class FactoryRunner:
    """Run a full factory cycle: generate -> evaluate -> rank."""

    def run(self, factory_run: FactoryRun, candles=None) -> FactoryRun:
        start = time.time()
        factory_run.status = FactoryStatus.RUNNING

        try:
            all_strategies: List[GeneratedStrategy] = []

            for tmpl_id_str in factory_run.templates_used:
                tmpl_id = TemplateId(tmpl_id_str)
                template = STRATEGY_TEMPLATES[tmpl_id]

                # Generate random strategies
                strategies = StrategyGenerator.generate(
                    template, factory_run.strategies_per_template
                )
                factory_run.total_generated += len(strategies)

                # Evaluate each strategy
                evaluator = FitnessEvaluator(
                    strategy_type=template.backtest_strategy_type,
                    symbol=factory_run.symbol,
                    timeframe=factory_run.timeframe,
                    duration_days=factory_run.duration_days,
                    initial_balance=factory_run.initial_balance,
                    challenge_firm=factory_run.challenge_firm,
                    weights={
                        "sharpe": 0.30,
                        "drawdown": 0.20,
                        "monte_carlo": 0.15,
                        "challenge": 0.15,
                        "regime": 0.10,
                        "profit_factor": 0.10,
                    },
                    mock_generator=mock_generator,
                    perf_calculator=performance_calculator,
                    strategy_scorer=strategy_scorer,
                    candles=candles,
                    template_id=tmpl_id.value,
                )

                for strat in strategies:
                    genome = StrategyGenome(genes=strat.genes)
                    evaluator.evaluate(genome)

                    strat.fitness = genome.fitness
                    strat.sharpe_ratio = genome.sharpe_ratio
                    strat.max_drawdown_pct = genome.max_drawdown_pct
                    strat.profit_factor = genome.profit_factor
                    strat.win_rate = genome.win_rate
                    strat.net_profit = genome.net_profit
                    strat.total_trades = genome.total_trades
                    strat.monte_carlo_score = genome.monte_carlo_score
                    strat.challenge_pass_pct = genome.challenge_pass_pct
                    strat.evaluated = True
                    factory_run.total_evaluated += 1

                all_strategies.extend(strategies)

            # Rank by fitness
            all_strategies.sort(key=lambda s: -s.fitness)
            factory_run.strategies = all_strategies
            factory_run.best_strategy = all_strategies[0] if all_strategies else None
            factory_run.status = FactoryStatus.COMPLETED

        except Exception as e:
            logger.error(f"Factory run failed: {e}")
            factory_run.status = FactoryStatus.FAILED
            factory_run.error_message = str(e)

        factory_run.execution_time_seconds = round(time.time() - start, 2)
        return factory_run
