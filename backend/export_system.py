"""
Export System
Packages validated strategies with cTrader bots, reports, and metadata for user download.
"""

import os
import json
import zipfile
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)


class StrategyExporter:
    """
    Exports validated strategies with their cTrader bots and performance reports.
    Creates a downloadable ZIP archive with organized structure.
    """
    
    def __init__(self, export_base_dir: str = "/tmp/strategy_exports"):
        self.export_base_dir = export_base_dir
        os.makedirs(export_base_dir, exist_ok=True)
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize strategy name for use as filename.
        
        Args:
            name: Original strategy name
            
        Returns:
            Sanitized filename-safe string
        """
        # Replace spaces and special characters
        safe_name = name.replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-.")
        # Limit length
        return safe_name[:50]
    
    def _create_strategy_report(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create comprehensive performance report for a strategy.
        
        Args:
            strategy: Strategy dict with all metrics
            
        Returns:
            Report dict with formatted data
        """
        report = {
            "strategy_name": strategy.get("name", "Unknown"),
            "generated_at": datetime.now().isoformat(),
            
            # Ranking
            "ranking": {
                "position": strategy.get("ranking_position", 0),
                "composite_score": strategy.get("composite_score", 0),
                "composite_grade": strategy.get("composite_grade", "F"),
            },
            
            # Backtest Metrics
            "backtest_performance": {
                "sharpe_ratio": strategy.get("sharpe_ratio", 0),
                "max_drawdown_pct": strategy.get("max_drawdown_pct", 0),
                "win_rate": strategy.get("win_rate", 0),
                "profit_factor": strategy.get("profit_factor", 0),
                "net_profit": strategy.get("net_profit", 0),
                "total_trades": strategy.get("total_trades", 0),
                "winning_trades": strategy.get("winning_trades", 0),
                "losing_trades": strategy.get("losing_trades", 0),
                "avg_win": strategy.get("avg_win", 0),
                "avg_loss": strategy.get("avg_loss", 0),
                "max_consecutive_wins": strategy.get("max_consecutive_wins", 0),
                "max_consecutive_losses": strategy.get("max_consecutive_losses", 0),
            },
            
            # Monte Carlo Results
            "monte_carlo_validation": {
                "survival_rate": strategy.get("monte_carlo_survival_rate", 0),
                "ruin_probability": strategy.get("monte_carlo_ruin_probability", 0),
                "worst_case_drawdown": strategy.get("monte_carlo_worst_drawdown", 0),
                "average_drawdown": strategy.get("monte_carlo_avg_drawdown", 0),
                "monte_carlo_score": strategy.get("monte_carlo_score", 0),
                "monte_carlo_grade": strategy.get("monte_carlo_grade", "F"),
                "is_robust": strategy.get("monte_carlo_is_robust", False),
                "risk_level": strategy.get("monte_carlo_risk_level", "Unknown"),
                "simulations_count": strategy.get("monte_carlo_simulations_count", 0),
            },
            
            # Strategy Parameters
            "parameters": {
                "template_id": strategy.get("template_id", "unknown"),
                "symbol": strategy.get("symbol", "UNKNOWN"),
                "timeframe": strategy.get("timeframe", "1h"),  # NEW: Include timeframe
                "genes": strategy.get("genes", {}),
            },
            
            # Bot Information
            "bot": {
                "class_name": strategy.get("class_name", "Unknown"),
                "file_name": strategy.get("bot_file", "bot.cs"),
                "file_path": strategy.get("bot_file_path", ""),
                "code_lines": strategy.get("code_lines", 0),
                "compiled": strategy.get("compiled", False),
                "indicators_count": strategy.get("indicators_count", 0),
                "filters_count": strategy.get("filters_count", 0),
                "has_risk_management": strategy.get("has_risk_management", False),
            },
            
            # Additional Info
            "metadata": {
                "strategy_id": strategy.get("id", ""),
                "generation_mode": strategy.get("generation_mode", "unknown"),
                "created_at": strategy.get("created_at", ""),
            }
        }
        
        return report
    
    def _create_summary_overview(
        self,
        strategies: List[Dict[str, Any]],
        run_id: str,
        pipeline_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create summary overview of all exported strategies.
        
        Args:
            strategies: List of strategy dicts
            run_id: Pipeline run ID
            pipeline_config: Optional pipeline configuration
            
        Returns:
            Summary dict
        """
        summary = {
            "export_info": {
                "run_id": run_id,
                "export_timestamp": datetime.now().isoformat(),
                "total_strategies": len(strategies),
            },
            
            "pipeline_configuration": pipeline_config or {},
            
            "strategies_overview": [
                {
                    "rank": idx + 1,
                    "name": strat.get("name", "Unknown"),
                    "composite_score": strat.get("composite_score", 0),
                    "composite_grade": strat.get("composite_grade", "F"),
                    "sharpe_ratio": strat.get("sharpe_ratio", 0),
                    "max_drawdown_pct": strat.get("max_drawdown_pct", 0),
                    "monte_carlo_score": strat.get("monte_carlo_score", 0),
                    "bot_file": f"strategy_{idx+1}_{self._sanitize_filename(strat.get('name', 'Unknown'))}/bot.cs"
                }
                for idx, strat in enumerate(strategies)
            ],
            
            "aggregate_metrics": {
                "avg_composite_score": sum(s.get("composite_score", 0) for s in strategies) / len(strategies) if strategies else 0,
                "avg_sharpe_ratio": sum(s.get("sharpe_ratio", 0) for s in strategies) / len(strategies) if strategies else 0,
                "avg_max_drawdown": sum(s.get("max_drawdown_pct", 0) for s in strategies) / len(strategies) if strategies else 0,
                "avg_monte_carlo_score": sum(s.get("monte_carlo_score", 0) for s in strategies) / len(strategies) if strategies else 0,
            },
            
            "readme": {
                "description": "This package contains validated and ranked cTrader trading strategies.",
                "contents": [
                    "Each strategy folder contains:",
                    "  - bot.cs: cTrader cBot source code (ready to import)",
                    "  - report.json: Comprehensive performance report with backtest and Monte Carlo results"
                ],
                "import_instructions": [
                    "1. Open cTrader",
                    "2. Go to Automate → cBots",
                    "3. Click 'Import' and select the bot.cs file",
                    "4. Review the report.json for strategy details and expected performance",
                    "5. Backtest on your own data before live trading"
                ],
                "disclaimer": "Past performance does not guarantee future results. Always test strategies thoroughly before live deployment."
            }
        }
        
        return summary
    
    def export_strategies(
        self,
        strategies: List[Dict[str, Any]],
        run_id: str,
        top_n: int = 5,
        pipeline_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Export top N strategies to a structured directory and create ZIP.
        
        Args:
            strategies: List of strategy dicts (should be sorted by composite_score)
            run_id: Pipeline run ID
            top_n: Number of top strategies to export
            pipeline_config: Optional pipeline configuration
            
        Returns:
            Dict with export info (directory path, zip path, etc.)
        """
        logger.info(f"Starting export for run_id: {run_id}")
        
        try:
            # Select top N strategies
            top_strategies = strategies[:top_n]
            logger.info(f"Exporting top {len(top_strategies)} strategies")
            
            # Create export directory
            export_dir = os.path.join(self.export_base_dir, f"export_{run_id}")
            os.makedirs(export_dir, exist_ok=True)
            
            exported_count = 0
            missing_bots = []
            
            # Export each strategy
            for idx, strategy in enumerate(top_strategies, 1):
                strategy_name = strategy.get("name", f"Strategy_{idx}")
                safe_name = self._sanitize_filename(strategy_name)
                strategy_dir = os.path.join(export_dir, f"strategy_{idx}_{safe_name}")
                os.makedirs(strategy_dir, exist_ok=True)
                
                logger.info(f"  [{idx}/{len(top_strategies)}] Exporting: {strategy_name}")
                
                # 1. Copy bot.cs file if it exists
                bot_file_path = strategy.get("bot_file_path", "")
                bot_destination = os.path.join(strategy_dir, "bot.cs")
                
                if bot_file_path and os.path.exists(bot_file_path):
                    shutil.copy2(bot_file_path, bot_destination)
                    logger.debug(f"    ✓ Copied bot.cs from {bot_file_path}")
                elif strategy.get("csharp_code"):
                    # If file doesn't exist but we have code in memory, write it
                    with open(bot_destination, 'w', encoding='utf-8') as f:
                        f.write(strategy.get("csharp_code"))
                    logger.debug(f"    ✓ Wrote bot.cs from in-memory code")
                else:
                    logger.warning(f"    ⚠ No bot.cs file found for {strategy_name}")
                    missing_bots.append(strategy_name)
                
                # 2. Create report.json
                report = self._create_strategy_report(strategy)
                report_path = os.path.join(strategy_dir, "report.json")
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2)
                logger.debug(f"    ✓ Created report.json")
                
                exported_count += 1
            
            # Create summary_overview.json
            summary = self._create_summary_overview(top_strategies, run_id, pipeline_config)
            summary_path = os.path.join(export_dir, "summary_overview.json")
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"  ✓ Created summary_overview.json")
            
            # Create ZIP archive
            zip_filename = f"ctrader_bots_{run_id}.zip"
            zip_path = os.path.join(self.export_base_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(export_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(export_dir))
                        zipf.write(file_path, arcname)
            
            zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            logger.info(f"  ✓ Created ZIP archive: {zip_filename} ({zip_size_mb:.2f} MB)")
            
            # Return export info
            export_info = {
                "success": True,
                "run_id": run_id,
                "export_directory": export_dir,
                "zip_path": zip_path,
                "zip_filename": zip_filename,
                "zip_size_mb": round(zip_size_mb, 2),
                "strategies_exported": exported_count,
                "missing_bots": missing_bots,
                "summary_file": summary_path,
            }
            
            logger.info(f"Export complete: {exported_count} strategies exported")
            if missing_bots:
                logger.warning(f"  ⚠ {len(missing_bots)} strategies missing bot files: {missing_bots}")
            
            return export_info
            
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "run_id": run_id,
            }
    
    def cleanup_old_exports(self, max_age_hours: int = 24):
        """
        Clean up old export files to save disk space.
        
        Args:
            max_age_hours: Delete exports older than this many hours
        """
        try:
            current_time = datetime.now().timestamp()
            max_age_seconds = max_age_hours * 3600
            
            deleted_count = 0
            for item in os.listdir(self.export_base_dir):
                item_path = os.path.join(self.export_base_dir, item)
                
                # Check if old enough
                if os.path.isfile(item_path) or os.path.isdir(item_path):
                    age_seconds = current_time - os.path.getmtime(item_path)
                    
                    if age_seconds > max_age_seconds:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        else:
                            shutil.rmtree(item_path)
                        deleted_count += 1
                        logger.debug(f"Deleted old export: {item}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old exports")
                
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")


# Helper function for easy use
def export_pipeline_strategies(
    run_id: str,
    strategies: List[Dict[str, Any]],
    top_n: int = 5,
    pipeline_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenient function to export strategies from a pipeline run.
    
    Args:
        run_id: Pipeline run ID
        strategies: List of strategy dicts (sorted by composite_score)
        top_n: Number of top strategies to export
        pipeline_config: Optional pipeline configuration
        
    Returns:
        Export info dict
    """
    exporter = StrategyExporter()
    return exporter.export_strategies(strategies, run_id, top_n, pipeline_config)
