"""
Improved Bot Generator - Phase 3
Generates optimized C# cBot code from improved_strategy JSON
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import re


@dataclass
class GeneratedBot:
    """Generated bot result"""
    code: str
    bot_name: str
    class_name: str
    indicators_count: int
    filters_count: int
    has_risk_management: bool
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "bot_name": self.bot_name,
            "class_name": self.class_name,
            "indicators_count": self.indicators_count,
            "filters_count": self.filters_count,
            "has_risk_management": self.has_risk_management,
            "version": self.version
        }


class ImprovedBotGenerator:
    """
    Generates optimized C# cBot code from improved strategy
    
    Produces production-ready code that:
    - Compiles without errors
    - Follows cTrader API standards
    - Includes all risk management
    - Has clean, readable structure
    """
    
    # cTrader indicator type mapping
    INDICATOR_MAP = {
        'RSI': ('RelativeStrengthIndex', 'Indicators.RelativeStrengthIndex'),
        'SMA': ('SimpleMovingAverage', 'Indicators.SimpleMovingAverage'),
        'EMA': ('ExponentialMovingAverage', 'Indicators.ExponentialMovingAverage'),
        'MovingAverage': ('SimpleMovingAverage', 'Indicators.SimpleMovingAverage'),
        'MACD': ('MacdCrossOver', 'Indicators.MacdCrossOver'),
        'BollingerBands': ('BollingerBands', 'Indicators.BollingerBands'),
        'ATR': ('AverageTrueRange', 'Indicators.AverageTrueRange'),
        'Stochastic': ('StochasticOscillator', 'Indicators.StochasticOscillator'),
        'ADX': ('DirectionalMovementSystem', 'Indicators.DirectionalMovementSystem'),
        'CCI': ('CommodityChannelIndex', 'Indicators.CommodityChannelIndex'),
        'Parabolic': ('ParabolicSAR', 'Indicators.ParabolicSAR'),
    }
    
    def __init__(self):
        self.indent = "    "  # 4 spaces
    
    def generate(self, improved_strategy: Dict[str, Any], parsed_data: Optional[Dict[str, Any]] = None) -> GeneratedBot:
        """
        Generate C# cBot code from improved strategy
        
        Args:
            improved_strategy: Output from refinement engine
            parsed_data: Original parsed data (optional, for preserving entry logic)
        
        Returns:
            GeneratedBot with complete C# code
        """
        # Extract strategy info
        name = improved_strategy.get('name', 'OptimizedBot')
        class_name = self._make_class_name(name)
        category = improved_strategy.get('category', 'trend_following')
        timeframe = improved_strategy.get('timeframe', '1h')  # NEW: Extract timeframe
        
        # Convert timeframe to cTrader format
        from timeframe_utils import TimeframeConverter
        try:
            ctrader_timeframe = TimeframeConverter.to_ctrader(timeframe)
        except (ValueError, KeyError):
            ctrader_timeframe = "TimeFrame.Hour"  # Fallback to 1h
        
        # Get components
        indicators = improved_strategy.get('indicators', [])
        entry_signals = improved_strategy.get('entry_signals', [])
        risk_config = improved_strategy.get('risk_config', {})
        filters = improved_strategy.get('filters', [])
        
        # Build code sections
        code_parts = []
        
        # Header
        code_parts.append(self._generate_header(name, category))
        
        # Using statements
        code_parts.append(self._generate_usings())
        
        # Robot attribute and class declaration
        code_parts.append(self._generate_class_start(name, class_name))
        
        # Parameters
        code_parts.append(self._generate_parameters(indicators, risk_config, filters))
        
        # Fields
        code_parts.append(self._generate_fields(indicators, filters))
        
        # OnStart method
        code_parts.append(self._generate_on_start(indicators, filters, ctrader_timeframe))
        
        # OnBar method
        code_parts.append(self._generate_on_bar(entry_signals, risk_config, filters, category, parsed_data))
        
        # Helper methods
        code_parts.append(self._generate_helper_methods(risk_config, filters))
        
        # Close class
        code_parts.append("}")
        
        # Combine all parts
        full_code = "\n".join(code_parts)
        
        return GeneratedBot(
            code=full_code,
            bot_name=name,
            class_name=class_name,
            indicators_count=len(indicators),
            filters_count=len(filters),
            has_risk_management=risk_config.get('stop_loss_type') != 'none',
            version="1.0"
        )
    
    def _make_class_name(self, name: str) -> str:
        """Convert name to valid C# class name"""
        # Remove special characters, keep alphanumeric
        clean = re.sub(r'[^a-zA-Z0-9]', '', name.replace(' ', ''))
        # Ensure starts with letter
        if clean and not clean[0].isalpha():
            clean = 'Bot' + clean
        return clean or 'OptimizedBot'
    
    def _generate_header(self, name: str, category: str) -> str:
        """Generate file header comment"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f'''// ============================================================
// {name}
// Generated by cBot Analyzer - Refinement Engine
// Category: {category}
// Generated: {timestamp}
// ============================================================
'''
    
    def _generate_usings(self) -> str:
        """Generate using statements"""
        return '''using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;
'''
    
    def _generate_class_start(self, name: str, class_name: str) -> str:
        """Generate robot attribute and class declaration"""
        return f'''namespace cAlgo.Robots
{{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class {class_name} : Robot
    {{'''
    
    def _generate_parameters(self, indicators: List[Dict], risk_config: Dict, filters: List[Dict]) -> str:
        """Generate parameter declarations"""
        params = []
        
        # Risk parameters
        sl_value = risk_config.get('stop_loss_value', 25)
        tp_value = risk_config.get('take_profit_value', 50)
        risk_pct = risk_config.get('size_value', 1.0) if risk_config.get('position_sizing') == 'percent_risk' else 1.0
        
        params.append(f'''
        // ==================== RISK PARAMETERS ====================
        [Parameter("Stop Loss (Pips)", DefaultValue = {sl_value}, MinValue = 5, MaxValue = 200)]
        public double StopLossPips {{ get; set; }}
        
        [Parameter("Take Profit (Pips)", DefaultValue = {tp_value}, MinValue = 10, MaxValue = 500)]
        public double TakeProfitPips {{ get; set; }}
        
        [Parameter("Risk Per Trade (%)", DefaultValue = {risk_pct}, MinValue = 0.1, MaxValue = 5)]
        public double RiskPercent {{ get; set; }}''')
        
        # Trailing stop
        if risk_config.get('trailing_stop'):
            trail_value = risk_config.get('trailing_value', 20)
            params.append(f'''
        
        [Parameter("Enable Trailing Stop", DefaultValue = true)]
        public bool UseTrailingStop {{ get; set; }}
        
        [Parameter("Trailing Stop (Pips)", DefaultValue = {trail_value}, MinValue = 5, MaxValue = 100)]
        public double TrailingStopPips {{ get; set; }}''')
        
        # Indicator parameters
        params.append('''
        
        // ==================== INDICATOR PARAMETERS ====================''')
        
        for idx, indicator in enumerate(indicators):
            ind_type = indicator.get('type', 'Unknown')
            ind_params = indicator.get('parameters', {})
            
            if ind_type in ['RSI']:
                period = self._get_param_value(ind_params, 'period', 14)
                params.append(f'''
        [Parameter("RSI Period", DefaultValue = {period}, MinValue = 5, MaxValue = 50, Group = "Indicators")]
        public int RsiPeriod {{ get; set; }}''')
            
            elif ind_type in ['SMA', 'EMA', 'MovingAverage']:
                period = self._get_param_value(ind_params, 'period', 20)
                suffix = 'Fast' if idx == 0 else 'Slow' if idx == 1 else str(idx + 1)
                params.append(f'''
        [Parameter("{ind_type} {suffix} Period", DefaultValue = {period}, MinValue = 1, MaxValue = 500, Group = "Indicators")]
        public int Ma{suffix}Period {{ get; set; }}''')
            
            elif ind_type == 'MACD':
                fast = self._get_param_value(ind_params, 'fast_period', 12)
                slow = self._get_param_value(ind_params, 'slow_period', 26)
                signal = self._get_param_value(ind_params, 'signal_period', 9)
                params.append(f'''
        [Parameter("MACD Fast", DefaultValue = {fast}, Group = "Indicators")]
        public int MacdFast {{ get; set; }}
        [Parameter("MACD Slow", DefaultValue = {slow}, Group = "Indicators")]
        public int MacdSlow {{ get; set; }}
        [Parameter("MACD Signal", DefaultValue = {signal}, Group = "Indicators")]
        public int MacdSignal {{ get; set; }}''')
            
            elif ind_type == 'BollingerBands':
                period = self._get_param_value(ind_params, 'period', 20)
                std = self._get_param_value(ind_params, 'std_dev', 2)
                params.append(f'''
        [Parameter("BB Period", DefaultValue = {period}, Group = "Indicators")]
        public int BbPeriod {{ get; set; }}
        [Parameter("BB StdDev", DefaultValue = {std}, Group = "Indicators")]
        public double BbStdDev {{ get; set; }}''')
            
            elif ind_type == 'ATR':
                period = self._get_param_value(ind_params, 'period', 14)
                params.append(f'''
        [Parameter("ATR Period", DefaultValue = {period}, Group = "Indicators")]
        public int AtrPeriod {{ get; set; }}''')
        
        # Filter parameters
        params.append('''
        
        // ==================== FILTER PARAMETERS ====================''')
        
        for f in filters:
            f_type = f.get('type', '')
            f_params = f.get('parameters', {})
            
            if f_type == 'time':
                start = f_params.get('start_hour', 8)
                end = f_params.get('end_hour', 17)
                params.append(f'''
        [Parameter("Trading Start Hour (UTC)", DefaultValue = {start}, MinValue = 0, MaxValue = 23, Group = "Filters")]
        public int TradingStartHour {{ get; set; }}
        
        [Parameter("Trading End Hour (UTC)", DefaultValue = {end}, MinValue = 0, MaxValue = 23, Group = "Filters")]
        public int TradingEndHour {{ get; set; }}''')
            
            elif f_type == 'spread':
                max_spread = f_params.get('max_spread_pips', 3)
                params.append(f'''
        [Parameter("Max Spread (Pips)", DefaultValue = {max_spread}, MinValue = 0.5, MaxValue = 20, Group = "Filters")]
        public double MaxSpreadPips {{ get; set; }}''')
            
            elif f_type == 'volatility':
                min_atr = f_params.get('min_atr_pips', 5)
                max_atr = f_params.get('max_atr_pips', 50)
                params.append(f'''
        [Parameter("Min ATR (Pips)", DefaultValue = {min_atr}, Group = "Filters")]
        public double MinAtrPips {{ get; set; }}
        
        [Parameter("Max ATR (Pips)", DefaultValue = {max_atr}, Group = "Filters")]
        public double MaxAtrPips {{ get; set; }}''')
            
            elif f_type == 'daily_limit':
                max_trades = f_params.get('max_trades_per_day', 5)
                params.append(f'''
        [Parameter("Max Trades Per Day", DefaultValue = {max_trades}, MinValue = 1, MaxValue = 50, Group = "Filters")]
        public int MaxTradesPerDay {{ get; set; }}''')
            
            elif f_type == 'loss_streak':
                max_losses = f_params.get('max_consecutive_losses', 2)
                params.append(f'''
        [Parameter("Max Consecutive Losses", DefaultValue = {max_losses}, MinValue = 1, MaxValue = 10, Group = "Filters")]
        public int MaxConsecutiveLosses {{ get; set; }}''')
            
            elif f_type == 'trend':
                max_adx = f_params.get('max_adx', 25)
                params.append(f'''
        [Parameter("Max ADX (Ranging)", DefaultValue = {max_adx}, MinValue = 10, MaxValue = 50, Group = "Filters")]
        public double MaxAdxForRanging {{ get; set; }}''')
        
        return '\n'.join(params)
    
    def _generate_fields(self, indicators: List[Dict], filters: List[Dict]) -> str:
        """Generate private field declarations"""
        fields = ['''
        
        // ==================== PRIVATE FIELDS ====================''']
        
        # Indicator fields
        ma_count = 0
        for indicator in indicators:
            ind_type = indicator.get('type', 'Unknown')
            
            if ind_type in ['RSI']:
                fields.append('        private RelativeStrengthIndex _rsi;')
            elif ind_type in ['SMA', 'EMA', 'MovingAverage']:
                suffix = 'Fast' if ma_count == 0 else 'Slow' if ma_count == 1 else str(ma_count + 1)
                ind_class = 'ExponentialMovingAverage' if ind_type == 'EMA' else 'SimpleMovingAverage'
                fields.append(f'        private {ind_class} _ma{suffix};')
                ma_count += 1
            elif ind_type == 'MACD':
                fields.append('        private MacdCrossOver _macd;')
            elif ind_type == 'BollingerBands':
                fields.append('        private BollingerBands _bb;')
            elif ind_type == 'ATR':
                fields.append('        private AverageTrueRange _atr;')
            elif ind_type == 'ADX':
                fields.append('        private DirectionalMovementSystem _adx;')
        
        # Always add ATR for volatility filter if not already present
        if not any(i.get('type') == 'ATR' for i in indicators):
            has_volatility_filter = any(f.get('type') == 'volatility' for f in filters)
            if has_volatility_filter:
                fields.append('        private AverageTrueRange _atrFilter;')
        
        # ADX for trend filter
        if not any(i.get('type') == 'ADX' for i in indicators):
            has_trend_filter = any(f.get('type') == 'trend' for f in filters)
            if has_trend_filter:
                fields.append('        private DirectionalMovementSystem _adxFilter;')
        
        # Tracking fields
        fields.append('''
        // Trading state tracking
        private int _todayTrades;
        private int _consecutiveLosses;
        private DateTime _lastTradeDate;
        private DateTime _cooldownUntil;''')
        
        return '\n'.join(fields)
    
    def _generate_on_start(self, indicators: List[Dict], filters: List[Dict], ctrader_timeframe: str = "TimeFrame.Hour") -> str:
        """Generate OnStart method"""
        lines = [f'''
        
        // ==================== LIFECYCLE METHODS ====================
        protected override void OnStart()
        {{
            // Timeframe: {ctrader_timeframe}
            // Initialize indicators''']
        
        ma_count = 0
        for indicator in indicators:
            ind_type = indicator.get('type', 'Unknown')
            
            if ind_type in ['RSI']:
                lines.append('            _rsi = Indicators.RelativeStrengthIndex(Bars.ClosePrices, RsiPeriod);')
            elif ind_type in ['SMA', 'EMA', 'MovingAverage']:
                suffix = 'Fast' if ma_count == 0 else 'Slow' if ma_count == 1 else str(ma_count + 1)
                ind_method = 'ExponentialMovingAverage' if ind_type == 'EMA' else 'SimpleMovingAverage'
                lines.append(f'            _ma{suffix} = Indicators.{ind_method}(Bars.ClosePrices, Ma{suffix}Period);')
                ma_count += 1
            elif ind_type == 'MACD':
                lines.append('            _macd = Indicators.MacdCrossOver(Bars.ClosePrices, MacdFast, MacdSlow, MacdSignal);')
            elif ind_type == 'BollingerBands':
                lines.append('            _bb = Indicators.BollingerBands(Bars.ClosePrices, BbPeriod, BbStdDev, MovingAverageType.Simple);')
            elif ind_type == 'ATR':
                lines.append('            _atr = Indicators.AverageTrueRange(AtrPeriod, MovingAverageType.Simple);')
            elif ind_type == 'ADX':
                lines.append('            _adx = Indicators.DirectionalMovementSystem(14);')
        
        # Filter indicators
        if not any(i.get('type') == 'ATR' for i in indicators):
            has_volatility_filter = any(f.get('type') == 'volatility' for f in filters)
            if has_volatility_filter:
                lines.append('            _atrFilter = Indicators.AverageTrueRange(14, MovingAverageType.Simple);')
        
        if not any(i.get('type') == 'ADX' for i in indicators):
            has_trend_filter = any(f.get('type') == 'trend' for f in filters)
            if has_trend_filter:
                lines.append('            _adxFilter = Indicators.DirectionalMovementSystem(14);')
        
        lines.append('''
            // Initialize tracking
            _todayTrades = 0;
            _consecutiveLosses = 0;
            _lastTradeDate = Server.Time.Date;
            _cooldownUntil = DateTime.MinValue;
            
            Print("Bot initialized - Risk: {0}%, SL: {1}, TP: {2}", RiskPercent, StopLossPips, TakeProfitPips);
        }
        
        protected override void OnStop()
        {
            Print("Bot stopped - Total trades today: {0}", _todayTrades);
        }''')
        
        return '\n'.join(lines)
    
    def _generate_on_bar(self, entry_signals: List[Dict], risk_config: Dict, filters: List[Dict], category: str, parsed_data: Optional[Dict]) -> str:
        """Generate OnBar method with entry logic"""
        lines = ['''
        
        // ==================== MAIN TRADING LOGIC ====================
        protected override void OnBar()
        {
            // Reset daily counter
            if (Server.Time.Date != _lastTradeDate)
            {
                _todayTrades = 0;
                _lastTradeDate = Server.Time.Date;
            }
            
            // Check all filters before trading
            if (!CanTrade())
                return;
            
            // Check for existing position
            var position = Positions.Find("OptimizedBot", SymbolName);
            
            // Manage existing position (trailing stop)
            if (position != null)
            {
                ManagePosition(position);
                return; // Don't open new trades while in position
            }
            
            // Generate trading signals''']
        
        # Determine signal generation based on indicators
        has_ma = parsed_data and any(i.get('type') in ['SMA', 'EMA', 'MovingAverage'] for i in parsed_data.get('indicators', []))
        has_rsi = parsed_data and any(i.get('type') == 'RSI' for i in parsed_data.get('indicators', []))
        has_macd = parsed_data and any(i.get('type') == 'MACD' for i in parsed_data.get('indicators', []))
        has_bb = parsed_data and any(i.get('type') == 'BollingerBands' for i in parsed_data.get('indicators', []))
        
        # Generate appropriate signal logic
        if has_ma:
            ma_count = sum(1 for i in parsed_data.get('indicators', []) if i.get('type') in ['SMA', 'EMA', 'MovingAverage'])
            if ma_count >= 2:
                lines.append('''
            bool longSignal = _maFast.Result.HasCrossedAbove(_maSlow.Result, 0);
            bool shortSignal = _maFast.Result.HasCrossedBelow(_maSlow.Result, 0);''')
            else:
                lines.append('''
            bool longSignal = Bars.ClosePrices.Last(1) > _maFast.Result.Last(1) && Bars.ClosePrices.Last(2) <= _maFast.Result.Last(2);
            bool shortSignal = Bars.ClosePrices.Last(1) < _maFast.Result.Last(1) && Bars.ClosePrices.Last(2) >= _maFast.Result.Last(2);''')
        
        elif has_rsi:
            lines.append('''
            double rsiValue = _rsi.Result.LastValue;
            bool longSignal = rsiValue < 30 && _rsi.Result.Last(1) >= 30; // RSI crosses below 30
            bool shortSignal = rsiValue > 70 && _rsi.Result.Last(1) <= 70; // RSI crosses above 70''')
        
        elif has_macd:
            lines.append('''
            bool longSignal = _macd.MACD.HasCrossedAbove(_macd.Signal, 0);
            bool shortSignal = _macd.MACD.HasCrossedBelow(_macd.Signal, 0);''')
        
        elif has_bb:
            lines.append('''
            double price = Bars.ClosePrices.LastValue;
            bool longSignal = price < _bb.Bottom.LastValue; // Price below lower band
            bool shortSignal = price > _bb.Top.LastValue; // Price above upper band''')
        
        else:
            # Default simple logic
            lines.append('''
            // Default signal logic - customize as needed
            bool longSignal = Bars.ClosePrices.Last(1) > Bars.ClosePrices.Last(2);
            bool shortSignal = Bars.ClosePrices.Last(1) < Bars.ClosePrices.Last(2);''')
        
        # Execute trades
        lines.append('''
            
            // Execute trades
            if (longSignal)
            {
                ExecuteLong();
            }
            else if (shortSignal)
            {
                ExecuteShort();
            }
        }''')
        
        return '\n'.join(lines)
    
    def _generate_helper_methods(self, risk_config: Dict, filters: List[Dict]) -> str:
        """Generate helper methods for trading logic"""
        methods = []
        
        # CanTrade filter method
        methods.append(self._generate_can_trade_method(filters))
        
        # Position management
        methods.append(self._generate_position_management(risk_config))
        
        # Execute trade methods
        methods.append(self._generate_execute_methods(risk_config))
        
        # Lot calculation
        methods.append(self._generate_lot_calculation())
        
        # OnPositionClosed for tracking
        methods.append(self._generate_position_closed_handler())
        
        return '\n'.join(methods)
    
    def _generate_can_trade_method(self, filters: List[Dict]) -> str:
        """Generate CanTrade filter method"""
        lines = ['''
        
        // ==================== FILTER METHODS ====================
        private bool CanTrade()
        {''']
        
        # Cooldown check
        lines.append('''            // Check cooldown from loss streak
            if (Server.Time < _cooldownUntil)
            {
                return false;
            }
''')
        
        # Generate filter checks
        for f in filters:
            f_type = f.get('type', '')
            
            if f_type == 'time':
                lines.append('''            // Session filter
            int hour = Server.Time.Hour;
            if (hour < TradingStartHour || hour >= TradingEndHour)
            {
                return false;
            }
''')
            
            elif f_type == 'spread':
                lines.append('''            // Spread filter
            double spreadPips = Symbol.Spread / Symbol.PipSize;
            if (spreadPips > MaxSpreadPips)
            {
                return false;
            }
''')
            
            elif f_type == 'volatility':
                lines.append('''            // Volatility filter (ATR)
            double atrPips = (_atrFilter != null ? _atrFilter.Result.LastValue : (_atr != null ? _atr.Result.LastValue : 0)) / Symbol.PipSize;
            if (atrPips < MinAtrPips || atrPips > MaxAtrPips)
            {
                return false;
            }
''')
            
            elif f_type == 'daily_limit':
                lines.append('''            // Daily trade limit
            if (_todayTrades >= MaxTradesPerDay)
            {
                return false;
            }
''')
            
            elif f_type == 'loss_streak':
                lines.append('''            // Loss streak protection
            if (_consecutiveLosses >= MaxConsecutiveLosses)
            {
                return false;
            }
''')
            
            elif f_type == 'trend':
                lines.append('''            // Trend filter for ranging (mean-reversion)
            double adxValue = _adxFilter != null ? _adxFilter.ADX.LastValue : (_adx != null ? _adx.ADX.LastValue : 0);
            if (adxValue > MaxAdxForRanging)
            {
                return false; // Market is trending, skip mean-reversion trades
            }
''')
        
        lines.append('''            return true;
        }''')
        
        return '\n'.join(lines)
    
    def _generate_position_management(self, risk_config: Dict) -> str:
        """Generate position management method"""
        if risk_config.get('trailing_stop'):
            return '''
        
        // ==================== POSITION MANAGEMENT ====================
        private void ManagePosition(Position position)
        {
            if (!UseTrailingStop)
                return;
            
            double trailPips = TrailingStopPips * Symbol.PipSize;
            double newSL;
            
            if (position.TradeType == TradeType.Buy)
            {
                double breakeven = position.EntryPrice + (TrailingStopPips * Symbol.PipSize);
                if (Symbol.Bid > breakeven)
                {
                    newSL = Symbol.Bid - trailPips;
                    if (position.StopLoss == null || newSL > position.StopLoss)
                    {
                        ModifyPosition(position, newSL, position.TakeProfit);
                    }
                }
            }
            else // Sell
            {
                double breakeven = position.EntryPrice - (TrailingStopPips * Symbol.PipSize);
                if (Symbol.Ask < breakeven)
                {
                    newSL = Symbol.Ask + trailPips;
                    if (position.StopLoss == null || newSL < position.StopLoss)
                    {
                        ModifyPosition(position, newSL, position.TakeProfit);
                    }
                }
            }
        }'''
        else:
            return '''
        
        // ==================== POSITION MANAGEMENT ====================
        private void ManagePosition(Position position)
        {
            // No trailing stop - position managed by SL/TP
        }'''
    
    def _generate_execute_methods(self, risk_config: Dict) -> str:
        """Generate trade execution methods"""
        return '''
        
        // ==================== TRADE EXECUTION ====================
        private void ExecuteLong()
        {
            double volume = CalculateVolume(StopLossPips);
            if (volume <= 0)
            {
                Print("Invalid volume calculated for long trade");
                return;
            }
            
            double sl = Symbol.Ask - (StopLossPips * Symbol.PipSize);
            double tp = Symbol.Ask + (TakeProfitPips * Symbol.PipSize);
            
            var result = ExecuteMarketOrder(TradeType.Buy, SymbolName, volume, "OptimizedBot", StopLossPips, TakeProfitPips);
            
            if (result.IsSuccessful)
            {
                _todayTrades++;
                Print("LONG opened: {0} lots, SL: {1}, TP: {2}", volume / 100000.0, sl, tp);
            }
            else
            {
                Print("LONG failed: {0}", result.Error);
            }
        }
        
        private void ExecuteShort()
        {
            double volume = CalculateVolume(StopLossPips);
            if (volume <= 0)
            {
                Print("Invalid volume calculated for short trade");
                return;
            }
            
            double sl = Symbol.Bid + (StopLossPips * Symbol.PipSize);
            double tp = Symbol.Bid - (TakeProfitPips * Symbol.PipSize);
            
            var result = ExecuteMarketOrder(TradeType.Sell, SymbolName, volume, "OptimizedBot", StopLossPips, TakeProfitPips);
            
            if (result.IsSuccessful)
            {
                _todayTrades++;
                Print("SHORT opened: {0} lots, SL: {1}, TP: {2}", volume / 100000.0, sl, tp);
            }
            else
            {
                Print("SHORT failed: {0}", result.Error);
            }
        }'''
    
    def _generate_lot_calculation(self) -> str:
        """Generate risk-based lot calculation"""
        return '''
        
        // ==================== RISK CALCULATION ====================
        private double CalculateVolume(double stopLossPips)
        {
            // Calculate position size based on risk percentage
            double riskAmount = Account.Balance * (RiskPercent / 100.0);
            double pipValue = Symbol.PipValue;
            
            // Volume = Risk Amount / (Stop Loss Pips * Pip Value)
            double volume = riskAmount / (stopLossPips * pipValue);
            
            // Round to valid volume
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            
            // Ensure within limits
            volume = Math.Max(Symbol.VolumeInUnitsMin, volume);
            volume = Math.Min(Symbol.VolumeInUnitsMax, volume);
            
            return volume;
        }'''
    
    def _generate_position_closed_handler(self) -> str:
        """Generate OnPositionClosed handler for tracking"""
        return '''
        
        // ==================== EVENT HANDLERS ====================
        protected override void OnPositionClosed(PositionClosedEventArgs args)
        {
            var position = args.Position;
            
            if (position.Label != "OptimizedBot")
                return;
            
            // Track consecutive losses
            if (position.NetProfit < 0)
            {
                _consecutiveLosses++;
                Print("Loss #{0} - Net: {1}", _consecutiveLosses, position.NetProfit);
                
                // Trigger cooldown if max losses reached
                if (_consecutiveLosses >= MaxConsecutiveLosses)
                {
                    _cooldownUntil = Server.Time.AddHours(4);
                    Print("Cooldown activated until: {0}", _cooldownUntil);
                }
            }
            else
            {
                _consecutiveLosses = 0; // Reset on win
                Print("Win! Net: {0} - Streak reset", position.NetProfit);
            }
        }
    '''
    
    def _get_param_value(self, params: Dict, key: str, default: Any) -> Any:
        """Get parameter value with fallback"""
        value = params.get(key, default)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return default
        return value if value is not None else default


def create_bot_generator() -> ImprovedBotGenerator:
    """Factory function to create bot generator"""
    return ImprovedBotGenerator()
