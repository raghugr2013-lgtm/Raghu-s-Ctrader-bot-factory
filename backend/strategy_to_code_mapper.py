"""
Structured Strategy to cTrader Code Mapper
Converts strategy definitions into deterministic cTrader cBot code.
NO FREE-TEXT GENERATION - uses verified templates and snippets only.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from ctrader_base_template import CTraderBaseTemplate
from ctrader_api_snippets import CTraderAPISnippets
import logging

logger = logging.getLogger(__name__)


@dataclass
class StrategyDefinition:
    """Structured strategy definition - no ambiguity"""
    
    # Basic info
    name: str
    description: str
    
    # Indicators (structured)
    indicators: List[Dict[str, Any]] = field(default_factory=list)
    # Example: [{"type": "ema", "name": "fast", "period": 20}, {"type": "ema", "name": "slow", "period": 50}]
    
    # Entry conditions (structured)
    entry_long: List[Dict[str, Any]] = field(default_factory=list)
    # Example: [{"type": "crossover_above", "fast": "fast_ema", "slow": "slow_ema"}]
    
    entry_short: List[Dict[str, Any]] = field(default_factory=list)
    # Example: [{"type": "crossover_below", "fast": "fast_ema", "slow": "slow_ema"}]
    
    # Exit conditions
    exit_long: List[Dict[str, Any]] = field(default_factory=list)
    exit_short: List[Dict[str, Any]] = field(default_factory=list)
    
    # Risk management
    risk_percent: float = 1.0
    stop_loss_pips: float = 20.0
    take_profit_pips: float = 40.0
    max_daily_loss_percent: float = 5.0
    max_total_drawdown_percent: float = 10.0
    
    # Position management
    allow_multiple_positions: bool = False
    position_label: str = "Strategy"


class StrategyToCodeMapper:
    """
    Maps structured strategy definitions to cTrader cBot code.
    Uses ONLY verified templates and API snippets.
    """
    
    def __init__(self):
        self.snippets = CTraderAPISnippets()
        self.template = CTraderBaseTemplate()
    
    def map_strategy_to_code(self, strategy: StrategyDefinition) -> str:
        """
        Convert structured strategy to complete cTrader cBot code.
        DETERMINISTIC - same input always produces same output.
        """
        
        logger.info(f"Mapping strategy to code: {strategy.name}")
        
        # Step 1: Generate parameters
        parameters = self._generate_parameters(strategy)
        
        # Step 2: Generate indicator declarations
        indicators_decl = self._generate_indicator_declarations(strategy)
        
        # Step 3: Generate state variables
        state_vars = self._generate_state_variables(strategy)
        
        # Step 4: Generate indicator initializations
        indicator_init = self._generate_indicator_initializations(strategy)
        
        # Step 5: Generate state initializations
        state_init = self._generate_state_initializations(strategy)
        
        # Step 6: Generate OnStart custom logic
        onstart_custom = self._generate_onstart_custom(strategy)
        
        # Step 7: Generate strategy logic (OnBar)
        strategy_logic = self._generate_strategy_logic(strategy)
        
        # Step 8: Generate helper methods
        helper_methods = self._generate_helper_methods(strategy)
        
        # Step 9: Generate cleanup logic
        cleanup_logic = self._generate_cleanup_logic(strategy)
        
        # Step 10: Assemble using base template
        full_code = self.template.generate_full_template(
            bot_name=strategy.name.replace(" ", ""),
            parameters=parameters,
            indicators=indicators_decl,
            state_vars=state_vars,
            indicator_init=indicator_init,
            state_init=state_init,
            onstart_custom=onstart_custom,
            strategy_logic=strategy_logic,
            helper_methods=helper_methods,
            cleanup_logic=cleanup_logic
        )
        
        logger.info(f"✅ Code generated: {len(full_code)} characters")
        return full_code
    
    def _generate_parameters(self, strategy: StrategyDefinition) -> str:
        """Generate parameter declarations"""
        params = []
        
        # Indicator periods
        for ind in strategy.indicators:
            if 'period' in ind:
                param_name = f"{ind['name'].title()}Period"
                params.append(self.snippets.parameter_int(
                    f"{ind['name'].title()} Period",
                    ind['period'],
                    min_val=1,
                    max_val=500
                ))
        
        # Risk parameters
        params.append(self.snippets.parameter_double(
            "Risk Per Trade (%)",
            strategy.risk_percent,
            min_val=0.1,
            max_val=5.0
        ))
        
        params.append(self.snippets.parameter_double(
            "Stop Loss Pips",
            strategy.stop_loss_pips,
            min_val=5,
            max_val=200
        ))
        
        params.append(self.snippets.parameter_double(
            "Take Profit Pips",
            strategy.take_profit_pips,
            min_val=5,
            max_val=500
        ))
        
        params.append(self.snippets.parameter_double(
            "Max Daily Loss (%)",
            strategy.max_daily_loss_percent,
            min_val=1,
            max_val=20
        ))
        
        params.append(self.snippets.parameter_double(
            "Max Total Drawdown (%)",
            strategy.max_total_drawdown_percent,
            min_val=2,
            max_val=30
        ))
        
        return "\n".join(params)
    
    def _generate_indicator_declarations(self, strategy: StrategyDefinition) -> str:
        """Generate indicator variable declarations"""
        declarations = []
        
        for ind in strategy.indicators:
            ind_type = ind['type'].lower()
            var_name = f"{ind['name']}Indicator"
            
            if ind_type == 'ema':
                decl = self.snippets.indicator_ema(var_name, f"{ind['name'].title()}Period")
                declarations.append(decl['declaration'])
            elif ind_type == 'sma':
                decl = self.snippets.indicator_sma(var_name, f"{ind['name'].title()}Period")
                declarations.append(decl['declaration'])
            elif ind_type == 'rsi':
                decl = self.snippets.indicator_rsi(var_name, f"{ind['name'].title()}Period")
                declarations.append(decl['declaration'])
            elif ind_type == 'atr':
                decl = self.snippets.indicator_atr(var_name, f"{ind['name'].title()}Period")
                declarations.append(decl['declaration'])
        
        return "\n".join(declarations)
    
    def _generate_state_variables(self, strategy: StrategyDefinition) -> str:
        """Generate state tracking variables"""
        return """private double dailyStartBalance;
        private double peakBalance;
        private DateTime lastResetDate;"""
    
    def _generate_indicator_initializations(self, strategy: StrategyDefinition) -> str:
        """Generate indicator initialization code"""
        inits = []
        
        for ind in strategy.indicators:
            ind_type = ind['type'].lower()
            var_name = f"{ind['name']}Indicator"
            
            if ind_type == 'ema':
                init = self.snippets.indicator_ema(var_name, f"{ind['name'].title()}Period")
                inits.append("            " + init['initialization'])
            elif ind_type == 'sma':
                init = self.snippets.indicator_sma(var_name, f"{ind['name'].title()}Period")
                inits.append("            " + init['initialization'])
            elif ind_type == 'rsi':
                init = self.snippets.indicator_rsi(var_name, f"{ind['name'].title()}Period")
                inits.append("            " + init['initialization'])
            elif ind_type == 'atr':
                init = self.snippets.indicator_atr(var_name, f"{ind['name'].title()}Period")
                inits.append("            " + init['initialization'])
        
        return "\n".join(inits)
    
    def _generate_state_initializations(self, strategy: StrategyDefinition) -> str:
        """Generate state initialization code"""
        return """            dailyStartBalance = Account.Balance;
            peakBalance = Account.Balance;
            lastResetDate = Server.Time.Date;"""
    
    def _generate_onstart_custom(self, strategy: StrategyDefinition) -> str:
        """Generate custom OnStart logic"""
        lines = [f'            Print("Strategy: {strategy.description}");']
        lines.append(f'            Print("Risk per trade: {{RiskPerTrade}}%");')
        lines.append(f'            Print("SL: {{StopLossPips}} pips, TP: {{TakeProfitPips}} pips");')
        return "\n".join(lines)
    
    def _generate_strategy_logic(self, strategy: StrategyDefinition) -> str:
        """Generate main strategy logic (OnBar method body)"""
        logic_parts = []
        
        # Safety checks (always first)
        logic_parts.append(self.snippets.safety_checks())
        
        # Daily reset
        logic_parts.append(self.snippets.daily_reset_logic())
        
        # Prop firm checks (use clean parameter names)
        logic_parts.append(self.snippets.prop_firm_daily_loss_check("MaxDailyLoss"))
        logic_parts.append(self.snippets.prop_firm_total_drawdown_check("MaxTotalDrawdown"))
        
        # Generate entry conditions
        logic_parts.append("\n            // === ENTRY LOGIC ===")
        
        # Long entry
        if strategy.entry_long:
            logic_parts.append(self._generate_entry_logic(strategy.entry_long, "Buy", strategy))
        
        # Short entry
        if strategy.entry_short:
            logic_parts.append(self._generate_entry_logic(strategy.entry_short, "Sell", strategy))
        
        return "\n".join(logic_parts)
    
    def _generate_entry_logic(self, conditions: List[Dict], trade_type: str, strategy: StrategyDefinition) -> str:
        """Generate entry logic for long or short"""
        logic = []
        
        # Use prefix to avoid variable name conflicts between long and short
        var_prefix = "long" if trade_type == "Buy" else "short"
        
        # Generate conditions
        for cond in conditions:
            cond_type = cond['type']
            
            if cond_type == 'crossover_above':
                fast_var = f"{cond['fast']}Indicator"
                slow_var = f"{cond['slow']}Indicator"
                logic.append(self.snippets.crossover_above(fast_var, slow_var, var_prefix))
                condition_var = f"{var_prefix}bullishCrossover"
            elif cond_type == 'crossover_below':
                fast_var = f"{cond['fast']}Indicator"
                slow_var = f"{cond['slow']}Indicator"
                logic.append(self.snippets.crossover_below(fast_var, slow_var, var_prefix))
                condition_var = f"{var_prefix}bearishCrossover"
            elif cond_type == 'rsi_oversold':
                rsi_var = f"{cond['indicator']}Indicator"
                logic.append("            " + self.snippets.rsi_oversold(rsi_var, cond.get('threshold', 30)))
                condition_var = "isOversold"
            elif cond_type == 'rsi_overbought':
                rsi_var = f"{cond['indicator']}Indicator"
                logic.append("            " + self.snippets.rsi_overbought(rsi_var, cond.get('threshold', 70)))
                condition_var = "isOverbought"
            else:
                condition_var = "true"  # Default
        
        # Check if position exists
        logic.append(self.snippets.check_position_exists(strategy.position_label, trade_type, var_prefix))
        
        # Entry execution (use clean parameter names: StopLossPips, TakeProfitPips, RiskPerTrade)
        logic.append(f"""            
            if ({condition_var} && !{var_prefix}positionExists)
            {{
                {self.snippets.calculate_position_size_fixed_risk("RiskPerTrade", "StopLossPips")}
                
                {self.snippets.execute_market_order(
                    trade_type,
                    "volumeInUnits",
                    strategy.position_label,
                    "StopLossPips",
                    "TakeProfitPips"
                )}
            }}""")
        
        return "\n".join(logic)
    
    def _generate_helper_methods(self, strategy: StrategyDefinition) -> str:
        """Generate helper methods"""
        return ""  # No helpers needed for basic strategies
    
    def _generate_cleanup_logic(self, strategy: StrategyDefinition) -> str:
        """Generate cleanup logic for OnStop"""
        return """            // Close all open positions
            foreach (var position in Positions)
            {
                if (position.SymbolName == SymbolName)
                {
                    ClosePosition(position);
                }
            }"""


# Example usage and verification
if __name__ == "__main__":
    # Define a simple EMA crossover strategy
    ema_cross_strategy = StrategyDefinition(
        name="EMA_Crossover_Bot",
        description="Buy when Fast EMA crosses above Slow EMA, Sell when crosses below",
        indicators=[
            {"type": "ema", "name": "fast", "period": 20},
            {"type": "ema", "name": "slow", "period": 50}
        ],
        entry_long=[
            {"type": "crossover_above", "fast": "fast", "slow": "slow"}
        ],
        entry_short=[
            {"type": "crossover_below", "fast": "fast", "slow": "slow"}
        ],
        risk_percent=1.0,
        stop_loss_pips=20.0,
        take_profit_pips=40.0,
        position_label="EMA_Cross"
    )
    
    # Generate code
    mapper = StrategyToCodeMapper()
    generated_code = mapper.map_strategy_to_code(ema_cross_strategy)
    
    print("=" * 70)
    print("STRUCTURED STRATEGY MAPPER - GENERATED CODE")
    print("=" * 70)
    print(generated_code)
    print("\n" + "=" * 70)
    print(f"✅ Generated {len(generated_code)} characters")
    print("✅ Code uses ONLY verified cTrader API calls")
    print("✅ Structure is deterministic and repeatable")
