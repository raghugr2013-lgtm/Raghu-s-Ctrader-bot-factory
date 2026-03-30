"""
Portfolio Manager for Paper Trading
Handles position sizing and capital allocation
"""
import logging

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Manages portfolio allocation and position sizing
    
    Portfolio Configuration:
    - 40% Gold (XAUUSD) @ 0.25% risk per trade
    - 60% S&P 500 @ 0.4% risk per trade
    """
    
    def __init__(self, initial_capital: float = 10000.0):
        """
        Initialize portfolio manager
        
        Args:
            initial_capital: Starting capital (default: $10,000)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        # Portfolio allocation
        self.allocations = {
            'GOLD': {
                'percentage': 0.40,
                'capital': initial_capital * 0.40,
                'risk_per_trade': 0.0025  # 0.25%
            },
            'SPY': {
                'percentage': 0.60,
                'capital': initial_capital * 0.60,
                'risk_per_trade': 0.004  # 0.4%
            }
        }
        
        # Track positions
        self.open_positions = {}  # symbol -> position dict
        self.peak_equity = initial_capital
        
        logger.info(f"Portfolio initialized with ${initial_capital:,.2f}")
        logger.info(f"Gold allocation: ${self.allocations['GOLD']['capital']:,.2f} (0.25% risk)")
        logger.info(f"S&P allocation: ${self.allocations['SPY']['capital']:,.2f} (0.4% risk)")
    
    def calculate_position_size(self, symbol: str, entry_price: float, stop_loss: float) -> float:
        """
        Calculate position size based on risk percentage
        
        Args:
            symbol: 'GOLD' or 'SPY'
            entry_price: Entry price for the trade
            stop_loss: Stop loss price
            
        Returns:
            Position size (number of units/shares)
        """
        if symbol not in self.allocations:
            logger.error(f"Unknown symbol: {symbol}")
            return 0.0
        
        allocation = self.allocations[symbol]
        risk_amount = self.current_capital * allocation['risk_per_trade']
        
        # Calculate risk per unit
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            logger.warning(f"Zero price risk for {symbol}, cannot calculate position size")
            return 0.0
        
        # Position size = Risk Amount / Risk per Unit
        position_size = risk_amount / price_risk
        
        # Apply leverage limits (max 2x for safety in paper trading)
        max_position_value = allocation['capital'] * 2.0
        max_position_size = max_position_value / entry_price
        
        position_size = min(position_size, max_position_size)
        
        logger.debug(f"{symbol}: Risk=${risk_amount:.2f}, Price risk=${price_risk:.2f}, Size={position_size:.4f}")
        
        return position_size
    
    def open_position(self, symbol: str, entry_price: float, position_size: float, signal: str, stop_loss: float = None):
        """
        Open a new position
        
        Args:
            symbol: 'GOLD' or 'SPY'
            entry_price: Entry price
            position_size: Number of units
            signal: 'LONG' or 'SHORT'
            stop_loss: Stop loss price (optional)
        """
        if symbol in self.open_positions:
            logger.warning(f"Position already open for {symbol}, skipping")
            return False
        
        position_value = position_size * entry_price
        
        self.open_positions[symbol] = {
            'entry_price': entry_price,
            'position_size': position_size,
            'signal': signal,
            'stop_loss': stop_loss,
            'position_value': position_value
        }
        
        logger.info(f"Opened {signal} position: {symbol} @ ${entry_price:.2f}, Size={position_size:.4f}, Value=${position_value:.2f}")
        
        return True
    
    def close_position(self, symbol: str, exit_price: float) -> dict:
        """
        Close an existing position
        
        Args:
            symbol: 'GOLD' or 'SPY'
            exit_price: Exit price
            
        Returns:
            dict with PnL and trade details
        """
        if symbol not in self.open_positions:
            logger.warning(f"No open position for {symbol}")
            return None
        
        position = self.open_positions[symbol]
        
        # Calculate PnL
        if position['signal'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['position_size']
        else:  # SHORT
            pnl = (position['entry_price'] - exit_price) * position['position_size']
        
        # Update capital
        self.current_capital += pnl
        
        # Update peak equity
        if self.current_capital > self.peak_equity:
            self.peak_equity = self.current_capital
        
        logger.info(f"Closed {position['signal']} position: {symbol} @ ${exit_price:.2f}, PnL=${pnl:+.2f}")
        
        trade_result = {
            'symbol': symbol,
            'signal': position['signal'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'position_size': position['position_size'],
            'pnl': pnl,
            'capital_after': self.current_capital
        }
        
        # Remove position
        del self.open_positions[symbol]
        
        return trade_result
    
    def get_current_drawdown(self) -> float:
        """
        Calculate current drawdown percentage
        
        Returns:
            Drawdown percentage (0-100)
        """
        if self.peak_equity == 0:
            return 0.0
        
        drawdown = ((self.peak_equity - self.current_capital) / self.peak_equity) * 100
        return max(0.0, drawdown)
    
    def get_unrealized_pnl(self, current_prices: dict) -> float:
        """
        Calculate unrealized PnL from open positions
        
        Args:
            current_prices: dict with symbol -> current price
            
        Returns:
            Total unrealized PnL
        """
        unrealized = 0.0
        
        for symbol, position in self.open_positions.items():
            if symbol not in current_prices:
                continue
            
            current_price = current_prices[symbol]
            
            if position['signal'] == 'LONG':
                pnl = (current_price - position['entry_price']) * position['position_size']
            else:  # SHORT
                pnl = (position['entry_price'] - current_price) * position['position_size']
            
            unrealized += pnl
        
        return unrealized
    
    def get_total_equity(self, current_prices: dict) -> float:
        """
        Get total equity (realized + unrealized)
        
        Args:
            current_prices: dict with symbol -> current price
            
        Returns:
            Total equity
        """
        unrealized = self.get_unrealized_pnl(current_prices)
        return self.current_capital + unrealized
    
    def get_portfolio_status(self, current_prices: dict) -> dict:
        """
        Get complete portfolio status
        
        Args:
            current_prices: dict with symbol -> current price
            
        Returns:
            dict with portfolio metrics
        """
        unrealized_pnl = self.get_unrealized_pnl(current_prices)
        total_equity = self.current_capital + unrealized_pnl
        total_pnl = total_equity - self.initial_capital
        total_return_pct = (total_pnl / self.initial_capital) * 100
        drawdown_pct = self.get_current_drawdown()
        
        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'unrealized_pnl': unrealized_pnl,
            'total_equity': total_equity,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'peak_equity': self.peak_equity,
            'drawdown_pct': drawdown_pct,
            'open_positions': len(self.open_positions),
            'positions': {
                symbol: {
                    'signal': pos['signal'],
                    'entry_price': pos['entry_price'],
                    'position_size': pos['position_size'],
                    'current_price': current_prices.get(symbol, pos['entry_price'])
                }
                for symbol, pos in self.open_positions.items()
            }
        }
