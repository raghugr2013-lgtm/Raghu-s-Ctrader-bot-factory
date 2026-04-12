"""
Auto-Fix Compilation Loop with Real .NET SDK
Iteratively fixes compilation errors until code compiles successfully.
"""

import logging
from typing import Dict, List, Tuple, Optional
from real_csharp_compiler import RealCSharpCompiler, CompilationError
import re

logger = logging.getLogger(__name__)


class CompilationAutoFixer:
    """
    Automatically fixes common compilation errors using pattern matching.
    Works with REAL .NET SDK compiler output.
    """
    
    def __init__(self):
        self.compiler = RealCSharpCompiler()
        self.max_iterations = 5
    
    def compile_with_auto_fix(self, code: str, bot_name: str = "GeneratedBot") -> Dict:
        """
        Compile code and auto-fix errors iteratively.
        
        Returns:
            Dict with final compilation result and fix history
        """
        current_code = code
        fixes_applied = []
        iteration = 0
        
        logger.info(f"Starting auto-fix compilation loop (max {self.max_iterations} iterations)")
        
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Iteration {iteration}/{self.max_iterations}")
            
            # Compile
            result = self.compiler.compile(current_code, bot_name)
            
            if result.success:
                logger.info(f"✅ Compilation successful on iteration {iteration}")
                return {
                    "success": True,
                    "code": current_code,
                    "compilation_time_ms": result.compilation_time_ms,
                    "iterations": iteration,
                    "fixes_applied": fixes_applied,
                    "warnings": [w.to_dict() for w in result.warnings],
                    "message": f"✅ Compiled successfully after {iteration} iteration(s)"
                }
            
            # Try to fix errors
            logger.info(f"Found {result.error_count} error(s), attempting fixes...")
            
            fixed_code, applied_fixes = self._attempt_fixes(current_code, result.errors)
            
            if not applied_fixes:
                # No fixes could be applied
                logger.warning("No automatic fixes available for current errors")
                break
            
            # Apply fixes
            current_code = fixed_code
            fixes_applied.extend(applied_fixes)
            logger.info(f"Applied {len(applied_fixes)} fix(es), retrying compilation...")
        
        # Failed after all iterations
        logger.error(f"❌ Compilation failed after {iteration} iterations")
        return {
            "success": False,
            "code": current_code,
            "iterations": iteration,
            "fixes_applied": fixes_applied,
            "errors": [e.to_dict() for e in result.errors],
            "warnings": [w.to_dict() for w in result.warnings],
            "message": f"❌ Failed to compile after {iteration} iteration(s) - {result.error_count} error(s) remain"
        }
    
    def _attempt_fixes(self, code: str, errors: List[CompilationError]) -> Tuple[str, List[str]]:
        """
        Attempt to fix compilation errors automatically.
        
        Returns:
            (fixed_code, list_of_fixes_applied)
        """
        fixed_code = code
        fixes = []
        
        for error in errors:
            # Try each fix pattern
            fix_result = self._fix_single_error(fixed_code, error)
            
            if fix_result:
                fixed_code, fix_description = fix_result
                fixes.append(fix_description)
        
        return fixed_code, fixes
    
    def _fix_single_error(self, code: str, error: CompilationError) -> Optional[Tuple[str, str]]:
        """
        Attempt to fix a single compilation error.
        
        Returns:
            (fixed_code, fix_description) or None if no fix available
        """
        error_code = error.code
        error_msg = error.message.lower()
        
        # CS0246: The type or namespace name could not be found
        if error_code == "CS0246":
            if "using directive" in error_msg or "are you missing" in error_msg:
                return self._fix_missing_using(code, error)
        
        # CS1002: ; expected
        elif error_code == "CS1002":
            return self._fix_missing_semicolon(code, error)
        
        # CS0103: The name does not exist in the current context
        elif error_code == "CS0103":
            return self._fix_undefined_name(code, error)
        
        # CS1061: Type does not contain a definition for member
        elif error_code == "CS1061":
            return self._fix_invalid_member(code, error)
        
        # CS0029: Cannot implicitly convert type
        elif error_code == "CS0029":
            return self._fix_type_conversion(code, error)
        
        # CS0019: Operator cannot be applied to operands
        elif error_code == "CS0019":
            return self._fix_invalid_operator(code, error)
        
        return None
    
    def _fix_missing_using(self, code: str, error: CompilationError) -> Optional[Tuple[str, str]]:
        """Fix missing using directive"""
        # Common missing usings for cTrader
        missing_usings = {
            "Bars": "using cAlgo.API.Internals;",
            "Symbol": "using cAlgo.API.Internals;",
            "MovingAverage": "using cAlgo.API.Indicators;",
            "RelativeStrengthIndex": "using cAlgo.API.Indicators;",
            "TradeType": "using cAlgo.API;",
            "Position": "using cAlgo.API;",
            "System.Linq": "using System.Linq;",
        }
        
        for type_name, using_directive in missing_usings.items():
            if type_name in error.message and using_directive not in code:
                # Add using at the top
                lines = code.split('\n')
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith('using '):
                        insert_index = i + 1
                
                lines.insert(insert_index, using_directive)
                fixed_code = '\n'.join(lines)
                return fixed_code, f"Added missing using: {using_directive}"
        
        return None
    
    def _fix_missing_semicolon(self, code: str, error: CompilationError) -> Optional[Tuple[str, str]]:
        """Fix missing semicolon"""
        if error.line > 0:
            lines = code.split('\n')
            line_index = error.line - 1
            
            if line_index < len(lines):
                line = lines[line_index]
                if not line.rstrip().endswith((';', '{', '}', ':')):
                    lines[line_index] = line.rstrip() + ';'
                    fixed_code = '\n'.join(lines)
                    return fixed_code, f"Added missing semicolon at line {error.line}"
        
        return None
    
    def _fix_undefined_name(self, code: str, error: CompilationError) -> Optional[Tuple[str, str]]:
        """Fix undefined name (common typos)"""
        # Extract variable name from error
        match = re.search(r"'(\w+)'", error.message)
        if not match:
            return None
        
        undefined_name = match.group(1)
        
        # Common typos in cTrader API
        corrections = {
            "Bid": "Symbol.Bid",
            "Ask": "Symbol.Ask",
            "ClosePrices": "Bars.ClosePrices",
            "OpenPrices": "Bars.OpenPrices",
            "HighPrices": "Bars.HighPrices",
            "LowPrices": "Bars.LowPrices",
        }
        
        if undefined_name in corrections:
            corrected = corrections[undefined_name]
            fixed_code = code.replace(f" {undefined_name}", f" {corrected}")
            fixed_code = fixed_code.replace(f"({undefined_name}", f"({corrected}")
            return fixed_code, f"Corrected '{undefined_name}' to '{corrected}'"
        
        return None
    
    def _fix_invalid_member(self, code: str, error: CompilationError) -> Optional[Tuple[str, str]]:
        """Fix invalid member access"""
        # Common mistakes: Symbol.Bid() -> Symbol.Bid
        if "Symbol.Bid()" in code:
            fixed_code = code.replace("Symbol.Bid()", "Symbol.Bid")
            return fixed_code, "Fixed Symbol.Bid() -> Symbol.Bid"
        
        if "Symbol.Ask()" in code:
            fixed_code = code.replace("Symbol.Ask()", "Symbol.Ask")
            return fixed_code, "Fixed Symbol.Ask() -> Symbol.Ask"
        
        return None
    
    def _fix_type_conversion(self, code: str, error: CompilationError) -> Optional[Tuple[str, str]]:
        """Fix type conversion issues"""
        # Common: int to double
        if "int" in error.message and "double" in error.message:
            # No automatic fix for this - requires manual intervention
            pass
        
        return None
    
    def _fix_invalid_operator(self, code: str, error: CompilationError) -> Optional[Tuple[str, str]]:
        """Fix invalid operator usage"""
        # Common: comparing null with value types
        return None


