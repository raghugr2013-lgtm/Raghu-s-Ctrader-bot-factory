"""
Test Script for Stage 10 cBot Generation
Tests the integration of bot generation and compilation in the pipeline.
"""

import asyncio
import logging
from codex_master_pipeline_controller import MasterPipelineController, PipelineConfig
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_bot_generation():
    """Test bot generation with a small pipeline run"""
    
    logger.info("="*80)
    logger.info("TEST: Stage 10 cBot Generation Integration")
    logger.info("="*80)
    
    # Create controller
    controller = MasterPipelineController(db_client=None)
    
    # Create minimal test config
    config = PipelineConfig(
        generation_mode="factory",
        templates=["ema_crossover"],  # Lowercase with underscores
        strategies_per_template=2,  # Small number for testing
        symbol="EURUSD",
        timeframe="1h",
        initial_balance=10000.0,
        duration_days=90,
        diversity_min_score=50.0,
        min_sharpe_ratio=0.0,  # Very low threshold for testing
        max_drawdown_pct=99.0,  # High threshold for testing
        min_win_rate=0.0,  # No threshold for testing
        portfolio_size=2,  # Small portfolio
        enable_monitoring=False,
        enable_auto_retrain=False,
    )
    
    logger.info(f"Config: {config}")
    logger.info("")
    
    try:
        # Run full pipeline
        logger.info("Starting pipeline run...")
        start_time = datetime.now()
        
        pipeline_run = await controller.run_full_pipeline(config)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("")
        logger.info("="*80)
        logger.info("PIPELINE RESULTS")
        logger.info("="*80)
        logger.info(f"Status: {pipeline_run.status}")
        logger.info(f"Duration: {duration:.2f}s")
        logger.info(f"Generated strategies: {len(pipeline_run.generated_strategies)}")
        logger.info(f"Backtested strategies: {len(pipeline_run.backtested_strategies)}")
        logger.info(f"Validated strategies: {len(pipeline_run.validated_strategies)}")
        logger.info(f"Selected for portfolio: {len(pipeline_run.selected_portfolio)}")
        logger.info(f"Compiled bots: {len(pipeline_run.compiled_bots)}")
        logger.info(f"Deployable bots: {len(pipeline_run.deployable_bots)}")
        
        # Check Stage 10 results
        logger.info("")
        logger.info("="*80)
        logger.info("STAGE 10: cBot Generation Details")
        logger.info("="*80)
        
        stage_10_result = None
        for stage_result in pipeline_run.stage_results:
            if stage_result.stage.value == "cbot_generation":
                stage_10_result = stage_result
                break
        
        if stage_10_result:
            logger.info(f"Success: {stage_10_result.success}")
            logger.info(f"Message: {stage_10_result.message}")
            logger.info(f"Execution time: {stage_10_result.execution_time_seconds:.2f}s")
            logger.info(f"Data: {stage_10_result.data}")
            
            if stage_10_result.warnings:
                logger.warning(f"Warnings ({len(stage_10_result.warnings)}):")
                for warn in stage_10_result.warnings:
                    logger.warning(f"  - {warn}")
        
        # Detailed bot analysis
        logger.info("")
        logger.info("="*80)
        logger.info("COMPILED BOTS ANALYSIS")
        logger.info("="*80)
        
        successful_compilations = 0
        failed_compilations = 0
        
        for idx, bot in enumerate(pipeline_run.compiled_bots):
            logger.info(f"\nBot #{idx+1}: {bot.get('name', 'Unknown')}")
            logger.info(f"  Class Name: {bot.get('class_name', 'N/A')}")
            logger.info(f"  Compiled: {bot.get('compiled', False)}")
            logger.info(f"  Compile Status: {bot.get('compile_status', 'unknown')}")
            logger.info(f"  Code Lines: {bot.get('code_lines', 0)}")
            logger.info(f"  Compile Time: {bot.get('compile_time_ms', 0)}ms")
            logger.info(f"  Errors: {bot.get('error_count', 0)}")
            logger.info(f"  Warnings: {bot.get('warning_count', 0)}")
            logger.info(f"  File Path: {bot.get('bot_file_path', 'N/A')}")
            logger.info(f"  Indicators: {bot.get('indicators_count', 0)}")
            logger.info(f"  Filters: {bot.get('filters_count', 0)}")
            logger.info(f"  Risk Management: {bot.get('has_risk_management', False)}")
            
            # Strategy metrics
            logger.info(f"  Strategy Metrics:")
            logger.info(f"    - Sharpe: {bot.get('sharpe_ratio', 0):.2f}")
            logger.info(f"    - Max DD: {bot.get('max_drawdown_pct', 0):.2f}%")
            logger.info(f"    - Win Rate: {bot.get('win_rate', 0):.2f}%")
            logger.info(f"    - Profit Factor: {bot.get('profit_factor', 0):.2f}")
            
            if bot.get('compiled'):
                successful_compilations += 1
            else:
                failed_compilations += 1
                
                # Show compilation errors
                if 'compilation_errors' in bot:
                    logger.error(f"  Compilation Errors:")
                    for err in bot['compilation_errors']:
                        logger.error(f"    - {err['code']}: {err['message']} (line {err['line']})")
        
        # Summary
        logger.info("")
        logger.info("="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"Total Bots: {len(pipeline_run.compiled_bots)}")
        logger.info(f"Successful Compilations: {successful_compilations}")
        logger.info(f"Failed Compilations: {failed_compilations}")
        logger.info(f"Deployable Bots: {len(pipeline_run.deployable_bots)}")
        
        # Check if we have C# code
        if pipeline_run.deployable_bots:
            first_bot = pipeline_run.deployable_bots[0]
            if 'csharp_code' in first_bot:
                code_length = len(first_bot['csharp_code'])
                logger.info(f"First bot C# code length: {code_length} characters")
                logger.info(f"First bot has actual C# code: {'using cAlgo' in first_bot['csharp_code']}")
        
        # Overall test result
        logger.info("")
        if pipeline_run.status == "completed" and successful_compilations > 0:
            logger.info("✓ TEST PASSED: Pipeline completed with generated and compiled bots!")
            return True
        elif pipeline_run.status == "completed" and successful_compilations == 0:
            logger.warning("⚠ TEST PARTIAL: Pipeline completed but no successful compilations")
            return False
        else:
            logger.error("✗ TEST FAILED: Pipeline did not complete successfully")
            return False
            
    except Exception as e:
        logger.error(f"✗ TEST FAILED with exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = asyncio.run(test_bot_generation())
    exit(0 if success else 1)
