"""
Fix Suggester Module - Auto-suggest fixes for validation and compilation errors
Pattern-based detection for common cBot code issues
Enhanced with confidence scoring
"""

import re
from typing import List, Dict, Any


# Confidence score mapping for each fix type
FIX_CONFIDENCE_SCORES = {
    "add-stop-loss": 95,           # Very safe, always applicable
    "add-take-profit": 90,         # Safe, standard pattern
    "add-using-statements": 95,    # Deterministic fix
    "fix-type-conversion": 90,     # Clear pattern match
    "add-null-checks": 85,         # Good but might need customization
    "fix-multiple-positions": 80,  # Might affect trading strategy
    "update-deprecated-api": 85,   # Safe but context-dependent
    "parameterize-values": 60      # Suggestion only, manual review needed
}


def _get_confidence_label(score: int) -> str:
    """Convert confidence score to label"""
    if score >= 90:
        return "High"
    elif score >= 70:
        return "Medium"
    else:
        return "Low"


def suggest_fixes(code: str, validation_errors: List = None, compile_errors: List = None) -> Dict[str, Any]:
    """
    Analyze code and errors to suggest fixes
    
    Args:
        code: C# cBot source code
        validation_errors: List of validation error messages
        compile_errors: List of compilation error messages
    
    Returns:
        Dict with suggestions list
    """
    suggestions = []
    
    # Combine all error messages for analysis
    all_errors = []
    if validation_errors:
        all_errors.extend([str(e) for e in validation_errors])
    if compile_errors:
        all_errors.extend([str(e) for e in compile_errors])
    
    # Check for missing stop loss
    if _has_missing_stop_loss(code):
        fix_id = "add-stop-loss"
        confidence = FIX_CONFIDENCE_SCORES[fix_id]
        suggestions.append({
            "id": fix_id,
            "title": "Add Stop Loss Parameter",
            "description": "ExecuteMarketOrder calls are missing stop loss. This is critical for risk management.",
            "fix_type": "risk",
            "severity": "critical",
            "auto_fixable": True,
            "confidence": confidence,
            "confidence_label": _get_confidence_label(confidence),
            "code_patch": _generate_stop_loss_patch(code)
        })
    
    # Check for missing take profit
    if _has_missing_take_profit(code):
        fix_id = "add-take-profit"
        confidence = FIX_CONFIDENCE_SCORES[fix_id]
        suggestions.append({
            "id": fix_id,
            "title": "Add Take Profit Parameter",
            "description": "ExecuteMarketOrder calls are missing take profit. Adding 2:1 risk-reward target.",
            "fix_type": "risk",
            "severity": "high",
            "auto_fixable": True,
            "confidence": confidence,
            "confidence_label": _get_confidence_label(confidence),
            "code_patch": _generate_take_profit_patch(code)
        })
    
    # Check for missing using statements
    missing_usings = _find_missing_using_statements(code, all_errors)
    if missing_usings:
        fix_id = "add-using-statements"
        confidence = FIX_CONFIDENCE_SCORES[fix_id]
        suggestions.append({
            "id": fix_id,
            "title": "Add Missing Using Statements",
            "description": f"Add required namespaces: {', '.join(missing_usings)}",
            "fix_type": "syntax",
            "severity": "high",
            "auto_fixable": True,
            "confidence": confidence,
            "confidence_label": _get_confidence_label(confidence),
            "code_patch": _generate_using_statements_patch(code, missing_usings)
        })
    
    # Check for type conversion issues
    if _has_type_conversion_issues(all_errors):
        fix_id = "fix-type-conversion"
        confidence = FIX_CONFIDENCE_SCORES[fix_id]
        suggestions.append({
            "id": fix_id,
            "title": "Fix Type Conversion",
            "description": "Add explicit type conversions for parameter assignments.",
            "fix_type": "syntax",
            "severity": "high",
            "auto_fixable": True,
            "confidence": confidence,
            "confidence_label": _get_confidence_label(confidence),
            "code_patch": _generate_type_conversion_patch(code, all_errors)
        })
    
    # Check for null checks missing
    if _needs_null_checks(code):
        fix_id = "add-null-checks"
        confidence = FIX_CONFIDENCE_SCORES[fix_id]
        suggestions.append({
            "id": fix_id,
            "title": "Add Null Checks for Indicators",
            "description": "Add validation to prevent null reference exceptions on indicator values.",
            "fix_type": "logic",
            "severity": "medium",
            "auto_fixable": True,
            "confidence": confidence,
            "confidence_label": _get_confidence_label(confidence),
            "code_patch": _generate_null_checks_patch(code)
        })
    
    # Check for multiple position issues
    if _has_multiple_position_issue(code):
        fix_id = "fix-multiple-positions"
        confidence = FIX_CONFIDENCE_SCORES[fix_id]
        suggestions.append({
            "id": fix_id,
            "title": "Prevent Multiple Positions",
            "description": "Add check to prevent opening duplicate positions on the same signal.",
            "fix_type": "logic",
            "severity": "medium",
            "auto_fixable": True,
            "confidence": confidence,
            "confidence_label": _get_confidence_label(confidence),
            "code_patch": _generate_position_check_patch(code)
        })
    
    # Check for hard-coded values
    hard_coded = _find_hard_coded_values(code)
    if hard_coded:
        fix_id = "parameterize-values"
        confidence = FIX_CONFIDENCE_SCORES[fix_id]
        suggestions.append({
            "id": fix_id,
            "title": "Convert Hard-coded Values to Parameters",
            "description": f"Found hard-coded values: {', '.join(hard_coded)}. Make them configurable.",
            "fix_type": "logic",
            "severity": "low",
            "auto_fixable": False,  # Requires manual decision
            "confidence": confidence,
            "confidence_label": _get_confidence_label(confidence),
            "code_patch": None
        })
    
    # Check for deprecated API usage
    if _has_deprecated_api(code):
        fix_id = "update-deprecated-api"
        confidence = FIX_CONFIDENCE_SCORES[fix_id]
        suggestions.append({
            "id": fix_id,
            "title": "Update Deprecated API Calls",
            "description": "Replace MarketSeries with Bars and PipSize with TickSize.",
            "fix_type": "syntax",
            "severity": "low",
            "auto_fixable": True,
            "confidence": confidence,
            "confidence_label": _get_confidence_label(confidence),
            "code_patch": _generate_api_update_patch(code)
        })
    
    # Calculate overall confidence (average of auto-fixable suggestions)
    auto_fixable = [s for s in suggestions if s.get("auto_fixable", False)]
    overall_confidence = 0
    if auto_fixable:
        overall_confidence = sum(s["confidence"] for s in auto_fixable) / len(auto_fixable)
    
    return {
        "success": True,
        "suggestions": suggestions,
        "total_count": len(suggestions),
        "auto_fixable_count": sum(1 for s in suggestions if s.get("auto_fixable", False)),
        "overall_confidence": round(overall_confidence, 1),
        "overall_confidence_label": _get_confidence_label(int(overall_confidence)) if overall_confidence > 0 else "N/A"
    }


