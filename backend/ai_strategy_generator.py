"""
AI Strategy Generator
Uses OpenAI API to generate trading strategies with proper error handling and fallbacks.
"""

import os
import logging
from typing import List, Dict, Any
from openai import OpenAI
import json

logger = logging.getLogger(__name__)


class AIStrategyGenerator:
    """Generates trading strategies using OpenAI API"""
    
    def __init__(self):
        # Get API key from environment variable (NEVER hardcode)
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.client = None
        
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                logger.info("[AI STRATEGY GENERATOR] ✓ OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"[AI STRATEGY GENERATOR] ❌ Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            logger.warning("[AI STRATEGY GENERATOR] ⚠ OPENAI_API_KEY not found in environment")
    
    def generate_strategies(
        self,
        count: int = 30,
        symbol: str = "EURUSD",
        timeframe: str = "1h",
        requirements: str = None
    ) -> List[Dict[str, Any]]:
        """
        Generate trading strategies using OpenAI API with fallback.
        
        Args:
            count: Number of strategies to generate
            symbol: Trading pair
            timeframe: Chart timeframe
            requirements: Optional custom requirements
            
        Returns:
            List of strategy dictionaries
        """
        logger.info(f"[AI STRATEGY GENERATOR] Starting strategy generation")
        logger.info(f"[AI STRATEGY GENERATOR] Target count: {count}")
        logger.info(f"[AI STRATEGY GENERATOR] Symbol: {symbol}, Timeframe: {timeframe}")
        
        if self.client and self.api_key:
            try:
                strategies = self._generate_with_openai(count, symbol, timeframe, requirements)
                if strategies and len(strategies) >= 10:
                    logger.info(f"[AI STRATEGY GENERATOR] ✓ OpenAI generated {len(strategies)} strategies")
                    return strategies
                else:
                    logger.warning(f"[AI STRATEGY GENERATOR] ⚠ OpenAI generated insufficient strategies, using fallback")
                    return self._generate_fallback_strategies(count)
            except Exception as e:
                logger.error(f"[AI STRATEGY GENERATOR] ❌ OpenAI generation failed: {e}")
                logger.info(f"[AI STRATEGY GENERATOR] → Falling back to predefined strategies")
                return self._generate_fallback_strategies(count)
        else:
            logger.warning(f"[AI STRATEGY GENERATOR] ⚠ OpenAI client not available, using fallback")
            return self._generate_fallback_strategies(count)
    
    def _generate_with_openai(
        self,
        count: int,
        symbol: str,
        timeframe: str,
        requirements: str = None
    ) -> List[Dict[str, Any]]:
        """Generate strategies using OpenAI API"""
        
        logger.info(f"[AI STRATEGY GENERATOR] 🤖 Calling OpenAI API...")
        
        # Build the prompt
        prompt = self._build_generation_prompt(count, symbol, timeframe, requirements)
        
        try:
            # Call OpenAI API with gpt-4o-mini (latest efficient model)
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Using latest available model
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert trading strategy architect specializing in algorithmic trading systems."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,  # Higher temperature for diversity
                max_tokens=4000,
            )
            
            # Parse response
            content = response.choices[0].message.content
            logger.info(f"[AI STRATEGY GENERATOR] ✓ OpenAI API call successful")
            logger.debug(f"[AI STRATEGY GENERATOR] Response length: {len(content)} characters")
            
            # Parse the JSON response
            strategies = self._parse_openai_response(content, count)
            
            logger.info(f"[AI STRATEGY GENERATOR] ✓ Parsed {len(strategies)} strategies from OpenAI")
            
            return strategies
            
        except Exception as e:
            logger.error(f"[AI STRATEGY GENERATOR] ❌ OpenAI API error: {str(e)}")
            raise
    
    def _build_generation_prompt(
        self,
        count: int,
        symbol: str,
        timeframe: str,
        requirements: str = None
    ) -> str:
        """Build the prompt for OpenAI"""
        
        base_prompt = f"""Generate {count} diverse trading strategies for {symbol} on {timeframe} timeframe.

Requirements:
- Mix of trend-following, mean-reversion, and breakout strategies
- Use different technical indicators (EMA, RSI, MACD, Bollinger Bands, ATR, ADX)
- Each strategy should have unique parameter combinations
- Include entry conditions, exit conditions, and risk management

{requirements if requirements else ''}

Return ONLY a JSON array of strategies with this structure:
[
  {{
    "name": "Strategy name",
    "type": "trend_following|mean_reversion|breakout",
    "description": "Brief description",
    "indicators": ["indicator1", "indicator2"],
    "parameters": {{
      "param1": value,
      "param2": value
    }},
    "entry_logic": "When to enter",
    "exit_logic": "When to exit",
    "stop_loss": "Stop loss logic",
    "take_profit": "Take profit logic"
  }}
]

Generate exactly {count} unique strategies with diverse approaches."""
        
        return base_prompt
    
    def _parse_openai_response(self, content: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse OpenAI response into strategy objects"""
        
        try:
            # Try to find JSON array in the response
            start_idx = content.find('[')
            end_idx = content.rfind(']')
            
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx+1]
                strategies_data = json.loads(json_str)
                
                # Convert to internal format
                strategies = []
                for idx, strat_data in enumerate(strategies_data):
                    strategy = {
                        "id": f"ai_strategy_{idx}",
                        "name": strat_data.get("name", f"AI Strategy {idx}"),
                        "type": strat_data.get("type", "trend_following"),
                        "description": strat_data.get("description", ""),
                        "template_id": strat_data.get("type", "CUSTOM").upper(),
                        "genes": strat_data.get("parameters", {}),
                        "fitness": 50.0,  # Default, will be calculated in backtest
                        "sharpe_ratio": 0.0,
                        "max_drawdown_pct": 0.0,
                        "profit_factor": 0.0,
                        "win_rate": 0.0,
                        "net_profit": 0.0,
                        "total_trades": 0,
                        "evaluated": False,
                        "source": "openai",
                        "indicators": strat_data.get("indicators", []),
                        "entry_logic": strat_data.get("entry_logic", ""),
                        "exit_logic": strat_data.get("exit_logic", ""),
                    }
                    strategies.append(strategy)
                
                logger.info(f"[AI STRATEGY GENERATOR] ✓ Successfully parsed {len(strategies)} strategies")
                return strategies
            else:
                logger.error("[AI STRATEGY GENERATOR] ❌ No JSON array found in response")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"[AI STRATEGY GENERATOR] ❌ JSON parsing error: {e}")
            return []
        except Exception as e:
            logger.error(f"[AI STRATEGY GENERATOR] ❌ Response parsing error: {e}")
            return []
    
    def _generate_fallback_strategies(self, count: int) -> List[Dict[str, Any]]:
        """
        Generate predefined fallback strategies when OpenAI is unavailable.
        Returns at least 10 diverse strategies.
        """
        logger.info(f"[AI STRATEGY GENERATOR] 📋 Generating {max(count, 10)} fallback strategies")
        
        # Predefined strategy templates with variations
        base_strategies = [
            {
                "name": "EMA Crossover Fast",
                "type": "trend_following",
                "template_id": "EMA_CROSSOVER",
                "genes": {
                    "fast_ma_period": 10,
                    "slow_ma_period": 30,
                    "atr_period": 14,
                    "stop_loss_atr_mult": 2.0,
                    "take_profit_atr_mult": 4.0,
                    "risk_per_trade_pct": 1.0,
                    "adx_threshold": 25.0
                }
            },
            {
                "name": "EMA Crossover Slow",
                "type": "trend_following",
                "template_id": "EMA_CROSSOVER",
                "genes": {
                    "fast_ma_period": 20,
                    "slow_ma_period": 50,
                    "atr_period": 14,
                    "stop_loss_atr_mult": 2.5,
                    "take_profit_atr_mult": 5.0,
                    "risk_per_trade_pct": 1.5,
                    "adx_threshold": 30.0
                }
            },
            {
                "name": "RSI Mean Reversion Aggressive",
                "type": "mean_reversion",
                "template_id": "RSI_MEAN_REVERSION",
                "genes": {
                    "rsi_period": 14,
                    "rsi_oversold": 25,
                    "rsi_overbought": 75,
                    "bb_period": 20,
                    "bb_std": 2.0,
                    "stop_loss_pct": 1.5,
                    "take_profit_pct": 2.0,
                    "risk_per_trade_pct": 1.0
                }
            },
            {
                "name": "RSI Mean Reversion Conservative",
                "type": "mean_reversion",
                "template_id": "RSI_MEAN_REVERSION",
                "genes": {
                    "rsi_period": 14,
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                    "bb_period": 20,
                    "bb_std": 2.5,
                    "stop_loss_pct": 1.0,
                    "take_profit_pct": 1.5,
                    "risk_per_trade_pct": 0.5
                }
            },
            {
                "name": "MACD Trend Following",
                "type": "trend_following",
                "template_id": "MACD_TREND",
                "genes": {
                    "fast_ma_period": 12,
                    "slow_ma_period": 26,
                    "atr_period": 14,
                    "stop_loss_atr_mult": 2.0,
                    "take_profit_atr_mult": 5.0,
                    "risk_per_trade_pct": 1.5,
                    "adx_threshold": 25.0
                }
            },
            {
                "name": "Bollinger Breakout Tight",
                "type": "breakout",
                "template_id": "BOLLINGER_BREAKOUT",
                "genes": {
                    "bb_period": 20,
                    "bb_std": 2.0,
                    "atr_period": 14,
                    "stop_loss_atr_mult": 1.5,
                    "take_profit_atr_mult": 4.0,
                    "risk_per_trade_pct": 1.0,
                    "adx_threshold": 20.0
                }
            },
            {
                "name": "Bollinger Breakout Wide",
                "type": "breakout",
                "template_id": "BOLLINGER_BREAKOUT",
                "genes": {
                    "bb_period": 20,
                    "bb_std": 2.5,
                    "atr_period": 14,
                    "stop_loss_atr_mult": 2.0,
                    "take_profit_atr_mult": 5.0,
                    "risk_per_trade_pct": 1.5,
                    "adx_threshold": 25.0
                }
            },
            {
                "name": "ATR Volatility Breakout",
                "type": "breakout",
                "template_id": "ATR_VOLATILITY_BREAKOUT",
                "genes": {
                    "atr_period": 14,
                    "stop_loss_atr_mult": 1.5,
                    "take_profit_atr_mult": 5.0,
                    "risk_per_trade_pct": 1.0,
                    "adx_threshold": 25.0,
                    "fast_ma_period": 10,
                    "slow_ma_period": 50
                }
            },
            {
                "name": "EMA Crossover Medium",
                "type": "trend_following",
                "template_id": "EMA_CROSSOVER",
                "genes": {
                    "fast_ma_period": 15,
                    "slow_ma_period": 40,
                    "atr_period": 14,
                    "stop_loss_atr_mult": 2.2,
                    "take_profit_atr_mult": 4.5,
                    "risk_per_trade_pct": 1.2,
                    "adx_threshold": 27.0
                }
            },
            {
                "name": "RSI Mean Reversion Balanced",
                "type": "mean_reversion",
                "template_id": "RSI_MEAN_REVERSION",
                "genes": {
                    "rsi_period": 14,
                    "rsi_oversold": 28,
                    "rsi_overbought": 72,
                    "bb_period": 20,
                    "bb_std": 2.2,
                    "stop_loss_pct": 1.2,
                    "take_profit_pct": 1.8,
                    "risk_per_trade_pct": 0.8
                }
            },
        ]
        
        # Generate variations to reach target count
        strategies = []
        target = max(count, 10)
        
        import random
        for i in range(target):
            base = base_strategies[i % len(base_strategies)].copy()
            
            # Add variation to parameters
            if i >= len(base_strategies):
                variation_factor = 1 + (random.random() - 0.5) * 0.2  # ±10% variation
                genes = base["genes"].copy()
                for key, value in genes.items():
                    if isinstance(value, (int, float)):
                        genes[key] = round(value * variation_factor, 2)
                base["genes"] = genes
                base["name"] = f"{base['name']} Var{i - len(base_strategies) + 1}"
            
            strategy = {
                "id": f"fallback_strategy_{i}",
                "name": base["name"],
                "type": base["type"],
                "template_id": base["template_id"],
                "genes": base["genes"],
                "fitness": 45.0 + random.random() * 10,  # Random initial fitness
                "sharpe_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "profit_factor": 0.0,
                "win_rate": 0.0,
                "net_profit": 0.0,
                "total_trades": 0,
                "evaluated": False,
                "source": "fallback",
                "description": f"Fallback {base['type']} strategy"
            }
            strategies.append(strategy)
        
        logger.info(f"[AI STRATEGY GENERATOR] ✓ Generated {len(strategies)} fallback strategies")
        return strategies
