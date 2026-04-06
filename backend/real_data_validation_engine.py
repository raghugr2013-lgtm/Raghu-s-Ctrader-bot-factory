"""
Real Data Handler & Walk-Forward Validation Engine
Handles real historical data import and performs robust strategy validation.

Features:
- CSV import for OHLC data
- Walk-forward validation (60/20/20 split)
- Stability filtering across data segments
- Risk-based filtering (DD, Sharpe, min trades)
"""

import logging
import csv
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ValidationSegment:
    """Data segment for validation"""
    name: str
    start_idx: int
    end_idx: int
    candles: List
    

@dataclass
class ValidationResult:
    """Results from walk-forward validation"""
    strategy_id: str
    strategy_name: str
    
    # Train segment
    train_fitness: float
    train_sharpe: float
    train_dd: float
    train_trades: int
    
    # Validation segment
    val_fitness: float
    val_sharpe: float
    val_dd: float
    val_trades: int
    
    # Test segment  
    test_fitness: float
    test_sharpe: float
    test_dd: float
    test_trades: int
    
    # Overall
    avg_fitness: float
    avg_sharpe: float
    max_dd: float
    total_trades: int
    consistency_score: float  # How consistent across segments (0-100)
    
    passed: bool
    failure_reason: Optional[str] = None


class RealDataHandler:
    """Handles real historical data import from CSV"""
    
    @staticmethod
    def import_from_csv(
        file_path: str,
        symbol: str = "EURUSD",
        timeframe: str = "1h"
    ) -> List:
        """
        Import OHLC data from CSV file.
        
        Expected CSV format:
        timestamp,open,high,low,close,volume
        2024-01-01 00:00:00,1.1050,1.1065,1.1045,1.1060,1000
        
        Args:
            file_path: Path to CSV file
            symbol: Trading pair
            timeframe: Chart timeframe
            
        Returns:
            List of Candle objects
        """
        from market_data_models import Candle
        
        logger.info(f"[REAL DATA] Importing from CSV: {file_path}")
        
        candles = []
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse timestamp
                    timestamp = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    
                    candle = Candle(
                        timestamp=timestamp,
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=int(float(row.get('volume', 0)))
                    )
                    candles.append(candle)
                    
                except Exception as e:
                    logger.warning(f"[REAL DATA] Skipping invalid row: {e}")
                    continue
        
        logger.info(f"[REAL DATA] ✓ Imported {len(candles)} candles")
        return candles
    
    @staticmethod
    def validate_candles(candles: List) -> Tuple[bool, str]:
        """
        Validate candle data quality.
        
        Returns:
            (is_valid, error_message)
        """
        if not candles:
            return False, "No candles provided"
        
        if len(candles) < 100:
            return False, f"Insufficient data: {len(candles)} candles (minimum 100 required)"
        
        # Check for gaps
        sorted_candles = sorted(candles, key=lambda c: c.timestamp)
        
        # Check OHLC validity
        invalid_count = 0
        for c in sorted_candles:
            if c.high < c.low:
                invalid_count += 1
            if c.high < max(c.open, c.close):
                invalid_count += 1
            if c.low > min(c.open, c.close):
                invalid_count += 1
        
        if invalid_count > len(candles) * 0.05:  # More than 5% invalid
            return False, f"Too many invalid candles: {invalid_count}/{len(candles)}"
        
        return True, "Valid"


