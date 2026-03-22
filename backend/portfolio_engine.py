"""
Portfolio Strategy Engine
Phase 7: Correlation Analysis, Portfolio Backtesting, Monte Carlo, Allocation Optimization
"""

import math
import random
import statistics
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone

from backtest_models import TradeRecord, TradeStatus, EquityPoint
from portfolio_models import (
    PortfolioStrategy,
    CorrelationPair,
    CorrelationResult,
    PortfolioEquityPoint,
    PortfolioPerformanceMetrics,
    PortfolioBacktestResult,
    PortfolioMonteCarloResult,
    AllocationResult,
    AllocationMethod,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Correlation Analysis
# ---------------------------------------------------------------------------

class CorrelationAnalyzer:
    """Analyze correlations between strategy return streams."""

    @staticmethod
    def pearson(x: List[float], y: List[float]) -> float:
        """Pearson correlation coefficient for two equal-length series."""
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
        x, y = x[:n], y[:n]
        mx = sum(x) / n
        my = sum(y) / n
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if sx == 0 or sy == 0:
            return 0.0
        return cov / (sx * sy)

    @staticmethod
    def interpret(r: float) -> str:
        ar = abs(r)
        if ar >= 0.7:
            return "strong_positive" if r > 0 else "strong_negative"
        if ar >= 0.4:
            return "moderate_positive" if r > 0 else "moderate_negative"
        if ar >= 0.2:
            return "weak_positive" if r > 0 else "weak_negative"
        return "uncorrelated"

    def analyze(self, strategies: List[PortfolioStrategy]) -> CorrelationResult:
        pairs: List[CorrelationPair] = []
        matrix: Dict[str, Dict[str, float]] = {}
        correlations: List[float] = []

        for s in strategies:
            matrix[s.name] = {}

        for i, sa in enumerate(strategies):
            for j, sb in enumerate(strategies):
                if i == j:
                    matrix[sa.name][sb.name] = 1.0
                    continue
                if j < i:
                    matrix[sa.name][sb.name] = matrix[sb.name][sa.name]
                    continue
                r = self.pearson(sa.daily_returns, sb.daily_returns)
                r = round(r, 4)
                matrix[sa.name][sb.name] = r
                matrix[sb.name][sa.name] = r
                pairs.append(CorrelationPair(
                    strategy_a=sa.name,
                    strategy_b=sb.name,
                    correlation=r,
                    interpretation=self.interpret(r),
                ))
                correlations.append(r)

        avg_corr = statistics.mean(correlations) if correlations else 0.0
        # Diversification score: lower avg correlation = higher score
        div_score = max(0, min(100, (1 - avg_corr) * 100))

        recs: List[str] = []
        high_pairs = [p for p in pairs if p.correlation > 0.7]
        if high_pairs:
            names = ", ".join(f"{p.strategy_a}/{p.strategy_b}" for p in high_pairs[:3])
            recs.append(f"High correlation detected: {names}. Consider replacing one strategy.")
        neg_pairs = [p for p in pairs if p.correlation < -0.3]
        if neg_pairs:
            recs.append("Negative correlations found - good diversification potential.")
        if div_score < 50:
            recs.append("Portfolio diversification is low. Add uncorrelated strategies.")
        if div_score >= 70:
            recs.append("Portfolio is well-diversified.")

        return CorrelationResult(
            portfolio_id="",
            pairs=pairs,
            matrix=matrix,
            average_correlation=round(avg_corr, 4),
            diversification_score=round(div_score, 1),
            recommendations=recs,
        )


# ---------------------------------------------------------------------------
# Portfolio Backtester
# ---------------------------------------------------------------------------

class PortfolioBacktester:
    """Backtest a portfolio of strategies by combining weighted trade streams."""

    def run(
        self,
        strategies: List[PortfolioStrategy],
        all_trades: Dict[str, List[TradeRecord]],
        all_equity: Dict[str, List[EquityPoint]],
        initial_balance: float,
    ) -> PortfolioBacktestResult:
        start = datetime.now()

        # Combine trades weighted by allocation
        combined_pnl: List[Tuple[str, float, str]] = []  # (timestamp_iso, pnl, strategy_name)
        strategy_results = []

        for strat in strategies:
            trades = all_trades.get(strat.backtest_id, [])
            closed = [t for t in trades if t.status == TradeStatus.CLOSED and t.profit_loss is not None]
            strat_pnl = sum(t.profit_loss for t in closed) * strat.weight
            strat_trades = len(closed)

            strategy_results.append({
                "name": strat.name,
                "weight": round(strat.weight, 4),
                "weight_percent": round(strat.weight * 100, 1),
                "net_profit": round(strat_pnl, 2),
                "total_trades": strat_trades,
                "contribution_percent": 0.0,  # filled later
            })

            for t in closed:
                ts = t.exit_time.isoformat() if t.exit_time else t.entry_time.isoformat()
                combined_pnl.append((ts, t.profit_loss * strat.weight, strat.name))

        # Sort by timestamp
        combined_pnl.sort(key=lambda x: x[0])

        # Build portfolio equity curve
        balance = initial_balance
        peak = initial_balance
        max_dd = 0.0
        max_dd_pct = 0.0
        drawdowns: List[float] = []
        equity_curve: List[PortfolioEquityPoint] = []
        contributions: Dict[str, float] = {s.name: 0.0 for s in strategies}
        trade_pnls: List[float] = []
        winners = 0
        total_closed = 0

        for ts, pnl, sname in combined_pnl:
            balance += pnl
            contributions[sname] = contributions.get(sname, 0.0) + pnl
            trade_pnls.append(pnl)
            total_closed += 1
            if pnl > 0:
                winners += 1

            if balance > peak:
                peak = balance
            dd = peak - balance
            dd_pct = (dd / peak * 100) if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
            if dd_pct > 0:
                drawdowns.append(dd_pct)

            equity_curve.append(PortfolioEquityPoint(
                timestamp=ts,
                balance=round(balance, 2),
                drawdown_percent=round(dd_pct, 2),
                strategy_contributions={k: round(v, 2) for k, v in contributions.items()},
            ))

        net_profit = balance - initial_balance
        total_return_pct = (net_profit / initial_balance) * 100 if initial_balance > 0 else 0
        avg_dd_pct = statistics.mean(drawdowns) if drawdowns else 0.0
        win_rate = (winners / total_closed * 100) if total_closed > 0 else 0

        gross_profit = sum(p for p in trade_pnls if p > 0)
        gross_loss = abs(sum(p for p in trade_pnls if p < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

        sharpe = self._sharpe(trade_pnls, initial_balance)
        sortino = self._sortino(trade_pnls, initial_balance)
        calmar = (total_return_pct / max_dd_pct) if max_dd_pct > 0 else 0

        # Diversification ratio
        weighted_vols = []
        for strat in strategies:
            if strat.daily_returns:
                vol = statistics.stdev(strat.daily_returns) if len(strat.daily_returns) > 1 else 0
                weighted_vols.append(strat.weight * vol)
        weighted_avg_vol = sum(weighted_vols) if weighted_vols else 1.0

        # Portfolio vol from combined returns
        if trade_pnls and len(trade_pnls) > 1:
            port_returns = [p / initial_balance for p in trade_pnls]
            port_vol = statistics.stdev(port_returns)
        else:
            port_vol = weighted_avg_vol

        div_ratio = weighted_avg_vol / port_vol if port_vol > 0 else 1.0

        # Score (simple weighted)
        pf_score_raw = min(profit_factor / 3.0, 1.0) * 30
        dd_score_raw = max(0, (30 - max_dd_pct) / 30) * 30
        wr_score_raw = min(win_rate / 80, 1.0) * 20
        sr_score_raw = min(max(sharpe, 0) / 3.0, 1.0) * 20
        portfolio_score = round(pf_score_raw + dd_score_raw + wr_score_raw + sr_score_raw, 1)

        # Fill contribution percentages
        for sr in strategy_results:
            sr["contribution_percent"] = round((sr["net_profit"] / net_profit) * 100, 1) if net_profit != 0 else 0.0

        grade = self._grade(portfolio_score)

        metrics = PortfolioPerformanceMetrics(
            net_profit=round(net_profit, 2),
            total_return_percent=round(total_return_pct, 2),
            profit_factor=round(profit_factor, 4),
            max_drawdown=round(max_dd, 2),
            max_drawdown_percent=round(max_dd_pct, 2),
            average_drawdown_percent=round(avg_dd_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            calmar_ratio=round(calmar, 2),
            total_trades=total_closed,
            win_rate=round(win_rate, 2),
            diversification_ratio=round(div_ratio, 4),
            portfolio_score=portfolio_score,
        )

        exec_time = (datetime.now() - start).total_seconds()

        return PortfolioBacktestResult(
            portfolio_id="",
            session_id="",
            initial_balance=initial_balance,
            strategy_count=len(strategies),
            strategy_results=strategy_results,
            metrics=metrics,
            equity_curve=equity_curve,
            grade=grade,
            is_deployable=portfolio_score >= 70,
            execution_time_seconds=round(exec_time, 3),
        )

    # helpers
    def _sharpe(self, pnls: List[float], balance: float) -> float:
        if len(pnls) < 2:
            return 0.0
        rets = [p / balance for p in pnls]
        avg = statistics.mean(rets)
        sd = statistics.stdev(rets)
        return (avg / sd) * math.sqrt(252) if sd > 0 else 0.0

    def _sortino(self, pnls: List[float], balance: float) -> float:
        if len(pnls) < 2:
            return 0.0
        rets = [p / balance for p in pnls]
        avg = statistics.mean(rets)
        neg = [r for r in rets if r < 0]
        if not neg:
            return 0.0
        dsd = math.sqrt(sum(r ** 2 for r in neg) / len(neg))
        return (avg / dsd) * math.sqrt(252) if dsd > 0 else 0.0

    def _grade(self, score: float) -> str:
        if score >= 90:
            return "S"
        if score >= 80:
            return "A"
        if score >= 70:
            return "B"
        if score >= 60:
            return "C"
        if score >= 50:
            return "D"
        return "F"


# ---------------------------------------------------------------------------
# Portfolio Monte Carlo
# ---------------------------------------------------------------------------

class PortfolioMonteCarloEngine:
    """Run Monte Carlo on the combined portfolio trade stream."""

    def run(
        self,
        strategies: List[PortfolioStrategy],
        all_trades: Dict[str, List[TradeRecord]],
        initial_balance: float,
        num_simulations: int = 1000,
        ruin_threshold_pct: float = 50.0,
    ) -> PortfolioMonteCarloResult:
        start = datetime.now()

        # Build weighted pnl list
        pnls: List[float] = []
        for strat in strategies:
            trades = all_trades.get(strat.backtest_id, [])
            for t in trades:
                if t.status == TradeStatus.CLOSED and t.profit_loss is not None:
                    pnls.append(t.profit_loss * strat.weight)

        if not pnls:
            return self._empty_result(initial_balance, num_simulations)

        ruin_threshold = initial_balance * (1 - ruin_threshold_pct / 100)
        final_balances: List[float] = []
        max_drawdowns: List[float] = []
        profitable = 0
        ruined = 0

        for _ in range(num_simulations):
            shuffled = pnls.copy()
            random.shuffle(shuffled)
            bal = initial_balance
            peak = initial_balance
            mdd_pct = 0.0
            for p in shuffled:
                bal += p
                if bal > peak:
                    peak = bal
                dd_pct = ((peak - bal) / peak * 100) if peak > 0 else 0
                if dd_pct > mdd_pct:
                    mdd_pct = dd_pct

            final_balances.append(bal)
            max_drawdowns.append(mdd_pct)
            if bal > initial_balance:
                profitable += 1
            if bal < ruin_threshold:
                ruined += 1

        n = len(final_balances)
        sorted_bal = sorted(final_balances)
        sorted_dd = sorted(max_drawdowns)
        returns = [(b - initial_balance) / initial_balance * 100 for b in final_balances]
        sorted_ret = sorted(returns)

        profit_prob = (profitable / n) * 100
        ruin_prob = (ruined / n) * 100
        avg_return = statistics.mean(returns)
        avg_dd = statistics.mean(max_drawdowns)
        worst_dd = max(max_drawdowns)

        ci_lo_idx = int(n * 0.025)
        ci_hi_idx = min(int(n * 0.975), n - 1)

        # Score
        dd_score = max(0, min(100, (1 - (sorted_dd[ci_hi_idx] / 50)) * 100))
        profit_score = min(profit_prob, 100)
        ruin_score = max(0, 100 - ruin_prob * 5)
        total_score = round(dd_score * 0.4 + profit_score * 0.4 + ruin_score * 0.2, 1)

        grade = "S" if total_score >= 90 else "A" if total_score >= 80 else "B" if total_score >= 70 else "C" if total_score >= 60 else "D" if total_score >= 50 else "F"
        risk_level = "Low" if total_score >= 80 else "Medium" if total_score >= 65 else "High" if total_score >= 50 else "Very High"

        strengths, weaknesses, recs = [], [], []
        if profit_prob >= 80:
            strengths.append(f"High portfolio profit probability ({profit_prob:.1f}%)")
        elif profit_prob < 60:
            weaknesses.append(f"Low portfolio profit probability ({profit_prob:.1f}%)")
            recs.append("Consider reducing allocation to weak strategies")
        if ruin_prob < 2:
            strengths.append(f"Very low portfolio ruin risk ({ruin_prob:.1f}%)")
        elif ruin_prob > 10:
            weaknesses.append(f"Elevated ruin risk ({ruin_prob:.1f}%)")
            recs.append("Reduce overall portfolio leverage")
        if worst_dd < 20:
            strengths.append("Controlled worst-case drawdown")
        if total_score >= 70:
            strengths.append("Portfolio passes Monte Carlo robustness test")
        else:
            recs.append("Portfolio robustness below threshold")

        exec_time = (datetime.now() - start).total_seconds()

        return PortfolioMonteCarloResult(
            portfolio_id="",
            session_id="",
            num_simulations=num_simulations,
            initial_balance=initial_balance,
            profit_probability=round(profit_prob, 2),
            ruin_probability=round(ruin_prob, 2),
            expected_return_percent=round(avg_return, 2),
            worst_case_drawdown=round(worst_dd, 2),
            average_drawdown=round(avg_dd, 2),
            balance_ci_lower=round(sorted_bal[ci_lo_idx], 2),
            balance_ci_upper=round(sorted_bal[ci_hi_idx], 2),
            return_ci_lower=round(sorted_ret[ci_lo_idx], 2),
            return_ci_upper=round(sorted_ret[ci_hi_idx], 2),
            robustness_score=total_score,
            grade=grade,
            risk_level=risk_level,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recs,
            execution_time_seconds=round(exec_time, 3),
        )

    def _empty_result(self, balance: float, n: int) -> PortfolioMonteCarloResult:
        return PortfolioMonteCarloResult(
            portfolio_id="", session_id="",
            num_simulations=n, initial_balance=balance,
            profit_probability=0, ruin_probability=0, expected_return_percent=0,
            worst_case_drawdown=0, average_drawdown=0,
            balance_ci_lower=balance, balance_ci_upper=balance,
            return_ci_lower=0, return_ci_upper=0,
            robustness_score=0, grade="F", risk_level="Very High",
            strengths=[], weaknesses=["No trades to simulate"],
            recommendations=["Add strategies with completed backtests"],
        )


# ---------------------------------------------------------------------------
# Allocation Optimizer
# ---------------------------------------------------------------------------

class AllocationOptimizer:
    """Optimize portfolio allocation weights."""

    def optimize(
        self,
        strategies: List[PortfolioStrategy],
        method: AllocationMethod,
        all_trades: Dict[str, List[TradeRecord]],
        initial_balance: float,
    ) -> AllocationResult:

        n = len(strategies)
        if n == 0:
            return self._empty(method)

        # Build return vectors
        returns_map: Dict[str, List[float]] = {}
        for s in strategies:
            trades = all_trades.get(s.backtest_id, [])
            pnls = [t.profit_loss for t in trades if t.status == TradeStatus.CLOSED and t.profit_loss is not None]
            returns_map[s.name] = [p / initial_balance for p in pnls] if pnls else [0.0]

        if method == AllocationMethod.EQUAL_WEIGHT:
            weights = {s.name: 1.0 / n for s in strategies}
        elif method == AllocationMethod.RISK_PARITY:
            weights = self._risk_parity(strategies, returns_map)
        elif method == AllocationMethod.MIN_VARIANCE:
            weights = self._min_variance(strategies, returns_map)
        elif method == AllocationMethod.MAX_DIVERSIFICATION:
            weights = self._max_diversification(strategies, returns_map)
        else:  # MAX_SHARPE
            weights = self._max_sharpe(strategies, returns_map)

        # Evaluate with these weights
        exp_ret, exp_vol, exp_sharpe = self._evaluate_weights(strategies, returns_map, weights)

        # Compare vs equal
        eq_w = {s.name: 1.0 / n for s in strategies}
        _, _, eq_sharpe = self._evaluate_weights(strategies, returns_map, eq_w)
        improvement = ((exp_sharpe - eq_sharpe) / abs(eq_sharpe) * 100) if eq_sharpe != 0 else 0

        recs = []
        max_w_name = max(weights, key=weights.get)
        min_w_name = min(weights, key=weights.get)
        recs.append(f"Highest allocation: {max_w_name} ({weights[max_w_name]*100:.1f}%)")
        recs.append(f"Lowest allocation: {min_w_name} ({weights[min_w_name]*100:.1f}%)")
        if improvement > 5:
            recs.append(f"Optimized allocation improves Sharpe by {improvement:.1f}% vs equal weight")
        else:
            recs.append("Equal weight allocation performs similarly to optimized")

        return AllocationResult(
            portfolio_id="",
            method=method,
            weights={k: round(v, 4) for k, v in weights.items()},
            expected_return=round(exp_ret * 100, 2),
            expected_volatility=round(exp_vol * 100, 2),
            expected_sharpe=round(exp_sharpe, 4),
            expected_max_drawdown=round(exp_vol * 2 * 100, 2),  # approximation
            improvement_vs_equal=round(improvement, 2),
            recommendations=recs,
        )

    # --- optimization methods ---

    def _risk_parity(self, strategies: List[PortfolioStrategy], returns_map: Dict[str, List[float]]) -> Dict[str, float]:
        """Allocate inversely proportional to volatility."""
        vols = {}
        for s in strategies:
            rets = returns_map.get(s.name, [0.0])
            vols[s.name] = statistics.stdev(rets) if len(rets) > 1 else 1.0
        inv_vols = {k: 1.0 / v if v > 0 else 1.0 for k, v in vols.items()}
        total = sum(inv_vols.values())
        return {k: v / total for k, v in inv_vols.items()}

    def _min_variance(self, strategies: List[PortfolioStrategy], returns_map: Dict[str, List[float]]) -> Dict[str, float]:
        """Minimize portfolio variance using grid search."""
        return self._grid_optimize(strategies, returns_map, objective="min_vol")

    def _max_sharpe(self, strategies: List[PortfolioStrategy], returns_map: Dict[str, List[float]]) -> Dict[str, float]:
        """Maximize Sharpe ratio using grid search."""
        return self._grid_optimize(strategies, returns_map, objective="max_sharpe")

    def _max_diversification(self, strategies: List[PortfolioStrategy], returns_map: Dict[str, List[float]]) -> Dict[str, float]:
        """Maximize diversification ratio."""
        return self._grid_optimize(strategies, returns_map, objective="max_div")

    def _grid_optimize(
        self,
        strategies: List[PortfolioStrategy],
        returns_map: Dict[str, List[float]],
        objective: str,
        num_samples: int = 500,
    ) -> Dict[str, float]:
        """Monte Carlo grid search for optimal weights."""
        n = len(strategies)
        if n == 1:
            return {strategies[0].name: 1.0}

        # Pre-compute aligned returns matrix for speed
        names = [s.name for s in strategies]
        max_len = max(len(returns_map.get(nm, [0.0])) for nm in names)
        if max_len == 0:
            return {nm: 1.0 / n for nm in names}

        # Build aligned returns as lists
        aligned = []
        strat_vols = []
        for nm in names:
            rets = returns_map.get(nm, [0.0])
            padded = [rets[i % len(rets)] for i in range(max_len)]
            aligned.append(padded)
            strat_vols.append(statistics.stdev(padded) if len(padded) > 1 else 0.01)

        best_weights = {nm: 1.0 / n for nm in names}
        best_metric = float('-inf') if objective != "min_vol" else float('inf')

        for _ in range(num_samples):
            raw = [random.random() for _ in range(n)]
            total = sum(raw)
            w_list = [raw[i] / total for i in range(n)]

            # Fast portfolio returns computation
            port_returns = [0.0] * max_len
            for si in range(n):
                wi = w_list[si]
                strat_rets = aligned[si]
                for j in range(max_len):
                    port_returns[j] += wi * strat_rets[j]

            avg_ret = sum(port_returns) / max_len
            var = sum((r - avg_ret) ** 2 for r in port_returns) / (max_len - 1) if max_len > 1 else 0.0001
            vol = math.sqrt(var) if var > 0 else 0.0001
            sharpe = (avg_ret / vol) * math.sqrt(252) if vol > 0 else 0

            if objective == "max_sharpe":
                if sharpe > best_metric:
                    best_metric = sharpe
                    best_weights = {names[i]: w_list[i] for i in range(n)}
            elif objective == "min_vol":
                if vol < best_metric:
                    best_metric = vol
                    best_weights = {names[i]: w_list[i] for i in range(n)}
            elif objective == "max_div":
                wav = sum(w_list[i] * strat_vols[i] for i in range(n))
                div_ratio = wav / vol if vol > 0 else 0
                if div_ratio > best_metric:
                    best_metric = div_ratio
                    best_weights = {names[i]: w_list[i] for i in range(n)}

        return best_weights

    def _evaluate_weights(
        self,
        strategies: List[PortfolioStrategy],
        returns_map: Dict[str, List[float]],
        weights: Dict[str, float],
    ) -> Tuple[float, float, float]:
        """Return (expected_return, volatility, sharpe) for given weights."""
        # Align all series to same length
        max_len = max(len(r) for r in returns_map.values()) if returns_map else 0
        if max_len == 0:
            return 0.0, 0.01, 0.0

        port_returns: List[float] = []
        for i in range(max_len):
            r = 0.0
            for s in strategies:
                rets = returns_map.get(s.name, [0.0])
                idx = i % len(rets)  # wrap around if unequal lengths
                r += weights.get(s.name, 0) * rets[idx]
            port_returns.append(r)

        avg_ret = statistics.mean(port_returns)
        vol = statistics.stdev(port_returns) if len(port_returns) > 1 else 0.01
        sharpe = (avg_ret / vol) * math.sqrt(252) if vol > 0 else 0
        return avg_ret, vol, sharpe

    def _empty(self, method: AllocationMethod) -> AllocationResult:
        return AllocationResult(
            portfolio_id="", method=method, weights={},
            expected_return=0, expected_volatility=0, expected_sharpe=0,
            expected_max_drawdown=0, improvement_vs_equal=0,
            recommendations=["Add strategies to optimize"],
        )


# ---------------------------------------------------------------------------
# Daily returns extractor (from equity curve)
# ---------------------------------------------------------------------------

def extract_daily_returns(equity_curve: List[Dict]) -> List[float]:
    """Extract daily percentage returns from an equity curve."""
    if not equity_curve or len(equity_curve) < 2:
        return []
    returns = []
    prev_bal = equity_curve[0].get("balance", 0)
    for pt in equity_curve[1:]:
        bal = pt.get("balance", prev_bal)
        if prev_bal > 0:
            returns.append((bal - prev_bal) / prev_bal)
        prev_bal = bal
    return returns
