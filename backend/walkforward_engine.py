"""
Walk-Forward Testing Engine
Phase 5: Strategy Validation and Stability Analysis
"""

from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import logging
import statistics
import itertools

from market_data_models import Candle, DataTimeframe
from backtest_models import BacktestConfig, PerformanceMetrics
from strategy_interface import SimpleMACrossStrategy
from strategy_simulator import create_strategy_simulator
from backtest_calculator import performance_calculator, strategy_scorer
from walkforward_models import (
    WalkForwardSegment,
    WalkForwardConfig,
    WalkForwardResult,
    StabilityMetrics,
    WalkForwardScore,
    SegmentType
)

logger = logging.getLogger(__name__)


class DataSegmenter:
    """Segment historical data for walk-forward testing"""
    
    @staticmethod
    def create_segments(
        candles: List[Candle],
        config: WalkForwardConfig
    ) -> List[Dict]:
        """
        Create training/testing segments from historical data
        
        Returns: List of {
            'segment_number': int,
            'training_start': datetime,
            'training_end': datetime,
            'testing_start': datetime,
            'testing_end': datetime
        }
        """
        segments = []
        
        start_date = config.start_date
        end_date = config.end_date
        
        current_date = start_date
        segment_num = 1
        
        while True:
            # Training period
            training_start = current_date
            training_end = current_date + timedelta(days=config.training_window_days)
            
            # Testing period
            testing_start = training_end
            testing_end = testing_start + timedelta(days=config.testing_window_days)
            
            # Check if we have enough data
            if testing_end > end_date:
                break
            
            segments.append({
                'segment_number': segment_num,
                'training_start': training_start,
                'training_end': training_end,
                'testing_start': testing_start,
                'testing_end': testing_end
            })
            
            segment_num += 1
            
            # Roll forward
            current_date += timedelta(days=config.step_size_days)
        
        logger.info(f"Created {len(segments)} walk-forward segments")
        return segments
    
    @staticmethod
    def filter_candles_by_date(
        candles: List[Candle],
        start_date: datetime,
        end_date: datetime
    ) -> List[Candle]:
        """Filter candles by date range"""
        return [
            c for c in candles
            if start_date <= c.timestamp <= end_date
        ]


class ParameterOptimizer:
    """Optimize strategy parameters"""
    
    @staticmethod
    def grid_search(
        candles: List[Candle],
        param_ranges: Dict[str, List],
        config: WalkForwardConfig,
        optimization_metric: str = "sharpe_ratio"
    ) -> Tuple[Dict, float]:
        """
        Perform grid search over parameter space
        
        Returns: (best_params, best_score)
        """
        # Generate all parameter combinations
        param_names = list(param_ranges.keys())
        param_values = [param_ranges[name] for name in param_names]
        combinations = list(itertools.product(*param_values))
        
        logger.info(f"Testing {len(combinations)} parameter combinations")
        
        best_params = None
        best_score = -float('inf')
        results = []
        
        for combo in combinations:
            params = dict(zip(param_names, combo))
            
            try:
                # Run backtest with these parameters
                score = ParameterOptimizer._evaluate_params(
                    candles, params, config, optimization_metric
                )
                
                results.append((params, score))
                
                if score > best_score:
                    best_score = score
                    best_params = params
            
            except Exception as e:
                logger.warning(f"Failed to evaluate params {params}: {str(e)}")
                continue
        
        logger.info(f"Best params: {best_params} with score {best_score:.3f}")
        
        return best_params, best_score
    
    @staticmethod
    def _evaluate_params(
        candles: List[Candle],
        params: Dict,
        config: WalkForwardConfig,
        metric: str
    ) -> float:
        """Evaluate parameter set by running backtest"""
        
        # Create strategy with params
        strategy = SimpleMACrossStrategy(
            symbol=config.symbol,
            timeframe=config.timeframe,
            fast_period=params.get('fast_ma', 20),
            slow_period=params.get('slow_ma', 50)
        )
        
        # Create backtest config
        backtest_config = BacktestConfig(
            symbol=config.symbol,
            timeframe=DataTimeframe(config.timeframe),
            start_date=candles[0].timestamp,
            end_date=candles[-1].timestamp,
            initial_balance=config.initial_balance
        )
        
        # Run simulation
        simulator = create_strategy_simulator(strategy, backtest_config, candles)
        result = simulator.run()
        
        # Calculate metrics
        metrics = performance_calculator.calculate_metrics(
            result['trades'],
            result['equity_curve'],
            backtest_config
        )
        
        # Return optimization metric
        return getattr(metrics, metric, 0.0)


