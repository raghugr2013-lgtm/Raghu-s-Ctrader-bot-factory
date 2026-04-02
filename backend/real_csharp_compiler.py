"""
Real C# Compilation Service for cTrader Bots
Uses actual .NET SDK and Roslyn compiler for accurate validation
"""

import subprocess
import tempfile
import shutil
import os
import re
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Path to template project with cTrader.Automate NuGet package
TEMPLATE_PROJECT_PATH = "/app/backend/ctrader_compiler/template"
DOTNET_PATH = "/usr/share/dotnet/dotnet"  # Full absolute path


@dataclass
class CompilationError:
    """Single compilation error or warning"""
    code: str           # e.g., "CS0246"
    severity: str       # "error" or "warning"
    message: str        # Full error message
    file: str = ""      # Source file
    line: int = 0       # Line number
    column: int = 0     # Column number
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass 
class RealCompilationResult:
    """Result of real C# compilation"""
    success: bool
    errors: List[CompilationError] = field(default_factory=list)
    warnings: List[CompilationError] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    raw_output: str = ""
    compilation_time_ms: int = 0
    compiler_version: str = ""
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "raw_output": self.raw_output,
            "compilation_time_ms": self.compilation_time_ms,
            "compiler_version": self.compiler_version
        }


class RealCSharpCompiler:
    """
    Real C# compiler using .NET SDK
    Provides accurate cTrader bot compilation validation
    """
    
    def __init__(self):
        self.template_path = TEMPLATE_PROJECT_PATH
        self.dotnet_path = DOTNET_PATH
        self._verify_setup()
    
    def _verify_setup(self):
        """Verify .NET SDK and template are available"""
        if not os.path.exists(self.dotnet_path):
            # Try system dotnet
            self.dotnet_path = "dotnet"
        
        try:
            result = subprocess.run(
                [self.dotnet_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            self.compiler_version = result.stdout.strip()
            logger.info(f"Real C# compiler initialized: .NET SDK {self.compiler_version}")
        except Exception as e:
            logger.error(f"Failed to verify .NET SDK: {e}")
            self.compiler_version = "unknown"
    
    def compile(self, code: str, bot_name: str = "GeneratedBot") -> RealCompilationResult:
        """
        Compile C# code using real .NET SDK
        
        Args:
            code: C# source code
            bot_name: Name for the bot class (used for file naming)
            
        Returns:
            RealCompilationResult with detailed errors/warnings
        """
        start_time = datetime.now(timezone.utc)
        temp_dir = None
        
        try:
            # Create temporary compilation directory
            temp_dir = tempfile.mkdtemp(prefix="ctrader_compile_")
            
            # Copy template project
            shutil.copy(
                os.path.join(self.template_path, "CTraderBot.csproj"),
                os.path.join(temp_dir, "CTraderBot.csproj")
            )
            
            # Copy obj folder with restored packages if exists (for faster builds)
            template_obj = os.path.join(self.template_path, "obj")
            if os.path.exists(template_obj):
                shutil.copytree(template_obj, os.path.join(temp_dir, "obj"))
            
            # DO NOT copy PlaceholderBot.cs - we only want to compile the user's code
            
            # Write the bot code
            code_file = os.path.join(temp_dir, f"{bot_name}.cs")
            with open(code_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # Run dotnet build (with restore if needed)
            result = subprocess.run(
                [
                    self.dotnet_path, "build",
                    "-v", "quiet",   # Quiet verbosity
                    "-nologo",       # No logo
                    "/p:GenerateFullPaths=true",  # Full file paths
                    "/clp:NoSummary"  # No summary
                ],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=60,
                env={
                    **os.environ, 
                    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                    "HOME": os.environ.get("HOME", "/root"),
                    "DOTNET_CLI_HOME": os.environ.get("HOME", "/root")
                }
            )
            
            # Parse output
            raw_output = result.stdout + result.stderr
            errors, warnings = self._parse_compiler_output(raw_output, bot_name)
            
            # Calculate compilation time
            end_time = datetime.now(timezone.utc)
            compilation_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            success = len(errors) == 0
            
            logger.info(
                f"Real compilation complete: {len(errors)} errors, {len(warnings)} warnings "
                f"({compilation_time_ms}ms)"
            )
            
            return RealCompilationResult(
                success=success,
                errors=errors,
                warnings=warnings,
                error_count=len(errors),
                warning_count=len(warnings),
                raw_output=raw_output,
                compilation_time_ms=compilation_time_ms,
                compiler_version=self.compiler_version
            )
            
        except subprocess.TimeoutExpired:
            logger.error("Compilation timed out")
            return RealCompilationResult(
                success=False,
                errors=[CompilationError(
                    code="TIMEOUT",
                    severity="error",
                    message="Compilation timed out after 60 seconds"
                )],
                error_count=1,
                raw_output="Compilation timeout"
            )
            
        except Exception as e:
            logger.error(f"Compilation error: {e}")
            return RealCompilationResult(
                success=False,
                errors=[CompilationError(
                    code="INTERNAL",
                    severity="error", 
                    message=f"Internal compilation error: {str(e)}"
                )],
                error_count=1,
                raw_output=str(e)
            )
            
        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")
    
    def _parse_compiler_output(
        self, 
        output: str, 
        bot_name: str
    ) -> tuple[List[CompilationError], List[CompilationError]]:
        """
        Parse dotnet build output for errors and warnings
        
        Format: file(line,col): severity code: message
        Example: Bot.cs(45,13): error CS0246: The type or namespace name 'Position' could not be found
        """
        errors = []
        warnings = []
        
        # Regex pattern for MSBuild error/warning format
        # Matches: path(line,col): severity CSxxxx: message
        pattern = re.compile(
            r'([^(]+)\((\d+),(\d+)\):\s*(error|warning)\s+(CS\d+|[A-Z]+\d*):\s*(.+?)(?=\r?\n|$)',
            re.MULTILINE
        )
        
        for match in pattern.finditer(output):
            file_path = match.group(1).strip()
            line = int(match.group(2))
            column = int(match.group(3))
            severity = match.group(4)
            code = match.group(5)
            message = match.group(6).strip()
            
            # Extract just filename from path
            filename = os.path.basename(file_path)
            
            error_obj = CompilationError(
                code=code,
                severity=severity,
                message=message,
                file=filename,
                line=line,
                column=column
            )
            
            if severity == "error":
                errors.append(error_obj)
            else:
                warnings.append(error_obj)
        
        # Also check for build failed message without specific errors
        if "Build FAILED" in output and not errors:
            # Try to extract any error-like messages
            general_error = re.search(r'error\s*:?\s*(.+?)(?:\r?\n|$)', output, re.IGNORECASE)
            if general_error:
                errors.append(CompilationError(
                    code="BUILD",
                    severity="error",
                    message=general_error.group(1).strip()
                ))
        
        return errors, warnings
    
    def format_errors_for_ai(self, result: RealCompilationResult) -> str:
        """Format compilation errors for AI to fix"""
        lines = []
        
        for e in result.errors:
            loc = f"Line {e.line}" if e.line > 0 else ""
            lines.append(f"[ERROR {e.code}] {loc}: {e.message}")
        
        for w in result.warnings:
            loc = f"Line {w.line}" if w.line > 0 else ""
            lines.append(f"[WARNING {w.code}] {loc}: {w.message}")
        
        return "\n".join(lines)
    
    def format_errors_for_ui(self, result: RealCompilationResult) -> List[dict]:
        """Format compilation errors for frontend display"""
        items = []
        
        for e in result.errors:
            items.append({
                "type": "error",
                "code": e.code,
                "message": e.message,
                "line": e.line,
                "column": e.column,
                "file": e.file
            })
        
        for w in result.warnings:
            items.append({
                "type": "warning", 
                "code": w.code,
                "message": w.message,
                "line": w.line,
                "column": w.column,
                "file": w.file
            })
        
        return items


# Global singleton
_compiler_instance = None

def get_real_compiler() -> RealCSharpCompiler:
    """Get or create the real C# compiler instance"""
    global _compiler_instance
    if _compiler_instance is None:
        _compiler_instance = RealCSharpCompiler()
    return _compiler_instance


def compile_csharp_code(code: str, bot_name: str = "GeneratedBot") -> Dict:
    """
    Main entry point for real C# compilation
    
    Returns dict compatible with existing validation flow:
    {
        "is_valid": bool,
        "errors": List[str],
        "warnings": List[str],
        "details": List[dict],  # Detailed error objects
        "raw_output": str
    }
    """
    compiler = get_real_compiler()
    result = compiler.compile(code, bot_name)
    
    return {
        "is_valid": result.success,
        "errors": [f"{e.code}: {e.message} (Line {e.line})" for e in result.errors],
        "warnings": [f"{w.code}: {w.message} (Line {w.line})" for w in result.warnings],
        "details": compiler.format_errors_for_ui(result),
        "raw_output": result.raw_output,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "compilation_time_ms": result.compilation_time_ms,
        "compiler_version": result.compiler_version
    }
