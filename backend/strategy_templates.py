"""
Pre-Built Strategy Templates for cTrader Bot Factory
Realistic strategies with proper risk management and filters
"""

from typing import List, Optional, Dict
from abc import abstractmethod
from datetime import datetime
import logging

from market_data_models import Candle, DataTimeframe
from strategy_interface import (
    BaseStrategy,
    TradingSignal,
    SignalType,
    Position,
    AccountInfo
)

logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """
    MEAN REVERSION STRATEGY (Bollinger Bands + RSI)
    
    Logic:
    - Buy when price touches lower BB and RSI < 30 (oversold)
    - Sell when price touches upper BB and RSI > 70 (overbought)
    - Exit at middle BB or opposite signal
    
    Best for: Ranging/sideways markets
    Risk: 1-2% per trade with BB middle as initial target
    """
    
    def __init__(self, symbol: str, timeframe: str,
                 bb_period: int = 20, bb_std: float = 2.0,
                 rsi_period: int = 14, rsi_oversold: int = 30, rsi_overbought: int = 70):
        super().__init__(symbol, timeframe)
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.last_signal = SignalType.NONE
        
        # Set pip size based on symbol
        if "XAU" in symbol.upper() or "GOLD" in symbol.upper():
            self.pip_size = 0.01
        else:
            self.pip_size = 0.0001
    
    def on_start(self):
        logger.info(f"Starting Mean Reversion Strategy: BB({self.bb_period}, {self.bb_std}) RSI({self.rsi_period})")
    
    def calculate_bollinger_bands(self) -> Optional[tuple]:
        """Calculate Bollinger Bands (middle, upper, lower)"""
        candles = self.get_candles(self.bb_period)
        if len(candles) < self.bb_period:
            return None
        
        closes = [c.close for c in candles]
        middle = sum(closes) / len(closes)
        
        # Standard deviation
        variance = sum((p - middle) ** 2 for p in closes) / len(closes)
        std_dev = variance ** 0.5
        
        upper = middle + (self.bb_std * std_dev)
        lower = middle - (self.bb_std * std_dev)
        
        return middle, upper, lower
    
    def on_candle(self, candle: Candle) -> Optional[TradingSignal]:
        # Need enough history
        if len(self.candle_history) < max(self.bb_period, self.rsi_period + 1):
            return None
        
        # Calculate indicators
        bb = self.calculate_bollinger_bands()
        rsi = self.calculate_rsi(self.rsi_period)
        
        if bb is None or rsi is None:
            return None
        
        middle, upper, lower = bb
        current_price = candle.close
        
        # Calculate realistic entry prices (accounting for spread)
        spread = 1.5 * self.pip_size  # 1.5 pip spread
        
        # Mean Reversion Logic
        if current_price <= lower and rsi < self.rsi_oversold:
            # Oversold - BUY signal
            if not self.has_open_positions() and self.last_signal != SignalType.BUY:
                self.last_signal = SignalType.BUY
                
                # Entry at ask price
                entry_price = current_price + spread
                
                # SL must be BELOW entry (50 pips below entry)
                stop_loss = entry_price - (50 * self.pip_size)
                
                # TP at middle BB (must be above entry)
                take_profit = max(middle, entry_price + (30 * self.pip_size))
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    volume=0.1,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=f"Mean Reversion BUY: Price at lower BB, RSI={rsi:.1f}"
                )
        
        elif current_price >= upper and rsi > self.rsi_overbought:
            # Overbought - SELL signal
            if not self.has_open_positions() and self.last_signal != SignalType.SELL:
                self.last_signal = SignalType.SELL
                
                # Entry at bid price (current_price)
                entry_price = current_price
                
                # SL must be ABOVE entry (50 pips above entry)
                stop_loss = entry_price + (50 * self.pip_size)
                
                # TP at middle BB (must be below entry)
                take_profit = min(middle, entry_price - (30 * self.pip_size))
                
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    volume=0.1,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=f"Mean Reversion SELL: Price at upper BB, RSI={rsi:.1f}"
                )
        
        return None


