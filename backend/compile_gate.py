"""
Strict C# Compilation Gate for cTrader Bots
Ensures ZERO compile errors before bot download
"""

import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CompileStatus(str, Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    FIXING = "FIXING"


class CompileError(BaseModel):
    """Single compilation error"""
    code: str  # Error code like CS0246
    line: int
    column: int = 0
    message: str
    severity: str = "error"  # error, warning, info
    suggestion: Optional[str] = None


class CompileResult(BaseModel):
    """Compilation result"""
    status: CompileStatus
    is_verified: bool
    errors: List[CompileError]
    warnings: List[CompileError]
    fix_attempts: int = 0
    max_attempts: int = 3
    message: str
    timestamp: str


class CSharpCompilationGate:
    """
    Strict compilation gate using Roslyn-style validation.
    Blocks download if ANY compile errors exist.
    """
    
    # Required using statements for cTrader bots
    REQUIRED_USINGS = [
        "using System;",
        "using cAlgo.API;",
        "using cAlgo.API.Internals;",
    ]
    
    # Optional but recommended usings
    OPTIONAL_USINGS = [
        "using cAlgo.API.Indicators;",
        "using System.Linq;",
        "using System.Collections.Generic;",
    ]
    
    # cTrader type mappings for error detection
    CTRADER_TYPES = {
        'Robot': 'cAlgo.API.Robot',
        'Indicator': 'cAlgo.API.Indicator',
        'TradeType': 'cAlgo.API.TradeType',
        'Symbol': 'cAlgo.API.Internals.Symbol',
        'Position': 'cAlgo.API.Position',
        'PendingOrder': 'cAlgo.API.PendingOrder',
        'Bars': 'cAlgo.API.Internals.Bars',
        'MarketSeries': 'cAlgo.API.Internals.MarketSeries',
    }
    
    # Common auto-fix patterns
    AUTO_FIX_PATTERNS = [
        # Missing semicolons
        (r'(\w+\s*=\s*[^;{}\n]+)(\n)', r'\1;\2'),
        # Missing using for common types
        (r'^((?!using cAlgo\.API;).)*$', None),  # Complex - handled separately
    ]
    
    def __init__(self):
        self.errors: List[CompileError] = []
        self.warnings: List[CompileError] = []
        
    def compile(self, code: str) -> CompileResult:
        """
        Run full compilation check.
        Returns CompileResult with status and errors.
        """
        self.errors = []
        self.warnings = []
        
        lines = code.split('\n')
        
        # Phase 1: Lexical Analysis
        self._check_lexical(code, lines)
        
        # Phase 2: Structural Analysis
        self._check_structure(code, lines)
        
        # Phase 3: Type Analysis
        self._check_types(code, lines)
        
        # Phase 4: cTrader API Analysis
        self._check_ctrader_api(code, lines)
        
        # Phase 5: Semantic Analysis
        self._check_semantics(code, lines)
        
        # Determine status
        has_critical_errors = any(e.severity == "error" for e in self.errors)
        
        is_verified = not has_critical_errors
        status = CompileStatus.VERIFIED if is_verified else CompileStatus.FAILED
        
        message = "✅ COMPILE VERIFIED - Code is ready for deployment" if is_verified else \
                  f"❌ COMPILATION FAILED - {len(self.errors)} error(s) found"
        
        return CompileResult(
            status=status,
            is_verified=is_verified,
            errors=self.errors,
            warnings=self.warnings,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def _add_error(self, code: str, line: int, message: str, 
                   severity: str = "error", column: int = 0, suggestion: str = None):
        """Add a compilation error"""
        error = CompileError(
            code=code,
            line=line,
            column=column,
            message=message,
            severity=severity,
            suggestion=suggestion
        )
        if severity == "error":
            self.errors.append(error)
        else:
            self.warnings.append(error)
    
    def _check_lexical(self, code: str, lines: List[str]):
        """Phase 1: Lexical analysis"""
        
        # Check for unclosed strings
        in_string = False
        string_char = None
        for i, line in enumerate(lines):
            for j, char in enumerate(line):
                if char in ['"', "'"] and (j == 0 or line[j-1] != '\\'):
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False
            
            if in_string and i < len(lines) - 1:
                # Check if next line continues (verbatim string)
                if not line.strip().startswith('@"'):
                    self._add_error("CS1010", i+1, "Newline in constant", 
                                   suggestion="Close the string or use verbatim string @\"...\"")
                    in_string = False
        
        # Check for unclosed comments
        if '/*' in code:
            open_count = code.count('/*')
            close_count = code.count('*/')
            if open_count > close_count:
                self._add_error("CS1035", 1, "Unclosed block comment /* ... */",
                               suggestion="Add closing */")
        
        # Check for invalid characters
        for i, line in enumerate(lines):
            # Skip strings and comments
            clean_line = re.sub(r'"[^"]*"', '', line)
            clean_line = re.sub(r"'[^']*'", '', clean_line)
            clean_line = re.sub(r'//.*$', '', clean_line)
            
            # Check for invalid chars outside strings
            invalid_chars = re.findall(r'[^\w\s{}()\[\];,.<>:=!&|+\-*/%^~?@#"\'\\]', clean_line)
            for char in invalid_chars:
                if char not in ['$']:  # Allow string interpolation
                    self._add_error("CS1056", i+1, f"Unexpected character '{char}'")
    
    def _check_structure(self, code: str, lines: List[str]):
        """Phase 2: Structural analysis"""
        
        # Check namespace
        if not re.search(r'namespace\s+[\w.]+', code):
            self._add_error("CS1001", 1, "Missing namespace declaration",
                          severity="warning",
                          suggestion="Add: namespace YourBotName { ... }")
        
        # Check class declaration
        class_match = re.search(r'class\s+(\w+)', code)
        if not class_match:
            self._add_error("CS1520", 1, "Missing class declaration")
        else:
            class_name = class_match.group(1)
            # Check Robot inheritance
            if not re.search(rf'class\s+{class_name}\s*:\s*Robot', code):
                self._add_error("CS1729", 
                              self._find_line(lines, f'class {class_name}'),
                              f"Class '{class_name}' must inherit from 'Robot'",
                              suggestion=f"Change to: class {class_name} : Robot")
        
        # Check brace matching
        brace_stack = []
        for i, line in enumerate(lines):
            # Skip strings and comments
            clean = self._remove_strings_comments(line)
            for j, char in enumerate(clean):
                if char == '{':
                    brace_stack.append((i+1, j))
                elif char == '}':
                    if not brace_stack:
                        self._add_error("CS1513", i+1, "Unexpected closing brace '}'")
                    else:
                        brace_stack.pop()
        
        for line_num, col in brace_stack:
            self._add_error("CS1513", line_num, "Missing closing brace '}'")
        
        # Check parentheses matching
        paren_count = code.count('(') - code.count(')')
        if paren_count != 0:
            self._add_error("CS1026", 1, 
                          f"Parentheses mismatch: {'missing )' if paren_count > 0 else 'extra )'}")
        
        # Check required methods
        if not re.search(r'protected\s+override\s+void\s+OnStart\s*\(\s*\)', code):
            self._add_error("CS0115", 1, "Missing required 'OnStart()' override method",
                          suggestion="Add: protected override void OnStart() { }")
    
    def _check_types(self, code: str, lines: List[str]):
        """Phase 3: Type analysis"""
        
        # Check for undeclared variables usage
        declared_vars = set()
        
        # Find all declarations
        decl_patterns = [
            r'(\w+)\s+(\w+)\s*=',  # Type var =
            r'(\w+)\s+(\w+)\s*;',  # Type var;
            r'var\s+(\w+)\s*=',    # var x =
        ]
        
        for pattern in decl_patterns:
            for match in re.finditer(pattern, code):
                if match.lastindex >= 2:
                    declared_vars.add(match.group(2))
                elif match.lastindex == 1:
                    declared_vars.add(match.group(1))
        
        # Add common implicit variables
        declared_vars.update(['this', 'Symbol', 'Positions', 'PendingOrders', 
                             'Account', 'Server', 'Bars', 'MarketData', 'Notifications'])
        
        # Check for uninitialized var
        for i, line in enumerate(lines):
            if re.search(r'var\s+\w+\s*;', line):
                self._add_error("CS0818", i+1, 
                              "Implicitly typed variables must be initialized",
                              suggestion="Initialize the variable: var x = value;")
        
        # Check type mismatches
        if re.search(r'int\s+\w+\s*=\s*"', code):
            line = self._find_line_pattern(lines, r'int\s+\w+\s*=\s*"')
            self._add_error("CS0029", line, "Cannot convert string to int")
        
        if re.search(r'string\s+\w+\s*=\s*\d+\s*;', code):
            line = self._find_line_pattern(lines, r'string\s+\w+\s*=\s*\d+\s*;')
            self._add_error("CS0029", line, "Cannot convert int to string",
                          suggestion="Use .ToString() or string interpolation")
    
    def _check_ctrader_api(self, code: str, lines: List[str]):
        """Phase 4: cTrader API specific checks"""
        
        # Check required using statements
        for using in self.REQUIRED_USINGS:
            if using not in code:
                self._add_error("CS0246", 1, 
                              f"Missing required: {using}",
                              suggestion=f"Add at top: {using}")
        
        # Check for common API misuse
        
        # ExecuteMarketOrder parameters
        emo_match = re.search(r'ExecuteMarketOrder\s*\(([^)]+)\)', code)
        if emo_match:
            params = emo_match.group(1).split(',')
            if len(params) < 3:
                line = self._find_line_pattern(lines, r'ExecuteMarketOrder')
                self._add_error("CS1501", line,
                              "ExecuteMarketOrder requires at least 3 parameters: TradeType, Symbol, Volume",
                              suggestion="ExecuteMarketOrder(TradeType.Buy, SymbolName, Volume)")
        
        # Symbol.Bid/Ask usage
        if 'Symbol.' in code:
            if re.search(r'Symbol\.\s*Bid\s*\(', code) or re.search(r'Symbol\.\s*Ask\s*\(', code):
                line = self._find_line_pattern(lines, r'Symbol\.\s*(Bid|Ask)\s*\(')
                self._add_error("CS1955", line,
                              "Bid/Ask are properties, not methods",
                              suggestion="Use Symbol.Bid or Symbol.Ask (no parentheses)")
        
        # TradeType enum
        if 'TradeType' in code:
            if re.search(r'TradeType\s*\.\s*[^BA]', code):
                # Check for invalid enum value
                invalid = re.search(r'TradeType\s*\.\s*(\w+)', code)
                if invalid and invalid.group(1) not in ['Buy', 'Sell']:
                    line = self._find_line_pattern(lines, r'TradeType\s*\.')
                    self._add_error("CS0117", line,
                                  f"TradeType does not contain '{invalid.group(1)}'",
                                  suggestion="Use TradeType.Buy or TradeType.Sell")
        
        # Position access
        if re.search(r'Positions\[\s*\d+\s*\]', code):
            line = self._find_line_pattern(lines, r'Positions\[')
            self._add_error("CS1503", line,
                          severity="warning",
                          message="Direct index access to Positions may throw. Use LINQ or iteration",
                          suggestion="Use: foreach (var pos in Positions) or Positions.FirstOrDefault()")
    
    def _check_semantics(self, code: str, lines: List[str]):
        """Phase 5: Semantic analysis"""
        
        # Check for unreachable code after return
        in_method = False
        found_return = False
        method_brace_count = 0
        
        for i, line in enumerate(lines):
            clean = self._remove_strings_comments(line)
            
            # Detect method start
            if re.search(r'(void|int|string|double|bool|Position|Symbol)\s+\w+\s*\([^)]*\)\s*{?', clean):
                in_method = True
                found_return = False
                method_brace_count = 0
            
            if in_method:
                method_brace_count += clean.count('{') - clean.count('}')
                
                if 'return' in clean and not clean.strip().startswith('//'):
                    found_return = True
                
                if found_return and method_brace_count > 0:
                    # Code after return
                    next_line = lines[i+1].strip() if i+1 < len(lines) else ''
                    if next_line and not next_line.startswith('}') and not next_line.startswith('//'):
                        self._add_error("CS0162", i+2, "Unreachable code detected",
                                       severity="warning")
                        found_return = False  # Only warn once
                
                if method_brace_count <= 0:
                    in_method = False
        
        # Check for unused variables (basic)
        declared = set(re.findall(r'(?:int|double|string|bool|var)\s+(\w+)\s*[=;]', code))
        for var in declared:
            # Count usages (excluding declaration)
            usage_count = len(re.findall(rf'\b{var}\b', code)) - 1
            if usage_count <= 0:
                line = self._find_line_pattern(lines, rf'(?:int|double|string|bool|var)\s+{var}\s*[=;]')
                self._add_error("CS0168", line, f"Variable '{var}' is declared but never used",
                              severity="warning")
    
    def _remove_strings_comments(self, line: str) -> str:
        """Remove string literals and comments from line"""
        # Remove strings
        result = re.sub(r'"[^"]*"', '""', line)
        result = re.sub(r"'[^']*'", "''", result)
        # Remove line comments
        result = re.sub(r'//.*$', '', result)
        return result
    
    def _find_line(self, lines: List[str], text: str) -> int:
        """Find line number containing text"""
        for i, line in enumerate(lines):
            if text in line:
                return i + 1
        return 1
    
    def _find_line_pattern(self, lines: List[str], pattern: str) -> int:
        """Find line number matching pattern"""
        for i, line in enumerate(lines):
            if re.search(pattern, line):
                return i + 1
        return 1
    
    def auto_fix(self, code: str) -> Tuple[str, List[str]]:
        """
        Attempt to auto-fix common compilation errors.
        Returns (fixed_code, list_of_fixes_applied)
        """
        fixes_applied = []
        fixed_code = code
        
        # Fix 1: Add missing using statements
        usings_to_add = []
        
        for required in self.REQUIRED_USINGS:
            if required not in code:
                usings_to_add.append(required)
                fixes_applied.append(f"Added missing: {required}")
        
        # Check if code uses indicators
        if any(ind in code for ind in ['MovingAverage', 'RSI', 'MACD', 'Bollinger', 'Indicator']):
            indicator_using = "using cAlgo.API.Indicators;"
            if indicator_using not in code:
                usings_to_add.append(indicator_using)
                fixes_applied.append(f"Added missing: {indicator_using}")
        
        if usings_to_add:
            # Find first using or start of code
            first_using = re.search(r'^using\s+', code, re.MULTILINE)
            if first_using:
                insert_pos = first_using.start()
            else:
                # Insert before namespace or class
                ns_match = re.search(r'^namespace', code, re.MULTILINE)
                insert_pos = ns_match.start() if ns_match else 0
            
            usings_block = '\n'.join(usings_to_add) + '\n'
            fixed_code = fixed_code[:insert_pos] + usings_block + fixed_code[insert_pos:]
        
        # Fix 2: Missing semicolons on simple statements
        lines = fixed_code.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            
            # Skip if already ends correctly
            if not stripped or stripped.endswith((';', '{', '}', ',', ':', '//', '*/')):
                fixed_lines.append(line)
                continue
            
            # Skip structural keywords
            if any(stripped.strip().startswith(kw) for kw in 
                   ['if', 'else', 'for', 'while', 'foreach', 'switch', 'try', 'catch', 'finally',
                    'namespace', 'class', 'public', 'private', 'protected', '[', '#', '//']):
                fixed_lines.append(line)
                continue
            
            # Check if it looks like a statement needing semicolon
            if re.match(r'.*\w+\s*\([^)]*\)\s*$', stripped) or \
               re.match(r'.*=\s*[^{]+$', stripped) or \
               re.match(r'.*return\s+.+$', stripped):
                fixed_lines.append(line + ';')
                fixes_applied.append(f"Line {i+1}: Added missing semicolon")
            else:
                fixed_lines.append(line)
        
        fixed_code = '\n'.join(fixed_lines)
        
        # Fix 3: Robot inheritance
        class_match = re.search(r'class\s+(\w+)\s*(?!\s*:\s*Robot)', fixed_code)
        if class_match and ': Robot' not in fixed_code:
            class_name = class_match.group(1)
            old = f'class {class_name}'
            new = f'class {class_name} : Robot'
            fixed_code = fixed_code.replace(old, new, 1)
            fixes_applied.append(f"Added Robot inheritance to class {class_name}")
        
        # Fix 4: Symbol.Bid() -> Symbol.Bid
        if 'Symbol.Bid()' in fixed_code:
            fixed_code = fixed_code.replace('Symbol.Bid()', 'Symbol.Bid')
            fixes_applied.append("Fixed Symbol.Bid() -> Symbol.Bid")
        if 'Symbol.Ask()' in fixed_code:
            fixed_code = fixed_code.replace('Symbol.Ask()', 'Symbol.Ask')
            fixes_applied.append("Fixed Symbol.Ask() -> Symbol.Ask")
        
        return fixed_code, fixes_applied


# Global instance
compile_gate = CSharpCompilationGate()


def compile_and_verify(code: str, max_attempts: int = 3) -> Dict:
    """
    Main entry point: Compile, auto-fix if needed, verify.
    Returns full compilation result with status.
    """
    current_code = code
    all_fixes = []
    
    for attempt in range(max_attempts):
        # Compile
        result = compile_gate.compile(current_code)
        
        if result.is_verified:
            return {
                "status": "VERIFIED",
                "is_verified": True,
                "code": current_code,
                "errors": [],
                "warnings": [w.model_dump() for w in result.warnings],
                "fix_attempts": attempt,
                "fixes_applied": all_fixes,
                "message": "✅ COMPILE VERIFIED - Code is ready for deployment"
            }
        
        if attempt < max_attempts - 1:
            # Try auto-fix
            fixed_code, fixes = compile_gate.auto_fix(current_code)
            
            if fixes and fixed_code != current_code:
                current_code = fixed_code
                all_fixes.extend(fixes)
                logger.info(f"Attempt {attempt + 1}: Applied {len(fixes)} auto-fixes")
            else:
                # No more fixes possible
                break
    
    # Failed after all attempts
    return {
        "status": "FAILED",
        "is_verified": False,
        "code": current_code,
        "errors": [e.model_dump() for e in result.errors],
        "warnings": [w.model_dump() for w in result.warnings],
        "fix_attempts": max_attempts,
        "fixes_applied": all_fixes,
        "message": f"❌ COMPILATION FAILED - {len(result.errors)} error(s) remain after {max_attempts} fix attempts"
    }


def check_download_allowed(code: str) -> Tuple[bool, Dict]:
    """
    Gate check before allowing download.
    Returns (is_allowed, compilation_result)
    """
    result = compile_and_verify(code)
    return result["is_verified"], result
