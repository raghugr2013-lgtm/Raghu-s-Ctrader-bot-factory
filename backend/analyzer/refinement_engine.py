"""
Strategy Refinement Engine - Phase 2
Automatically improves parsed strategies using rule-based analysis
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from copy import deepcopy
import math


class IssueSeverity(Enum):
    """Issue severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(Enum):
    """Categories of detected issues"""
    COMPLEXITY = "complexity"
    RISK_MANAGEMENT = "risk_management"
    ENTRY_LOGIC = "entry_logic"
    EXIT_LOGIC = "exit_logic"
    FILTERING = "filtering"
    OVERTRADING = "overtrading"
    PARAMETER = "parameter"


@dataclass
class DetectedIssue:
    """A detected issue in the strategy"""
    category: str
    severity: str
    title: str
    description: str
    impact: str
    recommendation: str
    auto_fixable: bool = True


@dataclass
class AppliedChange:
    """A change applied to the strategy"""
    change_type: str  # 'added', 'modified', 'removed', 'optimized'
    component: str    # 'filter', 'parameter', 'entry', 'exit', 'risk'
    description: str
    before: Optional[Any] = None
    after: Optional[Any] = None
    reason: str = ""


@dataclass
class RefinementResult:
    """Complete refinement result"""
    original_strategy: Dict[str, Any]
    issues: List[DetectedIssue]
    improved_strategy: Dict[str, Any]
    changes_made: List[AppliedChange]
    improvement_score: float = 0.0
    summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_strategy": self.original_strategy,
            "issues": [asdict(i) for i in self.issues],
            "improved_strategy": self.improved_strategy,
            "changes_made": [asdict(c) for c in self.changes_made],
            "improvement_score": self.improvement_score,
            "summary": self.summary
        }


