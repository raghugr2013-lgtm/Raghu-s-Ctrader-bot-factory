"""
Advanced Validation Module
Phase 2: Professional Quant-Grade Validation System

Provides:
- Bootstrap trade resampling (1000+ simulations)
- Parameter sensitivity testing
- Risk of ruin calculation
- Slippage & execution simulation
- Market regime-aware validation
"""

from .bootstrap_engine import (
    BootstrapEngine,
    BootstrapResult,
    BootstrapConfig,
    create_bootstrap_engine
)

from .sensitivity_analysis import (
    SensitivityAnalyzer,
    SensitivityResult,
    SensitivityConfig,
    create_sensitivity_analyzer
)

from .risk_of_ruin import (
    RiskOfRuinCalculator,
    RiskOfRuinResult,
    RiskOfRuinConfig,
    create_risk_of_ruin_calculator
)

from .slippage_simulator import (
    SlippageSimulator,
    SlippageResult,
    SlippageConfig,
    create_slippage_simulator
)

__all__ = [
    # Bootstrap Engine
    'BootstrapEngine',
    'BootstrapResult', 
    'BootstrapConfig',
    'create_bootstrap_engine',
    # Sensitivity Analysis
    'SensitivityAnalyzer',
    'SensitivityResult',
    'SensitivityConfig',
    'create_sensitivity_analyzer',
    # Risk of Ruin
    'RiskOfRuinCalculator',
    'RiskOfRuinResult',
    'RiskOfRuinConfig',
    'create_risk_of_ruin_calculator',
    # Slippage Simulator
    'SlippageSimulator',
    'SlippageResult',
    'SlippageConfig',
    'create_slippage_simulator'
]
