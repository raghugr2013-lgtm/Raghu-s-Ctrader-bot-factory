"""
Enhanced C# Validation Engine
Simulates Roslyn compilation with comprehensive error detection
"""

import re
from typing import Dict, List, Tuple


class RoslynValidator:
    """Enhanced C# validator that mimics Roslyn compilation behavior"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.line_number = 0
        
    def validate(self, code: str) -> Dict:
        """
        Comprehensive C# validation
        Returns: {is_valid, errors, warnings, diagnostics}
        """
        self.errors = []
        self.warnings = []
        
        # Split code into lines for line-by-line analysis
        lines = code.split('\n')
        
        # Phase 1: Structural validation
        self._validate_structure(code, lines)
        
        # Phase 2: Syntax validation
        self._validate_syntax(code, lines)
        
        # Phase 3: cTrader API validation
        self._validate_ctrader_api(code, lines)
        
        # Phase 4: Type checking (basic)
        self._validate_types(code, lines)
        
        is_valid = len(self.errors) == 0
        
        return {
            "is_valid": is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "message": "Compilation successful" if is_valid else f"Compilation failed with {len(self.errors)} error(s)",
            "diagnostics": {
                "total_lines": len(lines),
                "error_count": len(self.errors),
                "warning_count": len(self.warnings)
            }
        }
    
    def _validate_structure(self, code: str, lines: List[str]):
        """Validate basic C# structure"""
        
        # Check for namespace
        if not re.search(r'namespace\s+\w+', code):
            self.warnings.append("CS0010: Missing namespace declaration (recommended for cTrader bots)")
        
        # Check for Robot inheritance
        if not re.search(r'class\s+\w+\s*:\s*Robot', code):
            self.errors.append("CS1729: Bot class must inherit from 'Robot' base class")
        
        # Check for required using statements
        required_usings = {
            'cAlgo.API': 'CS0246: Required using directive - cTrader API not accessible',
            'System': 'CS0246: Missing System namespace'
        }
        
        for using, error in required_usings.items():
            if f'using {using}' not in code and f'using {using};' not in code:
                self.warnings.append(f"Warning: {error}")
        
        # Check brace matching
        open_count = code.count('{')
        close_count = code.count('}')
        if open_count != close_count:
            self.errors.append(f"CS1513: Brace mismatch - {open_count} opening vs {close_count} closing")
        
        # Check for OnStart method
        if not re.search(r'protected\s+override\s+void\s+OnStart\s*\(', code):
            self.errors.append("CS0115: Missing required OnStart() override method")
    
    def _validate_syntax(self, code: str, lines: List[str]):
        """Validate C# syntax"""
        
        # Check for semicolons
        in_block_comment = False
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip comments
            if line_stripped.startswith('//'):
                continue
            if '/*' in line_stripped:
                in_block_comment = True
            if '*/' in line_stripped:
                in_block_comment = False
                continue
            if in_block_comment:
                continue
            
            # Skip empty lines and structural lines
            if not line_stripped or line_stripped in ['{', '}']:
                continue
            
            # Check for statements that need semicolons
            needs_semicolon = (
                line_stripped and
                not line_stripped.startswith('namespace') and
                not line_stripped.startswith('using') and
                not line_stripped.startswith('public') and
                not line_stripped.startswith('private') and
                not line_stripped.startswith('protected') and
                not line_stripped.startswith('[') and
                not line_stripped.startswith('#') and
                not line_stripped.startswith('if') and
                not line_stripped.startswith('else') and
                not line_stripped.startswith('for') and
                not line_stripped.startswith('while') and
                not line_stripped.startswith('foreach') and
                not line_stripped.startswith('switch') and
                not line_stripped.startswith('try') and
                not line_stripped.startswith('catch') and
                not line_stripped.startswith('finally') and
                not line_stripped.endswith('{') and
                not line_stripped.endswith('}') and
                not line_stripped.endswith(';') and
                not line_stripped.endswith(',') and
                ':' not in line_stripped[-3:]  # Not a label or case
            )
            
            if needs_semicolon and (re.search(r'\w+\s*=\s*.+', line_stripped) or 
                                   re.search(r'\w+\(.*\)', line_stripped) or
                                   'return' in line_stripped):
                # Check if this might need a semicolon
                if i < 5:  # Only report first few to avoid spam
                    self.errors.append(f"CS1002: Line {i+1}: Expected ';' - '{line_stripped[:50]}...'")
        
        # Check for variable declarations
        invalid_declarations = re.findall(r'(var\s+\w+\s*;)', code)
        for decl in invalid_declarations:
            self.errors.append(f"CS0818: Implicitly typed variables must be initialized - '{decl}'")
        
        # Check for invalid method calls
        if re.search(r'\.\s*\(', code):
            self.errors.append("CS1001: Invalid method call syntax")
    
    def _validate_ctrader_api(self, code: str, lines: List[str]):
        """Validate cTrader-specific API usage"""
        
        # Check for Symbol usage
        if 'Symbol' in code and not re.search(r'Symbol\.(Bid|Ask|Spread|TickSize|PipSize)', code):
            self.warnings.append("Ensure proper Symbol property usage (e.g., Symbol.Bid, Symbol.Ask)")
        
        # Check for Positions usage
        if 'Positions' in code and not re.search(r'Positions\.(Open|Close|Find)', code):
            self.warnings.append("Verify Positions collection usage")
        
        # Check for trading operations
        trading_methods = ['ExecuteMarketOrder', 'PlaceStopOrder', 'PlaceLimitOrder', 'ModifyPosition', 'ClosePosition']
        has_trading = any(method in code for method in trading_methods)
        
        if not has_trading:
            self.warnings.append("No trading operations detected - bot may not execute trades")
        
        # Check for risk management
        if has_trading:
            if 'StopLoss' not in code:
                self.warnings.append("Consider adding StopLoss for risk management")
            if 'TakeProfit' not in code:
                self.warnings.append("Consider adding TakeProfit for trade management")
        
        # Check for OnTick or OnBar
        if not re.search(r'protected\s+override\s+void\s+OnTick\s*\(', code) and \
           not re.search(r'protected\s+override\s+void\s+OnBar\s*\(', code):
            self.warnings.append("Consider implementing OnTick() or OnBar() for trading logic")
        
        # Check for indicators
        common_indicators = ['SimpleMovingAverage', 'RelativeStrengthIndex', 'MovingAverage', 
                           'ExponentialMovingAverage', 'MACD', 'BollingerBands']
        indicator_count = sum(1 for ind in common_indicators if ind in code)
        
        if indicator_count == 0 and has_trading:
            self.warnings.append("No indicators detected - consider technical analysis for trade decisions")
    
    def _validate_types(self, code: str, lines: List[str]):
        """Basic type checking"""
        
        # Check for common type errors
        if re.search(r'int\s+\w+\s*=\s*["\']', code):
            self.errors.append("CS0029: Cannot implicitly convert type 'string' to 'int'")
        
        if re.search(r'string\s+\w+\s*=\s*\d+\s*;', code):
            self.errors.append("CS0029: Cannot implicitly convert type 'int' to 'string'")
        
        # Check for null reference potential
        if re.search(r'\w+\.(?:Bid|Ask|Open)\s+', code) and 'null' not in code:
            self.warnings.append("Consider null checks for Symbol and Position properties")
        
        # Check parameter types in methods
        # Note: We skip the void return check here as it produces too many false positives
        # Valid void methods can have "return;" statements for early exit
        # This check would require full AST parsing to be accurate
        pass


# Singleton instance
roslyn_validator = RoslynValidator()


def validate_csharp_code(code: str) -> Dict:
    """
    Main validation entry point
    Uses enhanced Roslyn-like validation
    """
    return roslyn_validator.validate(code)
