"""
Genetic Algorithm Strategy Optimizer Engine
Evolves strategy parameters using selection, crossover, and mutation.
"""

import math
import random
import statistics
import logging
import time
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone

from optimizer_models import (
    ParamDef,
    ParamType,
    StrategyGenome,
    GenerationSummary,
    OptimizationResult,
    OptimizationStatus,
    DEFAULT_PARAMS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Genome Factory
# ---------------------------------------------------------------------------

class GenomeFactory:
    """Create and manipulate strategy genomes."""

    def __init__(self, param_defs: List[ParamDef]):
        self.params = param_defs

    def random_genome(self, generation: int = 0) -> StrategyGenome:
        genes = {}
        for p in self.params:
            val = random.uniform(p.min_val, p.max_val)
            if p.step:
                val = round(val / p.step) * p.step
            if p.param_type == ParamType.INT:
                val = int(round(val))
            genes[p.name] = val
        return StrategyGenome(genes=genes, generation=generation)

    def clamp(self, genes: Dict[str, float]) -> Dict[str, float]:
        """Clamp gene values to valid ranges."""
        out = {}
        for p in self.params:
            v = genes.get(p.name, (p.min_val + p.max_val) / 2)
            v = max(p.min_val, min(p.max_val, v))
            if p.step:
                v = round(v / p.step) * p.step
            if p.param_type == ParamType.INT:
                v = int(round(v))
            out[p.name] = v
        return out


# ---------------------------------------------------------------------------
# Fitness Evaluator
# ---------------------------------------------------------------------------

class FitnessEvaluator:
    """Evaluate a genome using the backtest + analysis pipeline."""

    def __init__(
        self,
        strategy_type: str,
        symbol: str,
        timeframe: str,
        duration_days: int,
        initial_balance: float,
        challenge_firm: str,
        weights: Dict[str, float],
        mock_generator,
        perf_calculator,
        strategy_scorer,
        candles=None,
        template_id: str = None,
    ):
        self.strategy_type = strategy_type
        self.symbol = symbol
        self.timeframe = timeframe
        self.duration_days = duration_days
        self.initial_balance = initial_balance
        self.challenge_firm = challenge_firm
        self.weights = weights
        self.mock_gen = mock_generator
        self.perf_calc = perf_calculator
        self.scorer = strategy_scorer
        self.candles = candles  # Real OHLCV candles (optional)
        self.template_id = template_id or strategy_type

    def evaluate(self, genome: StrategyGenome) -> float:
        """
        Run backtest with genome parameters, compute multi-factor fitness.
        Uses real candles when available, falls back to mock generator.
        Returns fitness score (higher = better).
        """
        genes = genome.genes
        seed = hash(tuple(sorted(genes.items()))) & 0xFFFFFFFF
        rng = random.Random(seed)

        if self.candles and len(self.candles) >= 60:
            # --- REAL BACKTESTING PATH ---
            from real_backtester import real_backtester
            trades_raw, equity, config = real_backtester.run(
                template_id=self.template_id,
                genes=genes,
                candles=self.candles,
                initial_balance=self.initial_balance,
            )
            modified_trades = trades_raw  # no mock modifiers needed
        else:
            # --- MOCK FALLBACK PATH ---
            quality = self._gene_quality(genes)
            random.seed(seed)
            from backtest_models import Timeframe
            tf = Timeframe(self.timeframe) if self.timeframe in [t.value for t in Timeframe] else Timeframe.H1
            trades, equity, config = self.mock_gen.generate_mock_backtest(
                bot_name=f"GA_{self.strategy_type}",
                symbol=self.symbol,
                timeframe=tf,
                duration_days=self.duration_days,
                initial_balance=self.initial_balance,
                strategy_type=self.strategy_type,
            )
            random.seed()
            modified_trades = self._apply_gene_modifiers(trades, genes, quality, rng)

        # Calculate performance
        metrics = self.perf_calc.calculate_metrics(modified_trades, equity, config)
        score = self.scorer.calculate_score(metrics)

        # Store metrics in genome
        genome.sharpe_ratio = metrics.sharpe_ratio
        genome.max_drawdown_pct = metrics.max_drawdown_percent
        genome.profit_factor = metrics.profit_factor
        genome.win_rate = metrics.win_rate
        genome.net_profit = metrics.net_profit
        genome.total_trades = metrics.total_trades

        # Monte Carlo score (simplified inline)
        mc_score = self._quick_monte_carlo(modified_trades, rng)
        genome.monte_carlo_score = mc_score

        # Challenge score (simplified inline)
        ch_score = self._quick_challenge_score(modified_trades, rng)
        genome.challenge_pass_pct = ch_score

        # Regime consistency
        regime_score = self._quick_regime_consistency(modified_trades, rng)
        genome.regime_consistency = regime_score

        # Multi-factor fitness
        w = self.weights
        sharpe_norm = min(max(metrics.sharpe_ratio, 0) / 3.0, 1.0) * 100
        dd_norm = max(0, (20 - metrics.max_drawdown_percent) / 20) * 100
        pf_norm = min(metrics.profit_factor / 3.0, 1.0) * 100

        fitness = (
            sharpe_norm * w.get("sharpe", 0.30)
            + dd_norm * w.get("drawdown", 0.20)
            + mc_score * w.get("monte_carlo", 0.15)
            + ch_score * w.get("challenge", 0.15)
            + regime_score * w.get("regime", 0.10)
            + pf_norm * w.get("profit_factor", 0.10)
        )

        genome.fitness = round(fitness, 2)
        return genome.fitness

    def _gene_quality(self, genes: Dict[str, float]) -> float:
        """Derive a quality factor from gene interactions (0-1)."""
        quality = 0.5

        # Trend following: fast < slow is good
        if "fast_ma_period" in genes and "slow_ma_period" in genes:
            gap = genes["slow_ma_period"] - genes["fast_ma_period"]
            if gap > 10:
                quality += 0.15
            elif gap <= 0:
                quality -= 0.2

        # Risk-reward balance
        sl = genes.get("stop_loss_atr_mult", genes.get("stop_loss_pct", genes.get("stop_loss_pips", 1)))
        tp = genes.get("take_profit_atr_mult", genes.get("take_profit_pct", genes.get("take_profit_pips", 2)))
        if tp > 0 and sl > 0:
            rr = tp / sl
            if 1.5 <= rr <= 4:
                quality += 0.1
            elif rr < 0.8:
                quality -= 0.15

        # Mean reversion: RSI oversold < overbought
        if "rsi_oversold" in genes and "rsi_overbought" in genes:
            if genes["rsi_overbought"] - genes["rsi_oversold"] > 25:
                quality += 0.1
            elif genes["rsi_overbought"] <= genes["rsi_oversold"]:
                quality -= 0.25

        # Risk per trade
        risk = genes.get("risk_per_trade_pct", 1.0)
        if 0.5 <= risk <= 1.5:
            quality += 0.05
        elif risk > 2.5:
            quality -= 0.1

        return max(0.05, min(0.95, quality))

    def _apply_gene_modifiers(self, trades, genes, quality, rng):
        """Modify trade PnLs based on genome quality."""
        for t in trades:
            if t.profit_loss is not None:
                modifier = 0.5 + quality  # 0.55 to 1.45
                noise = rng.gauss(1.0, 0.05)
                t.profit_loss = t.profit_loss * modifier * noise
                if t.profit_loss_percent is not None:
                    t.profit_loss_percent = t.profit_loss_percent * modifier * noise
        return trades

    def _quick_monte_carlo(self, trades, rng) -> float:
        """Fast MC estimate (100 shuffles, not full engine)."""
        pnls = [t.profit_loss for t in trades if t.profit_loss is not None]
        if not pnls:
            return 0
        initial = self.initial_balance
        profitable = 0
        for _ in range(100):
            shuffled = pnls.copy()
            rng.shuffle(shuffled)
            bal = initial
            for p in shuffled:
                bal += p
            if bal > initial:
                profitable += 1
        return profitable  # 0-100

    def _quick_challenge_score(self, trades, rng) -> float:
        """Fast challenge estimate: can strategy hit 10% in time?"""
        pnls = [t.profit_loss for t in trades if t.profit_loss is not None]
        if not pnls:
            return 0
        target = self.initial_balance * 0.10
        dd_limit = self.initial_balance * 0.10
        passes = 0
        for _ in range(100):
            shuffled = pnls.copy()
            rng.shuffle(shuffled)
            bal = self.initial_balance
            peak = self.initial_balance
            passed = False
            for p in shuffled:
                bal += p
                if bal > peak:
                    peak = bal
                if peak - bal > dd_limit:
                    break
                if bal - self.initial_balance >= target:
                    passed = True
                    break
            if passed:
                passes += 1
        return passes  # 0-100

    def _quick_regime_consistency(self, trades, rng) -> float:
        """Estimate regime consistency: low variance across random subsets."""
        pnls = [t.profit_loss for t in trades if t.profit_loss is not None]
        if len(pnls) < 10:
            return 50
        # Split into 4 "regimes" randomly and check consistency
        subset_profits = []
        for _ in range(4):
            subset = rng.sample(pnls, len(pnls) // 4)
            subset_profits.append(sum(1 for p in subset if p > 0) / len(subset) * 100)
        if not subset_profits:
            return 50
        std = statistics.stdev(subset_profits) if len(subset_profits) > 1 else 0
        # Lower variance = higher score
        return max(0, min(100, 100 - std * 3))


# ---------------------------------------------------------------------------
# Genetic Operators
# ---------------------------------------------------------------------------

class GeneticOperators:
    """Selection, crossover, mutation operators."""

    def __init__(self, factory: GenomeFactory, tournament_size: int = 3):
        self.factory = factory
        self.tournament_size = tournament_size

    def tournament_select(self, population: List[StrategyGenome]) -> StrategyGenome:
        """Select one individual via tournament selection."""
        contestants = random.sample(population, min(self.tournament_size, len(population)))
        return max(contestants, key=lambda g: g.fitness)

    def crossover(
        self, parent_a: StrategyGenome, parent_b: StrategyGenome, generation: int
    ) -> Tuple[StrategyGenome, StrategyGenome]:
        """Uniform crossover between two parents."""
        genes_a, genes_b = {}, {}
        for p in self.factory.params:
            if random.random() < 0.5:
                genes_a[p.name] = parent_a.genes[p.name]
                genes_b[p.name] = parent_b.genes[p.name]
            else:
                genes_a[p.name] = parent_b.genes[p.name]
                genes_b[p.name] = parent_a.genes[p.name]
        return (
            StrategyGenome(genes=self.factory.clamp(genes_a), generation=generation),
            StrategyGenome(genes=self.factory.clamp(genes_b), generation=generation),
        )

    def mutate(
        self, genome: StrategyGenome, rate: float, strength: float
    ) -> StrategyGenome:
        """Gaussian mutation on random genes."""
        genes = dict(genome.genes)
        for p in self.factory.params:
            if random.random() < rate:
                rng_span = p.max_val - p.min_val
                delta = random.gauss(0, rng_span * strength)
                genes[p.name] = genes[p.name] + delta
        genome.genes = self.factory.clamp(genes)
        return genome


# ---------------------------------------------------------------------------
# GA Optimizer
# ---------------------------------------------------------------------------

class GeneticOptimizer:
    """Main evolutionary optimization loop."""

    def __init__(
        self,
        param_defs: List[ParamDef],
        evaluator: FitnessEvaluator,
        population_size: int = 30,
        num_generations: int = 20,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.15,
        mutation_strength: float = 0.2,
        elite_count: int = 3,
        tournament_size: int = 3,
    ):
        self.factory = GenomeFactory(param_defs)
        self.evaluator = evaluator
        self.ops = GeneticOperators(self.factory, tournament_size)
        self.pop_size = population_size
        self.n_gen = num_generations
        self.cx_rate = crossover_rate
        self.mut_rate = mutation_rate
        self.mut_strength = mutation_strength
        self.elite_count = min(elite_count, population_size)

    def run(self, result: OptimizationResult) -> OptimizationResult:
        """Execute the full evolutionary optimization."""
        start = time.time()
        result.status = OptimizationStatus.RUNNING

        try:
            # Initialize population
            population = [self.factory.random_genome(0) for _ in range(self.pop_size)]

            # Evaluate initial population
            for g in population:
                self.evaluator.evaluate(g)
                result.total_evaluations += 1

            result.generation_history.append(self._summarise(population, 0))
            result.current_generation = 0

            # Evolution loop
            for gen in range(1, self.n_gen + 1):
                population = self._evolve(population, gen)

                # Evaluate new individuals (non-elites only evaluated above in _evolve)
                for g in population:
                    if g.fitness == 0:
                        self.evaluator.evaluate(g)
                        result.total_evaluations += 1

                result.generation_history.append(self._summarise(population, gen))
                result.current_generation = gen

            # Final results
            ranked = sorted(population, key=lambda g: -g.fitness)
            result.best_genome = ranked[0]
            result.top_genomes = ranked[:min(10, len(ranked))]
            result.status = OptimizationStatus.COMPLETED
            result.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            result.status = OptimizationStatus.FAILED
            result.error_message = str(e)

        result.execution_time_seconds = round(time.time() - start, 2)
        return result

    def _evolve(self, population: List[StrategyGenome], gen: int) -> List[StrategyGenome]:
        """Create next generation."""
        ranked = sorted(population, key=lambda g: -g.fitness)

        # Elitism: carry over best unchanged
        next_gen = ranked[:self.elite_count]

        # Fill rest with crossover + mutation
        while len(next_gen) < self.pop_size:
            if random.random() < self.cx_rate and len(population) >= 2:
                p1 = self.ops.tournament_select(population)
                p2 = self.ops.tournament_select(population)
                c1, c2 = self.ops.crossover(p1, p2, gen)
                c1 = self.ops.mutate(c1, self.mut_rate, self.mut_strength)
                c2 = self.ops.mutate(c2, self.mut_rate, self.mut_strength)
                # Evaluate inline
                self.evaluator.evaluate(c1)
                self.evaluator.evaluate(c2)
                next_gen.append(c1)
                if len(next_gen) < self.pop_size:
                    next_gen.append(c2)
            else:
                mutant = self.factory.random_genome(gen)
                self.evaluator.evaluate(mutant)
                next_gen.append(mutant)

        return next_gen[:self.pop_size]

    @staticmethod
    def _summarise(population: List[StrategyGenome], gen: int) -> GenerationSummary:
        fitnesses = [g.fitness for g in population]
        # Diversity: average coefficient of variation across genes
        if population and population[0].genes:
            gene_stds = []
            for key in population[0].genes:
                vals = [g.genes.get(key, 0) for g in population]
                mean = statistics.mean(vals) if vals else 1
                std = statistics.stdev(vals) if len(vals) > 1 else 0
                gene_stds.append(std / abs(mean) if mean != 0 else 0)
            diversity = round(statistics.mean(gene_stds) * 100, 2) if gene_stds else 0
        else:
            diversity = 0

        return GenerationSummary(
            generation=gen,
            population_size=len(population),
            best_fitness=round(max(fitnesses), 2),
            avg_fitness=round(statistics.mean(fitnesses), 2),
            worst_fitness=round(min(fitnesses), 2),
            best_sharpe=round(max(g.sharpe_ratio for g in population), 2),
            best_drawdown=round(min(g.max_drawdown_pct for g in population), 2),
            diversity=diversity,
        )
