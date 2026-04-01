"""
Prop Firm Compliance Engine
Validates cTrader bots against prop firm trading rules
"""

import re
from typing import Dict, List, Optional
from pydantic import BaseModel


class PropFirmRules(BaseModel):
    """Prop firm trading rules"""
    name: str
    max_daily_loss: float  # in percentage
    max_total_drawdown: float  # in percentage
    max_risk_per_trade: float  # in percentage
    max_open_trades: int
    spread_limit: Optional[float] = None  # in pips
    allowed_trading_sessions: List[str]  # e.g., ["London", "NewYork", "Asian"]
    stop_loss_required: bool
    take_profit_recommended: bool
    max_lot_size: Optional[float] = None
    min_stop_loss_distance: Optional[int] = None  # in pips
    news_trading_restricted: bool = False
    weekend_trading_allowed: bool = False
    description: str = ""


# Predefined prop firm profiles
PROP_FIRM_PROFILES = {
    "ftmo": PropFirmRules(
        name="FTMO",
        max_daily_loss=5.0,
        max_total_drawdown=10.0,
        max_risk_per_trade=2.0,
        max_open_trades=10,
        spread_limit=None,
        allowed_trading_sessions=["London", "NewYork", "Asian"],
        stop_loss_required=True,
        take_profit_recommended=True,
        max_lot_size=None,
        min_stop_loss_distance=10,
        news_trading_restricted=False,
        weekend_trading_allowed=False,
        description="FTMO challenge rules - 5% daily loss, 10% max drawdown"
    ),
    "pipfarm": PropFirmRules(
        name="PipFarm",
        max_daily_loss=4.0,
        max_total_drawdown=8.0,
        max_risk_per_trade=1.5,
        max_open_trades=5,
        spread_limit=3.0,
        allowed_trading_sessions=["London", "NewYork"],
        stop_loss_required=True,
        take_profit_recommended=True,
        max_lot_size=5.0,
        min_stop_loss_distance=15,
        news_trading_restricted=True,
        weekend_trading_allowed=False,
        description="PipFarm rules - conservative 4% daily loss, spread limit 3 pips"
    ),
    "fundednext": PropFirmRules(
        name="FundedNext",
        max_daily_loss=5.0,
        max_total_drawdown=12.0,
        max_risk_per_trade=2.0,
        max_open_trades=15,
        spread_limit=None,
        allowed_trading_sessions=["London", "NewYork", "Asian"],
        stop_loss_required=True,
        take_profit_recommended=False,
        max_lot_size=None,
        min_stop_loss_distance=10,
        news_trading_restricted=False,
        weekend_trading_allowed=False,
        description="FundedNext rules - 5% daily loss, 12% max drawdown, flexible trading"
    ),
    "the5ers": PropFirmRules(
        name="The5ers",
        max_daily_loss=4.0,
        max_total_drawdown=6.0,
        max_risk_per_trade=1.0,
        max_open_trades=8,
        spread_limit=2.5,
        allowed_trading_sessions=["London", "NewYork"],
        stop_loss_required=True,
        take_profit_recommended=True,
        max_lot_size=3.0,
        min_stop_loss_distance=20,
        news_trading_restricted=True,
        weekend_trading_allowed=False,
        description="The5ers rules - strict 4% daily, 6% max DD, 1% risk per trade"
    ),
    "none": PropFirmRules(
        name="No Prop Firm (Personal Trading)",
        max_daily_loss=100.0,
        max_total_drawdown=100.0,
        max_risk_per_trade=100.0,
        max_open_trades=999,
        spread_limit=None,
        allowed_trading_sessions=["London", "NewYork", "Asian", "Pacific"],
        stop_loss_required=False,
        take_profit_recommended=False,
        max_lot_size=None,
        min_stop_loss_distance=None,
        news_trading_restricted=False,
        weekend_trading_allowed=True,
        description="No restrictions - personal trading account"
    )
}


class ComplianceViolation(BaseModel):
    """Represents a compliance rule violation"""
    rule: str
    severity: str  # "critical", "high", "medium", "low"
    message: str
    line_number: Optional[int] = None
    recommendation: str


class ComplianceResult(BaseModel):
    """Compliance validation result"""
    is_compliant: bool
    compliance_score: float  # 0-100
    violations: List[ComplianceViolation]
    prop_firm: str
    summary: str


