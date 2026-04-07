"""
AI Strategy Optimizer
Post-processing layer that uses AI to improve strategies selected by Codex
Includes automatic backtesting to validate improvements
"""

import logging
from typing import Dict, List, Optional, Tuple
from emergentintegrations.llm.chat import LlmChat, UserMessage
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class AIStrategyOptimizer:
    """Uses AI to optimize strategy parameters and logic"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def optimize_strategy(
        self,
        strategy: Dict,
        ai_model: str = "openai"
    ) -> Dict:
        """
        Optimize a single strategy using AI
        
        Args:
            strategy: Strategy dict with template_id, genes, and metrics
            ai_model: "openai" or "claude"
        
        Returns:
            Dict with optimized genes and reasoning
        """
        session_id = f"optimize_{strategy['id']}"
        
        # Create AI chat
        chat = LlmChat(
            api_key=self.api_key,
            session_id=session_id,
            system_message="""You are an expert forex trading strategy optimizer.
You analyze strategy parameters and suggest improvements to:
1. Improve entry timing (reduce false signals)
2. Improve exit logic (maximize profits, minimize losses)
3. Reduce drawdown (better risk management)

Return ONLY a JSON object with:
{
  "optimized_params": {
    "param_name": new_value,
    ...
  },
  "improvements": [
    "Description of improvement 1",
    "Description of improvement 2"
  ],
  "reasoning": "Why these changes will help"
}"""
        )
        
        # Select model
        if ai_model == "openai":
            chat.with_model("openai", "gpt-5.2")
        elif ai_model == "claude":
            chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        # Build optimization prompt
        prompt = self._build_optimization_prompt(strategy)
        
        try:
            response = await chat.send_message(UserMessage(text=prompt))
            
            # Parse AI response
            import json
            response_text = response.strip()
            
            # Extract JSON if wrapped in markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            optimization = json.loads(response_text)
            
            return {
                "success": True,
                "ai_model": ai_model,
                "optimized_params": optimization.get("optimized_params", {}),
                "improvements": optimization.get("improvements", []),
                "reasoning": optimization.get("reasoning", ""),
            }
            
        except Exception as e:
            logger.error(f"AI optimization failed for {strategy['id']}: {e}")
            return {
                "success": False,
                "error": str(e),
                "optimized_params": {},
                "improvements": [],
                "reasoning": "",
            }
    
    def _build_optimization_prompt(self, strategy: Dict) -> str:
        """Build prompt for AI optimization"""
        template = strategy.get("template_id", "unknown")
        genes = strategy.get("genes", {})
        
        # Current performance metrics
        pf = strategy.get("profit_factor", 0)
        sharpe = strategy.get("sharpe_ratio", 0)
        dd = strategy.get("max_drawdown_pct", 0)
        win_rate = strategy.get("win_rate", 0)
        trades = strategy.get("total_trades", 0)
        
        prompt = f"""Optimize this {template} strategy:

CURRENT PARAMETERS:
{self._format_params(genes)}

CURRENT PERFORMANCE:
- Profit Factor: {pf:.2f}
- Sharpe Ratio: {sharpe:.2f}
- Max Drawdown: {dd:.1f}%
- Win Rate: {win_rate:.1f}%
- Total Trades: {trades}

OPTIMIZATION GOALS:
1. Improve entry timing → Reduce false signals
2. Improve exit logic → Better profit capture
3. Reduce drawdown → Tighter risk management

Analyze the parameters and suggest improvements.
Consider:
- Are periods too short/long? (noise vs lag)
- Are stop loss/take profit balanced?
- Is risk per trade appropriate?
- Are filters (ADX, ATR) too strict/loose?

