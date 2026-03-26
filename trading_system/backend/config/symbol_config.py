"""
Symbol Configuration for Multi-Asset Trading Support
Supports: EURUSD, XAUUSD, US100, ETHUSD
"""

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class SymbolType(str, Enum):
    """Type of trading instrument"""
    FOREX = "forex"
    METAL = "metal"
    INDEX = "index"
    CRYPTO = "crypto"


class SymbolConfig(BaseModel):
    """Configuration for a trading symbol"""
    symbol: str
    type: SymbolType
    pip_value: float  # Value of 1 pip movement
    lot_size: float   # Contract size per lot
    spread: float     # Average spread in pips
    min_lot: float = 0.01  # Minimum lot size
    max_lot: float = 100.0  # Maximum lot size
    pip_digits: int = 4  # Decimal places for pip calculation
    value_per_pip_per_lot: float = 10.0  # $ value per pip per standard lot
    
    # Risk management defaults
    default_stop_loss_pips: float = 50.0
    default_take_profit_pips: float = 100.0
    volatility_multiplier: float = 1.0  # For adjusting SL/TP
    
    # Dukascopy data settings
    dukascopy_symbol: str = ""  # Symbol name in Dukascopy format
    
    class Config:
        use_enum_values = True


# Symbol Configurations
SYMBOL_CONFIG: Dict[str, SymbolConfig] = {
    "EURUSD": SymbolConfig(
        symbol="EURUSD",
        type=SymbolType.FOREX,
        pip_value=0.0001,
        lot_size=100000,
        spread=0.8,
        min_lot=0.01,
        max_lot=100.0,
        pip_digits=4,
        value_per_pip_per_lot=10.0,
        default_stop_loss_pips=30.0,
        default_take_profit_pips=60.0,
        volatility_multiplier=1.0,
        dukascopy_symbol="EURUSD"
    ),
    "XAUUSD": SymbolConfig(
        symbol="XAUUSD",
        type=SymbolType.METAL,
        pip_value=0.01,
        lot_size=100,
        spread=20.0,
        min_lot=0.01,
        max_lot=50.0,
        pip_digits=2,
        value_per_pip_per_lot=1.0,
        default_stop_loss_pips=100.0,  # Wider for Gold
        default_take_profit_pips=200.0,
        volatility_multiplier=2.5,  # Higher volatility
        dukascopy_symbol="XAUUSD"
    ),
    "US100": SymbolConfig(
        symbol="US100",
        type=SymbolType.INDEX,
        pip_value=1.0,
        lot_size=1,
        spread=2.0,
        min_lot=0.1,
        max_lot=100.0,
        pip_digits=1,
        value_per_pip_per_lot=1.0,
        default_stop_loss_pips=50.0,
        default_take_profit_pips=100.0,
        volatility_multiplier=1.5,
        dukascopy_symbol="USA100IDXUSD"
    ),
    "ETHUSD": SymbolConfig(
        symbol="ETHUSD",
        type=SymbolType.CRYPTO,
        pip_value=0.1,
        lot_size=1,
        spread=5.0,
        min_lot=0.01,
        max_lot=100.0,
        pip_digits=1,
        value_per_pip_per_lot=0.1,
        default_stop_loss_pips=200.0,  # Wide for crypto
        default_take_profit_pips=400.0,
        volatility_multiplier=3.0,  # High volatility
        dukascopy_symbol="ETHUSD"
    )
}


def get_symbol_config(symbol: str) -> Optional[SymbolConfig]:
    """Get configuration for a symbol"""
    # Normalize symbol name
    symbol_upper = symbol.upper().replace("/", "")
    
    if symbol_upper in SYMBOL_CONFIG:
        return SYMBOL_CONFIG[symbol_upper]
    
    # Try common variations
    variations = [
        symbol_upper,
        symbol_upper.replace("_", ""),
        f"{symbol_upper[:3]}/{symbol_upper[3:]}"
    ]
    
    for var in variations:
        if var in SYMBOL_CONFIG:
            return SYMBOL_CONFIG[var]
    
    logger.warning(f"Symbol {symbol} not found in config, using EURUSD defaults")
    return SYMBOL_CONFIG.get("EURUSD")


def get_supported_symbols() -> list:
    """Get list of supported symbols"""
    return list(SYMBOL_CONFIG.keys())


def calculate_pip_value(symbol: str, price: float, lot_size: float = 1.0) -> float:
    """
    Calculate the value of a pip for given symbol and lot size
    
    Args:
        symbol: Trading symbol
        price: Current price (needed for some calculations)
        lot_size: Position size in lots
    
    Returns:
        Value of 1 pip in account currency (USD)
    """
    config = get_symbol_config(symbol)
    if not config:
        return 10.0 * lot_size  # Default forex
    
    return config.value_per_pip_per_lot * lot_size


def calculate_pips(symbol: str, entry_price: float, exit_price: float, direction: str = "BUY") -> float:
    """
    Calculate pip difference between entry and exit
    
    Args:
        symbol: Trading symbol
        entry_price: Entry price
        exit_price: Exit price
        direction: "BUY" or "SELL"
    
    Returns:
        Number of pips (positive = profit, negative = loss)
    """
    config = get_symbol_config(symbol)
    if not config:
        pip_value = 0.0001
    else:
        pip_value = config.pip_value
    
    price_diff = exit_price - entry_price
    if direction.upper() == "SELL":
        price_diff = -price_diff
    
    return price_diff / pip_value


def get_symbol_risk_params(symbol: str) -> dict:
    """
    Get recommended risk parameters for a symbol
    
    Returns dict with:
    - default_sl_pips
    - default_tp_pips
    - risk_multiplier
    - recommended_lot_percent
    """
    config = get_symbol_config(symbol)
    if not config:
        return {
            "default_sl_pips": 50.0,
            "default_tp_pips": 100.0,
            "risk_multiplier": 1.0,
            "recommended_lot_percent": 1.0
        }
    
    return {
        "default_sl_pips": config.default_stop_loss_pips,
        "default_tp_pips": config.default_take_profit_pips,
        "risk_multiplier": config.volatility_multiplier,
        "recommended_lot_percent": 1.0 / config.volatility_multiplier  # Lower for volatile assets
    }
