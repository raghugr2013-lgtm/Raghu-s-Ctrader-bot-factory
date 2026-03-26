"""
Safety Injector - Inject safety rules into generated bot code
Uses refinement engine logic to add comprehensive safety mechanisms
"""

import re
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def inject_safety_rules(code: str, prop_firm: str = "none", risk_percent: float = 1.0) -> Dict[str, Any]:
    """
    Inject safety rules into bot code
    
    Args:
        code: Original C# cBot code
        prop_firm: Prop firm rules to apply (ftmo, fundednext, etc.)
        risk_percent: Risk percentage per trade
    
    Returns:
        Dict with enhanced code and applied changes
    """
    
    changes = []
    enhanced_code = code
    
    # 1. Inject Stop Loss if missing
    has_stop_loss = 'StopLoss' in code or 'stopLoss' in code or 'Stop' in code
    if not has_stop_loss:
        enhanced_code, sl_added = _inject_stop_loss(enhanced_code)
        if sl_added:
            changes.append("Added default stop loss (25 pips)")
    
    # 2. Inject Take Profit if missing
    has_take_profit = 'TakeProfit' in code or 'takeProfit' in code
    if not has_take_profit:
        enhanced_code, tp_added = _inject_take_profit(enhanced_code)
        if tp_added:
            changes.append("Added take profit target (2:1 risk-reward)")
    
    # 3. Inject Max Risk Per Trade
    enhanced_code, risk_added = _inject_risk_management(enhanced_code, risk_percent)
    if risk_added:
        changes.append(f"Added risk management ({risk_percent}% per trade)")
    
    # 4. Inject Daily Loss Limit
    enhanced_code, daily_added = _inject_daily_loss_limit(enhanced_code)
    if daily_added:
        changes.append("Added daily loss limit (5% max)")
    
    # 5. Inject Max Drawdown Protection
    enhanced_code, dd_added = _inject_drawdown_protection(enhanced_code)
    if dd_added:
        changes.append("Added max drawdown protection (10%)")
    
    # 6. Inject Spread Filter
    has_spread = 'Spread' in code and 'Symbol.Spread' in code
    if not has_spread:
        enhanced_code, spread_added = _inject_spread_filter(enhanced_code)
        if spread_added:
            changes.append("Added spread filter (max 3 pips)")
    
    # 7. Inject Session Filter
    has_session = 'TradingStartHour' in code or 'session' in code.lower()
    if not has_session:
        enhanced_code, session_added = _inject_session_filter(enhanced_code)
        if session_added:
            changes.append("Added trading session filter (8:00-17:00 UTC)")
    
    # 8. Apply prop firm specific rules
    if prop_firm and prop_firm != "none":
        enhanced_code, firm_changes = _inject_prop_firm_rules(enhanced_code, prop_firm)
        changes.extend(firm_changes)
    
    return {
        "success": True,
        "code": enhanced_code,
        "changes_applied": changes,
        "changes_count": len(changes),
        "message": f"Injected {len(changes)} safety enhancement(s)"
    }


def _inject_stop_loss(code: str) -> tuple[str, bool]:
    """Inject stop loss parameter and logic"""
    
    # Add parameter if not exists
    if 'StopLossPips' not in code:
        # Find parameter section
        param_pattern = r'(// .*?PARAMETERS.*?\n)'
        if re.search(param_pattern, code, re.IGNORECASE):
            insertion = '''
        [Parameter("Stop Loss (Pips)", DefaultValue = 25, MinValue = 5, MaxValue = 200)]
        public double StopLossPips { get; set; }
'''
            code = re.sub(param_pattern, r'\1' + insertion, code, flags=re.IGNORECASE)
        else:
            # Add after class declaration
            class_pattern = r'(public class \w+ : Robot\s*\{)'
            insertion = '''
        
        // Risk Parameters
        [Parameter("Stop Loss (Pips)", DefaultValue = 25, MinValue = 5, MaxValue = 200)]
        public double StopLossPips { get; set; }
'''
            code = re.sub(class_pattern, r'\1' + insertion, code)
        
        # Update ExecuteMarketOrder calls to use stop loss
        code = re.sub(
            r'ExecuteMarketOrder\((TradeType\.\w+), (\w+), (\w+), (["\w]+)\)',
            r'ExecuteMarketOrder(\1, \2, \3, \4, StopLossPips, null)',
            code
        )
        
        return code, True
    
    return code, False


def _inject_take_profit(code: str) -> tuple[str, bool]:
    """Inject take profit parameter and logic"""
    
    if 'TakeProfitPips' not in code:
        # Add parameter
        param_pattern = r'(StopLossPips.*?\n)'
        if re.search(param_pattern, code):
            insertion = '''
        [Parameter("Take Profit (Pips)", DefaultValue = 50, MinValue = 10, MaxValue = 500)]
        public double TakeProfitPips { get; set; }
'''
            code = re.sub(param_pattern, r'\1' + insertion, code)
        else:
            class_pattern = r'(public class \w+ : Robot\s*\{)'
            insertion = '''
        [Parameter("Take Profit (Pips)", DefaultValue = 50, MinValue = 10, MaxValue = 500)]
        public double TakeProfitPips { get; set; }
'''
            code = re.sub(class_pattern, r'\1' + insertion, code)
        
        # Update ExecuteMarketOrder calls
        code = re.sub(
            r'ExecuteMarketOrder\((TradeType\.\w+), (\w+), (\w+), (["\w]+), ([\w\.]+), null\)',
            r'ExecuteMarketOrder(\1, \2, \3, \4, \5, TakeProfitPips)',
            code
        )
        
        return code, True
    
    return code, False


