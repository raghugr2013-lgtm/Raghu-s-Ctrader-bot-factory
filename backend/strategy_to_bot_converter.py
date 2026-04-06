"""
Strategy to Bot Converter
Converts pipeline strategy objects (from factory/optimizer) to format expected by ImprovedBotGenerator.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class StrategyToBotConverter:
    """
    Converts strategy dictionaries from the pipeline into the format
    expected by analyzer/improved_bot_generator.py
    """
    
    # Template ID to category mapping
    TEMPLATE_CATEGORIES = {
        "ema_crossover": "trend_following",
        "EMA_CROSSOVER": "trend_following",
        "rsi_mean_reversion": "mean_reversion",
        "RSI_MEAN_REVERSION": "mean_reversion",
        "macd_trend": "trend_following",
        "MACD_TREND": "trend_following",
        "bollinger_breakout": "breakout",
        "BOLLINGER_BREAKOUT": "breakout",
        "atr_volatility_breakout": "breakout",
        "ATR_VOLATILITY_BREAKOUT": "breakout",
    }
    
    def convert(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert pipeline strategy to bot generator format.
        
        Args:
            strategy: Strategy dict from pipeline (has template_id, genes, metrics)
            
        Returns:
            Dictionary in format expected by ImprovedBotGenerator.generate()
        """
        template_id = strategy.get("template_id", "ema_crossover")
        genes = strategy.get("genes", {})
        name = strategy.get("name", f"Strategy_{template_id}")
        
        # Determine category
        category = self.TEMPLATE_CATEGORIES.get(template_id, "trend_following")
        
        # Convert based on template type
        if "ema" in template_id.lower() or "crossover" in template_id.lower():
            return self._convert_ema_crossover(name, genes, category)
        elif "rsi" in template_id.lower():
            return self._convert_rsi_mean_reversion(name, genes, category)
        elif "macd" in template_id.lower():
            return self._convert_macd_trend(name, genes, category)
        elif "bollinger" in template_id.lower():
            return self._convert_bollinger_breakout(name, genes, category)
        elif "atr" in template_id.lower():
            return self._convert_atr_volatility(name, genes, category)
        else:
            # Fallback: generic strategy
            return self._convert_generic(name, genes, category, template_id)
    
    def _convert_ema_crossover(self, name: str, genes: Dict[str, float], category: str) -> Dict[str, Any]:
        """Convert EMA Crossover strategy"""
        return {
            "name": name,
            "category": category,
            "indicators": [
                {
                    "type": "EMA",
                    "parameters": {
                        "period": int(genes.get("fast_ma_period", 10)),
                        "source": "close"
                    }
                },
                {
                    "type": "EMA",
                    "parameters": {
                        "period": int(genes.get("slow_ma_period", 50)),
                        "source": "close"
                    }
                },
                {
                    "type": "ATR",
                    "parameters": {
                        "period": int(genes.get("atr_period", 14))
                    }
                },
                {
                    "type": "ADX",
                    "parameters": {
                        "period": 14
                    }
                }
            ],
            "entry_signals": [
                {
                    "type": "crossover",
                    "condition": "fast_ema > slow_ema",
                    "direction": "buy"
                },
                {
                    "type": "crossover",
                    "condition": "fast_ema < slow_ema",
                    "direction": "sell"
                }
            ],
            "risk_config": {
                "stop_loss_type": "atr_multiple",
                "stop_loss_value": genes.get("stop_loss_atr_mult", 2.0),
                "take_profit_type": "atr_multiple",
                "take_profit_value": genes.get("take_profit_atr_mult", 4.0),
                "position_sizing": "percent_risk",
                "size_value": genes.get("risk_per_trade_pct", 1.0),
                "trailing_stop": False
            },
            "filters": [
                {
                    "type": "trend",
                    "parameters": {
                        "min_adx": genes.get("adx_threshold", 25.0)
                    }
                }
            ]
        }
    
    def _convert_rsi_mean_reversion(self, name: str, genes: Dict[str, float], category: str) -> Dict[str, Any]:
        """Convert RSI Mean Reversion strategy"""
        return {
            "name": name,
            "category": category,
            "indicators": [
                {
                    "type": "RSI",
                    "parameters": {
                        "period": int(genes.get("rsi_period", 14)),
                        "source": "close"
                    }
                },
                {
                    "type": "ATR",
                    "parameters": {
                        "period": int(genes.get("atr_period", 14))
                    }
                }
            ],
            "entry_signals": [
                {
                    "type": "threshold",
                    "condition": "rsi < oversold_level",
                    "direction": "buy",
                    "oversold_level": genes.get("rsi_oversold", 30)
                },
                {
                    "type": "threshold",
                    "condition": "rsi > overbought_level",
                    "direction": "sell",
                    "overbought_level": genes.get("rsi_overbought", 70)
                }
            ],
            "risk_config": {
                "stop_loss_type": "atr_multiple",
                "stop_loss_value": genes.get("stop_loss_atr_mult", 2.0),
                "take_profit_type": "atr_multiple",
                "take_profit_value": genes.get("take_profit_atr_mult", 3.0),
                "position_sizing": "percent_risk",
                "size_value": genes.get("risk_per_trade_pct", 1.0),
                "trailing_stop": False
            },
            "filters": []
        }
    
    def _convert_macd_trend(self, name: str, genes: Dict[str, float], category: str) -> Dict[str, Any]:
        """Convert MACD Trend Following strategy"""
        return {
            "name": name,
            "category": category,
            "indicators": [
                {
                    "type": "MACD",
                    "parameters": {
                        "fast_period": int(genes.get("macd_fast", 12)),
                        "slow_period": int(genes.get("macd_slow", 26)),
                        "signal_period": int(genes.get("macd_signal", 9))
                    }
                },
                {
                    "type": "ATR",
                    "parameters": {
                        "period": int(genes.get("atr_period", 14))
                    }
                }
            ],
            "entry_signals": [
                {
                    "type": "crossover",
                    "condition": "macd_line > signal_line",
                    "direction": "buy"
                },
                {
                    "type": "crossover",
                    "condition": "macd_line < signal_line",
                    "direction": "sell"
                }
            ],
            "risk_config": {
                "stop_loss_type": "atr_multiple",
                "stop_loss_value": genes.get("stop_loss_atr_mult", 2.0),
                "take_profit_type": "atr_multiple",
                "take_profit_value": genes.get("take_profit_atr_mult", 4.0),
                "position_sizing": "percent_risk",
                "size_value": genes.get("risk_per_trade_pct", 1.0),
                "trailing_stop": False
            },
            "filters": []
        }
    
    def _convert_bollinger_breakout(self, name: str, genes: Dict[str, float], category: str) -> Dict[str, Any]:
        """Convert Bollinger Bands Breakout strategy"""
        return {
            "name": name,
            "category": category,
            "indicators": [
                {
                    "type": "BollingerBands",
                    "parameters": {
                        "period": int(genes.get("bb_period", 20)),
                        "std_dev": genes.get("bb_std_dev", 2.0),
                        "source": "close"
                    }
                },
                {
                    "type": "ATR",
                    "parameters": {
                        "period": int(genes.get("atr_period", 14))
                    }
                }
            ],
            "entry_signals": [
                {
                    "type": "breakout",
                    "condition": "close > upper_band",
                    "direction": "buy"
                },
                {
                    "type": "breakout",
                    "condition": "close < lower_band",
                    "direction": "sell"
                }
            ],
            "risk_config": {
                "stop_loss_type": "atr_multiple",
                "stop_loss_value": genes.get("stop_loss_atr_mult", 2.0),
                "take_profit_type": "atr_multiple",
                "take_profit_value": genes.get("take_profit_atr_mult", 3.0),
                "position_sizing": "percent_risk",
                "size_value": genes.get("risk_per_trade_pct", 1.0),
                "trailing_stop": False
            },
            "filters": []
        }
    
    def _convert_atr_volatility(self, name: str, genes: Dict[str, float], category: str) -> Dict[str, Any]:
        """Convert ATR Volatility Breakout strategy"""
        return {
            "name": name,
            "category": category,
            "indicators": [
                {
                    "type": "ATR",
                    "parameters": {
                        "period": int(genes.get("atr_period", 14))
                    }
                },
                {
                    "type": "SMA",
                    "parameters": {
                        "period": int(genes.get("sma_period", 50)),
                        "source": "close"
                    }
                }
            ],
            "entry_signals": [
                {
                    "type": "volatility",
                    "condition": "high > sma + atr * multiplier",
                    "direction": "buy",
                    "multiplier": genes.get("breakout_atr_mult", 2.0)
                },
                {
                    "type": "volatility",
                    "condition": "low < sma - atr * multiplier",
                    "direction": "sell",
                    "multiplier": genes.get("breakout_atr_mult", 2.0)
                }
            ],
            "risk_config": {
                "stop_loss_type": "atr_multiple",
                "stop_loss_value": genes.get("stop_loss_atr_mult", 1.5),
                "take_profit_type": "atr_multiple",
                "take_profit_value": genes.get("take_profit_atr_mult", 3.0),
                "position_sizing": "percent_risk",
                "size_value": genes.get("risk_per_trade_pct", 1.0),
                "trailing_stop": False
            },
            "filters": [
                {
                    "type": "volatility",
                    "parameters": {
                        "min_atr_pips": genes.get("min_atr_pips", 5.0),
                        "max_atr_pips": genes.get("max_atr_pips", 50.0)
                    }
                }
            ]
        }
    
    def _convert_generic(self, name: str, genes: Dict[str, float], category: str, template_id: str) -> Dict[str, Any]:
        """Convert generic/unknown strategy type"""
        logger.warning(f"Unknown template_id '{template_id}', using generic conversion")
        
        # Extract common parameters
        indicators = []
        
        # Try to detect indicators from gene keys
        if any(k.startswith("rsi") for k in genes.keys()):
            indicators.append({
                "type": "RSI",
                "parameters": {"period": int(genes.get("rsi_period", 14))}
            })
        
        if any(k.startswith("ma") or k.startswith("ema") or k.startswith("sma") for k in genes.keys()):
            indicators.append({
                "type": "EMA",
                "parameters": {"period": int(genes.get("ma_period", 20))}
            })
        
        if any(k.startswith("atr") for k in genes.keys()):
            indicators.append({
                "type": "ATR",
                "parameters": {"period": int(genes.get("atr_period", 14))}
            })
        
        return {
            "name": name,
            "category": category,
            "indicators": indicators if indicators else [
                {"type": "EMA", "parameters": {"period": 20}},
                {"type": "ATR", "parameters": {"period": 14}}
            ],
            "entry_signals": [
                {
                    "type": "generic",
                    "condition": "indicator_signal",
                    "direction": "both"
                }
            ],
            "risk_config": {
                "stop_loss_type": "atr_multiple",
                "stop_loss_value": genes.get("stop_loss_atr_mult", 2.0),
                "take_profit_type": "atr_multiple",
                "take_profit_value": genes.get("take_profit_atr_mult", 3.0),
                "position_sizing": "percent_risk",
                "size_value": genes.get("risk_per_trade_pct", 1.0),
                "trailing_stop": False
            },
            "filters": []
        }