class WalkForwardValidator:
    """
    Performs walk-forward validation to test strategy robustness.
    
    Splits data into Train (60%), Validation (20%), Test (20%)
    and ensures consistent performance across all segments.
    """
    
    def __init__(self):
        self.train_ratio = 0.60
        self.val_ratio = 0.20
        self.test_ratio = 0.20
    
    def validate_strategy(
        self,
        strategy: Dict[str, Any],
        candles: List,
        initial_balance: float = 10000.0,
        symbol: str = "EURUSD",
        timeframe: str = "1h"
    ) -> ValidationResult:
        """
        Run walk-forward validation on a strategy.
        
        Args:
            strategy: Strategy configuration with genes
            candles: Historical candle data
            initial_balance: Starting balance for backtest
            symbol: Trading pair
            timeframe: Chart timeframe
            
        Returns:
            ValidationResult with performance across segments
        """
        from real_backtester import real_backtester
        
        # Split data into segments
        segments = self._split_data(candles)
        
        logger.info(f"[WALK-FORWARD] Validating {strategy.get('name', 'Unknown')}")
        logger.info(f"[WALK-FORWARD] Train: {len(segments[0].candles)} | Val: {len(segments[1].candles)} | Test: {len(segments[2].candles)}")
        
        results = {}
        
        # Run backtest on each segment
        for segment in segments:
            try:
                result = real_backtester.run_strategy_backtest(
                    strategy=strategy,
                    candles=segment.candles,
                    initial_balance=initial_balance,
                    symbol=symbol,
                    timeframe=timeframe
                )
                
                results[segment.name] = {
                    "fitness": result.get("fitness", 0),
                    "sharpe_ratio": result.get("sharpe_ratio", 0),
                    "max_drawdown_pct": result.get("max_drawdown_pct", 0),
                    "total_trades": result.get("total_trades", 0)
                }
                
            except Exception as e:
                logger.warning(f"[WALK-FORWARD] {segment.name} failed: {e}")
                results[segment.name] = {
                    "fitness": 0,
                    "sharpe_ratio": 0,
                    "max_drawdown_pct": 100,
                    "total_trades": 0
                }
        
        # Calculate consistency
        fitnesses = [r["fitness"] for r in results.values()]
        sharpes = [r["sharpe_ratio"] for r in results.values()]
        
        consistency_score = self._calculate_consistency(fitnesses)
        
        # Create validation result
        train = results.get("train", {})
        val = results.get("validation", {})
        test = results.get("test", {})
        
        avg_fitness = statistics.mean(fitnesses) if fitnesses else 0
        avg_sharpe = statistics.mean(sharpes) if sharpes else 0
        max_dd = max([r["max_drawdown_pct"] for r in results.values()])
        total_trades = sum([r["total_trades"] for r in results.values()])
        
        validation_result = ValidationResult(
            strategy_id=strategy.get("id", "unknown"),
            strategy_name=strategy.get("name", "Unknown"),
            
            train_fitness=train.get("fitness", 0),
            train_sharpe=train.get("sharpe_ratio", 0),
            train_dd=train.get("max_drawdown_pct", 0),
            train_trades=train.get("total_trades", 0),
            
            val_fitness=val.get("fitness", 0),
            val_sharpe=val.get("sharpe_ratio", 0),
            val_dd=val.get("max_drawdown_pct", 0),
            val_trades=val.get("total_trades", 0),
            
            test_fitness=test.get("fitness", 0),
            test_sharpe=test.get("sharpe_ratio", 0),
            test_dd=test.get("max_drawdown_pct", 0),
            test_trades=test.get("total_trades", 0),
            
            avg_fitness=avg_fitness,
            avg_sharpe=avg_sharpe,
            max_dd=max_dd,
            total_trades=total_trades,
            consistency_score=consistency_score,
            
            passed=False  # Will be set by risk filter
        )
        
        return validation_result
    
    def _split_data(self, candles: List) -> List[ValidationSegment]:
        """Split candles into train/val/test segments"""
        total = len(candles)
        
        train_end = int(total * self.train_ratio)
        val_end = train_end + int(total * self.val_ratio)
        
        segments = [
            ValidationSegment(
                name="train",
                start_idx=0,
                end_idx=train_end,
                candles=candles[0:train_end]
            ),
            ValidationSegment(
                name="validation",
                start_idx=train_end,
                end_idx=val_end,
                candles=candles[train_end:val_end]
            ),
            ValidationSegment(
                name="test",
                start_idx=val_end,
                end_idx=total,
                candles=candles[val_end:]
            )
        ]
        
        return segments
    
    def _calculate_consistency(self, values: List[float]) -> float:
        """
        Calculate consistency score (0-100).
        Lower variance = higher consistency.
        """
        if not values or len(values) < 2:
            return 0.0
        
        mean_val = statistics.mean(values)
        if mean_val == 0:
            return 0.0
        
        # Coefficient of variation
        std_dev = statistics.stdev(values)
        cv = (std_dev / abs(mean_val)) * 100
        
        # Convert to consistency score (lower CV = higher consistency)
        # CV of 0 = 100 consistency, CV of 50+ = 0 consistency
        consistency = max(0, 100 - cv * 2)
        
        return round(consistency, 1)