class TrendFollowingStrategy(BaseStrategy):
    """
    TREND FOLLOWING STRATEGY (EMA Pullback)
    
    Logic:
    - Identify trend: EMA 50 > EMA 200 = Uptrend, vice versa
    - Wait for pullback to EMA 50
    - Enter on price rejection (bullish/bearish engulfing)
    
    Best for: Trending markets
    Risk: 1-2% per trade, SL below/above EMA 50
    """
    
    def __init__(self, symbol: str, timeframe: str,
                 fast_ema: int = 50, slow_ema: int = 200,
                 pullback_threshold: float = 0.002):
        super().__init__(symbol, timeframe)
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.pullback_threshold = pullback_threshold
        self.last_signal = SignalType.NONE
        self.trend_direction = None
        
        # Set pip size based on symbol
        if "XAU" in symbol.upper() or "GOLD" in symbol.upper():
            self.pip_size = 0.01
        else:
            self.pip_size = 0.0001
    
    def on_start(self):
        logger.info(f"Starting Trend Following Strategy: EMA({self.fast_ema}/{self.slow_ema})")
    
    def is_bullish_engulfing(self, candle: Candle, prev_candle: Candle) -> bool:
        """Check for bullish engulfing pattern"""
        return (prev_candle.close < prev_candle.open and  # Previous bearish
                candle.close > candle.open and  # Current bullish
                candle.open <= prev_candle.close and  # Opens at/below prev close
                candle.close > prev_candle.open)  # Closes above prev open
    
    def is_bearish_engulfing(self, candle: Candle, prev_candle: Candle) -> bool:
        """Check for bearish engulfing pattern"""
        return (prev_candle.close > prev_candle.open and  # Previous bullish
                candle.close < candle.open and  # Current bearish
                candle.open >= prev_candle.close and  # Opens at/above prev close
                candle.close < prev_candle.open)  # Closes below prev open
    
    def on_candle(self, candle: Candle) -> Optional[TradingSignal]:
        # Need enough history
        if len(self.candle_history) < self.slow_ema + 1:
            return None
        
        # Calculate EMAs
        fast_ma = self.calculate_ema(self.fast_ema)
        slow_ma = self.calculate_ema(self.slow_ema)
        
        if fast_ma is None or slow_ma is None:
            return None
        
        prev_candle = self.candle_history[-2]
        current_price = candle.close
        
        # Determine trend
        if fast_ma > slow_ma:
            self.trend_direction = "UP"
        elif fast_ma < slow_ma:
            self.trend_direction = "DOWN"
        else:
            return None
        
        # Check for pullback to EMA 50
        price_to_ema = abs(current_price - fast_ma) / fast_ma
        near_fast_ema = price_to_ema < self.pullback_threshold
        
        if self.trend_direction == "UP" and near_fast_ema:
            # Uptrend + Pullback - Look for bullish entry
            if self.is_bullish_engulfing(candle, prev_candle):
                if not self.has_open_positions() and self.last_signal != SignalType.BUY:
                    self.last_signal = SignalType.BUY
                    
                    # Entry at ask price
                    spread = 1.5 * self.pip_size
                    entry_price = current_price + spread
                    
                    # SL below entry (50 pips)
                    stop_loss = entry_price - (50 * self.pip_size)
                    
                    # TP at 2:1 RR (100 pips above entry)
                    take_profit = entry_price + (100 * self.pip_size)
                    
                    return TradingSignal(
                        signal_type=SignalType.BUY,
                        volume=0.1,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        comment=f"Trend Follow BUY: Pullback to EMA{self.fast_ema} in uptrend"
                    )
        
        elif self.trend_direction == "DOWN" and near_fast_ema:
            # Downtrend + Pullback - Look for bearish entry
            if self.is_bearish_engulfing(candle, prev_candle):
                if not self.has_open_positions() and self.last_signal != SignalType.SELL:
                    self.last_signal = SignalType.SELL
                    
                    # Entry at bid price
                    entry_price = current_price
                    
                    # SL above entry (50 pips)
                    stop_loss = entry_price + (50 * self.pip_size)
                    
                    # TP at 2:1 RR (100 pips below entry)
                    take_profit = entry_price - (100 * self.pip_size)
                    
                    return TradingSignal(
                        signal_type=SignalType.SELL,
                        volume=0.1,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        comment=f"Trend Follow SELL: Pullback to EMA{self.fast_ema} in downtrend"
                    )
        
        return None