def _inject_risk_management(code: str, risk_percent: float) -> tuple[str, bool]:
    """Inject risk-based position sizing"""
    
    if 'RiskPercent' not in code:
        # Add parameter
        param_pattern = r'(TakeProfitPips.*?\n)'
        if re.search(param_pattern, code):
            insertion = f'''
        [Parameter("Risk Per Trade (%)", DefaultValue = {risk_percent}, MinValue = 0.1, MaxValue = 5)]
        public double RiskPercent {{ get; set; }}
'''
            code = re.sub(param_pattern, r'\1' + insertion, code)
        
        # Add CalculateVolume method if not exists
        if 'CalculateVolume' not in code:
            # Find end of class (before last })
            method_code = '''
        
        private double CalculateVolume(double stopLossPips)
        {
            double riskAmount = Account.Balance * (RiskPercent / 100.0);
            double pipValue = Symbol.PipValue;
            double volume = riskAmount / (stopLossPips * pipValue);
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            volume = Math.Max(Symbol.VolumeInUnitsMin, volume);
            volume = Math.Min(Symbol.VolumeInUnitsMax, volume);
            return volume;
        }
'''
            # Insert before final }
            code = code.rstrip()
            if code.endswith('}'):
                code = code[:-1] + method_code + '\n    }\n'
        
        return code, True
    
    return code, False


def _inject_daily_loss_limit(code: str) -> tuple[str, bool]:
    """Inject daily loss tracking and limit"""
    
    if '_dailyLoss' not in code and 'dailyLoss' not in code.lower():
        # Add fields
        field_pattern = r'(private.*?;)\s*\n\s*(protected override void OnStart)'
        if re.search(field_pattern, code, re.DOTALL):
            insertion = '''
        private double _dailyLoss;
        private DateTime _lastDayCheck;
        private const double MAX_DAILY_LOSS_PERCENT = 5.0;
        
        '''
            code = re.sub(field_pattern, r'\1\n' + insertion + r'\2', code, flags=re.DOTALL)
        
        # Add initialization in OnStart
        onstart_pattern = r'(protected override void OnStart\(\)\s*\{)'
        if re.search(onstart_pattern, code):
            init_code = '''
            _dailyLoss = 0;
            _lastDayCheck = Server.Time.Date;
'''
            code = re.sub(onstart_pattern, r'\1\n' + init_code, code)
        
        # Add check in OnBar
        onbar_pattern = r'(protected override void OnBar\(\)\s*\{)'
        if re.search(onbar_pattern, code):
            check_code = '''
            // Reset daily loss counter
            if (Server.Time.Date != _lastDayCheck)
            {
                _dailyLoss = 0;
                _lastDayCheck = Server.Time.Date;
            }
            
            // Check daily loss limit
            if (_dailyLoss >= Account.Balance * (MAX_DAILY_LOSS_PERCENT / 100.0))
            {
                Print("Daily loss limit reached. Trading paused.");
                return;
            }
            
'''
            code = re.sub(onbar_pattern, r'\1\n' + check_code, code)
        
        # Add OnPositionClosed handler
        if 'OnPositionClosed' not in code:
            handler_code = '''
        
        protected override void OnPositionClosed(PositionClosedEventArgs args)
        {
            if (args.Position.NetProfit < 0)
            {
                _dailyLoss += Math.Abs(args.Position.NetProfit);
            }
        }
'''
            code = code.rstrip()
            if code.endswith('}'):
                code = code[:-1] + handler_code + '\n    }\n'
        
        return code, True
    
    return code, False


def _inject_drawdown_protection(code: str) -> tuple[str, bool]:
    """Inject max drawdown protection"""
    
    if '_maxDrawdown' not in code and 'maxdrawdown' not in code.lower():
        # Add fields
        field_pattern = r'(private.*?;)\s*\n\s*(protected override void OnStart)'
        if re.search(field_pattern, code, re.DOTALL):
            insertion = '''
        private double _peakBalance;
        private const double MAX_DRAWDOWN_PERCENT = 10.0;
        
        '''
            code = re.sub(field_pattern, r'\1\n' + insertion + r'\2', code, flags=re.DOTALL)
        
        # Add initialization
        onstart_pattern = r'(protected override void OnStart\(\)\s*\{)'
        if re.search(onstart_pattern, code):
            init_code = '''
            _peakBalance = Account.Balance;
'''
            code = re.sub(onstart_pattern, r'\1\n' + init_code, code)
        
        # Add check in OnBar
        onbar_pattern = r'(protected override void OnBar\(\)\s*\{)'
        if re.search(onbar_pattern, code):
            check_code = '''
            // Update peak balance
            if (Account.Balance > _peakBalance)
                _peakBalance = Account.Balance;
            
            // Check drawdown limit
            double currentDrawdown = (_peakBalance - Account.Balance) / _peakBalance * 100.0;
            if (currentDrawdown >= MAX_DRAWDOWN_PERCENT)
            {
                Print("Max drawdown reached: {0}%. Trading halted.", currentDrawdown);
                Stop();
                return;
            }
            
'''
            code = re.sub(onbar_pattern, r'\1\n' + check_code, code)
        
        return code, True
    
    return code, False


