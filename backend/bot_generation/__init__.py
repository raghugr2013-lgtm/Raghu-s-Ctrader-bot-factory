"""
Bot Generation Module
Phase 8: Bot Testing & Validation System

This module provides:
- Bot compilation validation
- Sandbox backtesting execution
- Risk validation (DD limits, trade limits)
- Safety code injection
"""

from .bot_validation_engine import (
    BotValidationEngine,
    ValidationResult,
    CompilationResult,
    BacktestValidationResult,
    RiskValidationResult,
    create_validation_engine
)

from .safety_injection import (
    SafetyInjector,
    SafetyConfig,
    InjectionResult,
    create_safety_injector
)

__all__ = [
    # Validation Engine
    'BotValidationEngine',
    'ValidationResult',
    'CompilationResult',
    'BacktestValidationResult',
    'RiskValidationResult',
    'create_validation_engine',
    # Safety Injection
    'SafetyInjector',
    'SafetyConfig',
    'InjectionResult',
    'create_safety_injector'
]