class StabilityCalculator:
    """Calculate strategy stability across segments"""
    
    @staticmethod
    def calculate_stability(
        testing_segments: List[WalkForwardSegment]
    ) -> StabilityMetrics:
        """Calculate stability metrics from testing segments"""
        
        if len(testing_segments) < 2:
            # Not enough segments for stability analysis
            return StabilityCalculator._empty_stability()
        
        # Extract metrics from testing segments
        profit_factors = [s.profit_factor for s in testing_segments if s.profit_factor > 0]
        drawdowns = [s.max_drawdown_percent for s in testing_segments]
        win_rates = [s.win_rate for s in testing_segments]
        sharpe_ratios = [s.sharpe_ratio for s in testing_segments]
        
        # Calculate averages
        avg_pf = statistics.mean(profit_factors) if profit_factors else 0
        avg_dd = statistics.mean(drawdowns) if drawdowns else 0
        avg_wr = statistics.mean(win_rates) if win_rates else 0
        avg_sr = statistics.mean(sharpe_ratios) if sharpe_ratios else 0
        
        # Calculate standard deviations
        std_pf = statistics.stdev(profit_factors) if len(profit_factors) > 1 else 0
        std_dd = statistics.stdev(drawdowns) if len(drawdowns) > 1 else 0
        std_wr = statistics.stdev(win_rates) if len(win_rates) > 1 else 0
        std_sr = statistics.stdev(sharpe_ratios) if len(sharpe_ratios) > 1 else 0
        
        # Calculate coefficient of variation (lower is more stable)
        cv_pf = (std_pf / avg_pf) if avg_pf > 0 else 999
        cv_dd = (std_dd / avg_dd) if avg_dd > 0 else 999
        cv_wr = (std_wr / avg_wr) if avg_wr > 0 else 999
        cv_sr = (std_sr / abs(avg_sr)) if avg_sr != 0 else 999
        
        # Calculate consistency scores (0-100, higher is better)
        pf_consistency = StabilityCalculator._cv_to_score(cv_pf)
        dd_stability = StabilityCalculator._cv_to_score(cv_dd)
        wr_consistency = StabilityCalculator._cv_to_score(cv_wr)
        sr_consistency = StabilityCalculator._cv_to_score(cv_sr)
        
        return StabilityMetrics(
            profit_factor_consistency=pf_consistency,
            drawdown_stability=dd_stability,
            win_rate_consistency=wr_consistency,
            sharpe_consistency=sr_consistency,
            profit_factor_cv=cv_pf,
            drawdown_cv=cv_dd,
            win_rate_cv=cv_wr,
            sharpe_cv=cv_sr,
            avg_profit_factor=avg_pf,
            avg_drawdown=avg_dd,
            avg_win_rate=avg_wr,
            avg_sharpe=avg_sr,
            std_profit_factor=std_pf,
            std_drawdown=std_dd,
            std_win_rate=std_wr,
            std_sharpe=std_sr
        )
    
    @staticmethod
    def _cv_to_score(cv: float) -> float:
        """
        Convert coefficient of variation to consistency score (0-100)
        
        CV < 0.1 = 100 (very stable)
        CV = 0.2 = 80
        CV = 0.3 = 60
        CV = 0.5 = 40
        CV > 1.0 = 0 (unstable)
        """
        if cv >= 1.0:
            return 0.0
        elif cv <= 0.1:
            return 100.0
        elif cv <= 0.2:
            return 80.0 + ((0.2 - cv) / 0.1) * 20
        elif cv <= 0.3:
            return 60.0 + ((0.3 - cv) / 0.1) * 20
        elif cv <= 0.5:
            return 40.0 + ((0.5 - cv) / 0.2) * 20
        else:
            return ((1.0 - cv) / 0.5) * 40
    
    @staticmethod
    def _empty_stability() -> StabilityMetrics:
        """Return empty stability metrics"""
        return StabilityMetrics(
            profit_factor_consistency=0, drawdown_stability=0,
            win_rate_consistency=0, sharpe_consistency=0,
            profit_factor_cv=0, drawdown_cv=0, win_rate_cv=0, sharpe_cv=0,
            avg_profit_factor=0, avg_drawdown=0, avg_win_rate=0, avg_sharpe=0,
            std_profit_factor=0, std_drawdown=0, std_win_rate=0, std_sharpe=0
        )