class PropFirmComplianceEngine:
    """Validates cBot code against prop firm rules"""
    
    def __init__(self, prop_firm: str = "ftmo"):
        if prop_firm.lower() not in PROP_FIRM_PROFILES:
            raise ValueError(f"Unknown prop firm: {prop_firm}. Available: {list(PROP_FIRM_PROFILES.keys())}")
        
        self.rules = PROP_FIRM_PROFILES[prop_firm.lower()]
        self.violations = []
    
    def validate(self, code: str) -> ComplianceResult:
        """
        Validate cBot code against prop firm rules
        Returns ComplianceResult with violations and score
        """
        self.violations = []
        
        # Check all compliance rules
        self._check_stop_loss(code)
        self._check_take_profit(code)
        self._check_risk_management(code)
        self._check_position_limits(code)
        self._check_lot_size(code)
        self._check_drawdown_monitoring(code)
        self._check_trading_sessions(code)
        self._check_spread_limit(code)
        self._check_news_trading(code)
        
        # Calculate compliance score
        total_checks = 9
        critical_violations = len([v for v in self.violations if v.severity == "critical"])
        high_violations = len([v for v in self.violations if v.severity == "high"])
        medium_violations = len([v for v in self.violations if v.severity == "medium"])
        low_violations = len([v for v in self.violations if v.severity == "low"])
        
        # Weighted scoring
        score = 100.0
        score -= critical_violations * 25  # Critical: -25 points each
        score -= high_violations * 15      # High: -15 points each
        score -= medium_violations * 8     # Medium: -8 points each
        score -= low_violations * 3        # Low: -3 points each
        
        score = max(0.0, score)
        
        is_compliant = critical_violations == 0 and high_violations == 0
        
        # Generate summary
        if is_compliant:
            summary = f"✓ Bot is compliant with {self.rules.name} rules (Score: {score:.1f}/100)"
        else:
            summary = f"✗ Bot violates {self.rules.name} rules - {critical_violations} critical, {high_violations} high priority issues"
        
        return ComplianceResult(
            is_compliant=is_compliant,
            compliance_score=score,
            violations=self.violations,
            prop_firm=self.rules.name,
            summary=summary
        )
    
    def _check_stop_loss(self, code: str):
        """Check if stop loss is implemented"""
        if not self.rules.stop_loss_required:
            return
        
        has_stop_loss = any([
            'StopLoss' in code,
            'stopLoss' in code,
            'stop_loss' in code,
            'SetStopLoss' in code,
            'ModifyStopLoss' in code
        ])
        
        if not has_stop_loss:
            self.violations.append(ComplianceViolation(
                rule="Stop Loss Required",
                severity="critical",
                message=f"{self.rules.name} requires all trades to have a stop loss",
                recommendation="Add StopLoss parameter to ExecuteMarketOrder() or use ModifyPosition() to set stop loss"
            ))
        
        # Check for minimum stop loss distance
        if self.rules.min_stop_loss_distance and has_stop_loss:
            # Look for stop loss values
            sl_patterns = [
                r'StopLoss\s*=\s*(\d+)',
                r'stopLoss:\s*(\d+)',
                r'Symbol\.PipSize\s*\*\s*(\d+)'
            ]
            
            for pattern in sl_patterns:
                matches = re.findall(pattern, code)
                for match in matches:
                    sl_value = int(match)
                    if sl_value < self.rules.min_stop_loss_distance:
                        self.violations.append(ComplianceViolation(
                            rule="Minimum Stop Loss Distance",
                            severity="high",
                            message=f"Stop loss of {sl_value} pips is below minimum of {self.rules.min_stop_loss_distance} pips",
                            recommendation=f"Increase stop loss to at least {self.rules.min_stop_loss_distance} pips"
                        ))
                        break
    
    def _check_take_profit(self, code: str):
        """Check if take profit is implemented"""
        if not self.rules.take_profit_recommended:
            return
        
        has_take_profit = any([
            'TakeProfit' in code,
            'takeProfit' in code,
            'take_profit' in code,
            'SetTakeProfit' in code
        ])
        
        if not has_take_profit:
            self.violations.append(ComplianceViolation(
                rule="Take Profit Recommended",
                severity="medium",
                message=f"{self.rules.name} recommends setting take profit levels",
                recommendation="Add TakeProfit parameter to ExecuteMarketOrder() for better trade management"
            ))
    
    def _check_risk_management(self, code: str):
        """Check risk management implementation"""
        
        # Check for account balance usage
        has_balance_check = any([
            'Account.Balance' in code,
            'Account.Equity' in code,
            'AccountBalance' in code
        ])
        
        if not has_balance_check:
            self.violations.append(ComplianceViolation(
                rule="Risk Management",
                severity="high",
                message="No account balance monitoring detected",
                recommendation="Use Account.Balance or Account.Equity to calculate position sizes and risk"
            ))
        
        # Check for risk percentage calculation
        risk_keywords = ['risk', 'Risk', 'riskPercent', 'RiskPerTrade']
        has_risk_calc = any(keyword in code for keyword in risk_keywords)
        
        if not has_risk_calc:
            self.violations.append(ComplianceViolation(
                rule=f"Risk Per Trade ({self.rules.max_risk_per_trade}% max)",
                severity="critical",
                message=f"No risk per trade calculation found. {self.rules.name} limits risk to {self.rules.max_risk_per_trade}% per trade",
                recommendation=f"Implement risk calculation: double riskAmount = Account.Balance * {self.rules.max_risk_per_trade / 100};"
            ))
    
    def _check_position_limits(self, code: str):
        """Check position/trade limits"""
        
        has_position_count_check = any([
            'Positions.Count' in code,
            'Positions.Length' in code,
            'OpenPositions' in code
        ])
        
        if not has_position_count_check:
            self.violations.append(ComplianceViolation(
                rule=f"Max Open Trades ({self.rules.max_open_trades})",
                severity="high",
                message=f"{self.rules.name} limits open positions to {self.rules.max_open_trades}. No position count check detected",
                recommendation=f"Add check: if (Positions.Count >= {self.rules.max_open_trades}) return;"
            ))
    
    def _check_lot_size(self, code: str):
        """Check lot size limits"""
        if not self.rules.max_lot_size:
            return
        
        # Look for volume/lot size
        volume_pattern = r'volume\s*[=:]\s*(\d+\.?\d*)'
        matches = re.findall(volume_pattern, code, re.IGNORECASE)
        
        for match in matches:
            try:
                lot_size = float(match)
                if lot_size > self.rules.max_lot_size:
                    self.violations.append(ComplianceViolation(
                        rule=f"Max Lot Size ({self.rules.max_lot_size})",
                        severity="critical",
                        message=f"Lot size {lot_size} exceeds maximum of {self.rules.max_lot_size}",
                        recommendation=f"Reduce lot size to maximum {self.rules.max_lot_size} or implement dynamic sizing"
                    ))
            except ValueError:
                pass
    
    def _check_drawdown_monitoring(self, code: str):
        """Check daily loss and drawdown monitoring"""
        
        has_daily_loss_check = any([
            'dailyLoss' in code,
            'DailyLoss' in code,
            'daily_loss' in code,
            'DailyPnL' in code
        ])
        
        has_drawdown_check = any([
            'drawdown' in code,
            'Drawdown' in code,
            'maxDrawdown' in code,
            'MaxDrawdown' in code
        ])
        
        if not has_daily_loss_check:
            self.violations.append(ComplianceViolation(
                rule=f"Daily Loss Limit ({self.rules.max_daily_loss}%)",
                severity="critical",
                message=f"{self.rules.name} requires daily loss monitoring (max {self.rules.max_daily_loss}%)",
                recommendation=f"Implement daily P&L tracking and stop trading if loss exceeds {self.rules.max_daily_loss}%"
            ))
        
        if not has_drawdown_check:
            self.violations.append(ComplianceViolation(
                rule=f"Max Drawdown ({self.rules.max_total_drawdown}%)",
                severity="critical",
                message=f"{self.rules.name} requires drawdown monitoring (max {self.rules.max_total_drawdown}%)",
                recommendation=f"Track total drawdown and stop bot if it exceeds {self.rules.max_total_drawdown}%"
            ))
    
    def _check_trading_sessions(self, code: str):
        """Check trading session restrictions"""
        if len(self.rules.allowed_trading_sessions) >= 4:  # No restrictions
            return
        
        has_time_filter = any([
            'Server.Time' in code,
            'ServerTime' in code,
            'TimeFilter' in code,
            'TradingHours' in code,
            '.Hour' in code
        ])
        
        if not has_time_filter:
            self.violations.append(ComplianceViolation(
                rule="Trading Session Restrictions",
                severity="medium",
                message=f"{self.rules.name} recommends trading during: {', '.join(self.rules.allowed_trading_sessions)}",
                recommendation="Add time filter using Server.Time.Hour to trade only during optimal sessions"
            ))
    
    def _check_spread_limit(self, code: str):
        """Check spread limit"""
        if not self.rules.spread_limit:
            return
        
        has_spread_check = any([
            'Symbol.Spread' in code,
            'spread' in code.lower(),
            'Spread' in code
        ])
        
        if not has_spread_check:
            self.violations.append(ComplianceViolation(
                rule=f"Spread Limit ({self.rules.spread_limit} pips)",
                severity="high",
                message=f"{self.rules.name} requires spread checking (max {self.rules.spread_limit} pips)",
                recommendation=f"Add check: if (Symbol.Spread / Symbol.PipSize > {self.rules.spread_limit}) return;"
            ))
    
    def _check_news_trading(self, code: str):
        """Check news trading restrictions"""
        if not self.rules.news_trading_restricted:
            return
        
        has_news_filter = any([
            'news' in code.lower(),
            'calendar' in code.lower(),
            'economic' in code.lower(),
            'NewsFilter' in code
        ])
        
        if not has_news_filter:
            self.violations.append(ComplianceViolation(
                rule="News Trading Restricted",
                severity="medium",
                message=f"{self.rules.name} restricts trading during high-impact news",
                recommendation="Implement news filter to avoid trading 30 min before/after major economic events"
            ))


def get_compliance_engine(prop_firm: str) -> PropFirmComplianceEngine:
    """Factory function to create compliance engine"""
    return PropFirmComplianceEngine(prop_firm)


def get_prop_firm_profiles() -> Dict[str, PropFirmRules]:
    """Get all available prop firm profiles"""
    return PROP_FIRM_PROFILES
