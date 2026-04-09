"""
Strategy Configuration System
Dynamic configuration for strategy generation, filtering, and scoring.
All thresholds are configurable without code changes.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default configuration file path
CONFIG_FILE_PATH = os.environ.get("STRATEGY_CONFIG_PATH", "/app/backend/strategy_config.json")


class FilterConfig(BaseModel):
    """Strategy quality filter thresholds"""
    min_profit_factor: float = Field(default=1.2, ge=1.0, le=5.0, description="Minimum profit factor (≥1.2 recommended)")
    max_drawdown_pct: float = Field(default=20.0, ge=5.0, le=50.0, description="Maximum drawdown percentage")
    min_stability_pct: float = Field(default=60.0, ge=0.0, le=100.0, description="Minimum stability score percentage")
    min_trades: int = Field(default=50, ge=10, le=1000, description="Minimum number of trades")
    min_sharpe_ratio: float = Field(default=0.0, ge=-2.0, le=5.0, description="Minimum Sharpe ratio")
    min_win_rate: float = Field(default=30.0, ge=10.0, le=80.0, description="Minimum win rate percentage")
    
    # Strong strategy thresholds (for 🟢 label)
    strong_pf: float = Field(default=1.5, description="PF threshold for Strong label")
    strong_dd: float = Field(default=15.0, description="Max DD for Strong label")
    strong_sharpe: float = Field(default=1.0, description="Min Sharpe for Strong label")
    
    # Moderate strategy thresholds (for 🟡 label)
    moderate_pf: float = Field(default=1.2, description="PF threshold for Moderate label")
    moderate_dd: float = Field(default=20.0, description="Max DD for Moderate label")


class GenerationConfig(BaseModel):
    """Strategy generation settings"""
    default_strategy_count: int = Field(default=50, ge=10, le=500, description="Default strategies to generate")
    batch_size: int = Field(default=10, ge=5, le=50, description="Batch size for generation")
    max_retries: int = Field(default=3, ge=1, le=10, description="Max retries if no strategies pass filters")
    strategies_per_retry: int = Field(default=25, ge=10, le=100, description="Additional strategies per retry")
    min_data_years: float = Field(default=2.0, ge=0.5, le=10.0, description="Minimum years of data required")
    default_duration_days: int = Field(default=1825, ge=365, le=3650, description="Default backtest duration (days)")


class ScoringConfig(BaseModel):
    """Scoring weights for fitness calculation"""
    profit_factor_weight: float = Field(default=0.35, ge=0.0, le=1.0, description="Weight for profit factor")
    drawdown_weight: float = Field(default=0.25, ge=0.0, le=1.0, description="Weight for drawdown penalty")
    sharpe_weight: float = Field(default=0.20, ge=0.0, le=1.0, description="Weight for Sharpe ratio")
    monte_carlo_weight: float = Field(default=0.12, ge=0.0, le=1.0, description="Weight for Monte Carlo score")
    walkforward_weight: float = Field(default=0.08, ge=0.0, le=1.0, description="Weight for walk-forward score")
    
    # Fitness score thresholds
    fitness_threshold_strong: float = Field(default=70.0, description="Fitness threshold for Strong strategies")
    fitness_threshold_moderate: float = Field(default=50.0, description="Fitness threshold for Moderate strategies")


class SafetyConfig(BaseModel):
    """Safety and compliance settings"""
    max_daily_loss_pct: float = Field(default=5.0, ge=1.0, le=10.0, description="Max daily loss percentage")
    max_total_loss_pct: float = Field(default=10.0, ge=5.0, le=20.0, description="Max total loss percentage")
    require_stop_loss: bool = Field(default=True, description="Require stop loss in generated bots")
    require_take_profit: bool = Field(default=True, description="Require take profit in generated bots")
    max_position_size_pct: float = Field(default=2.0, ge=0.5, le=10.0, description="Max position size as % of balance")


class StrategyConfig(BaseModel):
    """Complete strategy configuration"""
    filters: FilterConfig = Field(default_factory=FilterConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    
    # Metadata
    version: str = Field(default="1.0.0")
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_by: str = Field(default="system")


class ConfigManager:
    """
    Singleton configuration manager.
    Loads config from file/database and provides runtime access.
    """
    _instance = None
    _config: Optional[StrategyConfig] = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def set_db(self, db):
        """Set database reference for persistent storage"""
        self._db = db
    
    def _load_config(self) -> None:
        """Load configuration from file or use defaults"""
        try:
            if os.path.exists(CONFIG_FILE_PATH):
                with open(CONFIG_FILE_PATH, 'r') as f:
                    data = json.load(f)
                    self._config = StrategyConfig(**data)
                    logger.info(f"Loaded config from {CONFIG_FILE_PATH}")
            else:
                self._config = StrategyConfig()
                self._save_config()
                logger.info("Created default configuration")
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            self._config = StrategyConfig()
    
    def _save_config(self) -> bool:
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE_PATH, 'w') as f:
                json.dump(self._config.model_dump(), f, indent=2)
            logger.info(f"Saved config to {CONFIG_FILE_PATH}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    @property
    def config(self) -> StrategyConfig:
        """Get current configuration"""
        if self._config is None:
            self._load_config()
        return self._config
    
    @property
    def filters(self) -> FilterConfig:
        """Get filter configuration"""
        return self.config.filters
    
    @property
    def generation(self) -> GenerationConfig:
        """Get generation configuration"""
        return self.config.generation
    
    @property
    def scoring(self) -> ScoringConfig:
        """Get scoring configuration"""
        return self.config.scoring
    
    @property
    def safety(self) -> SafetyConfig:
        """Get safety configuration"""
        return self.config.safety
    
    def update(self, updates: Dict[str, Any], updated_by: str = "user") -> StrategyConfig:
        """
        Update configuration with new values.
        Supports nested updates like {"filters": {"min_profit_factor": 1.3}}
        """
        current_data = self._config.model_dump()
        
        # Deep merge updates
        for key, value in updates.items():
            if key in current_data and isinstance(value, dict) and isinstance(current_data[key], dict):
                current_data[key].update(value)
            else:
                current_data[key] = value
        
        # Update metadata
        current_data['last_updated'] = datetime.now(timezone.utc).isoformat()
        current_data['updated_by'] = updated_by
        
        # Validate and apply
        self._config = StrategyConfig(**current_data)
        self._save_config()
        
        logger.info(f"Config updated by {updated_by}: {list(updates.keys())}")
        return self._config
    
    def reset_defaults(self) -> StrategyConfig:
        """Reset configuration to defaults"""
        self._config = StrategyConfig()
        self._save_config()
        logger.info("Config reset to defaults")
        return self._config
    
    def get_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return self.config.model_dump()
    
    def validate_strategy(self, strategy: Dict[str, Any]) -> tuple:
        """
        Validate strategy against current filter configuration.
        Returns (passes: bool, reasons: list, quality_label: str)
        """
        f = self.filters
        reasons = []
        
        pf = strategy.get('profit_factor', 0)
        if pf < f.min_profit_factor:
            reasons.append(f"PF {pf:.2f} < {f.min_profit_factor}")
        
        dd = abs(strategy.get('max_drawdown_pct', 100))
        if dd > f.max_drawdown_pct:
            reasons.append(f"DD {dd:.1f}% > {f.max_drawdown_pct}%")
        
        sharpe = strategy.get('sharpe_ratio', -999)
        if sharpe < f.min_sharpe_ratio:
            reasons.append(f"Sharpe {sharpe:.2f} < {f.min_sharpe_ratio}")
        
        trades = strategy.get('total_trades', 0)
        if trades < f.min_trades:
            reasons.append(f"Trades {trades} < {f.min_trades}")
        
        # Stability check
        stability = strategy.get('stability_score', 0)
        if not stability:
            wf = strategy.get('walkforward', {})
            stability = wf.get('stability_score', 0) * 100 if wf else 0
        if not stability:
            mc = strategy.get('monte_carlo_score', 0)
            stability = mc if mc else 50
        if stability < f.min_stability_pct:
            reasons.append(f"Stability {stability:.0f}% < {f.min_stability_pct}%")
        
        passes = len(reasons) == 0
        
        # Determine quality label (only Strong or Moderate if passes)
        if passes:
            if pf >= f.strong_pf and dd <= f.strong_dd and sharpe >= f.strong_sharpe:
                label = ('Strong', 'emerald', '🟢')
            elif pf >= f.moderate_pf and dd <= f.moderate_dd:
                label = ('Moderate', 'amber', '🟡')
            else:
                label = ('Moderate', 'amber', '🟡')  # Default passing to Moderate
        else:
            label = ('Weak', 'red', '🔴')
        
        return (passes, reasons, label)
    
    def can_generate_cbot(self, strategy: Dict[str, Any]) -> tuple:
        """
        Check if strategy is allowed to generate cBot.
        Returns (allowed: bool, reason: str)
        """
        f = self.filters
        pf = strategy.get('profit_factor', 0)
        dd = abs(strategy.get('max_drawdown_pct', 100))
        
        if pf < f.min_profit_factor:
            return (False, f"Profit Factor {pf:.2f} is below minimum {f.min_profit_factor}. Strategy not validated for cBot generation.")
        
        if dd > f.max_drawdown_pct:
            return (False, f"Drawdown {dd:.1f}% exceeds maximum {f.max_drawdown_pct}%. Strategy not validated for cBot generation.")
        
        passes, reasons, _ = self.validate_strategy(strategy)
        if not passes:
            return (False, f"Strategy does not meet quality filters: {', '.join(reasons)}")
        
        return (True, "Strategy validated for cBot generation")


# Global config manager instance
config_manager = ConfigManager()


def get_config() -> StrategyConfig:
    """Get current configuration"""
    return config_manager.config


def get_filters() -> FilterConfig:
    """Get filter configuration"""
    return config_manager.filters


def get_generation() -> GenerationConfig:
    """Get generation configuration"""
    return config_manager.generation


def get_scoring() -> ScoringConfig:
    """Get scoring configuration"""
    return config_manager.scoring


def update_config(updates: Dict[str, Any], updated_by: str = "user") -> StrategyConfig:
    """Update configuration"""
    return config_manager.update(updates, updated_by)


def validate_strategy(strategy: Dict[str, Any]) -> tuple:
    """Validate strategy against filters"""
    return config_manager.validate_strategy(strategy)


def can_generate_cbot(strategy: Dict[str, Any]) -> tuple:
    """Check if cBot generation is allowed"""
    return config_manager.can_generate_cbot(strategy)