# ── Detection Functions ──────────────────────────────────────

def _has_missing_stop_loss(code: str) -> bool:
    """Check if ExecuteMarketOrder calls are missing stop loss"""
    # Look for ExecuteMarketOrder with 4 parameters (no SL/TP)
    pattern = r'ExecuteMarketOrder\s*\(\s*TradeType\.\w+\s*,\s*[^,]+\s*,\s*[^,]+\s*,\s*[^,)]+\s*\)'
    matches = re.findall(pattern, code)
    return len(matches) > 0


def _has_missing_take_profit(code: str) -> bool:
    """Check if take profit is missing"""
    # Look for ExecuteMarketOrder with 5 parameters (SL but no TP)
    pattern = r'ExecuteMarketOrder\s*\([^)]+,\s*[^,)]+\s*,\s*null\s*\)'
    matches = re.findall(pattern, code)
    return len(matches) > 0 or ('TakeProfitPips' not in code and 'takeProfit' not in code)


def _find_missing_using_statements(code: str, errors: List[str]) -> List[str]:
    """Find missing using statements based on errors"""
    missing = []
    
    # Check for common missing namespaces
    if 'Symbol' in code and 'using cAlgo.API.Internals' not in code:
        missing.append('cAlgo.API.Internals')
    
    if 'Collections' in ' '.join(errors) and 'using cAlgo.API.Collections' not in code:
        missing.append('cAlgo.API.Collections')
    
    # Check errors for type not found
    for error in errors:
        if 'not found' in error.lower() or 'does not exist' in error.lower():
            if 'Indicators' in error and 'using cAlgo.API.Indicators' not in code:
                if 'cAlgo.API.Indicators' not in missing:
                    missing.append('cAlgo.API.Indicators')
    
    return missing


def _has_type_conversion_issues(errors: List[str]) -> bool:
    """Check if errors contain type conversion issues"""
    for error in errors:
        if 'cannot convert' in error.lower() or 'type mismatch' in error.lower():
            return True
    return False


