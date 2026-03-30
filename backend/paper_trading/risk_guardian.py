"""
Risk Guardian for Paper Trading
Monitors risk limits and stops trading when breached
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict

logger = logging.getLogger(__name__)


class RiskGuardian:
    """
    Monitors risk limits and circuit breakers
    
    Risk Controls:
    - Max Drawdown: 15%
    - Max Daily Loss: 2%
    """
    
    # Risk thresholds
    MAX_DRAWDOWN_PCT = 15.0
    MAX_DAILY_LOSS_PCT = 2.0
    
    def __init__(self, initial_capital: float):
        """
        Initialize risk guardian
        
        Args:
            initial_capital: Starting capital
        """
        self.initial_capital = initial_capital
        self.trading_enabled = True
        self.stop_reason = None
        
        # Track daily metrics
        self.daily_start_capital = initial_capital
        self.current_day = datetime.now(timezone.utc).date()
        
        logger.info(f"Risk Guardian initialized")
        logger.info(f"Max Drawdown: {self.MAX_DRAWDOWN_PCT}%")
        logger.info(f"Max Daily Loss: {self.MAX_DAILY_LOSS_PCT}%")
    
    def check_risk_limits(self, current_capital: float, peak_equity: float, drawdown_pct: float) -> bool:
        """
        Check if risk limits are breached
        
        Args:
            current_capital: Current account capital
            peak_equity: Peak equity level
            drawdown_pct: Current drawdown percentage
            
        Returns:
            True if trading should continue, False if stopped
        """
        # Reset daily tracking if new day
        self._check_new_day(current_capital)
        
        # Check drawdown limit
        if drawdown_pct > self.MAX_DRAWDOWN_PCT:
            self._trigger_stop(
                f"DRAWDOWN LIMIT BREACHED: {drawdown_pct:.2f}% > {self.MAX_DRAWDOWN_PCT}%"
            )
            return False
        
        # Check daily loss limit
        daily_loss_pct = ((self.daily_start_capital - current_capital) / self.daily_start_capital) * 100
        
        if daily_loss_pct > self.MAX_DAILY_LOSS_PCT:
            self._trigger_stop(
                f"DAILY LOSS LIMIT BREACHED: {daily_loss_pct:.2f}% > {self.MAX_DAILY_LOSS_PCT}%"
            )
            return False
        
        # All checks passed
        return True
    
    def _check_new_day(self, current_capital: float):
        """
        Check if it's a new trading day and reset daily metrics
        
        Args:
            current_capital: Current account capital
        """
        today = datetime.now(timezone.utc).date()
        
        if today != self.current_day:
            logger.info(f"New trading day: {today}")
            self.current_day = today
            self.daily_start_capital = current_capital
            
            # Reset trading if it was stopped due to daily loss
            if self.stop_reason and "DAILY LOSS" in self.stop_reason:
                logger.info("Daily loss limit reset - trading resumed")
                self.trading_enabled = True
                self.stop_reason = None
    
    def _trigger_stop(self, reason: str):
        """
        Trigger emergency stop
        
        Args:
            reason: Reason for stopping trading
        """
        if self.trading_enabled:
            self.trading_enabled = False
            self.stop_reason = reason
            logger.critical(f"🚨 TRADING STOPPED: {reason}")
    
    def is_trading_enabled(self) -> bool:
        """
        Check if trading is currently enabled
        
        Returns:
            True if trading allowed, False otherwise
        """
        return self.trading_enabled
    
    def get_stop_reason(self) -> str:
        """
        Get the reason trading was stopped
        
        Returns:
            Stop reason string or None
        """
        return self.stop_reason
    
    def get_risk_status(self, current_capital: float, peak_equity: float, drawdown_pct: float) -> Dict:
        """
        Get current risk status
        
        Args:
            current_capital: Current account capital
            peak_equity: Peak equity level
            drawdown_pct: Current drawdown percentage
            
        Returns:
            dict with risk metrics
        """
        # Calculate daily loss
        daily_loss_pct = ((self.daily_start_capital - current_capital) / self.daily_start_capital) * 100
        daily_loss_pct = max(0.0, daily_loss_pct)
        
        # Calculate margins to limits
        drawdown_margin = self.MAX_DRAWDOWN_PCT - drawdown_pct
        daily_loss_margin = self.MAX_DAILY_LOSS_PCT - daily_loss_pct
        
        return {
            'trading_enabled': self.trading_enabled,
            'stop_reason': self.stop_reason,
            'current_drawdown_pct': drawdown_pct,
            'max_drawdown_pct': self.MAX_DRAWDOWN_PCT,
            'drawdown_margin_pct': drawdown_margin,
            'daily_loss_pct': daily_loss_pct,
            'max_daily_loss_pct': self.MAX_DAILY_LOSS_PCT,
            'daily_loss_margin_pct': daily_loss_margin,
            'daily_start_capital': self.daily_start_capital,
            'current_capital': current_capital
        }
    
    def force_resume_trading(self):
        """
        Force resume trading (use with caution)
        """
        logger.warning("⚠️ Trading forcefully resumed by operator")
        self.trading_enabled = True
        self.stop_reason = None