class BreakoutStrategy(BaseStrategy):
    """
    BREAKOUT STRATEGY (Previous High/Low)
    
    Logic:
    - Track N-period high/low
    - Enter on breakout with volume confirmation
    - Use ATR for dynamic SL/TP
    
    Best for: Volatile/expanding markets
    Risk: 1-2% per trade, ATR-based stops
    """
    
    def __init__(self, symbol: str, timeframe: str,
                 lookback_period: int = 20, atr_period: int = 14,
                 volume_multiplier: float = 1.5):
        super().__init__(symbol, timeframe)
        self.lookback_period = lookback_period
        self.atr_period = atr_period
        self.volume_multiplier = volume_multiplier
        self.last_signal = SignalType.NONE
        self.breakout_level = None
        
        # Set pip size based on symbol
        if "XAU" in symbol.upper() or "GOLD" in symbol.upper():
            self.pip_size = 0.01
        else:
            self.pip_size = 0.0001
    
    def on_start(self):
        logger.info(f"Starting Breakout Strategy: Period({self.lookback_period}) ATR({self.atr_period})")
    
    def calculate_atr(self) -> Optional[float]:
        """Calculate Average True Range"""
        candles = self.get_candles(self.atr_period + 1)
        if len(candles) < self.atr_period + 1:
            return None
        
        tr_values = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i-1].close
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_values.append(tr)
        
        return sum(tr_values) / len(tr_values)
    
    def get_period_high_low(self) -> Optional[tuple]:
        """Get N-period high and low"""
        candles = self.get_candles(self.lookback_period)
        if len(candles) < self.lookback_period:
            return None
        
        period_high = max(c.high for c in candles[:-1])  # Exclude current
        period_low = min(c.low for c in candles[:-1])
        
        return period_high, period_low
    
    def get_average_volume(self) -> Optional[float]:
        """Get average volume"""
        candles = self.get_candles(self.lookback_period)
        if len(candles) < self.lookback_period:
            return None
        
        return sum(c.volume for c in candles[:-1]) / (len(candles) - 1)
    
    def on_candle(self, candle: Candle) -> Optional[TradingSignal]:
        # Need enough history
        if len(self.candle_history) < max(self.lookback_period, self.atr_period + 1):
            return None
        
        # Get indicators
        hl = self.get_period_high_low()
        atr = self.calculate_atr()
        avg_volume = self.get_average_volume()
        
        if hl is None or atr is None or avg_volume is None:
            return None
        
        period_high, period_low = hl
        current_price = candle.close
        current_volume = candle.volume
        
        # Volume confirmation
        volume_confirmed = current_volume > (avg_volume * self.volume_multiplier)
        
        # Spread
        spread = 1.5 * self.pip_size
        
        # Breakout above high
        if current_price > period_high and volume_confirmed:
            if not self.has_open_positions() and self.last_signal != SignalType.BUY:
                self.last_signal = SignalType.BUY
                self.breakout_level = period_high
                
                # Entry at ask price
                entry_price = current_price + spread
                
                # SL below entry (using ATR but minimum 30 pips)
                sl_distance = max(atr * 1.5, 30 * self.pip_size)
                stop_loss = entry_price - sl_distance
                
                # TP at 2:1 RR
                take_profit = entry_price + (sl_distance * 2)
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    volume=0.1,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=f"Breakout BUY: Above {period_high:.2f}, ATR={atr:.2f}"
                )
        
        # Breakout below low
        elif current_price < period_low and volume_confirmed:
            if not self.has_open_positions() and self.last_signal != SignalType.SELL:
                self.last_signal = SignalType.SELL
                self.breakout_level = period_low
                
                # Entry at bid price
                entry_price = current_price
                
                # SL above entry (using ATR but minimum 30 pips)
                sl_distance = max(atr * 1.5, 30 * self.pip_size)
                stop_loss = entry_price + sl_distance
                
                # TP at 2:1 RR
                take_profit = entry_price - (sl_distance * 2)
                
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    volume=0.1,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=f"Breakout SELL: Below {period_low:.2f}, ATR={atr:.2f}"
                )
        
        return None


