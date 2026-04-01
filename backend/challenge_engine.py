"""
Prop Firm Challenge Simulator Engine
Runs Monte Carlo simulations of prop firm challenges using backtest trade data.
"""

import math
import random
import statistics
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from backtest_models import TradeRecord, TradeStatus
from challenge_models import (
    ChallengeFirm,
    ChallengePhase,
    ChallengeRules,
    DayResult,
    SimulationOutcome,
    ChallengeSimulationResult,
    FullChallengeResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Challenge rule definitions for every firm + phase
# ---------------------------------------------------------------------------

CHALLENGE_RULES: Dict[str, List[ChallengeRules]] = {
    "ftmo": [
        ChallengeRules(
            firm=ChallengeFirm.FTMO, phase=ChallengePhase.PHASE_1,
            label="FTMO Challenge",
            profit_target_pct=10.0, daily_loss_limit_pct=5.0,
            max_drawdown_pct=10.0, min_trading_days=4, time_limit_days=30,
            trailing_drawdown=False,
        ),
        ChallengeRules(
            firm=ChallengeFirm.FTMO, phase=ChallengePhase.PHASE_2,
            label="FTMO Verification",
            profit_target_pct=5.0, daily_loss_limit_pct=5.0,
            max_drawdown_pct=10.0, min_trading_days=4, time_limit_days=60,
            trailing_drawdown=False,
        ),
    ],
    "fundednext": [
        ChallengeRules(
            firm=ChallengeFirm.FUNDED_NEXT, phase=ChallengePhase.PHASE_1,
            label="FundedNext Evaluation",
            profit_target_pct=10.0, daily_loss_limit_pct=5.0,
            max_drawdown_pct=10.0, min_trading_days=5, time_limit_days=30,
            trailing_drawdown=False,
        ),
        ChallengeRules(
            firm=ChallengeFirm.FUNDED_NEXT, phase=ChallengePhase.PHASE_2,
            label="FundedNext Verification",
            profit_target_pct=5.0, daily_loss_limit_pct=5.0,
            max_drawdown_pct=10.0, min_trading_days=5, time_limit_days=60,
            trailing_drawdown=False,
        ),
    ],
    "the5ers": [
        ChallengeRules(
            firm=ChallengeFirm.THE5ERS, phase=ChallengePhase.PHASE_1,
            label="The5ers Hyper Growth",
            profit_target_pct=8.0, daily_loss_limit_pct=4.0,
            max_drawdown_pct=6.0, min_trading_days=3, time_limit_days=60,
            trailing_drawdown=True,
        ),
        ChallengeRules(
            firm=ChallengeFirm.THE5ERS, phase=ChallengePhase.PHASE_2,
            label="The5ers Verification",
            profit_target_pct=5.0, daily_loss_limit_pct=4.0,
            max_drawdown_pct=6.0, min_trading_days=3, time_limit_days=60,
            trailing_drawdown=True,
        ),
    ],
    "pipfarm": [
        ChallengeRules(
            firm=ChallengeFirm.PIPFARM, phase=ChallengePhase.PHASE_1,
            label="PipFarm Evaluation",
            profit_target_pct=10.0, daily_loss_limit_pct=4.0,
            max_drawdown_pct=8.0, min_trading_days=5, time_limit_days=30,
            trailing_drawdown=False,
            news_trading_allowed=False,
        ),
        ChallengeRules(
            firm=ChallengeFirm.PIPFARM, phase=ChallengePhase.PHASE_2,
            label="PipFarm Verification",
            profit_target_pct=5.0, daily_loss_limit_pct=4.0,
            max_drawdown_pct=8.0, min_trading_days=5, time_limit_days=45,
            trailing_drawdown=False,
            news_trading_allowed=False,
        ),
    ],
}


def get_challenge_rules(firm: str) -> List[ChallengeRules]:
    key = firm.lower()
    if key not in CHALLENGE_RULES:
        raise ValueError(f"Unknown firm: {firm}. Available: {list(CHALLENGE_RULES.keys())}")
    return CHALLENGE_RULES[key]


# ---------------------------------------------------------------------------
# Challenge Simulator
# ---------------------------------------------------------------------------

class ChallengeSimulator:
    """Simulate a single challenge phase using trade PnL data."""

    def __init__(self, rules: ChallengeRules, initial_balance: float):
        self.rules = rules
        self.initial_balance = initial_balance

    # ---------------------------------------------------------------
    # Core: simulate one run
    # ---------------------------------------------------------------

    def _run_one(self, daily_pnls: List[float], run_id: int) -> SimulationOutcome:
        """
        Simulate one complete challenge attempt.
        `daily_pnls` is a list of per-day PnL values (already shuffled).
        """
        r = self.rules
        bal = self.initial_balance
        peak = self.initial_balance
        target_balance = self.initial_balance * (1 + r.profit_target_pct / 100)
        daily_loss_abs = self.initial_balance * r.daily_loss_limit_pct / 100
        dd_abs = self.initial_balance * r.max_drawdown_pct / 100

        trading_days = 0
        max_dd_pct = 0.0
        max_daily_loss_pct = 0.0

        for day_idx, pnl in enumerate(daily_pnls):
            if day_idx >= r.time_limit_days:
                break

            # Only count as trading day if trades happened
            if pnl != 0:
                trading_days += 1

            day_start_bal = bal
            bal += pnl

            # Daily loss check (from day start)
            day_loss = max(0, day_start_bal - bal)
            day_loss_pct = (day_loss / self.initial_balance) * 100
            if day_loss_pct > max_daily_loss_pct:
                max_daily_loss_pct = day_loss_pct

            if day_loss > daily_loss_abs:
                return SimulationOutcome(
                    run_id=run_id, passed=False, final_balance=round(bal, 2),
                    peak_balance=round(peak, 2), max_drawdown_pct=round(max_dd_pct, 2),
                    max_daily_loss_pct=round(day_loss_pct, 2), trading_days=trading_days,
                    fail_reason="daily_loss",
                )

            # Peak / drawdown
            if r.trailing_drawdown:
                if bal > peak:
                    peak = bal
            else:
                if bal > peak:
                    peak = bal

            dd = peak - bal
            dd_pct = (dd / self.initial_balance) * 100
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

            if dd > dd_abs:
                return SimulationOutcome(
                    run_id=run_id, passed=False, final_balance=round(bal, 2),
                    peak_balance=round(peak, 2), max_drawdown_pct=round(max_dd_pct, 2),
                    max_daily_loss_pct=round(max_daily_loss_pct, 2), trading_days=trading_days,
                    fail_reason="drawdown",
                )

            # Target hit
            if bal >= target_balance and trading_days >= r.min_trading_days:
                return SimulationOutcome(
                    run_id=run_id, passed=True,
                    days_to_target=day_idx + 1, final_balance=round(bal, 2),
                    peak_balance=round(peak, 2), max_drawdown_pct=round(max_dd_pct, 2),
                    max_daily_loss_pct=round(max_daily_loss_pct, 2), trading_days=trading_days,
                )

        # Ran out of days
        if bal >= target_balance and trading_days < r.min_trading_days:
            reason = "min_days"
        elif bal < target_balance:
            reason = "time_limit"
        else:
            reason = "time_limit"

        return SimulationOutcome(
            run_id=run_id, passed=False, final_balance=round(bal, 2),
            peak_balance=round(peak, 2), max_drawdown_pct=round(max_dd_pct, 2),
            max_daily_loss_pct=round(max_daily_loss_pct, 2), trading_days=trading_days,
            fail_reason=reason,
        )

    # ---------------------------------------------------------------
    # Monte Carlo: run N simulations
    # ---------------------------------------------------------------

    def simulate(
        self,
        trade_pnls: List[float],
        num_simulations: int = 1000,
    ) -> ChallengeSimulationResult:
        start = datetime.now()

        # Group trades into synthetic "days" of roughly equal count
        avg_trades_per_day = max(1, len(trade_pnls) // max(self.rules.time_limit_days, 1))
        if avg_trades_per_day < 1:
            avg_trades_per_day = 1

        outcomes: List[SimulationOutcome] = []
        for run_id in range(num_simulations):
            shuffled = trade_pnls.copy()
            random.shuffle(shuffled)

            # Build daily PnL by grouping shuffled trades
            daily = []
            for i in range(0, len(shuffled), avg_trades_per_day):
                chunk = shuffled[i:i + avg_trades_per_day]
                daily.append(sum(chunk))

            # Pad or trim to time_limit_days
            while len(daily) < self.rules.time_limit_days:
                daily.append(0.0)
            daily = daily[:self.rules.time_limit_days]

            outcomes.append(self._run_one(daily, run_id))

        return self._aggregate(outcomes, num_simulations, start)

    # ---------------------------------------------------------------
    # Aggregate outcomes into a result
    # ---------------------------------------------------------------

    def _aggregate(
        self,
        outcomes: List[SimulationOutcome],
        n: int,
        start: datetime,
    ) -> ChallengeSimulationResult:
        passed = [o for o in outcomes if o.passed]
        failed = [o for o in outcomes if not o.passed]

        pass_count = len(passed)
        pass_rate = (pass_count / n) * 100

        # Fail breakdown
        fail_reasons: Dict[str, int] = {}
        for o in failed:
            r = o.fail_reason or "unknown"
            fail_reasons[r] = fail_reasons.get(r, 0) + 1

        daily_fail = fail_reasons.get("daily_loss", 0)
        dd_fail = fail_reasons.get("drawdown", 0)
        time_fail = fail_reasons.get("time_limit", 0)

        daily_viol_pct = (daily_fail / n) * 100
        dd_viol_pct = (dd_fail / n) * 100
        time_viol_pct = (time_fail / n) * 100

        # Days to target stats
        days_list = [o.days_to_target for o in passed if o.days_to_target is not None]
        avg_days = statistics.mean(days_list) if days_list else None
        med_days = statistics.median(days_list) if days_list else None

        # Balance / drawdown stats
        avg_bal = statistics.mean(o.final_balance for o in outcomes)
        avg_dd = statistics.mean(o.max_drawdown_pct for o in outcomes)
        avg_daily = statistics.mean(o.max_daily_loss_pct for o in outcomes)

        # 95% CI on pass rate (Wilson score interval)
        ci_lo, ci_hi = self._wilson_ci(pass_count, n)

        # Score
        score = self._calc_score(pass_rate, dd_viol_pct, daily_viol_pct, time_viol_pct, avg_dd)
        grade = self._grade(score)
        risk_level = "Low" if score >= 80 else "Medium" if score >= 60 else "High" if score >= 40 else "Very High"

        # Insights
        strengths, weaknesses, recs = self._insights(
            pass_rate, daily_viol_pct, dd_viol_pct, time_viol_pct, avg_dd, avg_days
        )

        exec_time = (datetime.now() - start).total_seconds()

        return ChallengeSimulationResult(
            firm=self.rules.firm,
            phase=self.rules.phase,
            rules=self.rules,
            num_simulations=n,
            initial_balance=self.initial_balance,
            pass_probability=round(pass_rate, 2),
            daily_loss_violation_probability=round(daily_viol_pct, 2),
            drawdown_violation_probability=round(dd_viol_pct, 2),
            time_limit_violation_probability=round(time_viol_pct, 2),
            avg_days_to_target=round(avg_days, 1) if avg_days else None,
            median_days_to_target=round(med_days, 1) if med_days else None,
            avg_final_balance=round(avg_bal, 2),
            avg_max_drawdown=round(avg_dd, 2),
            avg_max_daily_loss=round(avg_daily, 2),
            pass_rate_ci_lower=round(ci_lo, 2),
            pass_rate_ci_upper=round(ci_hi, 2),
            challenge_score=score,
            grade=grade,
            risk_level=risk_level,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recs,
            fail_reasons=fail_reasons,
            execution_time_seconds=round(exec_time, 3),
        )

    # ---------------------------------------------------------------
    # Scoring
    # ---------------------------------------------------------------

    @staticmethod
    def _calc_score(
        pass_rate: float,
        daily_viol: float,
        dd_viol: float,
        time_viol: float,
        avg_dd: float,
    ) -> float:
        # Weighted components
        s = 0.0
        s += min(pass_rate, 100) * 0.45               # 45% weight on pass rate
        s += max(0, 100 - daily_viol * 4) * 0.15      # 15% on avoiding daily violations
        s += max(0, 100 - dd_viol * 4) * 0.15         # 15% on avoiding DD violations
        s += max(0, 100 - time_viol * 3) * 0.10       # 10% on not timing out
        s += max(0, min(100, (10 - avg_dd) / 10 * 100)) * 0.15  # 15% on low avg DD
        return round(max(0, min(100, s)), 1)

    @staticmethod
    def _grade(score: float) -> str:
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

    @staticmethod
    def _wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
        if n == 0:
            return 0.0, 0.0
        p = successes / n
        denom = 1 + z * z / n
        centre = p + z * z / (2 * n)
        spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
        lo = max(0, (centre - spread) / denom) * 100
        hi = min(100, (centre + spread) / denom * 100)
        return lo, hi

    @staticmethod
    def _insights(
        pass_rate, daily_pct, dd_pct, time_pct, avg_dd, avg_days,
    ):
        strengths, weaknesses, recs = [], [], []
        if pass_rate >= 80:
            strengths.append(f"High pass probability ({pass_rate:.1f}%)")
        elif pass_rate >= 50:
            strengths.append(f"Moderate pass probability ({pass_rate:.1f}%)")
        else:
            weaknesses.append(f"Low pass probability ({pass_rate:.1f}%)")
            recs.append("Strategy needs improvement before attempting this challenge")

        if daily_pct > 15:
            weaknesses.append(f"Frequent daily loss violations ({daily_pct:.1f}%)")
            recs.append("Reduce position size or add intraday loss cutoff")
        elif daily_pct < 5:
            strengths.append("Low daily loss violation risk")

        if dd_pct > 15:
            weaknesses.append(f"High drawdown violation risk ({dd_pct:.1f}%)")
            recs.append("Tighten stop losses or reduce consecutive-loss exposure")
        elif dd_pct < 5:
            strengths.append("Low drawdown violation risk")

        if time_pct > 30:
            weaknesses.append(f"Often fails to reach target in time ({time_pct:.1f}%)")
            recs.append("Increase trade frequency or loosen entry criteria")

        if avg_days is not None and avg_days < 15:
            strengths.append(f"Fast target completion ({avg_days:.0f} days avg)")

        if avg_dd < 3:
            strengths.append("Very controlled average drawdown")

        return strengths, weaknesses, recs


# ---------------------------------------------------------------------------
# Full multi-phase challenge runner
# ---------------------------------------------------------------------------

class FullChallengeRunner:
    """Run simulation for all phases of a prop firm challenge."""

    def run(
        self,
        firm: ChallengeFirm,
        trade_pnls: List[float],
        initial_balance: float,
        num_simulations: int = 1000,
    ) -> FullChallengeResult:
        start = datetime.now()
        rules_list = get_challenge_rules(firm.value)
        phase_results: List[ChallengeSimulationResult] = []

        for rules in rules_list:
            sim = ChallengeSimulator(rules, initial_balance)
            result = sim.simulate(trade_pnls, num_simulations)
            phase_results.append(result)

        # Combined pass probability = product of individual pass rates
        combined = 1.0
        for pr in phase_results:
            combined *= (pr.pass_probability / 100)
        combined_pct = combined * 100

        # Overall score = weighted average
        if phase_results:
            overall_score = sum(r.challenge_score for r in phase_results) / len(phase_results)
        else:
            overall_score = 0.0

        overall_grade = ChallengeSimulator._grade(overall_score)
        is_viable = combined_pct >= 50

        if combined_pct >= 70:
            recommendation = f"Strategy is well-suited for {firm.value.upper()} challenge ({combined_pct:.1f}% combined pass rate)"
        elif combined_pct >= 50:
            recommendation = f"Strategy is viable but risky for {firm.value.upper()} ({combined_pct:.1f}% pass). Consider risk reduction."
        elif combined_pct >= 25:
            recommendation = f"Strategy has moderate chance ({combined_pct:.1f}%). Significant improvements needed."
        else:
            recommendation = f"Strategy unlikely to pass {firm.value.upper()} challenge ({combined_pct:.1f}%). Rethink approach."

        exec_time = (datetime.now() - start).total_seconds()

        return FullChallengeResult(
            session_id="",
            backtest_id="",
            firm=firm,
            phase_results=phase_results,
            combined_pass_probability=round(combined_pct, 2),
            overall_score=round(overall_score, 1),
            overall_grade=overall_grade,
            is_viable=is_viable,
            recommendation=recommendation,
            execution_time_seconds=round(exec_time, 3),
        )