# Testing
if __name__ == "__main__":
    # Test with code that has fixable errors
    test_code_with_errors = """
using cAlgo.API;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class TestBot : Robot
    {
        protected override void OnStart()
        {
            var price = Bid  // Missing semicolon
            Print("Started")
        }
        
        protected override void OnBar()
        {
            var currentPrice = Symbol.Bid()  // Should be Symbol.Bid
        }
    }
}
"""
    
    print("=" * 70)
    print("AUTO-FIX COMPILATION LOOP TEST")
    print("=" * 70)
    
    fixer = CompilationAutoFixer()
    result = fixer.compile_with_auto_fix(test_code_with_errors, "TestBot")
    
    print(f"\nSuccess: {result['success']}")
    print(f"Iterations: {result['iterations']}")
    print(f"Fixes Applied: {len(result['fixes_applied'])}")
    
    if result['fixes_applied']:
        print("\nFixes:")
        for i, fix in enumerate(result['fixes_applied'], 1):
            print(f"  {i}. {fix}")
    
    if not result['success'] and 'errors' in result:
        print(f"\nRemaining Errors: {len(result['errors'])}")
        for err in result['errors'][:3]:
            print(f"  - [{err['code']}] Line {err['line']}: {err['message']}")
    
    print("\n" + "=" * 70)
    print("✅ Auto-fix system ready")
