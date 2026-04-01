"""
Strategy Parser - Phase 1
Converts parsed C# bot data into a structured strategy format
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from .csharp_parser import ParsedBot, IndicatorInfo, EntryCondition, RiskManagement


@dataclass
class StrategyIndicator:
    """Standardized indicator representation"""
    id: str
    type: str
    display_name: str
    parameters: Dict[str, Any]
    role: str  # 'signal', 'filter', 'exit', 'risk'


@dataclass
class StrategySignal:
    """Trading signal definition"""
    id: str
    name: str
    direction: str  # 'long', 'short'
    conditions: List[Dict[str, Any]]
    indicators_required: List[str]
    priority: int = 1


@dataclass
class StrategyRisk:
    """Risk management configuration"""
    stop_loss_type: str = "none"  # 'fixed_pips', 'atr_based', 'percent', 'none'
    stop_loss_value: Optional[float] = None
    take_profit_type: str = "none"  # 'fixed_pips', 'rr_ratio', 'percent', 'none'
    take_profit_value: Optional[float] = None
    trailing_stop: bool = False
    trailing_value: Optional[float] = None
    position_sizing: str = "fixed"  # 'fixed', 'percent_risk', 'percent_equity'
    size_value: Optional[float] = None
    max_concurrent_trades: int = 1


@dataclass
class StrategyFilter:
    """Trading filter/condition"""
    id: str
    type: str
    name: str
    parameters: Dict[str, Any]
    is_required: bool = True


@dataclass
class Strategy:
    """Complete structured strategy"""
    name: str
    version: str = "1.0"
    description: str = ""
    category: str = "trend_following"  # 'trend_following', 'mean_reversion', 'breakout', 'scalping'
    timeframes: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    indicators: List[StrategyIndicator] = field(default_factory=list)
    entry_signals: List[StrategySignal] = field(default_factory=list)
    exit_signals: List[StrategySignal] = field(default_factory=list)
    risk_config: StrategyRisk = field(default_factory=StrategyRisk)
    filters: List[StrategyFilter] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    analysis: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "timeframes": self.timeframes,
            "symbols": self.symbols,
            "indicators": [asdict(i) for i in self.indicators],
            "entry_signals": [asdict(s) for s in self.entry_signals],
            "exit_signals": [asdict(s) for s in self.exit_signals],
            "risk_config": asdict(self.risk_config),
            "filters": [asdict(f) for f in self.filters],
            "metadata": self.metadata,
            "analysis": self.analysis
        }


class StrategyParser:
    """
    Converts ParsedBot into structured Strategy format
    Analyzes trading logic and categorizes the strategy
    """
    
    # Strategy category detection rules
    CATEGORY_INDICATORS = {
        'trend_following': ['MovingAverage', 'SMA', 'EMA', 'MACD', 'ADX', 'Parabolic', 'Ichimoku'],
        'mean_reversion': ['RSI', 'Stochastic', 'CCI', 'BollingerBands', 'WilliamsR'],
        'breakout': ['BollingerBands', 'ATR', 'Parabolic'],
        'scalping': ['RSI', 'Stochastic', 'MACD'],
    }
    
    def __init__(self):
        self.strategy = None
        self.parsed_bot = None
    
    def parse(self, parsed_bot: ParsedBot) -> Strategy:
        """
        Convert ParsedBot to Strategy format
        """
        self.parsed_bot = parsed_bot
        
        # Create base strategy
        self.strategy = Strategy(
            name=parsed_bot.bot_name,
            description=self._generate_description(),
            category=self._detect_category(),
            timeframes=[parsed_bot.timeframe] if parsed_bot.timeframe != "Unknown" else [],
            symbols=[parsed_bot.symbol] if parsed_bot.symbol != "Unknown" else []
        )
        
        # Convert components
        self._convert_indicators()
        self._convert_entry_signals()
        self._convert_exit_signals()
        self._convert_risk_config()
        self._convert_filters()
        self._add_metadata()
        self._analyze_strategy()
        
        return self.strategy
    
    def _generate_description(self) -> str:
        """Generate human-readable strategy description"""
        parts = []
        
        # Describe indicators
        if self.parsed_bot.indicators:
            indicator_names = [i.name for i in self.parsed_bot.indicators]
            parts.append(f"Uses {', '.join(indicator_names)}")
        
        # Describe entry logic
        long_entries = [e for e in self.parsed_bot.entry_conditions if e.direction == "long"]
        short_entries = [e for e in self.parsed_bot.entry_conditions if e.direction == "short"]
        
        if long_entries and short_entries:
            parts.append("with both long and short entries")
        elif long_entries:
            parts.append("with long-only entries")
        elif short_entries:
            parts.append("with short-only entries")
        
        # Describe risk
        risk = self.parsed_bot.risk_management
        if risk.has_stop_loss:
            parts.append(f"Stop loss: {risk.stop_loss_pips} pips")
        if risk.has_take_profit:
            parts.append(f"Take profit: {risk.take_profit_pips} pips")
        if risk.has_trailing_stop:
            parts.append("with trailing stop")
        
        return ". ".join(parts) if parts else "Automated trading strategy"
    
    def _detect_category(self) -> str:
        """Detect strategy category based on indicators and logic"""
        indicator_types = [i.type for i in self.parsed_bot.indicators]
        
        scores = {cat: 0 for cat in self.CATEGORY_INDICATORS}
        
        for indicator in indicator_types:
            for category, cat_indicators in self.CATEGORY_INDICATORS.items():
                if indicator in cat_indicators:
                    scores[category] += 1
        
        # Check for specific patterns
        entry_conditions = " ".join([e.condition_text for e in self.parsed_bot.entry_conditions])
        
        if 'CrossedAbove' in entry_conditions or 'CrossedBelow' in entry_conditions:
            scores['trend_following'] += 2
        
        if any(i.type in ['RSI', 'Stochastic'] for i in self.parsed_bot.indicators):
            if '>' in entry_conditions and '<' in entry_conditions:
                scores['mean_reversion'] += 2
        
        # Return highest scoring category
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        return "trend_following"  # default
    
    def _convert_indicators(self) -> None:
        """Convert parsed indicators to strategy format"""
        for idx, indicator in enumerate(self.parsed_bot.indicators):
            role = self._determine_indicator_role(indicator)
            
            strat_indicator = StrategyIndicator(
                id=f"ind_{idx + 1}",
                type=indicator.type,
                display_name=self._get_indicator_display_name(indicator),
                parameters=indicator.parameters,
                role=role
            )
            self.strategy.indicators.append(strat_indicator)
    
    def _determine_indicator_role(self, indicator: IndicatorInfo) -> str:
        """Determine the role of an indicator in the strategy"""
        # Check if used in entry conditions
        for entry in self.parsed_bot.entry_conditions:
            if indicator.name in entry.indicators_used or indicator.variable_name in entry.condition_text:
                return "signal"
        
        # Check if used in exit conditions
        for exit_cond in self.parsed_bot.exit_conditions:
            if indicator.name.lower() in exit_cond.condition_text.lower():
                return "exit"
        
        # ATR often used for risk
        if indicator.type == 'ATR':
            return "risk"
        
        # ADX often used as filter
        if indicator.type in ['ADX']:
            return "filter"
        
        return "signal"  # default
    
    def _get_indicator_display_name(self, indicator: IndicatorInfo) -> str:
        """Generate human-readable indicator name"""
        name_map = {
            'SMA': 'Simple Moving Average',
            'EMA': 'Exponential Moving Average',
            'RSI': 'Relative Strength Index',
            'MACD': 'MACD',
            'BollingerBands': 'Bollinger Bands',
            'ATR': 'Average True Range',
            'ADX': 'Average Directional Index',
            'Stochastic': 'Stochastic Oscillator',
            'CCI': 'Commodity Channel Index',
            'Parabolic': 'Parabolic SAR',
            'Ichimoku': 'Ichimoku Cloud',
            'WilliamsR': 'Williams %R',
            'MFI': 'Money Flow Index',
            'OBV': 'On Balance Volume',
        }
        
        base_name = name_map.get(indicator.type, indicator.type)
        
        # Add period if available
        period = indicator.parameters.get('period')
        if period:
            return f"{base_name} ({period})"
        
        return base_name
    
    def _convert_entry_signals(self) -> None:
        """Convert entry conditions to strategy signals"""
        for idx, entry in enumerate(self.parsed_bot.entry_conditions):
            conditions = self._parse_condition_to_list(entry.condition_text, entry.logic_type)
            
            signal = StrategySignal(
                id=f"entry_{idx + 1}",
                name=f"{'Long' if entry.direction == 'long' else 'Short'} Entry {idx + 1}",
                direction=entry.direction,
                conditions=conditions,
                indicators_required=entry.indicators_used,
                priority=idx + 1
            )
            self.strategy.entry_signals.append(signal)
    
    def _convert_exit_signals(self) -> None:
        """Convert exit conditions to strategy signals"""
        for idx, exit_cond in enumerate(self.parsed_bot.exit_conditions):
            if exit_cond.exit_type == "signal":
                signal = StrategySignal(
                    id=f"exit_{idx + 1}",
                    name=f"Signal Exit {idx + 1}",
                    direction="both",
                    conditions=[{
                        "type": "custom",
                        "expression": exit_cond.condition_text
                    }],
                    indicators_required=[],
                    priority=idx + 1
                )
                self.strategy.exit_signals.append(signal)
    
    def _convert_risk_config(self) -> None:
        """Convert risk management to strategy format"""
        risk = self.parsed_bot.risk_management
        
        # Determine stop loss type
        sl_type = "none"
        sl_value = None
        if risk.has_stop_loss:
            if risk.stop_loss_pips:
                sl_type = "fixed_pips"
                sl_value = risk.stop_loss_pips
            elif risk.stop_loss_percent:
                sl_type = "percent"
                sl_value = risk.stop_loss_percent
        
        # Determine take profit type
        tp_type = "none"
        tp_value = None
        if risk.has_take_profit:
            if risk.take_profit_pips:
                tp_type = "fixed_pips"
                tp_value = risk.take_profit_pips
            elif risk.take_profit_percent:
                tp_type = "percent"
                tp_value = risk.take_profit_percent
        
        # Determine position sizing
        pos_sizing = "fixed"
        size_value = risk.lot_size
        if risk.risk_percent:
            pos_sizing = "percent_risk"
            size_value = risk.risk_percent
        
        self.strategy.risk_config = StrategyRisk(
            stop_loss_type=sl_type,
            stop_loss_value=sl_value,
            take_profit_type=tp_type,
            take_profit_value=tp_value,
            trailing_stop=risk.has_trailing_stop,
            trailing_value=risk.trailing_stop_pips,
            position_sizing=pos_sizing,
            size_value=size_value,
            max_concurrent_trades=risk.max_positions or 1
        )
    
    def _convert_filters(self) -> None:
        """Convert filters to strategy format"""
        for idx, filter_ in enumerate(self.parsed_bot.filters):
            strat_filter = StrategyFilter(
                id=f"filter_{idx + 1}",
                type=filter_.filter_type,
                name=filter_.description,
                parameters={"condition": filter_.condition_text},
                is_required=True
            )
            self.strategy.filters.append(strat_filter)
    
    def _add_metadata(self) -> None:
        """Add metadata about the strategy"""
        self.strategy.metadata = {
            "source": "ctrader_cbot",
            "original_class": self.parsed_bot.bot_class,
            "parameters_count": len(self.parsed_bot.parameters),
            "indicators_count": len(self.parsed_bot.indicators),
            "entry_signals_count": len(self.strategy.entry_signals),
            "has_long_entries": any(s.direction == "long" for s in self.strategy.entry_signals),
            "has_short_entries": any(s.direction == "short" for s in self.strategy.entry_signals),
            "has_filters": len(self.strategy.filters) > 0,
            "original_parameters": self.parsed_bot.parameters
        }
    
    def _analyze_strategy(self) -> None:
        """Perform analysis on the strategy"""
        analysis = {
            "complexity": self._calculate_complexity(),
            "risk_score": self._calculate_risk_score(),
            "completeness": self._calculate_completeness(),
            "recommendations": self._generate_recommendations(),
            "warnings": self.parsed_bot.warnings.copy()
        }
        self.strategy.analysis = analysis
    
    def _calculate_complexity(self) -> str:
        """Calculate strategy complexity level"""
        score = 0
        
        # Indicators add complexity
        score += len(self.strategy.indicators) * 2
        
        # Entry conditions add complexity
        for signal in self.strategy.entry_signals:
            score += len(signal.conditions)
        
        # Filters add complexity
        score += len(self.strategy.filters)
        
        if score <= 5:
            return "simple"
        elif score <= 10:
            return "moderate"
        else:
            return "complex"
    
    def _calculate_risk_score(self) -> Dict[str, Any]:
        """Calculate risk assessment score"""
        risk = self.strategy.risk_config
        score = 100  # Start with perfect score
        issues = []
        
        # Check stop loss
        if risk.stop_loss_type == "none":
            score -= 30
            issues.append("No stop loss defined - high risk")
        
        # Check take profit
        if risk.take_profit_type == "none":
            score -= 10
            issues.append("No take profit defined")
        
        # Check position sizing
        if risk.position_sizing == "fixed":
            score -= 5
            issues.append("Fixed position sizing may not adapt to account size")
        
        # Bonus for trailing stop
        if risk.trailing_stop:
            score += 5
        
        return {
            "score": max(0, min(100, score)),
            "level": "low" if score >= 70 else ("medium" if score >= 40 else "high"),
            "issues": issues
        }
    
    def _calculate_completeness(self) -> Dict[str, Any]:
        """Calculate how complete the strategy definition is"""
        checks = {
            "has_indicators": len(self.strategy.indicators) > 0,
            "has_entry_signals": len(self.strategy.entry_signals) > 0,
            "has_stop_loss": self.strategy.risk_config.stop_loss_type != "none",
            "has_take_profit": self.strategy.risk_config.take_profit_type != "none",
            "has_position_sizing": self.strategy.risk_config.size_value is not None,
            "has_timeframe": len(self.strategy.timeframes) > 0,
            "has_symbol": len(self.strategy.symbols) > 0,
        }
        
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        
        return {
            "score": round((passed / total) * 100),
            "passed": passed,
            "total": total,
            "checks": checks
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations for improving the strategy"""
        recommendations = []
        risk = self.strategy.risk_config
        
        # Stop loss recommendations
        if risk.stop_loss_type == "none":
            recommendations.append("Add a stop loss to limit potential losses")
        elif risk.stop_loss_type == "fixed_pips" and risk.stop_loss_value and risk.stop_loss_value > 50:
            recommendations.append("Consider tighter stop loss - current value may be too wide")
        
        # Take profit recommendations
        if risk.take_profit_type == "none":
            recommendations.append("Consider adding take profit targets")
        
        # Risk:Reward ratio
        if (risk.stop_loss_value and risk.take_profit_value and 
            risk.stop_loss_type == risk.take_profit_type):
            rr_ratio = risk.take_profit_value / risk.stop_loss_value
            if rr_ratio < 1:
                recommendations.append(f"Risk:Reward ratio is {rr_ratio:.2f}:1 - consider improving to at least 1:1")
        
        # Position sizing
        if risk.position_sizing == "fixed":
            recommendations.append("Consider using risk-based position sizing for better capital management")
        
        # Trailing stop
        if not risk.trailing_stop and self.strategy.category == "trend_following":
            recommendations.append("Trailing stop could help capture more profit in trending markets")
        
        # Filters
        if len(self.strategy.filters) == 0:
            recommendations.append("Consider adding filters (time, spread, volatility) to avoid bad trading conditions")
        
        # Entry signals
        if len(self.strategy.entry_signals) == 1:
            entry = self.strategy.entry_signals[0]
            if entry.direction in ["long", "short"]:
                recommendations.append(f"Strategy is {entry.direction}-only - consider adding opposite direction for more opportunities")
        
        return recommendations
    
    def _parse_condition_to_list(self, condition_text: str, logic_type: str) -> List[Dict[str, Any]]:
        """Parse condition text into structured list"""
        conditions = []
        
        if logic_type == "crossover":
            if "CrossedAbove" in condition_text:
                conditions.append({
                    "type": "crossover",
                    "direction": "above",
                    "expression": condition_text
                })
            elif "CrossedBelow" in condition_text:
                conditions.append({
                    "type": "crossover",
                    "direction": "below",
                    "expression": condition_text
                })
        
        elif logic_type == "compound":
            # Split by && or ||
            parts = [p.strip() for p in condition_text.replace('&&', '||').split('||')]
            for part in parts:
                if part:
                    conditions.append({
                        "type": "comparison",
                        "expression": part
                    })
        
        else:
            conditions.append({
                "type": "simple",
                "expression": condition_text
            })
        
        return conditions