class HybridStrategy(BaseStrategy):
    """
    HYBRID STRATEGY (Auto-Switch: Mean Reversion / Trend Following)
    
    Logic:
    - Detect market regime using ADX
    - ADX < 25: Ranging → Use Mean Reversion
    - ADX >= 25: Trending → Use Trend Following
    
    Best for: All market conditions
    Risk: Adaptive based on regime
    """
    
    def __init__(self, symbol: str, timeframe: str,
                 adx_period: int = 14, adx_threshold: int = 25):
        super().__init__(symbol, timeframe)
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.current_regime = None
        self.last_signal = SignalType.NONE
        
        # Initialize sub-strategies
        self.mean_reversion = MeanReversionStrategy(symbol, timeframe)
        self.trend_following = TrendFollowingStrategy(symbol, timeframe)
        
        # Set pip size based on symbol
        if "XAU" in symbol.upper() or "GOLD" in symbol.upper():
            self.pip_size = 0.01
        else:
            self.pip_size = 0.0001
    
    def on_start(self):
        logger.info(f"Starting Hybrid Strategy: ADX({self.adx_period}) Threshold({self.adx_threshold})")
        self.mean_reversion.on_start()
        self.trend_following.on_start()
    
    def calculate_adx(self) -> Optional[float]:
        """Calculate Average Directional Index (ADX)"""
        candles = self.get_candles(self.adx_period * 2)
        if len(candles) < self.adx_period * 2:
            return None
        
        # Calculate +DM, -DM, and TR
        plus_dm = []
        minus_dm = []
        tr_values = []
        
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_high = candles[i-1].high
            prev_low = candles[i-1].low
            prev_close = candles[i-1].close
            
            # True Range
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
            
            # Directional Movement
            up_move = high - prev_high
            down_move = prev_low - low
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
            
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)
        
        # Smoothed averages
        if len(tr_values) < self.adx_period:
            return None
        
        atr = sum(tr_values[-self.adx_period:]) / self.adx_period
        plus_di = (sum(plus_dm[-self.adx_period:]) / self.adx_period) / atr * 100 if atr > 0 else 0
        minus_di = (sum(minus_dm[-self.adx_period:]) / self.adx_period) / atr * 100 if atr > 0 else 0
        
        # DX and ADX
        dx_sum = abs(plus_di - minus_di)
        dx_denom = plus_di + minus_di
        dx = (dx_sum / dx_denom * 100) if dx_denom > 0 else 0
        
        return dx  # Simplified ADX
    
    def on_candle(self, candle: Candle) -> Optional[TradingSignal]:
        # Need enough history
        if len(self.candle_history) < self.adx_period * 2 + 50:
            return None
        
        # Update sub-strategy histories
        self.mean_reversion.candle_history = self.candle_history.copy()
        self.mean_reversion.positions = self.positions.copy()
        self.trend_following.candle_history = self.candle_history.copy()
        self.trend_following.positions = self.positions.copy()
        
        # Calculate ADX to determine regime
        adx = self.calculate_adx()
        
        if adx is None:
            return None
        
        # Determine regime
        if adx < self.adx_threshold:
            self.current_regime = "RANGING"
            signal = self.mean_reversion.on_candle(candle)
            if signal:
                signal.comment = f"[HYBRID-RANGE] {signal.comment}, ADX={adx:.1f}"
        else:
            self.current_regime = "TRENDING"
            signal = self.trend_following.on_candle(candle)
            if signal:
                signal.comment = f"[HYBRID-TREND] {signal.comment}, ADX={adx:.1f}"
        
        if signal:
            self.last_signal = signal.signal_type
        
        return signal


# Strategy Template Registry
STRATEGY_TEMPLATES = {
    "mean_reversion": {
        "name": "Mean Reversion",
        "description": "Bollinger Bands + RSI strategy for ranging markets",
        "class": MeanReversionStrategy,
        "default_params": {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70
        },
        "best_for": "Ranging/Sideways markets",
        "risk_per_trade": "1-2%"
    },
    "trend_following": {
        "name": "Trend Following (EMA Pullback)",
        "description": "EMA 50/200 trend with pullback entries",
        "class": TrendFollowingStrategy,
        "default_params": {
            "fast_ema": 50,
            "slow_ema": 200,
            "pullback_threshold": 0.002
        },
        "best_for": "Trending markets",
        "risk_per_trade": "1-2%"
    },
    "breakout": {
        "name": "Breakout Strategy",
        "description": "N-period high/low breakout with volume confirmation",
        "class": BreakoutStrategy,
        "default_params": {
            "lookback_period": 20,
            "atr_period": 14,
            "volume_multiplier": 1.5
        },
        "best_for": "Volatile/Expanding markets",
        "risk_per_trade": "1-2%"
    },
    "hybrid": {
        "name": "Hybrid (Auto-Switch)",
        "description": "Auto-switches between Mean Reversion and Trend Following based on ADX",
        "class": HybridStrategy,
        "default_params": {
            "adx_period": 14,
            "adx_threshold": 25
        },
        "best_for": "All market conditions",
        "risk_per_trade": "Adaptive"
    }
}


def get_strategy_template(template_id: str, symbol: str, timeframe: str, **kwargs) -> Optional[BaseStrategy]:
    """Factory function to create strategy from template"""
    if template_id not in STRATEGY_TEMPLATES:
        return None
    
    template = STRATEGY_TEMPLATES[template_id]
    strategy_class = template["class"]
    
    # Merge default params with overrides
    params = template["default_params"].copy()
    params.update(kwargs)
    
    return strategy_class(symbol, timeframe, **params)


def list_strategy_templates() -> List[dict]:
    """Get list of available strategy templates"""
    return [
        {
            "id": tid,
            "name": t["name"],
            "description": t["description"],
            "best_for": t["best_for"],
            "risk_per_trade": t["risk_per_trade"],
            "parameters": list(t["default_params"].keys())
        }
        for tid, t in STRATEGY_TEMPLATES.items()
    ]