def _inject_spread_filter(code: str) -> tuple[str, bool]:
    """Inject spread filter"""
    
    if 'MaxSpreadPips' not in code:
        # Add parameter
        param_pattern = r'(// .*?PARAMETERS.*?\n)'
        if re.search(param_pattern, code, re.IGNORECASE):
            insertion = '''
        [Parameter("Max Spread (Pips)", DefaultValue = 3, MinValue = 0.5, MaxValue = 20)]
        public double MaxSpreadPips { get; set; }
'''
            code = re.sub(param_pattern, r'\1' + insertion, code, flags=re.IGNORECASE)
        
        # Add check in trading logic
        onbar_pattern = r'(protected override void OnBar\(\)\s*\{)'
        if re.search(onbar_pattern, code):
            check_code = '''
            // Spread filter
            double spreadPips = Symbol.Spread / Symbol.PipSize;
            if (spreadPips > MaxSpreadPips)
                return;
            
'''
            code = re.sub(onbar_pattern, r'\1\n' + check_code, code)
        
        return code, True
    
    return code, False


def _inject_session_filter(code: str) -> tuple[str, bool]:
    """Inject trading session filter"""
    
    if 'TradingStartHour' not in code:
        # Add parameters
        param_pattern = r'(// .*?PARAMETERS.*?\n)'
        if re.search(param_pattern, code, re.IGNORECASE):
            insertion = '''
        [Parameter("Trading Start Hour (UTC)", DefaultValue = 8, MinValue = 0, MaxValue = 23)]
        public int TradingStartHour { get; set; }
        
        [Parameter("Trading End Hour (UTC)", DefaultValue = 17, MinValue = 0, MaxValue = 23)]
        public int TradingEndHour { get; set; }
'''
            code = re.sub(param_pattern, r'\1' + insertion, code, flags=re.IGNORECASE)
        
        # Add check in trading logic
        onbar_pattern = r'(protected override void OnBar\(\)\s*\{)'
        if re.search(onbar_pattern, code):
            check_code = '''
            // Session filter
            int hour = Server.Time.Hour;
            if (hour < TradingStartHour || hour >= TradingEndHour)
                return;
            
'''
            code = re.sub(onbar_pattern, r'\1\n' + check_code, code)
        
        return code, True
    
    return code, False


def _inject_prop_firm_rules(code: str, prop_firm: str) -> tuple[str, List[str]]:
    """Inject prop firm specific rules"""
    
    changes = []
    prop_firm = prop_firm.lower()
    
    # Prop firm rule mappings
    RULES = {
        'ftmo': {
            'max_daily_loss': 5.0,
            'max_drawdown': 10.0,
            'max_risk': 1.0,
            'max_positions': 10
        },
        'fundednext': {
            'max_daily_loss': 5.0,
            'max_drawdown': 12.0,
            'max_risk': 2.0,
            'max_positions': 15
        },
        'pipfarm': {
            'max_daily_loss': 4.0,
            'max_drawdown': 8.0,
            'max_risk': 1.5,
            'max_positions': 8
        },
        'the5ers': {
            'max_daily_loss': 5.0,
            'max_drawdown': 10.0,
            'max_risk': 1.0,
            'max_positions': 12
        }
    }
    
    if prop_firm in RULES:
        rules = RULES[prop_firm]
        
        # Update risk percent max
        code = re.sub(
            r'RiskPercent.*?MaxValue = [\d\.]+',
            f'RiskPercent.*?MaxValue = {rules["max_risk"]}',
            code
        )
        changes.append(f"Applied {prop_firm.upper()} max risk limit: {rules['max_risk']}%")
        
        # Update daily loss
        code = re.sub(
            r'MAX_DAILY_LOSS_PERCENT = [\d\.]+',
            f'MAX_DAILY_LOSS_PERCENT = {rules["max_daily_loss"]}',
            code
        )
        changes.append(f"Applied {prop_firm.upper()} daily loss limit: {rules['max_daily_loss']}%")
        
        # Update drawdown
        code = re.sub(
            r'MAX_DRAWDOWN_PERCENT = [\d\.]+',
            f'MAX_DRAWDOWN_PERCENT = {rules["max_drawdown"]}',
            code
        )
        changes.append(f"Applied {prop_firm.upper()} max drawdown: {rules['max_drawdown']}%")
    
    return code, changes
