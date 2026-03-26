"""
Safety Code Injection Engine
Phase 8: Automatic Safety Feature Injection for cTrader Bots

Injects safety features into generated bot code:
1. Daily loss limit monitoring
2. Max drawdown protection
3. Position limit enforcement
4. Risk per trade calculation
5. Spread filter
6. Session filter
7. Stop loss enforcement
"""

import re
import uuid
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SafetyConfig(BaseModel):
    """Configuration for safety code injection"""
    # Daily loss limit (percentage)
    max_daily_loss_percent: float = 5.0
    
    # Max drawdown (percentage)
    max_drawdown_percent: float = 10.0
    
    # Position limits
    max_open_positions: int = 10
    
    # Risk per trade (percentage)
    max_risk_per_trade_percent: float = 2.0
    
    # Stop loss (pips)
    default_stop_loss_pips: int = 20
    min_stop_loss_pips: int = 10
    
    # Take profit (pips)
    default_take_profit_pips: int = 40
    
    # Spread filter (pips)
    max_spread_pips: float = 3.0
    
    # Session filter
    trading_start_hour: int = 8  # UTC
    trading_end_hour: int = 20   # UTC
    
    # Prop firm profile
    prop_firm: str = "none"
    
    # API Logging Configuration
    enable_api_logging: bool = True
    api_base_url: str = ""  # Will be set from environment
    bot_id: str = ""  # Unique bot identifier
    bot_name: str = "PropBot"  # Human readable name
    strategy_type: str = "EMA Crossover"  # Strategy description
    execution_mode: str = "forward_test"  # backtest, forward_test, live
    max_trades_per_day: int = 5


