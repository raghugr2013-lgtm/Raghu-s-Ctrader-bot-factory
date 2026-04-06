"""
Forward Testing Engine
Tests strategy performance on unseen future data using rolling windows.

Different from walk-forward validation:
- Walk-forward: Static 60/20/20 split for consistency testing
- Forward testing: Rolling windows to test time decay and adaptability
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ForwardTestResult:
    """Results from forward testing"""
    strategy_id: str
    strategy_name: str
    
    # Overall metrics
    num_windows: int
    avg_forward_fitness: float
    avg_forward_sharpe: float
    avg_forward_dd: float
    
    # Performance decay
    decay_score: float  # How much performance drops from train to test (0-100, higher=less decay)
    
    # Individual window results
    window_results: List[Dict[str, Any]]
    
    # Pass/Fail
    passed: bool
    failure_reason: Optional[str] = None


class ForwardTestingEngine:
    """
    Performs rolling forward testing to validate strategy on unseen data.
    
    Methodology:
    1. Split data: 70% train, 30% test
    2. Run multiple rolling windows:
       - Window 1: Train on first 70%, test on next 30%
       - Window 2: Shift forward, repeat
       - Window 3: Shift forward, repeat
    3. Measure performance consistency and decay
    """
    
    def __init__(
        self,
        train_ratio: float = 0.70,
        test_ratio: float = 0.30,
        num_windows: int = 3,
        min_decay_score: float = 60.0
    ):
        self.train_ratio = train_ratio
        self.test_ratio = test_ratio
        self.num_windows = num_windows
        self.min_decay_score = min_decay_score
    
    def test_strategy(
        self,
        strategy: Dict[str, Any],
        candles: List,
        initial_balance: float = 10000.0,
        symbol: str = "EURUSD",
        timeframe: str = "1h"
    ) -> ForwardTestResult:
        """
        Run forward testing on strategy.
        
        Args:
            strategy: Strategy configuration
            candles: All available historical data
            initial_balance: Starting balance
            symbol: Trading pair
            timeframe: Chart timeframe
            
        Returns:
            ForwardTestResult with performance metrics
        """
        if len(candles) < 200:
            # Not enough data for forward testing
            return ForwardTestResult(
                strategy_id=strategy.get("id", "unknown"),
                strategy_name=strategy.get("name", "Unknown"),
                num_windows=0,
                avg_forward_fitness=0.0,
                avg_forward_sharpe=0.0,
                avg_forward_dd=0.0,
                decay_score=0.0,
                window_results=[],
                passed=False,
                failure_reason="Insufficient data for forward testing (minimum 200 candles required)"
            )
        
        logger.info(f"[FORWARD TEST] Testing {strategy.get('name')} with {len(candles)} candles")
        logger.info(f"[FORWARD TEST] Running {self.num_windows} rolling windows")
        
        from real_backtester import real_backtester
        
        window_results = []
        
        # Calculate window size
        total_candles = len(candles)
        train_size = int(total_candles * self.train_ratio)
        test_size = int(total_candles * self.test_ratio)
        
        # Rolling window approach
        for window_num in range(self.num_windows):
            # Calculate window boundaries
            # Each window shifts forward by (test_size / num_windows)
            shift = int((test_size / self.num_windows) * window_num)
            train_start = shift
            train_end = shift + train_size
            test_start = train_end
            test_end = min(test_start + test_size, total_candles)
            
            # Check if we have enough data
            if test_end - test_start < 50:
                logger.warning(f"[FORWARD TEST] Window {window_num + 1}: Insufficient test data, skipping")
                continue
            
            train_candles = candles[train_start:train_end]
            test_candles = candles[test_start:test_end]
            
            logger.info(f"[FORWARD TEST] Window {window_num + 1}: Train={len(train_candles)}, Test={len(test_candles)}")
            
            # Run backtest on train data
            try:
                train_result = real_backtester.run_strategy_backtest(
                    strategy=strategy,
                    candles=train_candles,
                    initial_balance=initial_balance,
                    symbol=symbol,
                    timeframe=timeframe
                )
                
                # Run backtest on test data (unseen)
                test_result = real_backtester.run_strategy_backtest(
                    strategy=strategy,
                    candles=test_candles,
                    initial_balance=initial_balance,
                    symbol=symbol,
                    timeframe=timeframe
                )
                
                # Calculate decay (performance drop from train to test)
                train_fitness = train_result.get("fitness", 0)
                test_fitness = test_result.get("fitness", 0)
                
                if train_fitness > 0:
                    decay_pct = ((train_fitness - test_fitness) / train_fitness) * 100
                else:
                    decay_pct = 100
                
                window_results.append({
                    "window": window_num + 1,
                    "train_fitness": train_fitness,
                    "train_sharpe": train_result.get("sharpe_ratio", 0),
                    "train_dd": train_result.get("max_drawdown_pct", 0),
                    "test_fitness": test_fitness,
                    "test_sharpe": test_result.get("sharpe_ratio", 0),
                    "test_dd": test_result.get("max_drawdown_pct", 0),
                    "decay_pct": decay_pct,
                    "test_trades": test_result.get("total_trades", 0)
                })
                
            except Exception as e:
                logger.warning(f"[FORWARD TEST] Window {window_num + 1} failed: {e}")
                continue
        
        # Analyze results
        if not window_results:
            return ForwardTestResult(
                strategy_id=strategy.get("id", "unknown"),
                strategy_name=strategy.get("name", "Unknown"),
                num_windows=0,
                avg_forward_fitness=0.0,
                avg_forward_sharpe=0.0,
                avg_forward_dd=0.0,
                decay_score=0.0,
                window_results=[],
                passed=False,
                failure_reason="All forward test windows failed"
            )
        
        # Calculate averages
        avg_forward_fitness = statistics.mean([w["test_fitness"] for w in window_results])
        avg_forward_sharpe = statistics.mean([w["test_sharpe"] for w in window_results])
        avg_forward_dd = statistics.mean([w["test_dd"] for w in window_results])
        avg_decay_pct = statistics.mean([w["decay_pct"] for w in window_results])
        
        # Calculate decay score (0-100, higher is better)
        # 0% decay = 100 score, 50%+ decay = 0 score
        decay_score = max(0, 100 - (avg_decay_pct * 2))
        
        # Check if passed
        passed = decay_score >= self.min_decay_score
        failure_reason = None
        if not passed:
            failure_reason = f"High performance decay: {avg_decay_pct:.1f}% (decay score: {decay_score:.1f})"
        
        result = ForwardTestResult(
            strategy_id=strategy.get("id", "unknown"),
            strategy_name=strategy.get("name", "Unknown"),
            num_windows=len(window_results),
            avg_forward_fitness=avg_forward_fitness,
            avg_forward_sharpe=avg_forward_sharpe,
            avg_forward_dd=avg_forward_dd,
            decay_score=decay_score,
            window_results=window_results,
            passed=passed,
            failure_reason=failure_reason
        )
        
        logger.info(
            f"[FORWARD TEST] ✓ Complete: Avg Test Fitness={avg_forward_fitness:.1f}, "
            f"Decay Score={decay_score:.1f}, Passed={passed}"
        )
        
        return result
    
    def batch_test(
        self,
        strategies: List[Dict[str, Any]],
        candles: List,
        initial_balance: float = 10000.0,
        symbol: str = "EURUSD",
        timeframe: str = "1h"
    ) -> Tuple[List[ForwardTestResult], List[ForwardTestResult]]:
        """
        Run forward testing on multiple strategies.
        
        Returns:
            (passed_strategies, failed_strategies)
        """
        passed = []
        failed = []
        
        for strategy in strategies:
            result = self.test_strategy(
                strategy=strategy,
                candles=candles,
                initial_balance=initial_balance,
                symbol=symbol,
                timeframe=timeframe
            )
            
            if result.passed:
                passed.append(result)
            else:
                failed.append(result)
        
        logger.info(f"[FORWARD TEST] Batch complete: {len(passed)} passed, {len(failed)} failed")
        
        return passed, failed