Return optimized parameters as JSON."""
        
        return prompt
    
    def _format_params(self, genes: Dict) -> str:
        """Format parameters for display"""
        lines = []
        for key, value in genes.items():
            if isinstance(value, float):
                lines.append(f"- {key}: {value:.2f}")
            else:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    async def dual_optimization(
        self,
        strategy: Dict
    ) -> Dict:
        """
        Optimize using both OpenAI and Claude, compare results
        
        Returns:
            Dict with both optimizations and recommended version
        """
        logger.info(f"[AI OPTIMIZER] Dual optimization for strategy {strategy['id']}")
        
        # Get OpenAI optimization
        openai_result = await self.optimize_strategy(strategy, "openai")
        
        # Get Claude optimization
        claude_result = await self.optimize_strategy(strategy, "claude")
        
        # Determine which is more conservative (better for live trading)
        openai_params = openai_result.get("optimized_params", {})
        claude_params = claude_result.get("optimized_params", {})
        
        # Use Claude as primary (more conservative), OpenAI as secondary
        recommended = "claude" if claude_result.get("success") else "openai"
        
        return {
            "openai": openai_result,
            "claude": claude_result,
            "recommended": recommended,
            "consensus_params": self._merge_optimizations(openai_params, claude_params),
        }
    
    def _merge_optimizations(self, openai_params: Dict, claude_params: Dict) -> Dict:
        """
        Merge two optimization suggestions
        Takes average for numeric values, Claude's choice for others
        """
        merged = {}
        all_keys = set(openai_params.keys()) | set(claude_params.keys())
        
        for key in all_keys:
            openai_val = openai_params.get(key)
            claude_val = claude_params.get(key)
            
            if openai_val is not None and claude_val is not None:
                # Both have value
                if isinstance(openai_val, (int, float)) and isinstance(claude_val, (int, float)):
                    # Average numeric values
                    merged[key] = (openai_val + claude_val) / 2
                else:
                    # Use Claude's choice for non-numeric
                    merged[key] = claude_val
            else:
                # Use whichever exists
                merged[key] = claude_val if claude_val is not None else openai_val
        
        return merged


async def backtest_strategy_params(
    symbol: str,
    timeframe: str,
    template_id: str,
    params: Dict,
    initial_balance: float,
    duration_days: int,
    db
) -> Dict:
    """
    Run backtest on strategy parameters
    
    Returns:
        Dict with backtest metrics
    """
    from backtest_real_engine import run_backtest_real
    from market_data_service import MarketDataService
    
    try:
        # Get market data
        data_service = MarketDataService(db)
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=duration_days)
        
        candles = await data_service.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        if not candles or len(candles) < 50:
            return {
                "success": False,
                "error": "Insufficient data for backtest",
                "metrics": {}
            }
        
        # Map template to backtest strategy type
        template_strategy_map = {
            "ema_crossover": "trend_following",
            "rsi_mean_reversion": "mean_reversion",
            "macd_trend": "trend_following",
            "bollinger_breakout": "breakout",
            "atr_volatility_breakout": "breakout"
        }
        
        strategy_type = template_strategy_map.get(template_id, "trend_following")
        
        # Run backtest
        result = run_backtest_real(
            symbol=symbol,
            timeframe=timeframe,
            initial_balance=initial_balance,
            duration_days=duration_days,
            strategy_type=strategy_type,
            params=params,
            candles=candles
        )
        
        return {
            "success": True,
            "metrics": {
                "net_profit": result.net_profit,
                "profit_factor": result.profit_factor,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown_pct": result.max_drawdown_percent,
                "win_rate": result.win_rate,
                "total_trades": result.total_trades,
                "avg_win": result.avg_win,
                "avg_loss": result.avg_loss,
            }
        }
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "metrics": {}
        }


async def optimize_portfolio_strategies(
    strategies: List[Dict],
    api_key: str,
    max_strategies: int = 5,
    run_backtest: bool = True,
    symbol: str = "EURUSD",
    timeframe: str = "1h",
    duration_days: int = 365,
    initial_balance: float = 10000.0,
    db = None
) -> List[Dict]:
    """
    Optimize top strategies from portfolio with automatic backtesting
    
    Args:
        strategies: List of strategy dicts (already sorted by fitness)
        api_key: Emergent LLM key
        max_strategies: Maximum strategies to optimize
        run_backtest: Whether to backtest optimized strategies
        symbol: Trading symbol for backtest
        timeframe: Timeframe for backtest
        duration_days: Backtest duration
        initial_balance: Starting balance
        db: Database connection for backtest data
    
    Returns:
        List of dicts with original, optimized versions, and comparison
    """
    optimizer = AIStrategyOptimizer(api_key)
    
    # Take top N strategies
    top_strategies = strategies[:max_strategies]
    
    results = []
    for strategy in top_strategies:
        logger.info(f"[AI OPTIMIZER] Optimizing strategy {strategy['id']}")
        
        # Run dual optimization
        optimization = await optimizer.dual_optimization(strategy)
        
        result_entry = {
            "original": strategy,
            "optimization": optimization,
            "status": "optimized" if optimization["claude"]["success"] or optimization["openai"]["success"] else "failed"
        }
        
        # Auto-backtest if enabled
        if run_backtest and db is not None and optimization["claude"]["success"]:
            logger.info(f"[AI OPTIMIZER] Backtesting optimized strategy {strategy['id']}")
            
            # Get optimized parameters (use consensus)
            optimized_params = optimization.get("consensus_params", {})
            
            # Merge with original params (in case some weren't optimized)
            original_genes = strategy.get("genes", {})
            final_params = {**original_genes, **optimized_params}
            
            # Backtest optimized version
            backtest_result = await backtest_strategy_params(
                symbol=symbol,
                timeframe=timeframe,
                template_id=strategy.get("template_id", ""),
                params=final_params,
                initial_balance=initial_balance,
                duration_days=duration_days,
                db=db
            )
            
            if backtest_result["success"]:
                # Compare with original metrics
                original_metrics = {
                    "profit_factor": strategy.get("profit_factor", 0),
                    "sharpe_ratio": strategy.get("sharpe_ratio", 0),
                    "max_drawdown_pct": strategy.get("max_drawdown_pct", 0),
                    "win_rate": strategy.get("win_rate", 0),
                    "total_trades": strategy.get("total_trades", 0),
                    "net_profit": strategy.get("net_profit", 0),
                }
                
                optimized_metrics = backtest_result["metrics"]
                
                # Calculate improvements
                improvements = {}
                for key in ["profit_factor", "sharpe_ratio", "win_rate", "net_profit"]:
                    original_val = original_metrics.get(key, 0)
                    optimized_val = optimized_metrics.get(key, 0)
                    if original_val > 0:
                        improvement_pct = ((optimized_val - original_val) / original_val) * 100
                        improvements[f"{key}_improvement_pct"] = round(improvement_pct, 2)
                    else:
                        improvements[f"{key}_improvement_pct"] = 0
                
                # Drawdown improvement (lower is better)
                original_dd = original_metrics.get("max_drawdown_pct", 0)
                optimized_dd = optimized_metrics.get("max_drawdown_pct", 0)
                if original_dd > 0:
                    dd_improvement = ((original_dd - optimized_dd) / original_dd) * 100
                    improvements["drawdown_reduction_pct"] = round(dd_improvement, 2)
                else:
                    improvements["drawdown_reduction_pct"] = 0
                
                # Add backtest comparison
                result_entry["backtest_comparison"] = {
                    "original_metrics": original_metrics,
                    "optimized_metrics": optimized_metrics,
                    "improvements": improvements,
                    "validation_status": "verified" if improvements.get("profit_factor_improvement_pct", 0) > 0 else "no_improvement"
                }
                
                logger.info(f"[AI OPTIMIZER] Backtest complete - PF improvement: {improvements.get('profit_factor_improvement_pct', 0):.2f}%")
            else:
                result_entry["backtest_comparison"] = {
                    "error": backtest_result.get("error", "Unknown error"),
                    "validation_status": "failed"
                }
        
        results.append(result_entry)
    
    return results
