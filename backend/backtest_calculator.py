"""
Backtesting Performance Calculator
Calculates all performance metrics and strategy scores
"""

import math
from typing import List, Tuple
from datetime import datetime
from backtest_models import (
    TradeRecord,
    PerformanceMetrics,
    StrategyScore,
    EquityPoint,
    BacktestConfig
)


class PerformanceCalculator:
    """Calculate backtest performance metrics"""
    
    @staticmethod
    def calculate_metrics(
        trades: List[TradeRecord],
        equity_curve: List[EquityPoint],
        config: BacktestConfig
    ) -> PerformanceMetrics:
        """
        Calculate all performance metrics from trade history
        """
        if not trades:
            return PerformanceCalculator._empty_metrics()
        
        # Filter closed trades
        closed_trades = [t for t in trades if t.status == "closed" and t.profit_loss is not None]
        
        if not closed_trades:
            return PerformanceCalculator._empty_metrics()
        
        # Separate winners and losers
        winning_trades = [t for t in closed_trades if t.profit_loss > 0]
        losing_trades = [t for t in closed_trades if t.profit_loss < 0]
        
        # Basic stats
        total_trades = len(closed_trades)
        winning_count = len(winning_trades)
        losing_count = len(losing_trades)
        
        # Profitability
        gross_profit = sum(t.profit_loss for t in winning_trades)
        gross_loss = abs(sum(t.profit_loss for t in losing_trades))
        net_profit = gross_profit - gross_loss
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
        
        # Win rate
        win_rate = (winning_count / total_trades * 100) if total_trades > 0 else 0
        
        # Average calculations
        average_win = gross_profit / winning_count if winning_count > 0 else 0
        average_loss = gross_loss / losing_count if losing_count > 0 else 0
        average_trade = net_profit / total_trades if total_trades > 0 else 0
        
        # Largest win/loss
        largest_win = max((t.profit_loss for t in winning_trades), default=0)
        largest_loss = min((t.profit_loss for t in losing_trades), default=0)
        
        # Drawdown calculations
        max_dd, max_dd_pct, avg_dd = PerformanceCalculator._calculate_drawdown(equity_curve)
        
        # Recovery factor
        recovery_factor = net_profit / abs(max_dd) if max_dd != 0 else 0
        
        # Risk-adjusted returns
        sharpe_ratio = PerformanceCalculator._calculate_sharpe_ratio(closed_trades, config)
        sortino_ratio = PerformanceCalculator._calculate_sortino_ratio(closed_trades, config)
        calmar_ratio = (net_profit / config.initial_balance) / (max_dd_pct / 100) if max_dd_pct > 0 else 0
        
        # Trade duration
        avg_duration = PerformanceCalculator._calculate_average_duration(closed_trades)
        avg_win_duration = PerformanceCalculator._calculate_average_duration(winning_trades)
        avg_loss_duration = PerformanceCalculator._calculate_average_duration(losing_trades)
        
        # Consecutive stats
        max_consec_wins, max_consec_losses = PerformanceCalculator._calculate_consecutive_stats(closed_trades)
        
        # Risk/Reward
        risk_reward = average_win / average_loss if average_loss > 0 else 0
        
        # Expectancy
        win_prob = win_rate / 100
        loss_prob = 1 - win_prob
        expectancy = (win_prob * average_win) - (loss_prob * average_loss)
        
        return PerformanceMetrics(
            net_profit=net_profit,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            
            max_drawdown=max_dd,
            max_drawdown_percent=max_dd_pct,
            average_drawdown=avg_dd,
            recovery_factor=recovery_factor,
            
            total_trades=total_trades,
            winning_trades=winning_count,
            losing_trades=losing_count,
            win_rate=win_rate,
            
            average_win=average_win,
            average_loss=average_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            average_trade=average_trade,
            
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            
            average_trade_duration_minutes=avg_duration,
            average_winning_duration_minutes=avg_win_duration,
            average_losing_duration_minutes=avg_loss_duration,
            
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses,
            
            risk_reward_ratio=risk_reward,
            expectancy=expectancy
        )
    
    @staticmethod
    def _calculate_drawdown(equity_curve: List[EquityPoint]) -> Tuple[float, float, float]:
        """Calculate max drawdown, max drawdown %, and average drawdown"""
        if not equity_curve:
            return 0.0, 0.0, 0.0
        
        peak = equity_curve[0].balance
        max_dd = 0.0
        max_dd_pct = 0.0
        drawdowns = []
        
        for point in equity_curve:
            if point.balance > peak:
                peak = point.balance
            
            dd = peak - point.balance
            dd_pct = (dd / peak * 100) if peak > 0 else 0
            
            if dd > max_dd:
                max_dd = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
            
            if dd > 0:
                drawdowns.append(dd)
        
        avg_dd = sum(drawdowns) / len(drawdowns) if drawdowns else 0
        
        return max_dd, max_dd_pct, avg_dd
    
    @staticmethod
    def _calculate_sharpe_ratio(trades: List[TradeRecord], config: BacktestConfig) -> float:
        """Calculate Sharpe ratio (annualized)"""
        if not trades:
            return 0.0
        
        returns = [t.profit_loss / config.initial_balance for t in trades if t.profit_loss is not None]
        
        if not returns:
            return 0.0
        
        avg_return = sum(returns) / len(returns)
        
        if len(returns) < 2:
            return 0.0
        
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0.0
        
        # Annualize (assuming 252 trading days)
        sharpe = (avg_return / std_dev) * math.sqrt(252)
        
        return round(sharpe, 2)
    
    @staticmethod
    def _calculate_sortino_ratio(trades: List[TradeRecord], config: BacktestConfig) -> float:
        """Calculate Sortino ratio (only considers downside deviation)"""
        if not trades:
            return 0.0
        
        returns = [t.profit_loss / config.initial_balance for t in trades if t.profit_loss is not None]
        
        if not returns:
            return 0.0
        
        avg_return = sum(returns) / len(returns)
        
        # Only negative returns for downside deviation
        negative_returns = [r for r in returns if r < 0]
        
        if not negative_returns:
            return 0.0
        
        downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
        downside_dev = math.sqrt(downside_variance)
        
        if downside_dev == 0:
            return 0.0
        
        sortino = (avg_return / downside_dev) * math.sqrt(252)
        
        return round(sortino, 2)
    
    @staticmethod
    def _calculate_average_duration(trades: List[TradeRecord]) -> float:
        """Calculate average trade duration in minutes"""
        if not trades:
            return 0.0
        
        durations = [t.duration_minutes for t in trades if t.duration_minutes is not None]
        
        if not durations:
            return 0.0
        
        return sum(durations) / len(durations)
    
    @staticmethod
    def _calculate_consecutive_stats(trades: List[TradeRecord]) -> Tuple[int, int]:
        """Calculate max consecutive wins and losses"""
        if not trades:
            return 0, 0
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in trades:
            if trade.profit_loss and trade.profit_loss > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif trade.profit_loss and trade.profit_loss < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
        
        return max_wins, max_losses
    
    @staticmethod
    def _empty_metrics() -> PerformanceMetrics:
        """Return empty metrics for no trades"""
        return PerformanceMetrics(
            net_profit=0, gross_profit=0, gross_loss=0, profit_factor=0,
            max_drawdown=0, max_drawdown_percent=0, average_drawdown=0, recovery_factor=0,
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=0,
            average_win=0, average_loss=0, largest_win=0, largest_loss=0, average_trade=0,
            sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
            average_trade_duration_minutes=0, average_winning_duration_minutes=0,
            average_losing_duration_minutes=0, max_consecutive_wins=0, max_consecutive_losses=0,
            risk_reward_ratio=0, expectancy=0
        )