class WalkForwardScorer:
    """Calculate overall walk-forward stability score"""
    
    @staticmethod
    def calculate_score(stability: StabilityMetrics) -> WalkForwardScore:
        """
        Calculate walk-forward score (0-100)
        
        Formula:
        Score = (PF_consistency × 0.40) +
                (DD_stability × 0.30) +
                (WR_consistency × 0.20) +
                (Sharpe_consistency × 0.10)
        """
        
        total_score = (
            stability.profit_factor_consistency * 0.40 +
            stability.drawdown_stability * 0.30 +
            stability.win_rate_consistency * 0.20 +
            stability.sharpe_consistency * 0.10
        )
        
        total_score = min(100, max(0, total_score))
        
        # Assign grade
        if total_score >= 90:
            grade = "S"
        elif total_score >= 80:
            grade = "A"
        elif total_score >= 70:
            grade = "B"
        elif total_score >= 60:
            grade = "C"
        elif total_score >= 50:
            grade = "D"
        else:
            grade = "F"
        
        # Deployable if score >= 70
        is_deployable = total_score >= 70
        
        # Generate insights
        strengths, weaknesses, recommendations = WalkForwardScorer._generate_insights(
            stability, total_score
        )
        
        return WalkForwardScore(
            profit_factor_consistency=stability.profit_factor_consistency,
            drawdown_stability=stability.drawdown_stability,
            win_rate_consistency=stability.win_rate_consistency,
            sharpe_consistency=stability.sharpe_consistency,
            total_score=round(total_score, 1),
            grade=grade,
            is_deployable=is_deployable,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )
    
    @staticmethod
    def _generate_insights(
        stability: StabilityMetrics,
        score: float
    ) -> Tuple[List[str], List[str], List[str]]:
        """Generate strengths, weaknesses, and recommendations"""
        
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Analyze profit factor consistency
        if stability.profit_factor_consistency >= 80:
            strengths.append(f"Highly consistent profit factor (CV: {stability.profit_factor_cv:.2f})")
        elif stability.profit_factor_consistency < 60:
            weaknesses.append(f"Inconsistent profit factor across periods (CV: {stability.profit_factor_cv:.2f})")
            recommendations.append("Review parameter sensitivity - strategy may be overfit to specific market conditions")
        
        # Analyze drawdown stability
        if stability.drawdown_stability >= 80:
            strengths.append(f"Stable drawdown control (Avg: {stability.avg_drawdown:.1f}%)")
        elif stability.drawdown_stability < 60:
            weaknesses.append(f"Inconsistent drawdown management (CV: {stability.drawdown_cv:.2f})")
            recommendations.append("Implement adaptive position sizing or stricter stop losses")
        
        # Analyze win rate consistency
        if stability.win_rate_consistency >= 80:
            strengths.append(f"Consistent win rate (Avg: {stability.avg_win_rate:.1f}%)")
        elif stability.win_rate_consistency < 60:
            weaknesses.append(f"Variable win rate across periods")
            recommendations.append("Refine entry signal quality or add market regime filter")
        
        # Overall assessment
        if score >= 70:
            strengths.append("✓ Strategy passes walk-forward validation - suitable for deployment")
        else:
            recommendations.append("⚠ Strategy stability below deployment threshold - further optimization required")
        
        return strengths, weaknesses, recommendations