def _needs_null_checks(code: str) -> bool:
    """Check if indicator null checks are missing"""
    # Check if indicators are used but not validated
    if '_rsi' in code.lower() or '_macd' in code.lower() or '_ema' in code.lower():
        # Look for null checks
        if 'if' not in code or 'null' not in code.lower():
            return True
        # Check if Result.LastValue is used without null check
        if '.Result.LastValue' in code and 'if (' not in code[:code.find('.Result.LastValue')]:
            return True
    return False


def _has_multiple_position_issue(code: str) -> bool:
    """Check if code might open multiple positions without checking"""
    # Look for ExecuteMarketOrder in OnBar without position check
    if 'ExecuteMarketOrder' in code and 'OnBar' in code:
        # Check if there's a position check before execution
        if 'Positions.Find' not in code and 'Positions.Count' not in code:
            return True
    return False


def _find_hard_coded_values(code: str) -> List[str]:
    """Find hard-coded numeric values that should be parameters"""
    hard_coded = []
    
    # Look for common hard-coded patterns
    if re.search(r'RSI\s*<\s*30', code):
        hard_coded.append('RSI oversold level (30)')
    if re.search(r'RSI\s*>\s*70', code):
        hard_coded.append('RSI overbought level (70)')
    if re.search(r'RiskPercent.*=.*[\d\.]+', code) and '[Parameter' not in code[:code.find('RiskPercent')]:
        hard_coded.append('Risk percentage')
    
    return hard_coded


def _has_deprecated_api(code: str) -> bool:
    """Check for deprecated API usage"""
    return 'MarketSeries' in code or 'Symbol.PipSize' in code


# ── Patch Generation Functions ───────────────────────────────

def _generate_stop_loss_patch(code: str) -> str:
    """Generate patch to add stop loss parameter and usage"""
    # Add parameter if not exists
    if 'StopLossPips' not in code:
        # Find class body
        class_match = re.search(r'(public class \w+ : Robot\s*\{)', code)
        if class_match:
            insertion_point = class_match.end()
            parameter_code = '''
        
        [Parameter("Stop Loss (Pips)", DefaultValue = 25, MinValue = 5, MaxValue = 200)]
        public double StopLossPips { get; set; }
'''
            code = code[:insertion_point] + parameter_code + code[insertion_point:]
    
    # Update ExecuteMarketOrder calls
    # Pattern: ExecuteMarketOrder(TradeType, Symbol, Volume, Label)
    code = re.sub(
        r'ExecuteMarketOrder\(\s*(TradeType\.\w+)\s*,\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,)]+)\s*\)',
        r'ExecuteMarketOrder(\1, \2, \3, \4, StopLossPips, null)',
        code
    )
    
    return code


def _generate_take_profit_patch(code: str) -> str:
    """Generate patch to add take profit parameter"""
    # Add parameter
    if 'TakeProfitPips' not in code:
        # Find StopLossPips or class body
        if 'StopLossPips' in code:
            pattern = r'(public double StopLossPips.*?\n)'
            insertion = r'''\1
        [Parameter("Take Profit (Pips)", DefaultValue = 50, MinValue = 10, MaxValue = 500)]
        public double TakeProfitPips { get; set; }
'''
            code = re.sub(pattern, insertion, code)
        else:
            class_match = re.search(r'(public class \w+ : Robot\s*\{)', code)
            if class_match:
                insertion_point = class_match.end()
                parameter_code = '''
        
        [Parameter("Take Profit (Pips)", DefaultValue = 50, MinValue = 10, MaxValue = 500)]
        public double TakeProfitPips { get; set; }
'''
                code = code[:insertion_point] + parameter_code + code[insertion_point:]
    
    # Update ExecuteMarketOrder calls - replace null with TakeProfitPips
    code = re.sub(
        r'ExecuteMarketOrder\(([^)]+),\s*([^,)]+)\s*,\s*null\s*\)',
        r'ExecuteMarketOrder(\1, \2, TakeProfitPips)',
        code
    )
    
    return code


def _generate_using_statements_patch(code: str, missing_usings: List[str]) -> str:
    """Add missing using statements"""
    # Find existing using statements
    using_match = re.search(r'(using .*?;)\s*\n', code)
    if using_match:
        last_using_pos = code.rfind('using ', 0, using_match.end() + 100)
        last_using_end = code.find(';', last_using_pos) + 1
        
        # Add new using statements
        new_usings = '\n'.join([f'using {u};' for u in missing_usings])
        code = code[:last_using_end] + '\n' + new_usings + code[last_using_end:]
    else:
        # Add at the beginning
        new_usings = '\n'.join([f'using {u};' for u in missing_usings])
        code = new_usings + '\n\n' + code
    
    return code


