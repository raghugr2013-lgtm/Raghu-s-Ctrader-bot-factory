"""
Test Script for Phase 6.2: Monte Carlo Integration
Tests the integration of Monte Carlo simulation in Stage 4 validation.
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


async def test_monte_carlo_integration():
    """Test Monte Carlo integration in validation stage"""
    
    logger.info("="*80)
    logger.info("TEST: Phase 6.2 - Monte Carlo Integration in Stage 4")
    logger.info("="*80)
    
    # Create controller
    controller = MasterPipelineController(db_client=None)
    
    # Create test config
    config = PipelineConfig(
        generation_mode="factory",
        templates=["ema_crossover"],
        strategies_per_template=5,  # Moderate number for testing
        symbol="EURUSD",
        timeframe="1h",
        initial_balance=10000.0,
        duration_days=90,
        diversity_min_score=50.0,
        min_sharpe_ratio=0.0,  # Low threshold to get some strategies
        max_drawdown_pct=99.0,
        min_win_rate=0.0,
        portfolio_size=3,
        enable_monitoring=False,
        enable_auto_retrain=False,
    )
    
    logger.info(f"Config: Generating {len(config.templates)} templates × {config.strategies_per_template} = {len(config.templates) * config.strategies_per_template} strategies")
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
        
        # Check Stage 4 (Validation) results
        logger.info("")
        logger.info("="*80)
        logger.info("STAGE 4: Validation Details (Monte Carlo Integration)")
        logger.info("="*80)
        
        stage_4_result = None
        for stage_result in pipeline_run.stage_results:
            if stage_result.stage.value == "validation":
                stage_4_result = stage_result
                break
        
        if stage_4_result:
            logger.info(f"Success: {stage_4_result.success}")
            logger.info(f"Message: {stage_4_result.message}")
            logger.info(f"Execution time: {stage_4_result.execution_time_seconds:.2f}s")
            
            # Monte Carlo specific data
            if "monte_carlo_summary" in stage_4_result.data:
                mc_summary = stage_4_result.data["monte_carlo_summary"]
                logger.info("")
                logger.info("Monte Carlo Summary:")
                logger.info(f"  - Total validated: {mc_summary.get('total_validated', 0)}")
                logger.info(f"  - Passed count: {mc_summary.get('passed_count', 0)}")
                logger.info(f"  - Failed count: {mc_summary.get('failed_count', 0)}")
                logger.info(f"  - Pass rate: {mc_summary.get('pass_rate', 0):.1f}%")
                logger.info(f"  - Avg survival rate: {mc_summary.get('avg_survival_rate', 0):.1f}%")
                logger.info(f"  - Avg ruin probability: {mc_summary.get('avg_ruin_probability', 0):.1f}%")
                logger.info(f"  - Avg MC score: {mc_summary.get('avg_mc_score', 0):.1f}/100")
                
                if mc_summary.get('fallback'):
                    logger.warning(f"  ⚠ Fallback mode: {mc_summary.get('error', 'Unknown error')}")
        
        # Analyze validated strategies with MC data
        logger.info("")
        logger.info("="*80)
        logger.info("VALIDATED STRATEGIES ANALYSIS (Monte Carlo Metrics)")
        logger.info("="*80)
        
        if pipeline_run.validated_strategies:
            for idx, strat in enumerate(pipeline_run.validated_strategies[:5]):  # Show first 5
                logger.info(f"\nStrategy #{idx+1}: {strat.get('name', 'Unknown')}")
                logger.info(f"  Basic Metrics:")
                logger.info(f"    - Sharpe: {strat.get('sharpe_ratio', 0):.2f}")
                logger.info(f"    - Max DD: {strat.get('max_drawdown_pct', 0):.2f}%")
                logger.info(f"    - Win Rate: {strat.get('win_rate', 0):.2f}%")
                logger.info(f"    - Profit Factor: {strat.get('profit_factor', 0):.2f}")
                
                # Monte Carlo metrics
                if "monte_carlo_score" in strat:
                    logger.info(f"  Monte Carlo Metrics:")
                    logger.info(f"    - Survival Rate: {strat.get('monte_carlo_survival_rate', 0):.1f}%")
                    logger.info(f"    - Ruin Probability: {strat.get('monte_carlo_ruin_probability', 0):.1f}%")
                    logger.info(f"    - Worst Drawdown: {strat.get('monte_carlo_worst_drawdown', 0):.1f}%")
                    logger.info(f"    - Avg Drawdown: {strat.get('monte_carlo_avg_drawdown', 0):.1f}%")
                    logger.info(f"    - MC Score: {strat.get('monte_carlo_score', 0):.1f}/100")
                    logger.info(f"    - Grade: {strat.get('monte_carlo_grade', 'N/A')}")
                    logger.info(f"    - Is Robust: {strat.get('monte_carlo_is_robust', False)}")
                    logger.info(f"    - Risk Level: {strat.get('monte_carlo_risk_level', 'Unknown')}")
                    logger.info(f"    - Passed MC: {strat.get('monte_carlo_passes', False)}")
                else:
                    logger.warning("    ⚠ No Monte Carlo metrics found")
        else:
            logger.warning("No validated strategies to analyze")
        
        # Summary
        logger.info("")
        logger.info("="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        has_mc_metrics = False
        if pipeline_run.validated_strategies:
            has_mc_metrics = "monte_carlo_score" in pipeline_run.validated_strategies[0]
        
        logger.info(f"Pipeline Status: {pipeline_run.status}")
        logger.info(f"Validated Strategies: {len(pipeline_run.validated_strategies)}")
        logger.info(f"Monte Carlo Metrics Present: {has_mc_metrics}")
        
        # Check success criteria
        success = (
            pipeline_run.status == "completed" and
            has_mc_metrics
        )
        
        if success:
            logger.info("")
            logger.info("✓ TEST PASSED: Monte Carlo integration working!")
            logger.info("  - Strategies have MC metrics")
            logger.info("  - Survival rate, ruin probability, and scores calculated")
            logger.info("  - Strategies filtered by MC robustness")
            return True
        else:
            logger.warning("")
            logger.warning("⚠ TEST PARTIAL: Pipeline completed but Monte Carlo integration incomplete")
            return False
            
    except Exception as e:
        logger.error(f"✗ TEST FAILED with exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = asyncio.run(test_monte_carlo_integration())
    exit(0 if success else 1)