class InjectionResult(BaseModel):
    """Result of safety code injection"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    success: bool = False
    original_code: str = ""
    modified_code: str = ""
    
    injections_applied: List[str] = []
    injections_skipped: List[str] = []
    
    config_used: Optional[SafetyConfig] = None
    message: str = ""


class SafetyInjector:
    """
    Injects safety code into cTrader bots
    
    Automatically adds risk management features while preserving
    the original trading logic.
    """
    
    # Safety code templates
    DAILY_LOSS_TEMPLATE = '''
        // ===== DAILY LOSS PROTECTION (Auto-Injected) =====
        private double _initialDailyBalance;
        private DateTime _lastTradingDay;
        private bool _dailyLossLimitReached = false;
        
        private void CheckDailyLossLimit()
        {{
            var today = Server.Time.Date;
            if (_lastTradingDay != today)
            {{
                _initialDailyBalance = Account.Balance;
                _lastTradingDay = today;
                _dailyLossLimitReached = false;
            }}
            
            double dailyLoss = (_initialDailyBalance - Account.Balance) / _initialDailyBalance * 100;
            if (dailyLoss >= {max_daily_loss})
            {{
                _dailyLossLimitReached = true;
                Print("Daily loss limit reached: " + dailyLoss.ToString("F2") + "%");
            }}
        }}
        // ===== END DAILY LOSS PROTECTION =====
'''
    
    DRAWDOWN_TEMPLATE = '''
        // ===== DRAWDOWN PROTECTION (Auto-Injected) =====
        private double _peakEquity;
        private bool _maxDrawdownReached = false;
        
        private void CheckDrawdownLimit()
        {{
            if (Account.Equity > _peakEquity)
                _peakEquity = Account.Equity;
            
            double drawdown = (_peakEquity - Account.Equity) / _peakEquity * 100;
            if (drawdown >= {max_drawdown})
            {{
                _maxDrawdownReached = true;
                Print("Max drawdown limit reached: " + drawdown.ToString("F2") + "%");
            }}
        }}
        // ===== END DRAWDOWN PROTECTION =====
'''
    
    POSITION_LIMIT_TEMPLATE = '''
        // ===== POSITION LIMIT CHECK (Auto-Injected) =====
        private bool CanOpenNewPosition()
        {{
            if (Positions.Count >= {max_positions})
            {{
                Print($"Position limit reached: {{Positions.Count}}/{max_positions}");
                return false;
            }}
            return true;
        }}
        // ===== END POSITION LIMIT CHECK =====
'''
    
    RISK_CALCULATION_TEMPLATE = '''
        // ===== RISK CALCULATION (Auto-Injected) =====
        private double CalculateVolume(double stopLossPips)
        {{
            double riskAmount = Account.Balance * {risk_percent} / 100;
            double pipValue = Symbol.PipValue;
            double volume = riskAmount / (stopLossPips * pipValue);
            
            volume = Math.Max(Symbol.VolumeInUnitsMin, volume);
            volume = Math.Min(Symbol.VolumeInUnitsMax, volume);
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            
            return volume;
        }}
        // ===== END RISK CALCULATION =====
'''
    
    SPREAD_FILTER_TEMPLATE = '''
        // ===== SPREAD FILTER (Auto-Injected) =====
        private bool IsSpreadAcceptable()
        {{
            double spreadPips = Symbol.Spread / Symbol.PipSize;
            if (spreadPips > {max_spread})
            {{
                Print("Spread too high: " + spreadPips.ToString("F1") + " pips");
                return false;
            }}
            return true;
        }}
        // ===== END SPREAD FILTER =====
'''
    
    SESSION_FILTER_TEMPLATE = '''
        // ===== SESSION FILTER (Auto-Injected) =====
        private bool IsWithinTradingSession()
        {{
            int hour = Server.Time.Hour;
            if (hour < {start_hour} || hour >= {end_hour})
            {{
                return false;
            }}
            return true;
        }}
        // ===== END SESSION FILTER =====
'''
    
    SAFETY_CHECK_TEMPLATE = '''
        // ===== SAFETY CHECKS (Auto-Injected) =====
        private bool PassesAllSafetyChecks()
        {{
            CheckDailyLossLimit();
            CheckDrawdownLimit();
            
            if (_dailyLossLimitReached)
            {{
                Print("Trading halted: Daily loss limit reached");
                return false;
            }}
            
            if (_maxDrawdownReached)
            {{
                Print("Trading halted: Max drawdown reached");
                return false;
            }}
            
            if (!CanOpenNewPosition())
                return false;
            
            if (!IsSpreadAcceptable())
                return false;
            
            if (!IsWithinTradingSession())
                return false;
            
            return true;
        }}
        // ===== END SAFETY CHECKS =====
'''
    
    ONSTART_INIT_TEMPLATE = '''
            // ===== SAFETY INITIALIZATION (Auto-Injected) =====
            _initialDailyBalance = Account.Balance;
            _lastTradingDay = Server.Time.Date;
            _peakEquity = Account.Equity;
            // ===== END SAFETY INITIALIZATION =====
'''
    
    ONSTART_INIT_WITH_API_TEMPLATE = '''
            // ===== SAFETY INITIALIZATION (Auto-Injected) =====
            _initialDailyBalance = Account.Balance;
            _lastTradingDay = Server.Time.Date;
            _peakEquity = Account.Equity;
            RegisterBot();
            StartHeartbeat();
            // ===== END SAFETY INITIALIZATION =====
'''
    
    # API Logging Templates for real-time trade tracking
    API_LOGGING_FIELDS_TEMPLATE = '''
        // ===== API LOGGING FIELDS (Auto-Injected) =====
        private string _botId = "{bot_id}";
        private string _botName = "{bot_name}";
        private string _apiBaseUrl = "{api_url}";
        private string _executionMode = "{mode}"; // backtest, forward_test, live
        private System.Net.Http.HttpClient _httpClient = new System.Net.Http.HttpClient();
        private System.Threading.Timer _heartbeatTimer;
        // ===== END API LOGGING FIELDS =====
'''
    
    API_BOT_REGISTRATION_TEMPLATE = '''
        // ===== BOT REGISTRATION (Auto-Injected) =====
        private void RegisterBot()
        {{
            try
            {{
                var payload = new {{
                    bot_id = _botId,
                    bot_name = _botName,
                    symbol = Symbol.Name,
                    timeframe = TimeFrame.ToString(),
                    strategy_type = "{strategy_type}",
                    initial_balance = Account.Balance,
                    risk_config = new {{
                        maxDailyDrawdown = {max_daily_dd},
                        maxTotalDrawdown = {max_total_dd},
                        maxTradesPerDay = {max_trades}
                    }},
                    mode = _executionMode
                }};
                
                var json = Newtonsoft.Json.JsonConvert.SerializeObject(payload);
                var content = new System.Net.Http.StringContent(json, System.Text.Encoding.UTF8, "application/json");
                
                var task = _httpClient.PostAsync(_apiBaseUrl + "/api/bots/register", content);
                task.Wait(5000); // 5 second timeout
                Print("Bot registered with tracking system");
            }}
            catch (Exception ex)
            {{
                Print("Warning: Could not register bot - " + ex.Message);
            }}
        }}
        // ===== END BOT REGISTRATION =====
'''
    
    API_HEARTBEAT_TEMPLATE = '''
        // ===== HEARTBEAT SYSTEM (Auto-Injected) =====
        private int _tradesToday = 0;
        private DateTime _lastTradeTime = DateTime.MinValue;
        
        private void StartHeartbeat()
        {{
            _heartbeatTimer = new System.Threading.Timer(_ => SendHeartbeat(), null, 10000, 15000);
        }}
        
        private void SendHeartbeat()
        {{
            try
            {{
                double dailyPnl = Account.Balance - _initialDailyBalance;
                double dailyPnlPercent = (dailyPnl / _initialDailyBalance) * 100;
                double totalPnl = Account.Equity - _peakEquity;
                double totalPnlPercent = (totalPnl / _peakEquity) * 100;
                double currentDrawdown = (_peakEquity - Account.Equity) / _peakEquity * 100;
                
                string status = "RUNNING";
                if (_dailyLossLimitReached || _maxDrawdownReached) status = "STOPPED";
                else if (currentDrawdown >= {max_daily_dd} * 0.8) status = "WARNING";
                
                var payload = new {{
                    bot_id = _botId,
                    status = status,
                    current_balance = Account.Balance,
                    daily_pnl = dailyPnl,
                    daily_pnl_percent = dailyPnlPercent,
                    total_pnl = totalPnl,
                    total_pnl_percent = totalPnlPercent,
                    current_drawdown = Math.Max(0, currentDrawdown),
                    max_drawdown_reached = Math.Max(0, (_peakEquity - Account.Equity) / _peakEquity * 100),
                    trades_today = _tradesToday,
                    open_trades = Positions.Count,
                    win_rate = CalculateWinRate(),
                    last_trade_time = _lastTradeTime == DateTime.MinValue ? null : _lastTradeTime.ToString("o")
                }};
                
                var json = Newtonsoft.Json.JsonConvert.SerializeObject(payload);
                var content = new System.Net.Http.StringContent(json, System.Text.Encoding.UTF8, "application/json");
                
                _httpClient.PostAsync(_apiBaseUrl + "/api/bots/heartbeat", content);
            }}
            catch {{ /* Non-blocking - don't crash bot if API fails */ }}
        }}
        
        private double CalculateWinRate()
        {{
            var history = History.Where(h => h.ClosingTime.Date == Server.Time.Date).ToList();
            if (history.Count == 0) return 0;
            int wins = history.Count(h => h.NetProfit > 0);
            return (double)wins / history.Count * 100;
        }}
        // ===== END HEARTBEAT SYSTEM =====
'''
    
    API_TRADE_LOGGING_TEMPLATE = '''
        // ===== TRADE LOGGING (Auto-Injected) =====
        private void LogTradeOpen(Position position, string reason)
        {{
            try
            {{
                _tradesToday++;
                _lastTradeTime = Server.Time;
                
                var payload = new {{
                    bot_id = _botId,
                    bot_name = _botName,
                    symbol = position.SymbolName,
                    direction = position.TradeType.ToString().ToUpper(),
                    lot_size = position.VolumeInUnits / 100000.0,
                    entry_price = position.EntryPrice,
                    stop_loss = position.StopLoss ?? 0,
                    take_profit = position.TakeProfit ?? 0,
                    reason = reason,
                    mode = _executionMode,
                    result = "OPEN"
                }};
                
                var json = Newtonsoft.Json.JsonConvert.SerializeObject(payload);
                var content = new System.Net.Http.StringContent(json, System.Text.Encoding.UTF8, "application/json");
                
                _httpClient.PostAsync(_apiBaseUrl + "/api/trades/log", content);
                Print($"Trade logged: {{position.TradeType}} {{position.SymbolName}}");
            }}
            catch {{ /* Non-blocking */ }}
        }}
        
        private void LogTradeClose(Position position, string closeReason)
        {{
            try
            {{
                double pips = position.TradeType == TradeType.Buy 
                    ? (position.CurrentPrice - position.EntryPrice) / Symbol.PipSize
                    : (position.EntryPrice - position.CurrentPrice) / Symbol.PipSize;
                
                string result = position.NetProfit > 0 ? "WIN" : position.NetProfit < 0 ? "LOSS" : "BREAKEVEN";
                
                var payload = new {{
                    bot_id = _botId,
                    bot_name = _botName,
                    symbol = position.SymbolName,
                    direction = position.TradeType.ToString().ToUpper(),
                    lot_size = position.VolumeInUnits / 100000.0,
                    entry_price = position.EntryPrice,
                    exit_price = position.CurrentPrice,
                    stop_loss = position.StopLoss ?? 0,
                    take_profit = position.TakeProfit ?? 0,
                    pnl = position.NetProfit,
                    pips = pips,
                    result = result,
                    reason = "Entry signal",
                    close_reason = closeReason,
                    mode = _executionMode
                }};
                
                var json = Newtonsoft.Json.JsonConvert.SerializeObject(payload);
                var content = new System.Net.Http.StringContent(json, System.Text.Encoding.UTF8, "application/json");
                
                _httpClient.PostAsync(_apiBaseUrl + "/api/trades/log", content);
                Print($"Trade closed: {{result}} {{position.NetProfit:F2}}");
            }}
            catch {{ /* Non-blocking */ }}
        }}
        // ===== END TRADE LOGGING =====
'''
    
    API_POSITION_EVENTS_TEMPLATE = '''
        // ===== POSITION EVENT HANDLERS (Auto-Injected) =====
        protected override void OnPositionOpened(PositionOpenedEventArgs args)
        {{
            if (args.Position.Label == _botId || args.Position.SymbolName == Symbol.Name)
            {{
                LogTradeOpen(args.Position, "Signal triggered");
            }}
        }}
        
        protected override void OnPositionClosed(PositionClosedEventArgs args)
        {{
            if (args.Position.Label == _botId || args.Position.SymbolName == Symbol.Name)
            {{
                string reason = "Manual close";
                if (args.Reason == PositionCloseReason.StopLoss) reason = "Stop loss hit";
                else if (args.Reason == PositionCloseReason.TakeProfit) reason = "Take profit hit";
                else if (args.Reason == PositionCloseReason.StopOut) reason = "Stop out";
                
                LogTradeClose(args.Position, reason);
            }}
        }}
        // ===== END POSITION EVENT HANDLERS =====
'''
    
    API_CLEANUP_TEMPLATE = '''
        // ===== CLEANUP (Auto-Injected) =====
        protected override void OnStop()
        {{
            _heartbeatTimer?.Dispose();
            _httpClient?.Dispose();
        }}
        // ===== END CLEANUP =====
'''
    
    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or SafetyConfig()
        
        # Load prop firm config if specified
        if self.config.prop_firm and self.config.prop_firm != "none":
            self._load_prop_firm_config()
    
    def _load_prop_firm_config(self):
        """Load safety config from prop firm profile"""
        try:
            from compliance_engine import PROP_FIRM_PROFILES
            
            rules = PROP_FIRM_PROFILES.get(self.config.prop_firm.lower())
            if rules:
                self.config.max_daily_loss_percent = rules.max_daily_loss
                self.config.max_drawdown_percent = rules.max_total_drawdown
                self.config.max_open_positions = rules.max_open_trades
                self.config.max_risk_per_trade_percent = rules.max_risk_per_trade
                if rules.min_stop_loss_distance:
                    self.config.min_stop_loss_pips = rules.min_stop_loss_distance
                if rules.spread_limit:
                    self.config.max_spread_pips = rules.spread_limit
                    
                logger.info(f"Loaded {rules.name} prop firm safety config")
                
        except Exception as e:
            logger.warning(f"Could not load prop firm config: {str(e)}")
    
    def inject_safety_code(self, code: str) -> InjectionResult:
        """
        Inject all safety features into bot code
        
        Returns InjectionResult with modified code and injection details
        """
        result = InjectionResult(
            original_code=code,
            config_used=self.config
        )
        
        try:
            modified_code = code
            injections_applied = []
            injections_skipped = []
            
            # Find the class body insertion point (after class declaration)
            class_match = re.search(r'class\s+\w+\s*:\s*Robot\s*{', modified_code)
            if not class_match:
                result.success = False
                result.message = "Could not find Robot class declaration"
                return result
            
            class_body_start = class_match.end()
            
            # Prepare safety code blocks
            safety_blocks = []
            
            # 1. Daily Loss Protection
            if not self._has_daily_loss_protection(code):
                block = self.DAILY_LOSS_TEMPLATE.format(
                    max_daily_loss=self.config.max_daily_loss_percent
                )
                safety_blocks.append(block)
                injections_applied.append(f"Daily Loss Limit ({self.config.max_daily_loss_percent}%)")
            else:
                injections_skipped.append("Daily Loss Limit (already present)")
            
            # 2. Drawdown Protection
            if not self._has_drawdown_protection(code):
                block = self.DRAWDOWN_TEMPLATE.format(
                    max_drawdown=self.config.max_drawdown_percent
                )
                safety_blocks.append(block)
                injections_applied.append(f"Drawdown Protection ({self.config.max_drawdown_percent}%)")
            else:
                injections_skipped.append("Drawdown Protection (already present)")
            
            # 3. Position Limit
            if not self._has_position_limit(code):
                block = self.POSITION_LIMIT_TEMPLATE.format(
                    max_positions=self.config.max_open_positions
                )
                safety_blocks.append(block)
                injections_applied.append(f"Position Limit ({self.config.max_open_positions})")
            else:
                injections_skipped.append("Position Limit (already present)")
            
            # 4. Risk Calculation
            if not self._has_risk_calculation(code):
                block = self.RISK_CALCULATION_TEMPLATE.format(
                    risk_percent=self.config.max_risk_per_trade_percent
                )
                safety_blocks.append(block)
                injections_applied.append(f"Risk Per Trade ({self.config.max_risk_per_trade_percent}%)")
            else:
                injections_skipped.append("Risk Calculation (already present)")
            
            # 5. Spread Filter
            if not self._has_spread_filter(code):
                block = self.SPREAD_FILTER_TEMPLATE.format(
                    max_spread=self.config.max_spread_pips
                )
                safety_blocks.append(block)
                injections_applied.append(f"Spread Filter ({self.config.max_spread_pips} pips)")
            else:
                injections_skipped.append("Spread Filter (already present)")
            
            # 6. Session Filter
            if not self._has_session_filter(code):
                block = self.SESSION_FILTER_TEMPLATE.format(
                    start_hour=self.config.trading_start_hour,
                    end_hour=self.config.trading_end_hour
                )
                safety_blocks.append(block)
                injections_applied.append(f"Session Filter ({self.config.trading_start_hour}:00-{self.config.trading_end_hour}:00 UTC)")
            else:
                injections_skipped.append("Session Filter (already present)")
            
            # 7. Master Safety Check Function
            if safety_blocks:
                safety_blocks.append(self.SAFETY_CHECK_TEMPLATE)
                injections_applied.append("Master Safety Check")
            
            # 8. API Logging (if enabled)
            if self.config.enable_api_logging and self.config.api_base_url:
                # Generate bot_id if not provided
                bot_id = self.config.bot_id or f"bot_{uuid.uuid4().hex[:8]}"
                
                # Add API logging fields
                api_fields = self.API_LOGGING_FIELDS_TEMPLATE.format(
                    bot_id=bot_id,
                    bot_name=self.config.bot_name,
                    api_url=self.config.api_base_url,
                    mode=self.config.execution_mode
                )
                safety_blocks.append(api_fields)
                
                # Add bot registration
                api_register = self.API_BOT_REGISTRATION_TEMPLATE.format(
                    strategy_type=self.config.strategy_type,
                    max_daily_dd=self.config.max_daily_loss_percent,
                    max_total_dd=self.config.max_drawdown_percent,
                    max_trades=self.config.max_trades_per_day
                )
                safety_blocks.append(api_register)
                
                # Add heartbeat system
                api_heartbeat = self.API_HEARTBEAT_TEMPLATE.format(
                    max_daily_dd=self.config.max_daily_loss_percent
                )
                safety_blocks.append(api_heartbeat)
                
                # Add trade logging
                safety_blocks.append(self.API_TRADE_LOGGING_TEMPLATE)
                
                # Add position event handlers
                safety_blocks.append(self.API_POSITION_EVENTS_TEMPLATE)
                
                # Add cleanup
                safety_blocks.append(self.API_CLEANUP_TEMPLATE)
                
                injections_applied.append(f"API Logging ({self.config.execution_mode} mode)")
                injections_applied.append("Trade Logging")
                injections_applied.append("Heartbeat System (15s)")
                injections_applied.append("Position Event Handlers")
            
            # Insert safety blocks after class opening
            if safety_blocks:
                safety_code = '\n'.join(safety_blocks)
                modified_code = (
                    modified_code[:class_body_start] +
                    '\n' + safety_code +
                    modified_code[class_body_start:]
                )
            
            # Inject initialization in OnStart
            modified_code = self._inject_onstart_init(modified_code)
            if "_initialDailyBalance" in modified_code:
                injections_applied.append("OnStart Initialization")
            
            # Inject safety check calls in trading methods
            modified_code = self._inject_safety_checks(modified_code)
            
            result.success = True
            result.modified_code = modified_code
            result.injections_applied = injections_applied
            result.injections_skipped = injections_skipped
            result.message = f"Successfully injected {len(injections_applied)} safety features"
            
            logger.info(f"Safety injection complete: {len(injections_applied)} applied, {len(injections_skipped)} skipped")
            
        except Exception as e:
            logger.error(f"Safety injection error: {str(e)}")
            result.success = False
            result.message = f"Injection failed: {str(e)}"
        
        return result
    
    def _has_daily_loss_protection(self, code: str) -> bool:
        """Check if daily loss protection already exists"""
        return bool(re.search(r'dailyLoss|DailyLoss|daily_loss|_dailyLossLimitReached', code))
    
    def _has_drawdown_protection(self, code: str) -> bool:
        """Check if drawdown protection already exists"""
        return bool(re.search(r'drawdown|Drawdown|_maxDrawdownReached|_peakEquity', code))
    
    def _has_position_limit(self, code: str) -> bool:
        """Check if position limit check exists"""
        return bool(re.search(r'Positions\.Count.*>=|CanOpenNewPosition|maxOpenTrades', code))
    
    def _has_risk_calculation(self, code: str) -> bool:
        """Check if risk calculation exists"""
        return bool(re.search(r'CalculateVolume|riskPercent|RiskPerTrade|riskAmount', code, re.IGNORECASE))
    
    def _has_spread_filter(self, code: str) -> bool:
        """Check if spread filter exists"""
        return bool(re.search(r'Symbol\.Spread.*PipSize|IsSpreadAcceptable|spreadLimit|maxSpread', code))
    
    def _has_session_filter(self, code: str) -> bool:
        """Check if session filter exists"""
        return bool(re.search(r'Server\.Time\.Hour|IsWithinTradingSession|TradingHours', code))
    
    def _inject_onstart_init(self, code: str) -> str:
        """
        Inject safety initialization code in OnStart method
        """
        # Find OnStart method
        onstart_match = re.search(
            r'(protected\s+override\s+void\s+OnStart\s*\(\s*\)\s*{)',
            code
        )
        
        if onstart_match:
            insert_pos = onstart_match.end()
            # Use API-enabled template if API logging is configured
            template = self.ONSTART_INIT_WITH_API_TEMPLATE if (self.config.enable_api_logging and self.config.api_base_url) else self.ONSTART_INIT_TEMPLATE
            code = (
                code[:insert_pos] +
                template +
                code[insert_pos:]
            )
        
        return code
    
    def _inject_safety_checks(self, code: str) -> str:
        """
        Inject safety check calls before trading operations
        """
        # Pattern to find ExecuteMarketOrder calls
        trade_patterns = [
            (r'(ExecuteMarketOrder\s*\()', 'if (!PassesAllSafetyChecks()) return;\n            '),
            (r'(PlaceLimitOrder\s*\()', 'if (!PassesAllSafetyChecks()) return;\n            '),
            (r'(PlaceStopOrder\s*\()', 'if (!PassesAllSafetyChecks()) return;\n            ')
        ]
        
        for pattern, safety_check in trade_patterns:
            # Only inject if safety check not already present before the trading operation
            # and if PassesAllSafetyChecks exists in the code
            if 'PassesAllSafetyChecks' in code:
                # Find all matches
                matches = list(re.finditer(pattern, code))
                
                # Process in reverse to maintain positions
                for match in reversed(matches):
                    # Check if safety check already exists before this call
                    preceding_code = code[max(0, match.start() - 100):match.start()]
                    if 'PassesAllSafetyChecks' not in preceding_code:
                        code = (
                            code[:match.start()] +
                            safety_check +
                            code[match.start():]
                        )
        
        return code


def create_safety_injector(config: Optional[SafetyConfig] = None) -> SafetyInjector:
    """Factory function to create safety injector"""
    return SafetyInjector(config)


def create_safety_injector_for_prop_firm(prop_firm: str) -> SafetyInjector:
    """Create safety injector with prop firm specific config"""
    config = SafetyConfig(prop_firm=prop_firm)
    return SafetyInjector(config)