def _generate_type_conversion_patch(code: str, errors: List[str]) -> str:
    """Fix type conversion issues"""
    # Common pattern: int parameter assigned double value
    # Look for: int something = 14.5; → int something = 14;
    code = re.sub(r'(int\s+\w+\s*=\s*)(\d+\.\d+)', r'\1(int)\2', code)
    
    # Fix double to int in Parameter DefaultValue
    # [Parameter("...", DefaultValue = 14.5)] where type is int
    code = re.sub(
        r'(\[Parameter\([^]]+DefaultValue\s*=\s*)(\d+\.\d+)(\s*[,\)])',
        lambda m: m.group(1) + str(int(float(m.group(2)))) + m.group(3),
        code
    )
    
    return code


def _generate_null_checks_patch(code: str) -> str:
    """Add null checks for indicator values"""
    # Find OnBar method
    onbar_match = re.search(r'(protected override void OnBar\(\)\s*\{)', code)
    if onbar_match:
        insertion_point = onbar_match.end()
        
        # Detect indicators used
        null_checks = []
        if '_rsi' in code.lower():
            null_checks.append('if (_rsi == null || double.IsNaN(_rsi.Result.LastValue)) return;')
        if '_macd' in code.lower():
            null_checks.append('if (_macd == null) return;')
        if '_ema' in code.lower():
            null_checks.append('if (_ema == null || double.IsNaN(_ema.Result.LastValue)) return;')
        
        if null_checks:
            check_code = '\n            ' + '\n            '.join(null_checks) + '\n'
            code = code[:insertion_point] + check_code + code[insertion_point:]
    
    return code


def _generate_position_check_patch(code: str) -> str:
    """Add position check before ExecuteMarketOrder"""
    # Find ExecuteMarketOrder calls and add check before
    # This is complex, so we'll add a general check in OnBar
    onbar_match = re.search(r'(protected override void OnBar\(\)\s*\{)', code)
    if onbar_match:
        insertion_point = onbar_match.end()
        check_code = '''
            
            // Prevent multiple positions
            if (Positions.FindAll(Label).Length > 0)
                return;
            
'''
        code = code[:insertion_point] + check_code + code[insertion_point:]
    
    return code


def _generate_api_update_patch(code: str) -> str:
    """Update deprecated API calls"""
    # Replace MarketSeries with Bars
    code = code.replace('MarketSeries.Close', 'Bars.ClosePrices')
    code = code.replace('MarketSeries.Open', 'Bars.OpenPrices')
    code = code.replace('MarketSeries.High', 'Bars.HighPrices')
    code = code.replace('MarketSeries.Low', 'Bars.LowPrices')
    code = code.replace('MarketSeries', 'Bars')
    
    # Replace Symbol.PipSize with Symbol.TickSize
    code = code.replace('Symbol.PipSize', 'Symbol.TickSize')
    
    return code


def apply_fix(code: str, fix_id: str, code_patch: str = None) -> Dict[str, Any]:
    """
    Apply a specific fix to the code
    
    Args:
        code: Original code
        fix_id: ID of the fix to apply
        code_patch: Pre-generated patch (optional)
    
    Returns:
        Dict with updated code and status
    """
    if not code_patch:
        return {
            "success": False,
            "code": code,
            "message": "No patch available for this fix"
        }
    
    return {
        "success": True,
        "code": code_patch,
        "message": f"Fix '{fix_id}' applied successfully"
    }


def apply_all_fixes(code: str, suggestions: List[Dict]) -> Dict[str, Any]:
    """
    Apply all auto-fixable suggestions
    
    Args:
        code: Original code
        suggestions: List of suggestions from suggest_fixes
    
    Returns:
        Dict with updated code and applied fixes
    """
    updated_code = code
    applied_fixes = []
    
    for suggestion in suggestions:
        if suggestion.get("auto_fixable", False) and suggestion.get("code_patch"):
            updated_code = suggestion["code_patch"]
            applied_fixes.append(suggestion["id"])
    
    return {
        "success": True,
        "code": updated_code,
        "applied_fixes": applied_fixes,
        "count": len(applied_fixes),
        "message": f"Applied {len(applied_fixes)} fix(es) successfully"
    }