class StabilityFilter:
    """
    Filters strategies based on stability and risk criteria.
    
    Rejects strategies that:
    - Only perform well in one segment
    - Have excessive drawdown
    - Have insufficient trades
    - Have poor Sharpe ratio
    """
    
    def __init__(
        self,
        max_drawdown_pct: float = 20.0,
        min_sharpe_ratio: float = 0.8,
        min_trades_per_segment: int = 5,
        min_consistency_score: float = 50.0
    ):
        self.max_drawdown_pct = max_drawdown_pct
        self.min_sharpe_ratio = min_sharpe_ratio
        self.min_trades_per_segment = min_trades_per_segment
        self.min_consistency_score = min_consistency_score
    
    def apply_filter(
        self,
        validation_results: List[ValidationResult]
    ) -> Tuple[List[ValidationResult], List[ValidationResult]]:
        """
        Apply stability and risk filters.
        
        Returns:
            (passed_strategies, rejected_strategies)
        """
        passed = []
        rejected = []
        
        for result in validation_results:
            passed_check, reason = self._check_strategy(result)
            
            if passed_check:
                result.passed = True
                passed.append(result)
                logger.info(
                    f"[STABILITY FILTER] ✓ {result.strategy_name} - "
                    f"Consistency: {result.consistency_score:.1f}, "
                    f"Sharpe: {result.avg_sharpe:.2f}, "
                    f"DD: {result.max_dd:.1f}%"
                )
            else:
                result.passed = False
                result.failure_reason = reason
                rejected.append(result)
                logger.info(
                    f"[STABILITY FILTER] ✗ {result.strategy_name} - "
                    f"Rejected: {reason}"
                )
        
        logger.info(f"[STABILITY FILTER] Passed: {len(passed)}, Rejected: {len(rejected)}")
        
        return passed, rejected
    
    def _check_strategy(self, result: ValidationResult) -> Tuple[bool, Optional[str]]:
        """
        Check if strategy meets all criteria.
        
        Returns:
            (passed, failure_reason)
        """
        # Check max drawdown
        if result.max_dd > self.max_drawdown_pct:
            return False, f"Excessive DD: {result.max_dd:.1f}% > {self.max_drawdown_pct}%"
        
        # Check Sharpe ratio
        if result.avg_sharpe < self.min_sharpe_ratio:
            return False, f"Low Sharpe: {result.avg_sharpe:.2f} < {self.min_sharpe_ratio}"
        
        # Check minimum trades per segment
        min_trades = min(result.train_trades, result.val_trades, result.test_trades)
        if min_trades < self.min_trades_per_segment:
            return False, f"Insufficient trades: {min_trades} < {self.min_trades_per_segment}"
        
        # Check consistency across segments
        if result.consistency_score < self.min_consistency_score:
            return False, f"Inconsistent: {result.consistency_score:.1f} < {self.min_consistency_score}"
        
        # Check that strategy performs in ALL segments (not just one)
        segment_fitnesses = [result.train_fitness, result.val_fitness, result.test_fitness]
        if any(f < 30 for f in segment_fitnesses):  # Any segment below 30 fitness
            worst_segment = ["train", "val", "test"][segment_fitnesses.index(min(segment_fitnesses))]
            return False, f"Poor {worst_segment} performance: {min(segment_fitnesses):.1f}"
        
        return True, None