class StrategyRefinementEngine:
    """
    Rule-based strategy refinement engine
    Analyzes parsed strategies and applies improvements
    """
    
    # Optimal parameter ranges by indicator type
    OPTIMAL_PARAMETERS = {
        'RSI': {'period': (10, 21), 'overbought': (65, 80), 'oversold': (20, 35)},
        'EMA': {'period': (8, 50)},
        'SMA': {'period': (10, 200)},
        'MovingAverage': {'period': (10, 200)},
        'MACD': {'fast_period': (8, 15), 'slow_period': (20, 30), 'signal_period': (7, 12)},
        'BollingerBands': {'period': (15, 25), 'std_dev': (1.5, 2.5)},
        'ATR': {'period': (10, 20)},
        'Stochastic': {'k_period': (10, 20), 'k_slowing': (2, 5), 'd_period': (3, 5)},
        'ADX': {'period': (12, 18)},
    }
    
    # Risk-reward thresholds
    MIN_RR_RATIO = 1.5
    MAX_RR_RATIO = 3.0
    OPTIMAL_RR_RATIO = 2.0
    
    # Complexity thresholds
    MAX_INDICATORS = 5
    MAX_CONDITIONS_PER_ENTRY = 4
    MAX_ENTRY_SIGNALS = 4
    
    # Overtrading thresholds
    DEFAULT_MAX_TRADES_PER_DAY = 5
    DEFAULT_MAX_LOSS_STREAK = 2
    
    def __init__(self):
        self.issues: List[DetectedIssue] = []
        self.changes: List[AppliedChange] = []
    
    def refine(self, parsed_data: Dict[str, Any], strategy_data: Dict[str, Any]) -> RefinementResult:
        """
        Main refinement method
        
        Args:
            parsed_data: Output from CSharpBotParser.parse().to_dict()
            strategy_data: Output from StrategyParser.parse().to_dict()
        
        Returns:
            RefinementResult with issues found and improved strategy
        """
        self.issues = []
        self.changes = []
        
        # Deep copy to avoid modifying originals
        original_strategy = deepcopy(strategy_data)
        improved_strategy = deepcopy(strategy_data)
        improved_parsed = deepcopy(parsed_data)
        
        # Phase 1: Detect issues
        self._detect_complexity_issues(parsed_data, strategy_data)
        self._detect_risk_issues(parsed_data, strategy_data)
        self._detect_entry_logic_issues(parsed_data, strategy_data)
        self._detect_filtering_issues(parsed_data, strategy_data)
        self._detect_overtrading_issues(parsed_data, strategy_data)
        self._detect_parameter_issues(parsed_data, strategy_data)
        
        # Phase 2: Apply improvements
        improved_strategy = self._apply_complexity_fixes(improved_strategy, improved_parsed)
        improved_strategy = self._apply_risk_fixes(improved_strategy, improved_parsed)
        improved_strategy = self._add_missing_filters(improved_strategy, improved_parsed)
        improved_strategy = self._add_overtrading_protection(improved_strategy, improved_parsed)
        improved_strategy = self._optimize_parameters(improved_strategy, improved_parsed)
        
        # Calculate improvement score
        improvement_score = self._calculate_improvement_score(original_strategy, improved_strategy)
        
        # Generate summary
        summary = self._generate_summary()
        
        return RefinementResult(
            original_strategy=original_strategy,
            issues=self.issues,
            improved_strategy=improved_strategy,
            changes_made=self.changes,
            improvement_score=improvement_score,
            summary=summary
        )
    
    # ==================== ISSUE DETECTION ====================
    
    def _detect_complexity_issues(self, parsed: Dict, strategy: Dict) -> None:
        """Detect over-complexity issues"""
        indicators = parsed.get('indicators', [])
        entry_conditions = parsed.get('entry_conditions', [])
        
        # Too many indicators
        if len(indicators) > self.MAX_INDICATORS:
            self.issues.append(DetectedIssue(
                category=IssueCategory.COMPLEXITY.value,
                severity=IssueSeverity.MEDIUM.value,
                title="Too Many Indicators",
                description=f"Strategy uses {len(indicators)} indicators (max recommended: {self.MAX_INDICATORS})",
                impact="Increases lag, conflicting signals, and curve-fitting risk",
                recommendation="Reduce to 2-3 core indicators with clear roles",
                auto_fixable=False
            ))
        
        # Redundant indicators (multiple MAs of same type)
        indicator_types = [i.get('type') for i in indicators]
        ma_count = sum(1 for t in indicator_types if t in ['SMA', 'EMA', 'MovingAverage'])
        if ma_count > 2:
            self.issues.append(DetectedIssue(
                category=IssueCategory.COMPLEXITY.value,
                severity=IssueSeverity.LOW.value,
                title="Redundant Moving Averages",
                description=f"Strategy uses {ma_count} moving averages",
                impact="May cause signal conflicts and over-smoothing",
                recommendation="Use maximum 2 MAs (fast and slow)",
                auto_fixable=False
            ))
        
        # Complex entry conditions
        for idx, entry in enumerate(entry_conditions):
            condition_text = entry.get('condition_text', '')
            # Count logical operators
            and_count = condition_text.count('&&')
            or_count = condition_text.count('||')
            if and_count + or_count > self.MAX_CONDITIONS_PER_ENTRY:
                self.issues.append(DetectedIssue(
                    category=IssueCategory.COMPLEXITY.value,
                    severity=IssueSeverity.MEDIUM.value,
                    title=f"Complex Entry Condition #{idx+1}",
                    description=f"Entry has {and_count + or_count + 1} conditions combined",
                    impact="Hard to debug, may miss valid entries",
                    recommendation="Simplify to 2-3 clear conditions",
                    auto_fixable=False
                ))
    
    def _detect_risk_issues(self, parsed: Dict, strategy: Dict) -> None:
        """Detect risk management issues"""
        risk = parsed.get('risk_management', {})
        risk_config = strategy.get('risk_config', {})
        
        # No stop loss
        if not risk.get('has_stop_loss'):
            self.issues.append(DetectedIssue(
                category=IssueCategory.RISK_MANAGEMENT.value,
                severity=IssueSeverity.CRITICAL.value,
                title="Missing Stop Loss",
                description="Strategy has no stop loss protection",
                impact="Unlimited downside risk, potential account blowout",
                recommendation="Add fixed or ATR-based stop loss (15-30 pips for forex)",
                auto_fixable=True
            ))
        
        # No take profit
        if not risk.get('has_take_profit'):
            self.issues.append(DetectedIssue(
                category=IssueCategory.RISK_MANAGEMENT.value,
                severity=IssueSeverity.HIGH.value,
                title="Missing Take Profit",
                description="Strategy has no take profit target",
                impact="May miss profit opportunities, relies on manual exit",
                recommendation="Add take profit at 1.5-2x stop loss distance",
                auto_fixable=True
            ))
        
        # Poor risk-reward ratio
        sl = risk.get('stop_loss_pips')
        tp = risk.get('take_profit_pips')
        if sl and tp:
            rr_ratio = tp / sl
            if rr_ratio < self.MIN_RR_RATIO:
                self.issues.append(DetectedIssue(
                    category=IssueCategory.RISK_MANAGEMENT.value,
                    severity=IssueSeverity.HIGH.value,
                    title="Poor Risk-Reward Ratio",
                    description=f"Current R:R is 1:{rr_ratio:.2f} (below 1:{self.MIN_RR_RATIO})",
                    impact="Requires high win rate to be profitable",
                    recommendation=f"Adjust to at least 1:{self.MIN_RR_RATIO} ratio",
                    auto_fixable=True
                ))
            elif rr_ratio > self.MAX_RR_RATIO:
                self.issues.append(DetectedIssue(
                    category=IssueCategory.RISK_MANAGEMENT.value,
                    severity=IssueSeverity.LOW.value,
                    title="Aggressive Risk-Reward Ratio",
                    description=f"Current R:R is 1:{rr_ratio:.2f} (above 1:{self.MAX_RR_RATIO})",
                    impact="May result in low win rate and drawdowns",
                    recommendation=f"Consider 1:{self.OPTIMAL_RR_RATIO} for balance",
                    auto_fixable=True
                ))
        
        # Fixed position sizing
        if risk_config.get('position_sizing') == 'fixed':
            self.issues.append(DetectedIssue(
                category=IssueCategory.RISK_MANAGEMENT.value,
                severity=IssueSeverity.MEDIUM.value,
                title="Fixed Position Sizing",
                description="Strategy uses fixed lot size regardless of account balance",
                impact="Risk per trade varies with account growth/drawdown",
                recommendation="Use percentage-based or risk-based position sizing",
                auto_fixable=True
            ))
        
        # No trailing stop for trend strategies
        category = strategy.get('category', '')
        if category == 'trend_following' and not risk.get('has_trailing_stop'):
            self.issues.append(DetectedIssue(
                category=IssueCategory.RISK_MANAGEMENT.value,
                severity=IssueSeverity.MEDIUM.value,
                title="No Trailing Stop for Trend Strategy",
                description="Trend-following strategy without trailing stop",
                impact="May give back profits when trend reverses",
                recommendation="Add trailing stop to lock in profits",
                auto_fixable=True
            ))
    
    def _detect_entry_logic_issues(self, parsed: Dict, strategy: Dict) -> None:
        """Detect entry logic issues"""
        entry_conditions = parsed.get('entry_conditions', [])
        indicators = parsed.get('indicators', [])
        
        # No entry conditions
        if not entry_conditions:
            self.issues.append(DetectedIssue(
                category=IssueCategory.ENTRY_LOGIC.value,
                severity=IssueSeverity.CRITICAL.value,
                title="No Entry Logic Detected",
                description="Could not parse entry conditions from code",
                impact="Bot may not execute any trades",
                recommendation="Review OnBar/OnTick method for entry logic",
                auto_fixable=False
            ))
            return
        
        # Single direction only
        directions = set(e.get('direction') for e in entry_conditions)
        if len(directions) == 1:
            direction = list(directions)[0]
            self.issues.append(DetectedIssue(
                category=IssueCategory.ENTRY_LOGIC.value,
                severity=IssueSeverity.LOW.value,
                title=f"{direction.title()}-Only Strategy",
                description=f"Strategy only trades {direction} positions",
                impact="Misses opportunities in opposite direction",
                recommendation="Consider adding reverse entry for ranging markets",
                auto_fixable=False
            ))
        
        # Weak support/resistance logic (no price level checks)
        all_conditions = ' '.join(e.get('condition_text', '') for e in entry_conditions)
        has_sr_logic = any(term in all_conditions.lower() for term in 
                          ['high', 'low', 'support', 'resistance', 'level', 'price'])
        
        # Check for pure indicator-based entries
        indicator_names = [i.get('variable_name', '').lower() for i in indicators]
        uses_only_indicators = all(
            any(ind_name in e.get('condition_text', '').lower() for ind_name in indicator_names)
            for e in entry_conditions
        )
        
        if uses_only_indicators and not has_sr_logic:
            self.issues.append(DetectedIssue(
                category=IssueCategory.ENTRY_LOGIC.value,
                severity=IssueSeverity.LOW.value,
                title="No Price Level Logic",
                description="Entry relies solely on indicator signals without price context",
                impact="May enter at poor price levels (resistance for longs, support for shorts)",
                recommendation="Consider adding price level filters",
                auto_fixable=False
            ))
    
    def _detect_filtering_issues(self, parsed: Dict, strategy: Dict) -> None:
        """Detect missing filters"""
        filters = parsed.get('filters', [])
        filter_types = [f.get('filter_type') for f in filters]
        indicators = parsed.get('indicators', [])
        indicator_types = [i.get('type') for i in indicators]
        
        # No time filter
        if 'time' not in filter_types:
            self.issues.append(DetectedIssue(
                category=IssueCategory.FILTERING.value,
                severity=IssueSeverity.MEDIUM.value,
                title="Missing Session Filter",
                description="No trading session/time filter detected",
                impact="May trade during low-liquidity or news periods",
                recommendation="Add session filter (e.g., London/NY overlap)",
                auto_fixable=True
            ))
        
        # No spread filter
        if 'spread' not in filter_types:
            self.issues.append(DetectedIssue(
                category=IssueCategory.FILTERING.value,
                severity=IssueSeverity.MEDIUM.value,
                title="Missing Spread Filter",
                description="No spread/slippage filter detected",
                impact="May enter during high-spread conditions",
                recommendation="Add max spread filter (e.g., < 3 pips for major pairs)",
                auto_fixable=True
            ))
        
        # No volatility filter
        if 'volatility' not in filter_types and 'ATR' not in indicator_types:
            self.issues.append(DetectedIssue(
                category=IssueCategory.FILTERING.value,
                severity=IssueSeverity.MEDIUM.value,
                title="Missing Volatility Filter",
                description="No volatility/ATR filter detected",
                impact="May trade during low-volatility (choppy) or extreme conditions",
                recommendation="Add ATR-based volatility filter",
                auto_fixable=True
            ))
        
        # No trend filter for mean-reversion
        category = strategy.get('category', '')
        if category == 'mean_reversion' and 'trend' not in filter_types:
            # Check if any MA/ADX is used as trend filter
            has_trend_indicator = any(t in indicator_types for t in ['ADX', 'SMA', 'EMA', 'MovingAverage'])
            if not has_trend_indicator:
                self.issues.append(DetectedIssue(
                    category=IssueCategory.FILTERING.value,
                    severity=IssueSeverity.HIGH.value,
                    title="No Trend Filter for Mean-Reversion",
                    description="Mean-reversion strategy without trend context",
                    impact="May counter-trend trade in strong trends",
                    recommendation="Add trend filter to only trade in ranging conditions",
                    auto_fixable=True
                ))
    
    def _detect_overtrading_issues(self, parsed: Dict, strategy: Dict) -> None:
        """Detect potential overtrading issues"""
        risk = parsed.get('risk_management', {})
        filters = parsed.get('filters', [])
        
        # No max positions limit
        if not risk.get('max_positions'):
            self.issues.append(DetectedIssue(
                category=IssueCategory.OVERTRADING.value,
                severity=IssueSeverity.MEDIUM.value,
                title="No Position Limit",
                description="No maximum concurrent positions defined",
                impact="May pyramid positions during strong signals",
                recommendation=f"Add max positions limit (suggested: 1-3)",
                auto_fixable=True
            ))
        
        # No daily trade limit
        has_daily_limit = any('daily' in f.get('description', '').lower() or 
                             'day' in f.get('filter_type', '').lower() 
                             for f in filters)
        if not has_daily_limit:
            self.issues.append(DetectedIssue(
                category=IssueCategory.OVERTRADING.value,
                severity=IssueSeverity.MEDIUM.value,
                title="No Daily Trade Limit",
                description="No maximum trades per day restriction",
                impact="May overtrade during volatile days",
                recommendation=f"Add daily trade limit (suggested: {self.DEFAULT_MAX_TRADES_PER_DAY})",
                auto_fixable=True
            ))
        
        # No loss streak protection
        has_loss_protection = any('loss' in f.get('description', '').lower() or
                                  'streak' in f.get('description', '').lower()
                                  for f in filters)
        if not has_loss_protection:
            self.issues.append(DetectedIssue(
                category=IssueCategory.OVERTRADING.value,
                severity=IssueSeverity.HIGH.value,
                title="No Loss Streak Protection",
                description="No consecutive loss limit detected",
                impact="May continue trading during drawdown periods",
                recommendation=f"Stop after {self.DEFAULT_MAX_LOSS_STREAK} consecutive losses",
                auto_fixable=True
            ))
    
    def _detect_parameter_issues(self, parsed: Dict, strategy: Dict) -> None:
        """Detect suboptimal parameters"""
        indicators = parsed.get('indicators', [])
        parameters = parsed.get('parameters', {})
        
        for indicator in indicators:
            ind_type = indicator.get('type', '')
            ind_params = indicator.get('parameters', {})
            
            if ind_type in self.OPTIMAL_PARAMETERS:
                optimal = self.OPTIMAL_PARAMETERS[ind_type]
                
                for param_name, (min_val, max_val) in optimal.items():
                    param_value = ind_params.get(param_name)
                    
                    # Handle parameter references (e.g., "FastPeriod")
                    if isinstance(param_value, str) and param_value in parameters:
                        param_info = parameters[param_value]
                        param_value = param_info.get('default')
                    
                    if param_value is not None:
                        try:
                            val = float(param_value) if isinstance(param_value, (int, float, str)) else None
                            if val and (val < min_val or val > max_val):
                                self.issues.append(DetectedIssue(
                                    category=IssueCategory.PARAMETER.value,
                                    severity=IssueSeverity.LOW.value,
                                    title=f"Suboptimal {ind_type} {param_name}",
                                    description=f"Current: {val}, Recommended: {min_val}-{max_val}",
                                    impact="May reduce indicator effectiveness",
                                    recommendation=f"Adjust to {min_val}-{max_val} range",
                                    auto_fixable=True
                                ))
                        except (ValueError, TypeError):
                            pass
    
    # ==================== APPLY IMPROVEMENTS ====================
    
    def _apply_complexity_fixes(self, strategy: Dict, parsed: Dict) -> Dict:
        """Apply fixes for complexity issues (mostly recommendations, not auto-fix)"""
        # Complexity fixes are mostly manual, but we can add analysis metadata
        analysis = strategy.get('analysis', {})
        
        indicators = parsed.get('indicators', [])
        if len(indicators) > self.MAX_INDICATORS:
            analysis['complexity_warning'] = f"Consider reducing from {len(indicators)} to {self.MAX_INDICATORS} indicators"
        
        strategy['analysis'] = analysis
        return strategy
    
    def _apply_risk_fixes(self, strategy: Dict, parsed: Dict) -> Dict:
        """Apply risk management improvements"""
        risk_config = strategy.get('risk_config', {})
        original_risk = deepcopy(risk_config)
        risk = parsed.get('risk_management', {})
        
        # Add stop loss if missing
        if risk_config.get('stop_loss_type') == 'none' or not risk.get('has_stop_loss'):
            risk_config['stop_loss_type'] = 'fixed_pips'
            risk_config['stop_loss_value'] = 25.0  # Default 25 pips
            self.changes.append(AppliedChange(
                change_type='added',
                component='risk',
                description="Added default stop loss",
                before=original_risk.get('stop_loss_value'),
                after=25.0,
                reason="Missing stop loss protection"
            ))
        
        # Add take profit if missing
        if risk_config.get('take_profit_type') == 'none' or not risk.get('has_take_profit'):
            sl_value = risk_config.get('stop_loss_value', 25.0)
            tp_value = sl_value * self.OPTIMAL_RR_RATIO
            risk_config['take_profit_type'] = 'fixed_pips'
            risk_config['take_profit_value'] = tp_value
            self.changes.append(AppliedChange(
                change_type='added',
                component='risk',
                description="Added take profit target",
                before=original_risk.get('take_profit_value'),
                after=tp_value,
                reason=f"Set to {self.OPTIMAL_RR_RATIO}x stop loss for optimal R:R"
            ))
        
        # Fix poor risk-reward ratio
        sl = risk_config.get('stop_loss_value')
        tp = risk_config.get('take_profit_value')
        if sl and tp:
            rr = tp / sl
            if rr < self.MIN_RR_RATIO:
                new_tp = sl * self.OPTIMAL_RR_RATIO
                risk_config['take_profit_value'] = new_tp
                self.changes.append(AppliedChange(
                    change_type='optimized',
                    component='risk',
                    description=f"Improved R:R ratio from 1:{rr:.2f} to 1:{self.OPTIMAL_RR_RATIO}",
                    before=tp,
                    after=new_tp,
                    reason="Poor risk-reward ratio"
                ))
            elif rr > self.MAX_RR_RATIO:
                new_tp = sl * self.OPTIMAL_RR_RATIO
                risk_config['take_profit_value'] = new_tp
                self.changes.append(AppliedChange(
                    change_type='optimized',
                    component='risk',
                    description=f"Adjusted R:R ratio from 1:{rr:.2f} to 1:{self.OPTIMAL_RR_RATIO}",
                    before=tp,
                    after=new_tp,
                    reason="Overly aggressive R:R may hurt win rate"
                ))
        
        # Add trailing stop for trend strategies
        category = strategy.get('category', '')
        if category == 'trend_following' and not risk_config.get('trailing_stop'):
            risk_config['trailing_stop'] = True
            risk_config['trailing_value'] = risk_config.get('stop_loss_value', 25.0) * 0.8
            self.changes.append(AppliedChange(
                change_type='added',
                component='risk',
                description="Added trailing stop for trend strategy",
                before=False,
                after=True,
                reason="Lock in profits during trending moves"
            ))
        
        # Improve position sizing
        if risk_config.get('position_sizing') == 'fixed':
            risk_config['position_sizing'] = 'percent_risk'
            risk_config['size_value'] = 1.0  # 1% risk per trade
            self.changes.append(AppliedChange(
                change_type='modified',
                component='risk',
                description="Changed to percentage-based position sizing",
                before='fixed',
                after='percent_risk (1%)',
                reason="Better risk management across account size changes"
            ))
        
        strategy['risk_config'] = risk_config
        return strategy
    
    def _add_missing_filters(self, strategy: Dict, parsed: Dict) -> Dict:
        """Add missing filters to the strategy"""
        filters = strategy.get('filters', [])
        filter_types = [f.get('type') for f in filters]
        
        next_filter_id = len(filters) + 1
        
        # Add session filter
        if 'time' not in filter_types:
            filters.append({
                'id': f'filter_{next_filter_id}',
                'type': 'time',
                'name': 'Trading Session Filter',
                'parameters': {
                    'start_hour': 8,
                    'end_hour': 17,
                    'timezone': 'UTC',
                    'description': 'Trade during London/NY sessions (8:00-17:00 UTC)'
                },
                'is_required': True
            })
            self.changes.append(AppliedChange(
                change_type='added',
                component='filter',
                description="Added trading session filter (8:00-17:00 UTC)",
                reason="Avoid low-liquidity periods"
            ))
            next_filter_id += 1
        
        # Add spread filter
        if 'spread' not in filter_types:
            filters.append({
                'id': f'filter_{next_filter_id}',
                'type': 'spread',
                'name': 'Maximum Spread Filter',
                'parameters': {
                    'max_spread_pips': 3.0,
                    'description': 'Skip trades when spread > 3 pips'
                },
                'is_required': True
            })
            self.changes.append(AppliedChange(
                change_type='added',
                component='filter',
                description="Added spread filter (max 3 pips)",
                reason="Avoid high-spread conditions"
            ))
            next_filter_id += 1
        
        # Add volatility filter
        if 'volatility' not in filter_types:
            filters.append({
                'id': f'filter_{next_filter_id}',
                'type': 'volatility',
                'name': 'ATR Volatility Filter',
                'parameters': {
                    'atr_period': 14,
                    'min_atr_pips': 5.0,
                    'max_atr_pips': 50.0,
                    'description': 'Trade only when ATR between 5-50 pips'
                },
                'is_required': True
            })
            self.changes.append(AppliedChange(
                change_type='added',
                component='filter',
                description="Added ATR volatility filter (5-50 pips)",
                reason="Avoid choppy and extreme volatility"
            ))
            next_filter_id += 1
        
        # Add trend filter for mean-reversion
        category = strategy.get('category', '')
        if category == 'mean_reversion' and 'trend' not in filter_types:
            filters.append({
                'id': f'filter_{next_filter_id}',
                'type': 'trend',
                'name': 'Trend Strength Filter (ADX)',
                'parameters': {
                    'adx_period': 14,
                    'max_adx': 25,
                    'description': 'Only trade when ADX < 25 (ranging market)'
                },
                'is_required': True
            })
            self.changes.append(AppliedChange(
                change_type='added',
                component='filter',
                description="Added ADX trend filter (trade when ADX < 25)",
                reason="Mean-reversion works best in ranging markets"
            ))
            next_filter_id += 1
        
        strategy['filters'] = filters
        return strategy
    
    def _add_overtrading_protection(self, strategy: Dict, parsed: Dict) -> Dict:
        """Add overtrading protection mechanisms"""
        filters = strategy.get('filters', [])
        risk_config = strategy.get('risk_config', {})
        
        next_filter_id = len(filters) + 1
        
        # Add max positions
        if not risk_config.get('max_concurrent_trades') or risk_config.get('max_concurrent_trades', 0) > 3:
            risk_config['max_concurrent_trades'] = 1
            self.changes.append(AppliedChange(
                change_type='added',
                component='risk',
                description="Set max concurrent trades to 1",
                reason="Prevent position pyramiding"
            ))
        
        # Add daily trade limit filter
        has_daily_limit = any('daily' in f.get('name', '').lower() for f in filters)
        if not has_daily_limit:
            filters.append({
                'id': f'filter_{next_filter_id}',
                'type': 'daily_limit',
                'name': 'Daily Trade Limit',
                'parameters': {
                    'max_trades_per_day': self.DEFAULT_MAX_TRADES_PER_DAY,
                    'description': f'Maximum {self.DEFAULT_MAX_TRADES_PER_DAY} trades per day'
                },
                'is_required': True
            })
            self.changes.append(AppliedChange(
                change_type='added',
                component='filter',
                description=f"Added daily trade limit ({self.DEFAULT_MAX_TRADES_PER_DAY} trades/day)",
                reason="Prevent overtrading"
            ))
            next_filter_id += 1
        
        # Add loss streak protection
        has_loss_protection = any('loss' in f.get('name', '').lower() for f in filters)
        if not has_loss_protection:
            filters.append({
                'id': f'filter_{next_filter_id}',
                'type': 'loss_streak',
                'name': 'Loss Streak Protection',
                'parameters': {
                    'max_consecutive_losses': self.DEFAULT_MAX_LOSS_STREAK,
                    'cooldown_hours': 4,
                    'description': f'Stop trading after {self.DEFAULT_MAX_LOSS_STREAK} consecutive losses, resume after 4 hours'
                },
                'is_required': True
            })
            self.changes.append(AppliedChange(
                change_type='added',
                component='filter',
                description=f"Added loss streak protection ({self.DEFAULT_MAX_LOSS_STREAK} losses → 4hr cooldown)",
                reason="Prevent revenge trading and drawdown spirals"
            ))
        
        strategy['filters'] = filters
        strategy['risk_config'] = risk_config
        return strategy
    
    def _optimize_parameters(self, strategy: Dict, parsed: Dict) -> Dict:
        """Optimize indicator parameters"""
        indicators = strategy.get('indicators', [])
        parameters = parsed.get('parameters', {})
        
        # Track optimized parameters
        optimized_params = {}
        
        for indicator in indicators:
            ind_type = indicator.get('type', '')
            ind_params = indicator.get('parameters', {})
            
            if ind_type in self.OPTIMAL_PARAMETERS:
                optimal = self.OPTIMAL_PARAMETERS[ind_type]
                
                for param_name, (min_val, max_val) in optimal.items():
                    param_value = ind_params.get(param_name)
                    
                    # Handle parameter references
                    original_ref = None
                    if isinstance(param_value, str) and param_value in parameters:
                        original_ref = param_value
                        param_info = parameters[param_value]
                        param_value = param_info.get('default')
                    
                    if param_value is not None:
                        try:
                            val = float(param_value)
                            if val < min_val:
                                optimal_val = min_val
                                ind_params[param_name] = optimal_val
                                if original_ref:
                                    optimized_params[original_ref] = optimal_val
                                self.changes.append(AppliedChange(
                                    change_type='optimized',
                                    component='parameter',
                                    description=f"Adjusted {ind_type} {param_name}",
                                    before=val,
                                    after=optimal_val,
                                    reason=f"Value was below optimal range ({min_val}-{max_val})"
                                ))
                            elif val > max_val:
                                optimal_val = max_val
                                ind_params[param_name] = optimal_val
                                if original_ref:
                                    optimized_params[original_ref] = optimal_val
                                self.changes.append(AppliedChange(
                                    change_type='optimized',
                                    component='parameter',
                                    description=f"Adjusted {ind_type} {param_name}",
                                    before=val,
                                    after=optimal_val,
                                    reason=f"Value was above optimal range ({min_val}-{max_val})"
                                ))
                        except (ValueError, TypeError):
                            pass
            
            indicator['parameters'] = ind_params
        
        # Add optimized parameters to metadata
        metadata = strategy.get('metadata', {})
        if optimized_params:
            metadata['optimized_parameters'] = optimized_params
        strategy['metadata'] = metadata
        strategy['indicators'] = indicators
        
        return strategy
    
    # ==================== SCORING & SUMMARY ====================
    
    def _calculate_improvement_score(self, original: Dict, improved: Dict) -> float:
        """Calculate improvement score (0-100)"""
        score = 0.0
        max_score = 100.0
        
        # Risk improvements (40 points max)
        orig_risk = original.get('risk_config', {})
        impr_risk = improved.get('risk_config', {})
        
        if impr_risk.get('stop_loss_type') != 'none' and orig_risk.get('stop_loss_type') == 'none':
            score += 15
        if impr_risk.get('take_profit_type') != 'none' and orig_risk.get('take_profit_type') == 'none':
            score += 10
        if impr_risk.get('trailing_stop') and not orig_risk.get('trailing_stop'):
            score += 5
        if impr_risk.get('position_sizing') != 'fixed' and orig_risk.get('position_sizing') == 'fixed':
            score += 10
        
        # Filter improvements (40 points max)
        orig_filters = len(original.get('filters', []))
        impr_filters = len(improved.get('filters', []))
        filter_diff = impr_filters - orig_filters
        score += min(filter_diff * 8, 40)
        
        # Parameter optimizations (20 points max)
        param_changes = sum(1 for c in self.changes if c.change_type == 'optimized')
        score += min(param_changes * 5, 20)
        
        return min(score, max_score)
    
    def _generate_summary(self) -> str:
        """Generate human-readable summary"""
        if not self.changes:
            return "No changes needed - strategy already well-configured."
        
        parts = [f"Applied {len(self.changes)} improvement(s):"]
        
        # Group changes by component
        by_component = {}
        for change in self.changes:
            comp = change.component
            if comp not in by_component:
                by_component[comp] = []
            by_component[comp].append(change)
        
        for component, changes in by_component.items():
            parts.append(f"  {component.upper()}: {len(changes)} change(s)")
        
        # Count issues by severity
        critical = sum(1 for i in self.issues if i.severity == IssueSeverity.CRITICAL.value)
        high = sum(1 for i in self.issues if i.severity == IssueSeverity.HIGH.value)
        
        if critical > 0:
            parts.append(f"⚠️ {critical} CRITICAL issue(s) addressed")
        if high > 0:
            parts.append(f"⚡ {high} HIGH priority issue(s) addressed")
        
        return " | ".join(parts)


def create_refinement_engine() -> StrategyRefinementEngine:
    """Factory function to create refinement engine"""
    return StrategyRefinementEngine()
