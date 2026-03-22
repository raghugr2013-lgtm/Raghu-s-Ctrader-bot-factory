"""
C# cBot Parser - Phase 1
Extracts trading logic from cTrader cBot C# code
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class IndicatorInfo:
    """Extracted indicator information"""
    name: str
    type: str  # e.g., 'MovingAverage', 'RSI', 'MACD'
    parameters: Dict[str, Any] = field(default_factory=dict)
    variable_name: str = ""
    source: str = "Close"  # Price source


@dataclass
class EntryCondition:
    """Extracted entry condition"""
    direction: str  # 'long', 'short', 'both'
    condition_text: str
    indicators_used: List[str] = field(default_factory=list)
    logic_type: str = "simple"  # 'simple', 'compound', 'crossover'


@dataclass
class ExitCondition:
    """Extracted exit condition"""
    exit_type: str  # 'stop_loss', 'take_profit', 'trailing', 'signal', 'time'
    condition_text: str
    value: Optional[float] = None
    is_dynamic: bool = False


@dataclass
class RiskManagement:
    """Extracted risk management settings"""
    has_stop_loss: bool = False
    stop_loss_pips: Optional[float] = None
    stop_loss_percent: Optional[float] = None
    has_take_profit: bool = False
    take_profit_pips: Optional[float] = None
    take_profit_percent: Optional[float] = None
    has_trailing_stop: bool = False
    trailing_stop_pips: Optional[float] = None
    position_sizing: str = "fixed"  # 'fixed', 'percent', 'risk_based'
    lot_size: Optional[float] = None
    risk_percent: Optional[float] = None
    max_positions: Optional[int] = None


@dataclass
class Filter:
    """Trading filter/condition"""
    filter_type: str  # 'time', 'spread', 'volatility', 'trend', 'custom'
    description: str
    condition_text: str


@dataclass
class ParsedBot:
    """Complete parsed bot structure"""
    bot_name: str = "Unknown"
    bot_class: str = ""
    timeframe: str = "Unknown"
    symbol: str = "Unknown"
    indicators: List[IndicatorInfo] = field(default_factory=list)
    entry_conditions: List[EntryCondition] = field(default_factory=list)
    exit_conditions: List[ExitCondition] = field(default_factory=list)
    risk_management: RiskManagement = field(default_factory=RiskManagement)
    filters: List[Filter] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    raw_methods: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "bot_name": self.bot_name,
            "bot_class": self.bot_class,
            "timeframe": self.timeframe,
            "symbol": self.symbol,
            "indicators": [asdict(i) for i in self.indicators],
            "entry_conditions": [asdict(e) for e in self.entry_conditions],
            "exit_conditions": [asdict(e) for e in self.exit_conditions],
            "risk_management": asdict(self.risk_management),
            "filters": [asdict(f) for f in self.filters],
            "parameters": self.parameters,
            "raw_methods": self.raw_methods,
            "warnings": self.warnings
        }


class CSharpBotParser:
    """
    Parser for cTrader cBot C# code
    Extracts indicators, entry/exit logic, risk management, and filters
    """
    
    # Common cTrader indicator patterns
    INDICATOR_PATTERNS = {
        'MovingAverage': r'Indicators\.(?:Simple|Exponential|Weighted|Smoothed)?MovingAverage\s*\(\s*([^)]+)\)',
        'SMA': r'Indicators\.SimpleMovingAverage\s*\(\s*([^)]+)\)',
        'EMA': r'Indicators\.ExponentialMovingAverage\s*\(\s*([^)]+)\)',
        'RSI': r'Indicators\.RelativeStrengthIndex\s*\(\s*([^)]+)\)',
        'MACD': r'Indicators\.MacdCrossOver\s*\(\s*([^)]+)\)|Indicators\.Macd\s*\(\s*([^)]+)\)',
        'BollingerBands': r'Indicators\.BollingerBands\s*\(\s*([^)]+)\)',
        'Stochastic': r'Indicators\.StochasticOscillator\s*\(\s*([^)]+)\)',
        'ATR': r'Indicators\.AverageTrueRange\s*\(\s*([^)]+)\)',
        'ADX': r'Indicators\.DirectionalMovementSystem\s*\(\s*([^)]+)\)',
        'CCI': r'Indicators\.CommodityChannelIndex\s*\(\s*([^)]+)\)',
        'Parabolic': r'Indicators\.ParabolicSAR\s*\(\s*([^)]+)\)',
        'Ichimoku': r'Indicators\.IchimokuKinkoHyo\s*\(\s*([^)]+)\)',
        'WilliamsR': r'Indicators\.WilliamsPercentRange\s*\(\s*([^)]+)\)',
        'MFI': r'Indicators\.MoneyFlowIndex\s*\(\s*([^)]+)\)',
        'OBV': r'Indicators\.OnBalanceVolume\s*\(\s*([^)]+)\)',
    }
    
    # Entry signal patterns
    ENTRY_PATTERNS = {
        'crossover_above': r'(\w+)\.Result\.HasCrossedAbove\s*\(\s*([^,]+)',
        'crossover_below': r'(\w+)\.Result\.HasCrossedBelow\s*\(\s*([^,]+)',
        'cross_up': r'(\w+)\.Result\.Last\s*\(\s*\d+\s*\)\s*>\s*(\w+)',
        'cross_down': r'(\w+)\.Result\.Last\s*\(\s*\d+\s*\)\s*<\s*(\w+)',
        'value_above': r'(\w+)\.Result\.LastValue\s*>\s*(\d+)',
        'value_below': r'(\w+)\.Result\.LastValue\s*<\s*(\d+)',
    }
    
    # Trade execution patterns
    TRADE_PATTERNS = {
        'execute_buy': r'ExecuteMarketOrder\s*\(\s*TradeType\.Buy',
        'execute_sell': r'ExecuteMarketOrder\s*\(\s*TradeType\.Sell',
        'place_buy_limit': r'PlaceLimitOrder\s*\(\s*TradeType\.Buy',
        'place_sell_limit': r'PlaceLimitOrder\s*\(\s*TradeType\.Sell',
        'place_buy_stop': r'PlaceStopOrder\s*\(\s*TradeType\.Buy',
        'place_sell_stop': r'PlaceStopOrder\s*\(\s*TradeType\.Sell',
        'close_position': r'ClosePosition\s*\(',
        'modify_position': r'ModifyPosition\s*\(',
    }
    
    def __init__(self):
        self.parsed = ParsedBot()
    
    def parse(self, code: str) -> ParsedBot:
        """
        Main parsing method - extracts all components from C# code
        """
        self.parsed = ParsedBot()
        
        # Clean the code
        code = self._clean_code(code)
        
        # Extract components
        self._extract_class_info(code)
        self._extract_parameters(code)
        self._extract_indicators(code)
        self._extract_entry_conditions(code)
        self._extract_exit_conditions(code)
        self._extract_risk_management(code)
        self._extract_filters(code)
        self._extract_raw_methods(code)
        
        return self.parsed
    
    def _clean_code(self, code: str) -> str:
        """Remove comments and normalize whitespace"""
        # Remove single-line comments
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        # Remove multi-line comments
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        return code
    
    def _extract_class_info(self, code: str) -> None:
        """Extract bot class name and metadata"""
        # Find Robot attribute
        robot_attr = re.search(r'\[Robot\s*\(\s*([^]]*)\)\s*\]', code, re.DOTALL)
        if robot_attr:
            attr_content = robot_attr.group(1)
            # Extract AccessRights, TimeZone, etc.
            name_match = re.search(r'Name\s*=\s*"([^"]*)"', attr_content)
            if name_match:
                self.parsed.bot_name = name_match.group(1)
        
        # Find class definition
        class_match = re.search(r'class\s+(\w+)\s*:\s*Robot', code)
        if class_match:
            self.parsed.bot_class = class_match.group(1)
            if not self.parsed.bot_name or self.parsed.bot_name == "Unknown":
                self.parsed.bot_name = class_match.group(1)
        
        # Try to find symbol/timeframe from parameters or code
        symbol_match = re.search(r'Symbol\s*(?:\.Name)?\s*==?\s*"?(\w+)"?', code)
        if symbol_match:
            self.parsed.symbol = symbol_match.group(1)
        
        timeframe_match = re.search(r'TimeFrame\s*(?:\.Name)?\s*==?\s*"?(\w+)"?', code)
        if timeframe_match:
            self.parsed.timeframe = timeframe_match.group(1)
    
    def _extract_parameters(self, code: str) -> None:
        """Extract bot parameters with [Parameter] attribute"""
        param_pattern = r'\[Parameter\s*\(([^]]*)\)\s*\]\s*public\s+(\w+)\s+(\w+)\s*(?:\{[^}]*\}|;)'
        
        for match in re.finditer(param_pattern, code):
            attr_content = match.group(1)
            param_type = match.group(2)
            param_name = match.group(3)
            
            param_info = {
                'type': param_type,
                'name': param_name
            }
            
            # Extract default value
            default_match = re.search(r'DefaultValue\s*=\s*([^,)]+)', attr_content)
            if default_match:
                param_info['default'] = self._parse_value(default_match.group(1).strip())
            
            # Extract min/max
            min_match = re.search(r'MinValue\s*=\s*([^,)]+)', attr_content)
            if min_match:
                param_info['min'] = self._parse_value(min_match.group(1).strip())
            
            max_match = re.search(r'MaxValue\s*=\s*([^,)]+)', attr_content)
            if max_match:
                param_info['max'] = self._parse_value(max_match.group(1).strip())
            
            self.parsed.parameters[param_name] = param_info
    
    def _extract_indicators(self, code: str) -> None:
        """Extract all indicators used in the bot"""
        # Find indicator field declarations
        indicator_fields = re.findall(
            r'private\s+(\w+)\s+(\w+)\s*;',
            code
        )
        
        # Map field names to types
        field_types = {name: type_ for type_, name in indicator_fields}
        
        # Track found indicators to avoid duplicates
        found_indicators = set()
        
        # Find indicator initializations
        for indicator_type, pattern in self.INDICATOR_PATTERNS.items():
            for match in re.finditer(pattern, code):
                params_str = match.group(1) if match.group(1) else (match.group(2) if len(match.groups()) > 1 else "")
                
                # Find the variable being assigned
                line_start = code.rfind('\n', 0, match.start()) + 1
                line = code[line_start:match.end() + 50]
                
                var_match = re.search(r'(\w+)\s*=\s*Indicators\.', line)
                var_name = var_match.group(1) if var_match else f"{indicator_type.lower()}"
                
                # Skip if we've already found this variable
                if var_name in found_indicators:
                    continue
                found_indicators.add(var_name)
                
                # Parse parameters
                params = self._parse_indicator_params(params_str, indicator_type)
                
                indicator = IndicatorInfo(
                    name=indicator_type,
                    type=indicator_type,
                    parameters=params,
                    variable_name=var_name,
                    source=params.get('source', 'Close')
                )
                self.parsed.indicators.append(indicator)
        
        # Also check for custom indicators
        custom_pattern = r'Indicators\.GetIndicator<(\w+)>\s*\(\s*([^)]*)\)'
        for match in re.finditer(custom_pattern, code):
            indicator = IndicatorInfo(
                name=match.group(1),
                type="Custom",
                parameters={'args': match.group(2)},
                variable_name=""
            )
            self.parsed.indicators.append(indicator)
    
    def _parse_indicator_params(self, params_str: str, indicator_type: str) -> Dict:
        """Parse indicator initialization parameters"""
        params = {}
        parts = [p.strip() for p in params_str.split(',') if p.strip()]
        
        # Different indicators have different parameter orders
        if indicator_type in ['SMA', 'EMA', 'MovingAverage', 'SimpleMovingAverage', 'ExponentialMovingAverage']:
            if len(parts) >= 1:
                params['source'] = parts[0]
            if len(parts) >= 2:
                params['period'] = self._parse_value(parts[1])
        
        elif indicator_type == 'RSI':
            if len(parts) >= 1:
                params['source'] = parts[0]
            if len(parts) >= 2:
                params['period'] = self._parse_value(parts[1])
        
        elif indicator_type == 'MACD':
            if len(parts) >= 1:
                params['source'] = parts[0]
            if len(parts) >= 2:
                params['fast_period'] = self._parse_value(parts[1])
            if len(parts) >= 3:
                params['slow_period'] = self._parse_value(parts[2])
            if len(parts) >= 4:
                params['signal_period'] = self._parse_value(parts[3])
        
        elif indicator_type == 'BollingerBands':
            if len(parts) >= 1:
                params['source'] = parts[0]
            if len(parts) >= 2:
                params['period'] = self._parse_value(parts[1])
            if len(parts) >= 3:
                params['std_dev'] = self._parse_value(parts[2])
        
        elif indicator_type == 'ATR':
            if len(parts) >= 1:
                params['period'] = self._parse_value(parts[0])
        
        elif indicator_type == 'Stochastic':
            if len(parts) >= 1:
                params['k_period'] = self._parse_value(parts[0])
            if len(parts) >= 2:
                params['k_slowing'] = self._parse_value(parts[1])
            if len(parts) >= 3:
                params['d_period'] = self._parse_value(parts[2])
        
        return params
    
    def _extract_entry_conditions(self, code: str) -> None:
        """Extract entry/buy/sell conditions"""
        # Look for OnBar or OnTick methods - improved regex
        onbar_match = re.search(
            r'(?:protected\s+)?(?:override\s+)?void\s+OnBar\s*\(\s*\)\s*\{([\s\S]*?)(?=\n\s*(?:protected|private|public|void|\}$))',
            code
        )
        ontick_match = re.search(
            r'(?:protected\s+)?(?:override\s+)?void\s+OnTick\s*\(\s*\)\s*\{([\s\S]*?)(?=\n\s*(?:protected|private|public|void|\}$))',
            code
        )
        
        method_code = ""
        if onbar_match:
            method_code += onbar_match.group(1)
        if ontick_match:
            method_code += ontick_match.group(1)
        
        if not method_code:
            # Fallback: search entire code for trade patterns
            method_code = code
            self.parsed.warnings.append("No OnBar or OnTick method found - searching entire code")
        
        # Helper function to extract balanced parentheses content
        def extract_condition(text, start_pos):
            """Extract condition from if statement with balanced parentheses"""
            paren_count = 0
            start = -1
            for i, char in enumerate(text[start_pos:], start_pos):
                if char == '(':
                    if start == -1:
                        start = i + 1
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        return text[start:i]
            return None
        
        # Find all if statements with ExecuteMarketOrder
        if_pattern = r'if\s*\('
        
        for match in re.finditer(if_pattern, method_code):
            # Extract the full condition
            condition = extract_condition(method_code, match.start())
            if not condition:
                continue
            
            # Find what follows the if condition
            end_of_condition = match.start() + len(match.group(0)) + len(condition) + 1
            following_code = method_code[end_of_condition:end_of_condition + 200]
            
            # Clean up condition
            condition = ' '.join(condition.split())
            
            # Check if this leads to a Buy or Sell
            if 'TradeType.Buy' in following_code and 'ExecuteMarketOrder' in following_code:
                indicators_used = self._find_indicators_in_condition(condition)
                logic_type = self._determine_logic_type(condition)
                
                entry = EntryCondition(
                    direction="long",
                    condition_text=condition,
                    indicators_used=indicators_used,
                    logic_type=logic_type
                )
                self.parsed.entry_conditions.append(entry)
                
            elif 'TradeType.Sell' in following_code and 'ExecuteMarketOrder' in following_code:
                indicators_used = self._find_indicators_in_condition(condition)
                logic_type = self._determine_logic_type(condition)
                
                entry = EntryCondition(
                    direction="short",
                    condition_text=condition,
                    indicators_used=indicators_used,
                    logic_type=logic_type
                )
                self.parsed.entry_conditions.append(entry)
    
    def _extract_exit_conditions(self, code: str) -> None:
        """Extract exit conditions (stop loss, take profit, signals)"""
        # Look for ClosePosition calls
        close_pattern = r'if\s*\(([^)]+)\)\s*(?:\{[^}]*)?ClosePosition'
        for match in re.finditer(close_pattern, code, re.DOTALL):
            condition_text = match.group(1).strip()
            
            exit_cond = ExitCondition(
                exit_type="signal",
                condition_text=condition_text,
                is_dynamic=True
            )
            self.parsed.exit_conditions.append(exit_cond)
        
        # Look for ModifyPosition for trailing stops
        if re.search(r'ModifyPosition.*StopLoss', code):
            exit_cond = ExitCondition(
                exit_type="trailing",
                condition_text="Dynamic stop loss modification",
                is_dynamic=True
            )
            self.parsed.exit_conditions.append(exit_cond)
    
    def _extract_risk_management(self, code: str) -> None:
        """Extract risk management settings"""
        risk = RiskManagement()
        
        # Check for stop loss - in parameters using the parsed parameters
        for param_name, param_info in self.parsed.parameters.items():
            name_lower = param_name.lower()
            if 'stoploss' in name_lower or 'stop_loss' in name_lower or name_lower == 'sl':
                risk.has_stop_loss = True
                if 'default' in param_info:
                    risk.stop_loss_pips = float(param_info['default'])
                break
        
        # Fallback: Check code patterns
        if not risk.has_stop_loss:
            sl_param_patterns = [
                r'StopLoss\s*=\s*(\d+\.?\d*)',
                r'StopLossPips\s*=\s*(\d+\.?\d*)',
                r'stopLoss\s*=\s*(\d+\.?\d*)',
            ]
            
            for pattern in sl_param_patterns:
                match = re.search(pattern, code, re.IGNORECASE)
                if match:
                    risk.has_stop_loss = True
                    risk.stop_loss_pips = float(match.group(1))
                    break
        
        # Check for take profit - in parameters using the parsed parameters
        for param_name, param_info in self.parsed.parameters.items():
            name_lower = param_name.lower()
            if 'takeprofit' in name_lower or 'take_profit' in name_lower or name_lower == 'tp':
                risk.has_take_profit = True
                if 'default' in param_info:
                    risk.take_profit_pips = float(param_info['default'])
                break
        
        # Fallback: Check code patterns
        if not risk.has_take_profit:
            tp_param_patterns = [
                r'TakeProfit\s*=\s*(\d+\.?\d*)',
                r'TakeProfitPips\s*=\s*(\d+\.?\d*)',
                r'takeProfit\s*=\s*(\d+\.?\d*)',
            ]
            
            for pattern in tp_param_patterns:
                match = re.search(pattern, code, re.IGNORECASE)
                if match:
                    risk.has_take_profit = True
                    risk.take_profit_pips = float(match.group(1))
                    break
        
        # Check for trailing stop
        if re.search(r'TrailingStop|trailing.*stop|ModifyPosition.*StopLoss', code, re.IGNORECASE):
            risk.has_trailing_stop = True
            trailing_match = re.search(r'TrailingStop\s*=\s*(\d+\.?\d*)', code)
            if trailing_match:
                risk.trailing_stop_pips = float(trailing_match.group(1))
        
        # Check for lot size / volume
        for param_name, param_info in self.parsed.parameters.items():
            name_lower = param_name.lower()
            if 'volume' in name_lower or 'lotsize' in name_lower or 'lot_size' in name_lower:
                if 'default' in param_info:
                    risk.lot_size = float(param_info['default'])
                break
        
        # Check for risk percent
        for param_name, param_info in self.parsed.parameters.items():
            name_lower = param_name.lower()
            if 'riskpercent' in name_lower or 'risk_percent' in name_lower:
                if 'default' in param_info:
                    risk.risk_percent = float(param_info['default'])
                    risk.position_sizing = "risk_based"
                break
        
        # Check for max positions
        max_pos_match = re.search(r'MaxPositions?\s*=\s*(\d+)', code)
        if max_pos_match:
            risk.max_positions = int(max_pos_match.group(1))
        
        self.parsed.risk_management = risk
    
    def _extract_filters(self, code: str) -> None:
        """Extract trading filters (time, spread, etc.)"""
        # Time filters
        time_patterns = [
            (r'Server\.Time\.Hour\s*[<>=]+\s*(\d+)', 'Time filter on hour'),
            (r'IsTrading(?:Time|Hour)', 'Trading time filter'),
            (r'DayOfWeek\s*[!=]=', 'Day of week filter'),
        ]
        
        for pattern, desc in time_patterns:
            if re.search(pattern, code):
                filter_ = Filter(
                    filter_type="time",
                    description=desc,
                    condition_text=pattern
                )
                self.parsed.filters.append(filter_)
        
        # Spread filter
        if re.search(r'Symbol\.Spread|Spread\s*[<>]', code):
            spread_match = re.search(r'Spread\s*[<>]=?\s*(\d+\.?\d*)', code)
            filter_ = Filter(
                filter_type="spread",
                description="Spread filter",
                condition_text=spread_match.group(0) if spread_match else "Spread check"
            )
            self.parsed.filters.append(filter_)
        
        # Trend filter
        if re.search(r'(trend|Trend)\s*[!=]=', code):
            filter_ = Filter(
                filter_type="trend",
                description="Trend direction filter",
                condition_text="Trend filter detected"
            )
            self.parsed.filters.append(filter_)
        
        # Volatility filter (ATR-based)
        if re.search(r'ATR|AverageTrueRange', code) and re.search(r'if.*ATR|if.*atr', code, re.IGNORECASE):
            filter_ = Filter(
                filter_type="volatility",
                description="ATR-based volatility filter",
                condition_text="ATR volatility check"
            )
            self.parsed.filters.append(filter_)
    
    def _extract_raw_methods(self, code: str) -> None:
        """Extract raw method bodies for reference"""
        methods = ['OnStart', 'OnBar', 'OnTick', 'OnStop', 'OnError']
        
        for method in methods:
            pattern = rf'(?:protected\s+)?(?:override\s+)?void\s+{method}\s*\([^)]*\)\s*\{{([^}}]+(?:\{{[^}}]*\}}[^}}]*)*)\}}'
            match = re.search(pattern, code, re.DOTALL)
            if match:
                self.parsed.raw_methods[method] = match.group(1).strip()
    
    def _find_indicators_in_condition(self, condition: str) -> List[str]:
        """Find which indicators are referenced in a condition"""
        indicators = []
        for indicator in self.parsed.indicators:
            if indicator.variable_name and indicator.variable_name in condition:
                indicators.append(indicator.name)
            elif indicator.name.lower() in condition.lower():
                indicators.append(indicator.name)
        return list(set(indicators))
    
    def _determine_logic_type(self, condition: str) -> str:
        """Determine if condition is simple, compound, or crossover"""
        if 'CrossedAbove' in condition or 'CrossedBelow' in condition:
            return "crossover"
        elif '&&' in condition or '||' in condition:
            return "compound"
        return "simple"
    
    def _parse_value(self, value_str: str) -> Any:
        """Parse a string value to appropriate type"""
        value_str = value_str.strip().strip('"\'')
        
        # Try int
        try:
            return int(value_str)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value_str)
        except ValueError:
            pass
        
        # Try bool
        if value_str.lower() == 'true':
            return True
        if value_str.lower() == 'false':
            return False
        
        return value_str