class WalkForwardEngine:
    """Main walk-forward testing engine"""
    
    def __init__(self, config: WalkForwardConfig, candles: List[Candle]):
        self.config = config
        self.candles = candles
        self.data_segmenter = DataSegmenter()
        self.param_optimizer = ParameterOptimizer()
        self.stability_calculator = StabilityCalculator()
        self.scorer = WalkForwardScorer()
    
    async def run(self) -> WalkForwardResult:
        """Run complete walk-forward test"""
        
        logger.info("Starting walk-forward test")
        start_time = datetime.now()
        
        # Create segments
        segment_defs = self.data_segmenter.create_segments(self.candles, self.config)
        
        all_segments = []
        testing_segments = []
        
        # Process each segment
        for seg_def in segment_defs:
            # Training phase
            training_candles = self.data_segmenter.filter_candles_by_date(
                self.candles,
                seg_def['training_start'],
                seg_def['training_end']
            )
            
            if len(training_candles) < 100:
                logger.warning(f"Segment {seg_def['segment_number']}: Not enough training data")
                continue
            
            # Optimize parameters
            best_params, best_score = self.param_optimizer.grid_search(
                training_candles,
                self.config.param_ranges,
                self.config,
                self.config.optimization_metric
            )
            
            # Create training segment record
            training_seg = WalkForwardSegment(
                segment_number=seg_def['segment_number'],
                segment_type=SegmentType.TRAINING,
                start_date=seg_def['training_start'],
                end_date=seg_def['training_end'],
                optimized_params=best_params
            )
            all_segments.append(training_seg)
            
            # Testing phase
            testing_candles = self.data_segmenter.filter_candles_by_date(
                self.candles,
                seg_def['testing_start'],
                seg_def['testing_end']
            )
            
            if len(testing_candles) < 50:
                logger.warning(f"Segment {seg_def['segment_number']}: Not enough testing data")
                continue
            
            # Run backtest with optimized parameters
            testing_result = await self._run_test_backtest(
                testing_candles,
                best_params,
                seg_def['testing_start'],
                seg_def['testing_end']
            )
            
            # Create testing segment record
            testing_seg = WalkForwardSegment(
                segment_number=seg_def['segment_number'],
                segment_type=SegmentType.TESTING,
                start_date=seg_def['testing_start'],
                end_date=seg_def['testing_end'],
                optimized_params=best_params,
                total_trades=testing_result['total_trades'],
                net_profit=testing_result['net_profit'],
                win_rate=testing_result['win_rate'],
                profit_factor=testing_result['profit_factor'],
                max_drawdown_percent=testing_result['max_drawdown_percent'],
                sharpe_ratio=testing_result['sharpe_ratio']
            )
            all_segments.append(testing_seg)
            testing_segments.append(testing_seg)
        
        # Calculate stability
        stability = self.stability_calculator.calculate_stability(testing_segments)
        
        # Calculate walk-forward score
        wf_score = self.scorer.calculate_score(stability)
        
        # Determine best overall parameters (from best testing segment)
        if testing_segments:
            best_test_seg = max(testing_segments, key=lambda s: s.profit_factor)
            best_params = best_test_seg.optimized_params
        else:
            best_params = {}
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Walk-forward test completed: Score {wf_score.total_score:.1f}/100, Grade {wf_score.grade}")
        
        return WalkForwardResult(
            session_id="",  # Will be set by API
            strategy_name=f"MA Cross ({self.config.symbol})",
            config=self.config,
            segments=all_segments,
            testing_segments=testing_segments,
            stability_metrics=stability,
            walk_forward_score=wf_score,
            best_params=best_params,
            total_segments=len(segment_defs),
            execution_time_seconds=execution_time
        )
    
    async def _run_test_backtest(
        self,
        candles: List[Candle],
        params: Dict,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Run backtest on testing period"""
        
        # Create strategy
        strategy = SimpleMACrossStrategy(
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            fast_period=params.get('fast_ma', 20),
            slow_period=params.get('slow_ma', 50)
        )
        
        # Create config
        backtest_config = BacktestConfig(
            symbol=self.config.symbol,
            timeframe=DataTimeframe(self.config.timeframe),
            start_date=start_date,
            end_date=end_date,
            initial_balance=self.config.initial_balance
        )
        
        # Run simulation
        simulator = create_strategy_simulator(strategy, backtest_config, candles)
        result = simulator.run()
        
        # Calculate metrics
        metrics = performance_calculator.calculate_metrics(
            result['trades'],
            result['equity_curve'],
            backtest_config
        )
        
        return {
            'total_trades': metrics.total_trades,
            'net_profit': metrics.net_profit,
            'win_rate': metrics.win_rate,
            'profit_factor': metrics.profit_factor,
            'max_drawdown_percent': metrics.max_drawdown_percent,
            'sharpe_ratio': metrics.sharpe_ratio
        }


# Factory function
def create_walk_forward_engine(config: WalkForwardConfig, candles: List[Candle]) -> WalkForwardEngine:
    """Create walk-forward engine instance"""
    return WalkForwardEngine(config, candles)
