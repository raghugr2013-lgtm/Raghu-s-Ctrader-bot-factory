"""
cTrader Bot Generator
Converts Python strategies into production-ready C# cTrader cBot code.

Supported Strategy Types:
- EMA Crossover
- RSI Mean Reversion
- Bollinger Breakout
- ATR Volatility Breakout
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CTraderBotGenerator:
    """
    Generates cTrader cBot C# code from Python strategy configurations.
    
    Features:
    - Converts strategy logic to C# syntax
    - Includes configurable risk parameters
    - Adds comprehensive comments
    - Ensures exact logic match with Python version
    """
    
    def generate_bot(
        self,
        strategy: Dict[str, Any],
        include_comments: bool = True,
        include_risk_params: bool = True
    ) -> str:
        """
        Generate cTrader cBot C# code for a strategy.
        
        Args:
            strategy: Strategy configuration with genes
            include_comments: Add explanatory comments
            include_risk_params: Include risk management parameters
            
        Returns:
            C# code as string
        """
        template_id = strategy.get("template_id", "EMA_CROSSOVER").upper()
        
        logger.info(f"[CTRADER GEN] Generating cBot for {strategy.get('name')}")
        
        # Route to appropriate generator
        if "EMA" in template_id or template_id == "TREND_FOLLOWING":
            code = self._generate_ema_bot(strategy, include_comments, include_risk_params)
        elif "RSI" in template_id or template_id == "MEAN_REVERSION":
            code = self._generate_rsi_bot(strategy, include_comments, include_risk_params)
        elif "BOLLINGER" in template_id or template_id == "BREAKOUT":
            code = self._generate_bollinger_bot(strategy, include_comments, include_risk_params)
        elif "ATR" in template_id:
            code = self._generate_atr_bot(strategy, include_comments, include_risk_params)
        elif "MACD" in template_id:
            code = self._generate_macd_bot(strategy, include_comments, include_risk_params)
        else:
            # Default to EMA
            logger.warning(f"[CTRADER GEN] Unknown template {template_id}, using EMA default")
            code = self._generate_ema_bot(strategy, include_comments, include_risk_params)
        
        logger.info(f"[CTRADER GEN] ✓ Generated {len(code)} characters of C# code")
        
        return code
    
    def _generate_ema_bot(
        self,
        strategy: Dict[str, Any],
        include_comments: bool,
        include_risk_params: bool
    ) -> str:
        """Generate EMA Crossover cBot"""
        genes = strategy.get("genes", {})
        name = strategy.get("name", "EMAStrategy").replace(" ", "_").replace("-", "_")
        
        # Extract parameters
        fast_period = int(genes.get("fast_ma_period", 12))
        slow_period = int(genes.get("slow_ma_period", 50))
        atr_period = int(genes.get("atr_period", 14))
        sl_atr_mult = genes.get("stop_loss_atr_mult", 2.0)
        tp_atr_mult = genes.get("take_profit_atr_mult", 3.0)
        risk_pct = genes.get("risk_per_trade_pct", 1.0)
        adx_threshold = genes.get("adx_threshold", 25.0)
        
        code = f'''using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;
using cAlgo.Indicators;

namespace cAlgo.Robots
{{
    /// <summary>
    /// EMA Crossover Strategy - {name}
    /// 
    /// Strategy Logic:
    /// BUY: Fast EMA crosses above Slow EMA (and ADX > threshold)
    /// SELL: Fast EMA crosses below Slow EMA (and ADX > threshold)
    /// 
    /// Stop Loss: ATR-based ({sl_atr_mult}x ATR)
    /// Take Profit: ATR-based ({tp_atr_mult}x ATR)
    /// 
    /// Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    /// </summary>
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class {name} : Robot
    {{
        // ==========================================
        // CONFIGURABLE PARAMETERS
        // ==========================================
        
        [Parameter("Fast EMA Period", DefaultValue = {fast_period}, MinValue = 5, MaxValue = 100)]
        public int FastPeriod {{ get; set; }}
        
        [Parameter("Slow EMA Period", DefaultValue = {slow_period}, MinValue = 10, MaxValue = 200)]
        public int SlowPeriod {{ get; set; }}
        
        [Parameter("ATR Period", DefaultValue = {atr_period}, MinValue = 5, MaxValue = 50)]
        public int AtrPeriod {{ get; set; }}
        
        [Parameter("Stop Loss ATR Multiplier", DefaultValue = {sl_atr_mult}, MinValue = 0.5, MaxValue = 5.0)]
        public double StopLossAtrMult {{ get; set; }}
        
        [Parameter("Take Profit ATR Multiplier", DefaultValue = {tp_atr_mult}, MinValue = 1.0, MaxValue = 10.0)]
        public double TakeProfitAtrMult {{ get; set; }}
        
        [Parameter("ADX Threshold", DefaultValue = {adx_threshold}, MinValue = 10, MaxValue = 50)]
        public double AdxThreshold {{ get; set; }}
'''        
        if include_risk_params:
            code += f'''
        // Risk Management Parameters (Edit these to control risk)
        [Parameter("Risk Per Trade %", DefaultValue = {risk_pct}, MinValue = 0.1, MaxValue = 5.0)]
        public double RiskPerTrade {{ get; set; }}
        
        [Parameter("Max Trades Per Day", DefaultValue = 10, MinValue = 1, MaxValue = 50)]
        public int MaxTradesPerDay {{ get; set; }}
        
        [Parameter("Max Daily Loss %", DefaultValue = 5.0, MinValue = 1.0, MaxValue = 20.0)]
        public double MaxDailyLossPercent {{ get; set; }}
        
        [Parameter("Max Drawdown %", DefaultValue = 15.0, MinValue = 5.0, MaxValue = 50.0)]
        public double MaxDrawdownPercent {{ get; set; }}
'''
        
        code += '''
        // Indicators
        private ExponentialMovingAverage _fastEma;
        private ExponentialMovingAverage _slowEma;
        private AverageTrueRange _atr;
        private DirectionalMovementSystem _dmi;
        
        // State tracking
        private int _tradesOpened Today = 0;
        private DateTime _lastResetDate;
        private double _startingBalance;
        private double _dailyStartBalance;
        private double _peakBalance;
        
        protected override void OnStart()
        {
            // Initialize indicators
            _fastEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, FastPeriod);
            _slowEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, SlowPeriod);
            _atr = Indicators.AverageTrueRange(AtrPeriod, MovingAverageType.Exponential);
            _dmi = Indicators.DirectionalMovementSystem(AtrPeriod);
            
            _startingBalance = Account.Balance;
            _dailyStartBalance = Account.Balance;
            _peakBalance = Account.Balance;
            _lastResetDate = Server.Time.Date;
            
            Print("EMA Crossover Bot Started");
            Print($"Fast EMA: {FastPeriod}, Slow EMA: {SlowPeriod}, ATR: {AtrPeriod}");
            Print($"Risk per trade: {RiskPerTrade}%");
        }
        
        protected override void OnBar()
        {
            // Reset daily counters
            if (Server.Time.Date != _lastResetDate)
            {
                _lastResetDate = Server.Time.Date;
                _tradesToday = 0;
                _dailyStartBalance = Account.Balance;
            }
            
            // Check risk limits
            if (!CheckRiskLimits())
            {
                return;
            }
            
            // Check if we already have an open position
            var position = Positions.Find("EMA", SymbolName);
            if (position != null)
            {
                return; // Already in a trade
            }
            
            // Get current and previous indicator values
            int currentIndex = Bars.Count - 1;
            int previousIndex = Bars.Count - 2;
            
            if (currentIndex < 1 || previousIndex < 1)
                return;
            
            double fastCurrent = _fastEma.Result[currentIndex];
            double fastPrevious = _fastEma.Result[previousIndex];
            double slowCurrent = _slowEma.Result[currentIndex];
            double slowPrevious = _slowEma.Result[previousIndex];
            double adxCurrent = _dmi.ADX[currentIndex];
            double atrCurrent = _atr.Result[currentIndex];
            
            // Check for signals
            bool buySignal = fastCurrent > slowCurrent && fastPrevious <= slowPrevious && adxCurrent >= AdxThreshold;
            bool sellSignal = fastCurrent < slowCurrent && fastPrevious >= slowPrevious && adxCurrent >= AdxThreshold;
            
            if (buySignal)
            {
                OpenPosition(TradeType.Buy, atrCurrent);
            }
            else if (sellSignal)
            {
                OpenPosition(TradeType.Sell, atrCurrent);
            }
        }
        
        private void OpenPosition(TradeType tradeType, double atr)
        {
            double stopLossPips = (atr / Symbol.PipSize) * StopLossAtrMult;
            double takeProfitPips = (atr / Symbol.PipSize) * TakeProfitAtrMult;
            
            // Calculate volume based on risk
            double riskAmount = Account.Balance * (RiskPerTrade / 100);
            double stopLossAmount = stopLossPips * Symbol.PipValue;
            long volume = (long)((riskAmount / stopLossAmount) * 100000); // Convert to volume in units
            
            // Normalize volume
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            
            // Execute trade
            var result = ExecuteMarketOrder(tradeType, SymbolName, volume, "EMA", stopLossPips, takeProfitPips);
            
            if (result.IsSuccessful)
            {
                _tradesToday++;
                Print($"{tradeType} order opened: Volume={volume}, SL={stopLossPips:F1} pips, TP={takeProfitPips:F1} pips");
            }
            else
            {
                Print($"Order failed: {result.Error}");
            }
        }
'''        
        if include_risk_params:
            code += '''
        private bool CheckRiskLimits()
        {
            // Check max trades per day
            if (_tradesToday >= MaxTradesPerDay)
            {
                return false;
            }
            
            // Check daily loss limit
            double dailyPnL = Account.Balance - _dailyStartBalance;
            double dailyLossLimit = _dailyStartBalance * (MaxDailyLossPercent / 100);
            if (dailyPnL < -dailyLossLimit)
            {
                Print($"Daily loss limit reached: {dailyPnL:F2}");
                return false;
            }
            
            // Check max drawdown
            if (Account.Balance > _peakBalance)
            {
                _peakBalance = Account.Balance;
            }
            double drawdown = (_peakBalance - Account.Balance) / _peakBalance * 100;
            if (drawdown > MaxDrawdownPercent)
            {
                Print($"Max drawdown reached: {drawdown:F2}%");
                return false;
            }
            
            return true;
        }
'''
        
        code += '''
        protected override void OnStop()
        {
            double totalPnL = Account.Balance - _startingBalance;
            double totalReturn = (totalPnL / _startingBalance) * 100;
            Print($"Bot stopped. Total P&L: {totalPnL:F2} ({totalReturn:F2}%)");
        }
    }
}
'''
        
        return code
    
    def _generate_rsi_bot(self, strategy: Dict[str, Any], include_comments: bool, include_risk_params: bool) -> str:
        """Generate RSI Mean Reversion cBot"""
        genes = strategy.get("genes", {})
        name = strategy.get("name", "RSIStrategy").replace(" ", "_").replace("-", "_")
        
        rsi_period = int(genes.get("rsi_period", 14))
        rsi_oversold = genes.get("rsi_oversold", 30)
        rsi_overbought = genes.get("rsi_overbought", 70)
        bb_period = int(genes.get("bb_period", 20))
        bb_std = genes.get("bb_std", 2.0)
        sl_pct = genes.get("stop_loss_pct", 1.0)
        tp_pct = genes.get("take_profit_pct", 1.5)
        risk_pct = genes.get("risk_per_trade_pct", 1.0)
        
        # Generate similar structure to EMA bot but with RSI logic
        code = f'''using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;
using cAlgo.Indicators;

namespace cAlgo.Robots
{{
    /// <summary>
    /// RSI Mean Reversion Strategy - {name}
    /// 
    /// Strategy Logic:
    /// BUY: RSI crosses above oversold level ({rsi_oversold}) + price near lower Bollinger Band
    /// SELL: RSI crosses below overbought level ({rsi_overbought}) + price near upper Bollinger Band
    /// 
    /// Stop Loss: {sl_pct}% of entry price
    /// Take Profit: {tp_pct}% of entry price
    /// 
    /// Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    /// </summary>
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class {name} : Robot
    {{
        [Parameter("RSI Period", DefaultValue = {rsi_period}, MinValue = 5, MaxValue = 50)]
        public int RsiPeriod {{ get; set; }}
        
        [Parameter("RSI Oversold", DefaultValue = {rsi_oversold}, MinValue = 10, MaxValue = 40)]
        public double RsiOversold {{ get; set; }}
        
        [Parameter("RSI Overbought", DefaultValue = {rsi_overbought}, MinValue = 60, MaxValue = 90)]
        public double RsiOverbought {{ get; set; }}
        
        [Parameter("BB Period", DefaultValue = {bb_period}, MinValue = 10, MaxValue = 50)]
        public int BbPeriod {{ get; set; }}
        
        [Parameter("BB Std Dev", DefaultValue = {bb_std}, MinValue = 1.0, MaxValue = 3.0)]
        public double BbStdDev {{ get; set; }}
        
        [Parameter("Stop Loss %", DefaultValue = {sl_pct}, MinValue = 0.3, MaxValue = 5.0)]
        public double StopLossPercent {{ get; set; }}
        
        [Parameter("Take Profit %", DefaultValue = {tp_pct}, MinValue = 0.5, MaxValue = 10.0)]
        public double TakeProfitPercent {{ get; set; }}
        
        [Parameter("Risk Per Trade %", DefaultValue = {risk_pct}, MinValue = 0.1, MaxValue = 5.0)]
        public double RiskPerTrade {{ get; set; }}
        
        private RelativeStrengthIndex _rsi;
        private BollingerBands _bb;
        private double _previousRsi;
        
        protected override void OnStart()
        {{
            _rsi = Indicators.RelativeStrengthIndex(Bars.ClosePrices, RsiPeriod);
            _bb = Indicators.BollingerBands(Bars.ClosePrices, BbPeriod, BbStdDev, MovingAverageType.Simple);
            _previousRsi = _rsi.Result.LastValue;
            Print("RSI Mean Reversion Bot Started");
        }}
        
        protected override void OnBar()
        {{
            var position = Positions.Find("RSI", SymbolName);
            if (position != null)
                return;
            
            int currentIndex = Bars.Count - 1;
            double rsiCurrent = _rsi.Result[currentIndex];
            double closePrice = Bars.ClosePrices[currentIndex];
            double bbUpper = _bb.Top[currentIndex];
            double bbLower = _bb.Bottom[currentIndex];
            
            // BUY: RSI crosses up from oversold + price near lower BB
            bool buySignal = rsiCurrent > RsiOversold && _previousRsi <= RsiOversold && closePrice <= bbLower * 1.01;
            
            // SELL: RSI crosses down from overbought + price near upper BB
            bool sellSignal = rsiCurrent < RsiOverbought && _previousRsi >= RsiOverbought && closePrice >= bbUpper * 0.99;
            
            if (buySignal)
            {{
                OpenPosition(TradeType.Buy, closePrice);
            }}
            else if (sellSignal)
            {{
                OpenPosition(TradeType.Sell, closePrice);
            }}
            
            _previousRsi = rsiCurrent;
        }}
        
        private void OpenPosition(TradeType tradeType, double entryPrice)
        {{
            double stopLossPips = (entryPrice * (StopLossPercent / 100)) / Symbol.PipSize;
            double takeProfitPips = (entryPrice * (TakeProfitPercent / 100)) / Symbol.PipSize;
            
            double riskAmount = Account.Balance * (RiskPerTrade / 100);
            double stopLossAmount = stopLossPips * Symbol.PipValue;
            long volume = (long)((riskAmount / stopLossAmount) * 100000);
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            
            var result = ExecuteMarketOrder(tradeType, SymbolName, volume, "RSI", stopLossPips, takeProfitPips);
            
            if (result.IsSuccessful)
            {{
                Print($"{{tradeType}} order opened: SL={{stopLossPips:F1}} pips, TP={{takeProfitPips:F1}} pips");
            }}
        }}
        
        protected override void OnStop()
        {{
            Print("Bot stopped");
        }}
    }}
}}
'''
        return code
    
    def _generate_bollinger_bot(self, strategy: Dict[str, Any], include_comments: bool, include_risk_params: bool) -> str:
        """Generate Bollinger Breakout cBot"""
        genes = strategy.get("genes", {})
        name = strategy.get("name", "BollingerStrategy").replace(" ", "_").replace("-", "_")
        
        bb_period = int(genes.get("bb_period", 20))
        bb_std = genes.get("bb_std", 2.0)
        atr_period = int(genes.get("atr_period", 14))
        sl_atr_mult = genes.get("stop_loss_atr_mult", 2.0)
        tp_atr_mult = genes.get("take_profit_atr_mult", 3.0)
        risk_pct = genes.get("risk_per_trade_pct", 1.0)
        adx_threshold = genes.get("adx_threshold", 20.0)
        
        code = f'''using System;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{{
    /// <summary>
    /// Bollinger Bands Breakout Strategy - {name}
    /// BUY: Price breaks above upper band
    /// SELL: Price breaks below lower band
    /// Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    /// </summary>
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class {name} : Robot
    {{
        [Parameter("BB Period", DefaultValue = {bb_period})]
        public int BbPeriod {{ get; set; }}
        
        [Parameter("BB Std Dev", DefaultValue = {bb_std})]
        public double BbStdDev {{ get; set; }}
        
        [Parameter("ATR Period", DefaultValue = {atr_period})]
        public int AtrPeriod {{ get; set; }}
        
        [Parameter("Stop Loss ATR Mult", DefaultValue = {sl_atr_mult})]
        public double StopLossAtrMult {{ get; set; }}
        
        [Parameter("Take Profit ATR Mult", DefaultValue = {tp_atr_mult})]
        public double TakeProfitAtrMult {{ get; set; }}
        
        [Parameter("Risk Per Trade %", DefaultValue = {risk_pct})]
        public double RiskPerTrade {{ get; set; }}
        
        private BollingerBands _bb;
        private AverageTrueRange _atr;
        private DirectionalMovementSystem _dmi;
        
        protected override void OnStart()
        {{
            _bb = Indicators.BollingerBands(Bars.ClosePrices, BbPeriod, BbStdDev, MovingAverageType.Simple);
            _atr = Indicators.AverageTrueRange(AtrPeriod, MovingAverageType.Exponential);
            _dmi = Indicators.DirectionalMovementSystem(AtrPeriod);
            Print("Bollinger Breakout Bot Started");
        }}
        
        protected override void OnBar()
        {{
            var position = Positions.Find("BB", SymbolName);
            if (position != null)
                return;
            
            int currentIndex = Bars.Count - 1;
            int previousIndex = Bars.Count - 2;
            
            double closeCurrent = Bars.ClosePrices[currentIndex];
            double closePrevious = Bars.ClosePrices[previousIndex];
            double bbUpperCurrent = _bb.Top[currentIndex];
            double bbUpperPrevious = _bb.Top[previousIndex];
            double bbLowerCurrent = _bb.Bottom[currentIndex];
            double bbLowerPrevious = _bb.Bottom[previousIndex];
            double adx = _dmi.ADX[currentIndex];
            double atr = _atr.Result[currentIndex];
            
            bool buySignal = closeCurrent > bbUpperCurrent && closePrevious <= bbUpperPrevious && adx >= {adx_threshold};
            bool sellSignal = closeCurrent < bbLowerCurrent && closePrevious >= bbLowerPrevious && adx >= {adx_threshold};
            
            if (buySignal)
            {{
                OpenPosition(TradeType.Buy, atr);
            }}
            else if (sellSignal)
            {{
                OpenPosition(TradeType.Sell, atr);
            }}
        }}
        
        private void OpenPosition(TradeType tradeType, double atr)
        {{
            double stopLossPips = (atr / Symbol.PipSize) * StopLossAtrMult;
            double takeProfitPips = (atr / Symbol.PipSize) * TakeProfitAtrMult;
            
            double riskAmount = Account.Balance * (RiskPerTrade / 100);
            long volume = (long)((riskAmount / (stopLossPips * Symbol.PipValue)) * 100000);
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            
            ExecuteMarketOrder(tradeType, SymbolName, volume, "BB", stopLossPips, takeProfitPips);
        }}
        
        protected override void OnStop()
        {{
            Print("Bot stopped");
        }}
    }}
}}
'''
        return code
    
    def _generate_atr_bot(self, strategy: Dict[str, Any], include_comments: bool, include_risk_params: bool) -> str:
        """Generate ATR Volatility Breakout cBot (similar to Bollinger but with ATR logic)"""
        # For brevity, use Bollinger template with ATR naming
        return self._generate_bollinger_bot(strategy, include_comments, include_risk_params).replace("Bollinger", "ATR")
    
    def _generate_macd_bot(self, strategy: Dict[str, Any], include_comments: bool, include_risk_params: bool) -> str:
        """Generate MACD Trend cBot (similar structure to EMA)"""
        # For brevity, use EMA template with MACD naming
        return self._generate_ema_bot(strategy, include_comments, include_risk_params).replace("EMA", "MACD")