class StrategyScorer:
    """Calculate overall strategy score (0-100)"""
    
    @staticmethod
    def calculate_score(metrics: PerformanceMetrics) -> StrategyScore:
        """
        Calculate strategy score based on weighted components
        
        Formula:
        Score = (Profitability × 40) + (Risk × 30) + (Consistency × 20) + (Efficiency × 10)
        """
        
        # Component 1: Profitability Score (0-100) - based on profit factor
        profitability_score = StrategyScorer._calculate_profitability_score(metrics.profit_factor)
        
        # Component 2: Risk Score (0-100) - based on drawdown
        risk_score = StrategyScorer._calculate_risk_score(metrics.max_drawdown_percent)
        
        # Component 3: Consistency Score (0-100) - based on win rate
        consistency_score = StrategyScorer._calculate_consistency_score(metrics.win_rate)
        
        # Component 4: Efficiency Score (0-100) - based on Sharpe ratio
        efficiency_score = StrategyScorer._calculate_efficiency_score(metrics.sharpe_ratio)
        
        # Weighted total score
        total_score = (
            profitability_score * 0.40 +
            risk_score * 0.30 +
            consistency_score * 0.20 +
            efficiency_score * 0.10
        )
        
        total_score = min(100, max(0, total_score))
        
        # Assign grade
        grade = StrategyScorer._assign_grade(total_score)
        
        # Generate evaluation
        strengths, weaknesses, recommendations = StrategyScorer._generate_evaluation(
            metrics, profitability_score, risk_score, consistency_score, efficiency_score
        )
        
        return StrategyScore(
            profitability_score=round(profitability_score, 1),
            risk_score=round(risk_score, 1),
            consistency_score=round(consistency_score, 1),
            efficiency_score=round(efficiency_score, 1),
            total_score=round(total_score, 1),
            grade=grade,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )
    
    @staticmethod
    def _calculate_profitability_score(profit_factor: float) -> float:
        """
        Score based on profit factor
        PF < 1.0 = 0 points
        PF = 1.5 = 50 points
        PF = 2.0 = 75 points
        PF >= 3.0 = 100 points
        """
        if profit_factor < 1.0:
            return 0
        elif profit_factor >= 3.0:
            return 100
        elif profit_factor >= 2.0:
            return 75 + ((profit_factor - 2.0) / 1.0) * 25
        elif profit_factor >= 1.5:
            return 50 + ((profit_factor - 1.5) / 0.5) * 25
        else:
            return (profit_factor - 1.0) / 0.5 * 50
    
    @staticmethod
    def _calculate_risk_score(max_drawdown_pct: float) -> float:
        """
        Score based on max drawdown (lower is better)
        DD > 30% = 0 points
        DD = 20% = 40 points
        DD = 10% = 70 points
        DD <= 5% = 100 points
        """
        if max_drawdown_pct >= 30:
            return 0
        elif max_drawdown_pct <= 5:
            return 100
        elif max_drawdown_pct <= 10:
            return 70 + ((10 - max_drawdown_pct) / 5) * 30
        elif max_drawdown_pct <= 20:
            return 40 + ((20 - max_drawdown_pct) / 10) * 30
        else:
            return ((30 - max_drawdown_pct) / 10) * 40
    
    @staticmethod
    def _calculate_consistency_score(win_rate: float) -> float:
        """
        Score based on win rate
        WR < 30% = 0 points
        WR = 50% = 50 points
        WR = 70% = 85 points
        WR >= 80% = 100 points
        """
        if win_rate < 30:
            return 0
        elif win_rate >= 80:
            return 100
        elif win_rate >= 70:
            return 85 + ((win_rate - 70) / 10) * 15
        elif win_rate >= 50:
            return 50 + ((win_rate - 50) / 20) * 35
        else:
            return (win_rate - 30) / 20 * 50
    
    @staticmethod
    def _calculate_efficiency_score(sharpe_ratio: float) -> float:
        """
        Score based on Sharpe ratio
        SR < 0 = 0 points
        SR = 1.0 = 50 points
        SR = 2.0 = 80 points
        SR >= 3.0 = 100 points
        """
        if sharpe_ratio < 0:
            return 0
        elif sharpe_ratio >= 3.0:
            return 100
        elif sharpe_ratio >= 2.0:
            return 80 + ((sharpe_ratio - 2.0) / 1.0) * 20
        elif sharpe_ratio >= 1.0:
            return 50 + ((sharpe_ratio - 1.0) / 1.0) * 30
        else:
            return sharpe_ratio / 1.0 * 50
    
    @staticmethod
    def _assign_grade(score: float) -> str:
        """Assign letter grade based on score"""
        if score >= 90:
            return "S"  # Exceptional
        elif score >= 80:
            return "A"  # Excellent
        elif score >= 70:
            return "B"  # Good
        elif score >= 60:
            return "C"  # Average
        elif score >= 50:
            return "D"  # Below Average
        else:
            return "F"  # Poor
    
    @staticmethod
    def _generate_evaluation(
        metrics: PerformanceMetrics,
        profit_score: float,
        risk_score: float,
        consistency_score: float,
        efficiency_score: float
    ) -> Tuple[List[str], List[str], List[str]]:
        """Generate strengths, weaknesses, and recommendations"""
        
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Analyze profitability
        if profit_score >= 75:
            strengths.append(f"Strong profitability (Profit Factor: {metrics.profit_factor:.2f})")
        elif profit_score < 50:
            weaknesses.append(f"Low profitability (Profit Factor: {metrics.profit_factor:.2f})")
            recommendations.append("Optimize entry/exit rules to improve profit factor")
        
        # Analyze risk
        if risk_score >= 70:
            strengths.append(f"Excellent risk control (Max DD: {metrics.max_drawdown_percent:.1f}%)")
        elif risk_score < 50:
            weaknesses.append(f"High drawdown risk ({metrics.max_drawdown_percent:.1f}%)")
            recommendations.append("Implement tighter stop losses or reduce position sizing")
        
        # Analyze consistency
        if consistency_score >= 70:
            strengths.append(f"Consistent performance (Win Rate: {metrics.win_rate:.1f}%)")
        elif consistency_score < 50:
            weaknesses.append(f"Low win rate ({metrics.win_rate:.1f}%)")
            recommendations.append("Review entry signal quality and filter false signals")
        
        # Analyze efficiency
        if efficiency_score >= 70:
            strengths.append(f"Strong risk-adjusted returns (Sharpe: {metrics.sharpe_ratio:.2f})")
        elif efficiency_score < 50:
            weaknesses.append(f"Poor risk-adjusted returns (Sharpe: {metrics.sharpe_ratio:.2f})")
            recommendations.append("Balance risk and reward more effectively")
        
        # Risk/Reward analysis
        if metrics.risk_reward_ratio >= 2.0:
            strengths.append(f"Excellent risk/reward ratio ({metrics.risk_reward_ratio:.2f})")
        elif metrics.risk_reward_ratio < 1.0:
            weaknesses.append(f"Poor risk/reward ratio ({metrics.risk_reward_ratio:.2f})")
            recommendations.append("Adjust take profit targets to capture larger moves")
        
        return strengths, weaknesses, recommendations


# Singleton instances
performance_calculator = PerformanceCalculator()
strategy_scorer = StrategyScorer()
