"""
Paper Trading Engine - Phase 6
Real-time market monitoring and trade execution (simulated)

Strategy: EMA 10/150 Crossover
Portfolio: 40% Gold (0.25% risk) + 60% S&P 500 (0.4% risk)
Risk Controls: 15% max drawdown, 2% daily loss limit
"""
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import yfinance as yf
import json

# Add paper_trading package to path
sys.path.insert(0, str(Path(__file__).parent))

from portfolio_manager import PortfolioManager
from trade_logger import TradeLogger
from risk_guardian import RiskGuardian

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/backend/paper_trading/engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """
    Paper Trading Engine
    
    Monitors markets in real-time and executes EMA 10/150 crossover strategy
    """
    
    # Market symbols
    SYMBOLS = {
        'GOLD': 'GLD',   # Gold ETF (more reliable than futures)
        'SPY': 'SPY'     # S&P 500 ETF
    }
    
    # EMA parameters
    EMA_FAST = 10
    EMA_SLOW = 150
    
    # Data lookback (need enough for EMA calculation)
    LOOKBACK_DAYS = 200
    
    # Check interval (seconds) - check every hour for H1 candles
    CHECK_INTERVAL = 3600  # 1 hour
    
    def __init__(self, initial_capital: float = 10000.0):
        """
        Initialize paper trading engine
        
        Args:
            initial_capital: Starting capital (default: $10,000)
        """
        self.portfolio = PortfolioManager(initial_capital)
        self.trade_logger = TradeLogger()
        self.risk_guardian = RiskGuardian(initial_capital)
        
        self.running = False
        self.last_check_time = {}
        
        # Track last bar close for each symbol
        self.last_bar_timestamp = {}
        
        # Track previous signals to detect crossovers
        self.previous_signal = {}
        
        # Statistics
        self.total_trades = 0
        self.start_time = None
        
        logger.info("=" * 80)
        logger.info("PAPER TRADING ENGINE INITIALIZED")
        logger.info("=" * 80)
        logger.info(f"Strategy: EMA {self.EMA_FAST}/{self.EMA_SLOW} Crossover")
        logger.info(f"Portfolio: 40% Gold + 60% S&P 500")
        logger.info(f"Initial Capital: ${initial_capital:,.2f}")
        logger.info(f"Risk Controls: 15% DD limit, 2% daily loss limit")
        logger.info("=" * 80)
    
    def fetch_market_data(self, symbol: str, ticker: str) -> pd.DataFrame:
        """
        Fetch latest H1 candle data from yfinance
        
        Args:
            symbol: 'GOLD' or 'SPY'
            ticker: yfinance ticker symbol
            
        Returns:
            DataFrame with OHLC data
        """
        try:
            # Fetch data with 1h interval
            df = yf.download(
                ticker,
                period=f'{self.LOOKBACK_DAYS}d',
                interval='1h',
                progress=False
            )
            
            if df.empty:
                logger.warning(f"No data received for {symbol}")
                return None
            
            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                # For multi-level, take the first level (the price type)
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
            
            # Ensure we have required columns
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in df.columns for col in required_cols):
                logger.error(f"Missing required columns for {symbol}. Available: {df.columns.tolist()}")
                return None
            
            logger.info(f"Fetched {len(df)} H1 candles for {symbol}, latest close: ${df['Close'].iloc[-1]:.2f}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return None
    
    def calculate_ema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate EMA indicators
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with EMA columns added
        """
        df = df.copy()
        df[f'EMA_{self.EMA_FAST}'] = df['Close'].ewm(span=self.EMA_FAST, adjust=False).mean()
        df[f'EMA_{self.EMA_SLOW}'] = df['Close'].ewm(span=self.EMA_SLOW, adjust=False).mean()
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> str:
        """
        Generate trading signal based on EMA crossover
        
        Args:
            df: DataFrame with EMA columns
            
        Returns:
            'LONG', 'SHORT', or 'NEUTRAL'
        """
        if len(df) < 2:
            return 'NEUTRAL'
        
        # Get current and previous EMA values
        current_fast = df[f'EMA_{self.EMA_FAST}'].iloc[-1]
        current_slow = df[f'EMA_{self.EMA_SLOW}'].iloc[-1]
        prev_fast = df[f'EMA_{self.EMA_FAST}'].iloc[-2]
        prev_slow = df[f'EMA_{self.EMA_SLOW}'].iloc[-2]
        
        # Check for crossover
        if current_fast > current_slow and prev_fast <= prev_slow:
            # Bullish crossover
            return 'LONG'
        elif current_fast < current_slow and prev_fast >= prev_slow:
            # Bearish crossover
            return 'SHORT'
        elif current_fast > current_slow:
            # Already in uptrend
            return 'LONG'
        elif current_fast < current_slow:
            # Already in downtrend
            return 'SHORT'
        else:
            return 'NEUTRAL'
    
    def check_symbol(self, symbol: str, ticker: str):
        """
        Check a single symbol for trading signals
        
        Args:
            symbol: 'GOLD' or 'SPY'
            ticker: yfinance ticker symbol
        """
        logger.debug(f"Checking {symbol}...")
        
        # Fetch market data
        df = self.fetch_market_data(symbol, ticker)
        if df is None or len(df) < self.EMA_SLOW + 10:
            logger.warning(f"Insufficient data for {symbol}")
            return
        
        # Calculate EMAs
        df = self.calculate_ema(df)
        
        # Get latest bar timestamp
        latest_timestamp = df.index[-1]
        
        # Check if this is a new bar
        if symbol in self.last_bar_timestamp:
            if latest_timestamp <= self.last_bar_timestamp[symbol]:
                logger.debug(f"No new bar for {symbol}, skipping")
                return
        
        # Update last bar timestamp
        self.last_bar_timestamp[symbol] = latest_timestamp
        
        # Generate signal
        current_signal = self.generate_signal(df)
        previous_signal = self.previous_signal.get(symbol, 'NEUTRAL')
        
        logger.info(f"{symbol}: Signal={current_signal}, Previous={previous_signal}")
        
        # Get current price
        current_price = float(df['Close'].iloc[-1])
        
        # Check if we have an open position
        has_position = symbol in self.portfolio.open_positions
        
        # Trading logic
        if current_signal != 'NEUTRAL' and current_signal != previous_signal:
            # Signal changed - potential trade
            
            if has_position:
                # Close existing position
                logger.info(f"Signal changed for {symbol}, closing existing position")
                trade = self.portfolio.close_position(symbol, current_price)
                
                if trade:
                    trade['timestamp'] = datetime.now(timezone.utc).isoformat()
                    trade['strategy_signal'] = f"{previous_signal} -> {current_signal}"
                    self.trade_logger.log_trade_sync(trade)
                    self.total_trades += 1
            
            # Open new position if trading enabled
            if self.risk_guardian.is_trading_enabled():
                # Calculate stop loss (simple ATR-based or fixed % for now)
                stop_loss = current_price * 0.98 if current_signal == 'LONG' else current_price * 1.02
                
                # Calculate position size
                position_size = self.portfolio.calculate_position_size(symbol, current_price, stop_loss)
                
                if position_size > 0:
                    success = self.portfolio.open_position(
                        symbol=symbol,
                        entry_price=current_price,
                        position_size=position_size,
                        signal=current_signal,
                        stop_loss=stop_loss
                    )
                    
                    if success:
                        logger.info(f"Opened {current_signal} position for {symbol}")
            else:
                logger.warning(f"Trading disabled: {self.risk_guardian.get_stop_reason()}")
        
        # Update previous signal
        self.previous_signal[symbol] = current_signal
    
    def monitor_risk(self):
        """
        Monitor risk limits
        """
        # Get current prices for equity calculation
        current_prices = {}
        for symbol, ticker in self.SYMBOLS.items():
            try:
                data = yf.download(ticker, period='1d', interval='1h', progress=False)
                if not data.empty:
                    # Handle multi-index columns
                    if isinstance(data.columns, pd.MultiIndex):
                        price_series = data['Close'].iloc[-1]
                        # Extract the actual float value from Series
                        if isinstance(price_series, pd.Series):
                            current_prices[symbol] = float(price_series.iloc[0])
                        else:
                            current_prices[symbol] = float(price_series)
                    else:
                        current_prices[symbol] = float(data['Close'].iloc[-1])
            except Exception as e:
                logger.warning(f"Failed to get current price for {symbol}: {e}")
                pass
        
        # Get portfolio status
        status = self.portfolio.get_portfolio_status(current_prices)
        
        # Check risk limits based on REALIZED capital (not including unrealized PnL)
        self.risk_guardian.check_risk_limits(
            current_capital=status['current_capital'],  # Realized capital only
            peak_equity=status['peak_equity'],
            drawdown_pct=status['drawdown_pct']
        )
        
        # Log status
        logger.info(f"Portfolio Status: Equity=${status['total_equity']:,.2f}, "
                   f"PnL=${status['total_pnl']:+,.2f} ({status['total_return_pct']:+.2f}%), "
                   f"DD={status['drawdown_pct']:.2f}%, Open={status['open_positions']}")
    
    def run(self):
        """
        Main trading loop
        """
        self.running = True
        self.start_time = datetime.now(timezone.utc)
        
        logger.info("🚀 Paper trading engine started")
        logger.info(f"Check interval: {self.CHECK_INTERVAL}s (H1 candles)")
        
        while self.running:
            try:
                logger.info("-" * 80)
                logger.info(f"Market check: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
                
                # Check risk limits first
                self.monitor_risk()
                
                # Check each symbol if trading is enabled
                if self.risk_guardian.is_trading_enabled():
                    for symbol, ticker in self.SYMBOLS.items():
                        self.check_symbol(symbol, ticker)
                else:
                    logger.warning(f"Trading disabled: {self.risk_guardian.get_stop_reason()}")
                
                # Sleep until next check
                logger.info(f"Next check in {self.CHECK_INTERVAL}s...")
                time.sleep(self.CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute before retrying
    
    def stop(self):
        """
        Stop the trading engine
        """
        self.running = False
        
        # Close all open positions
        logger.info("Closing all open positions...")
        for symbol, ticker in self.SYMBOLS.items():
            if symbol in self.portfolio.open_positions:
                try:
                    data = yf.download(ticker, period='1d', interval='1h', progress=False)
                    if not data.empty:
                        # Handle multi-index columns
                        if isinstance(data.columns, pd.MultiIndex):
                            price_series = data['Close'].iloc[-1]
                            if isinstance(price_series, pd.Series):
                                current_price = float(price_series.iloc[0])
                            else:
                                current_price = float(price_series)
                        else:
                            current_price = float(data['Close'].iloc[-1])
                        
                        trade = self.portfolio.close_position(symbol, current_price)
                        if trade:
                            trade['timestamp'] = datetime.now(timezone.utc).isoformat()
                            trade['strategy_signal'] = 'MANUAL_CLOSE'
                            self.trade_logger.log_trade_sync(trade)
                except Exception as e:
                    logger.error(f"Failed to close position for {symbol}: {e}")
        
        # Log final statistics
        runtime = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600
        
        logger.info("=" * 80)
        logger.info("PAPER TRADING ENGINE STOPPED")
        logger.info(f"Runtime: {runtime:.1f} hours")
        logger.info(f"Total trades: {self.total_trades}")
        logger.info(f"Final capital: ${self.portfolio.current_capital:,.2f}")
        logger.info(f"Total return: ${self.portfolio.current_capital - self.portfolio.initial_capital:+,.2f}")
        logger.info("=" * 80)
        
        self.trade_logger.close()
    
    def get_status(self) -> dict:
        """
        Get current engine status
        
        Returns:
            dict with status information
        """
        # Get current prices
        current_prices = {}
        for symbol, ticker in self.SYMBOLS.items():
            try:
                data = yf.download(ticker, period='1d', interval='1h', progress=False)
                if not data.empty:
                    # Handle multi-index columns
                    if isinstance(data.columns, pd.MultiIndex):
                        price_series = data['Close'].iloc[-1]
                        if isinstance(price_series, pd.Series):
                            current_prices[symbol] = float(price_series.iloc[0])
                        else:
                            current_prices[symbol] = float(price_series)
                    else:
                        current_prices[symbol] = float(data['Close'].iloc[-1])
            except Exception as e:
                logger.warning(f"Failed to get price for {symbol}: {e}")
                pass
        
        portfolio_status = self.portfolio.get_portfolio_status(current_prices)
        risk_status = self.risk_guardian.get_risk_status(
            portfolio_status['total_equity'],
            portfolio_status['peak_equity'],
            portfolio_status['drawdown_pct']
        )
        
        runtime_hours = 0
        if self.start_time:
            runtime_hours = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600
        
        return {
            'running': self.running,
            'runtime_hours': runtime_hours,
            'total_trades': self.total_trades,
            'portfolio': portfolio_status,
            'risk': risk_status
        }


def main():
    """Main entry point"""
    engine = PaperTradingEngine(initial_capital=10000.0)
    
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        engine.stop()


if __name__ == "__main__":
    main()
