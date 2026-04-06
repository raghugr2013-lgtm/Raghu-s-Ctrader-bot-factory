"""
Test Script for Phase 6.4: Export System
Tests the export functionality for packaging and downloading strategies.
"""

import asyncio
import logging
import os
import zipfile
import json
from codex_master_pipeline_controller import MasterPipelineController, PipelineConfig
from export_system import StrategyExporter, export_pipeline_strategies
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_export_system():
    """Test export system with a pipeline run"""
    
    logger.info("="*80)
    logger.info("TEST: Phase 6.4 - Export System")
    logger.info("="*80)
    
    # Create controller
    controller = MasterPipelineController(db_client=None)
    
    # Create test config with lenient thresholds to get strategies
    config = PipelineConfig(
        generation_mode="factory",
        templates=["ema_crossover"],
        strategies_per_template=3,
        symbol="EURUSD",
        timeframe="1h",
        initial_balance=10000.0,
        duration_days=90,
        diversity_min_score=0.0,
        min_sharpe_ratio=0.0,
        max_drawdown_pct=99.0,
        min_win_rate=0.0,
        portfolio_size=3,  # Export top 3
        enable_monitoring=False,
        enable_auto_retrain=False,
    )
    
    logger.info(f"Config: {len(config.templates)} templates, portfolio size: {config.portfolio_size}")
    logger.info("")
    
    try:
        # Step 1: Run pipeline
        logger.info("Step 1: Running pipeline...")
        start_time = datetime.now()
        
        pipeline_run = await controller.run_full_pipeline(config)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"  ✓ Pipeline completed in {duration:.2f}s")
        logger.info(f"  Status: {pipeline_run.status}")
        logger.info(f"  Selected strategies: {len(pipeline_run.selected_portfolio)}")
        logger.info(f"  Deployable bots: {len(pipeline_run.deployable_bots)}")
        
        # Use selected_portfolio instead of deployable_bots (since compilation might fail without .NET SDK)
        strategies_to_export = pipeline_run.deployable_bots if pipeline_run.deployable_bots else pipeline_run.selected_portfolio
        
        if pipeline_run.status != "completed" or not strategies_to_export:
            logger.error("Pipeline did not produce strategies to export")
            return False
        
        # Step 2: Export strategies
        logger.info("")
        logger.info("="*80)
        logger.info("Step 2: Exporting strategies...")
        logger.info("="*80)
        
        export_info = export_pipeline_strategies(
            run_id=pipeline_run.run_id,
            strategies=strategies_to_export,
            top_n=3,
            pipeline_config={
                "symbol": config.symbol,
                "timeframe": config.timeframe,
                "initial_balance": config.initial_balance,
            }
        )
        
        if not export_info.get("success"):
            logger.error(f"Export failed: {export_info.get('error')}")
            return False
        
        logger.info(f"  ✓ Export successful")
        logger.info(f"  Run ID: {export_info['run_id']}")
        logger.info(f"  Export directory: {export_info['export_directory']}")
        logger.info(f"  ZIP file: {export_info['zip_filename']}")
        logger.info(f"  ZIP size: {export_info['zip_size_mb']} MB")
        logger.info(f"  Strategies exported: {export_info['strategies_exported']}")
        
        if export_info.get("missing_bots"):
            logger.warning(f"  ⚠ Missing bots: {export_info['missing_bots']}")
        
        # Step 3: Verify export contents
        logger.info("")
        logger.info("="*80)
        logger.info("Step 3: Verifying export contents...")
        logger.info("="*80)
        
        zip_path = export_info["zip_path"]
        
        if not os.path.exists(zip_path):
            logger.error(f"ZIP file not found: {zip_path}")
            return False
        
        # Open and inspect ZIP
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            file_list = zipf.namelist()
            logger.info(f"  ZIP contains {len(file_list)} files:")
            
            # Check for required files
            has_summary = any("summary_overview.json" in f for f in file_list)
            bot_files = [f for f in file_list if f.endswith("bot.cs")]
            report_files = [f for f in file_list if f.endswith("report.json")]
            
            logger.info(f"  - Summary overview: {'✓' if has_summary else '✗'}")
            logger.info(f"  - Bot files (.cs): {len(bot_files)}")
            logger.info(f"  - Report files (.json): {len(report_files)}")
            
            # Display file structure
            logger.info("")
            logger.info("  File structure:")
            for file_name in sorted(file_list):
                logger.info(f"    - {file_name}")
            
            # Verify summary_overview.json
            if has_summary:
                summary_file = [f for f in file_list if "summary_overview.json" in f][0]
                summary_data = json.loads(zipf.read(summary_file))
                
                logger.info("")
                logger.info("  Summary Overview:")
                logger.info(f"    Total strategies: {summary_data['export_info']['total_strategies']}")
                logger.info(f"    Export timestamp: {summary_data['export_info']['export_timestamp']}")
                logger.info(f"    Avg composite score: {summary_data['aggregate_metrics']['avg_composite_score']:.2f}")
                
                logger.info("    Strategies:")
                for strat in summary_data['strategies_overview']:
                    logger.info(f"      {strat['rank']}. {strat['name']} - Score: {strat['composite_score']:.2f}, Grade: {strat['composite_grade']}")
            
            # Verify at least one report.json
            if report_files:
                report_file = report_files[0]
                report_data = json.loads(zipf.read(report_file))
                
                logger.info("")
                logger.info(f"  Sample Report ({report_file}):")
                logger.info(f"    Strategy: {report_data['strategy_name']}")
                logger.info(f"    Composite Score: {report_data['ranking']['composite_score']}/100")
                logger.info(f"    Composite Grade: {report_data['ranking']['composite_grade']}")
                logger.info(f"    Sharpe Ratio: {report_data['backtest_performance']['sharpe_ratio']:.2f}")
                logger.info(f"    Max Drawdown: {report_data['backtest_performance']['max_drawdown_pct']:.2f}%")
                logger.info(f"    MC Survival Rate: {report_data['monte_carlo_validation']['survival_rate']:.1f}%")
        
        # Step 4: Verify individual bot files
        logger.info("")
        logger.info("="*80)
        logger.info("Step 4: Verifying bot file contents...")
        logger.info("="*80)
        
        if bot_files:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                bot_file = bot_files[0]
                bot_content = zipf.read(bot_file).decode('utf-8')
                
                logger.info(f"  Bot file: {bot_file}")
                logger.info(f"  Size: {len(bot_content)} characters")
                logger.info(f"  Lines: {len(bot_content.splitlines())}")
                
                # Check for key components
                has_using = "using cAlgo" in bot_content
                has_class = "class" in bot_content and "Robot" in bot_content
                has_onbar = "OnBar" in bot_content
                
                logger.info(f"  Has cAlgo imports: {'✓' if has_using else '✗'}")
                logger.info(f"  Has Robot class: {'✓' if has_class else '✗'}")
                logger.info(f"  Has OnBar method: {'✓' if has_onbar else '✗'}")
        
        # Test Summary
        logger.info("")
        logger.info("="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        success_criteria = {
            "Pipeline completed": pipeline_run.status == "completed",
            "Export created": export_info.get("success", False),
            "ZIP file exists": os.path.exists(zip_path),
            "Has summary": has_summary,
            "Has bot files": len(bot_files) > 0,
            "Has reports": len(report_files) > 0,
            "Bot files match strategy count": len(bot_files) == export_info["strategies_exported"],
        }
        
        for criterion, passed in success_criteria.items():
            status = "✓" if passed else "✗"
            logger.info(f"  {status} {criterion}")
        
        all_passed = all(success_criteria.values())
        
        if all_passed:
            logger.info("")
            logger.info("✓ TEST PASSED: Export system working correctly!")
            logger.info("  - ZIP archive created")
            logger.info("  - All bot files present")
            logger.info("  - All reports generated")
            logger.info("  - Summary overview included")
            logger.info(f"  - Download ready: {zip_path}")
            return True
        else:
            logger.warning("")
            logger.warning("⚠ TEST PARTIAL: Some criteria not met")
            return False
            
    except Exception as e:
        logger.error(f"✗ TEST FAILED with exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = asyncio.run(test_export_system())
    exit(0 if success else 1)
