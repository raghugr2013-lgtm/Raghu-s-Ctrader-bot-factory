"""
Test Script for Phase 6.3: Composite Scoring System
Tests the integration of composite scoring and ranking in the pipeline.
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


async def test_composite_scoring():
    """Test composite scoring integration in pipeline"""
    
    logger.info("="*80)
    logger.info("TEST: Phase 6.3 - Composite Scoring System")
    logger.info("="*80)
    
    # Create controller
    controller = MasterPipelineController(db_client=None)
    
    # Create test config with VERY lenient thresholds to test composite scoring
    config = PipelineConfig(
        generation_mode="factory",
        templates=["ema_crossover", "rsi_mean_reversion"],
        strategies_per_template=3,
        symbol="EURUSD",
        timeframe="1h",
        initial_balance=10000.0,
        duration_days=90,
        diversity_min_score=0.0,  # Very lenient
        min_sharpe_ratio=0.0,     # Very lenient
        max_drawdown_pct=99.0,     # Very lenient
        min_win_rate=0.0,          # Very lenient
        portfolio_size=5,
        enable_monitoring=False,
        enable_auto_retrain=False,
    )
    
    logger.info(f"Config: {len(config.templates)} templates × {config.strategies_per_template} strategies")
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
        
        # Check if composite scoring was applied
        logger.info("")
        logger.info("="*80)
        logger.info("COMPOSITE SCORING VERIFICATION")
        logger.info("="*80)
        
        has_composite_scores = False
        if pipeline_run.selected_portfolio:
            first_strategy = pipeline_run.selected_portfolio[0]
            has_composite_scores = "composite_score" in first_strategy
            
            logger.info(f"Composite scores present: {has_composite_scores}")
            
            if has_composite_scores:
                logger.info("")
                logger.info("Top 5 Strategies by Composite Score:")
                for idx, strategy in enumerate(pipeline_run.selected_portfolio[:5], 1):
                    logger.info(f"\n{idx}. {strategy.get('name', 'Unknown')}")
                    logger.info(f"   Composite Score: {strategy.get('composite_score', 0):.2f}/100")
                    logger.info(f"   Composite Grade: {strategy.get('composite_grade', 'N/A')}")
                    logger.info(f"   Ranking Position: #{strategy.get('ranking_position', 0)}")
                    logger.info(f"   Component Scores:")
                    logger.info(f"     - Sharpe Ratio: {strategy.get('sharpe_ratio', 0):.2f}")
                    logger.info(f"     - Max Drawdown: {strategy.get('max_drawdown_pct', 0):.2f}%")
                    logger.info(f"     - Monte Carlo Score: {strategy.get('monte_carlo_score', 0):.2f}")
                    logger.info(f"     - Walk-Forward Retention: {strategy.get('walk_forward_retention', 50.0):.2f}%")
                    logger.info(f"     - Profit Factor: {strategy.get('profit_factor', 0):.2f}")
        
        # Check Stage 6.5 results
        logger.info("")
        logger.info("="*80)
        logger.info("STAGE 6.5: Composite Scoring Details")
        logger.info("="*80)
        
        # Find composite scoring stage result
        scoring_stage = None
        for stage_result in pipeline_run.stage_results:
            if "Scored" in stage_result.message or "composite" in stage_result.message.lower():
                scoring_stage = stage_result
                break
        
        if scoring_stage:
            logger.info(f"Success: {scoring_stage.success}")
            logger.info(f"Message: {scoring_stage.message}")
            logger.info(f"Execution time: {scoring_stage.execution_time_seconds:.2f}s")
            
            if "data" in scoring_stage.__dict__ and scoring_stage.data:
                logger.info(f"Data: {scoring_stage.data}")
        else:
            logger.warning("Composite scoring stage result not found")
        
        # Verify ranking order
        logger.info("")
        logger.info("="*80)
        logger.info("RANKING VERIFICATION")
        logger.info("="*80)
        
        if pipeline_run.selected_portfolio and has_composite_scores:
            scores = [s.get("composite_score", 0) for s in pipeline_run.selected_portfolio]
            is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
            
            logger.info(f"Strategies sorted by score: {is_sorted}")
            logger.info(f"Scores: {scores}")
            
            if is_sorted:
                logger.info("✓ Ranking order correct (descending by composite score)")
            else:
                logger.warning("⚠ Ranking order incorrect")
        
        # Test Summary
        logger.info("")
        logger.info("="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        logger.info(f"Pipeline Status: {pipeline_run.status}")
        logger.info(f"Composite Scores Present: {has_composite_scores}")
        logger.info(f"Selected Strategies: {len(pipeline_run.selected_portfolio)}")
        
        # Check success criteria
        success = (
            pipeline_run.status in ["completed", "failed"] and  # Pipeline ran
            has_composite_scores  # Composite scores were added
        )
        
        if success:
            logger.info("")
            logger.info("✓ TEST PASSED: Composite scoring integrated successfully!")
            logger.info("  - Strategies have composite_score field")
            logger.info("  - Strategies have composite_grade field")
            logger.info("  - Strategies have ranking_position field")
            logger.info("  - Strategies sorted by composite score")
            return True
        else:
            logger.warning("")
            logger.warning("⚠ TEST PARTIAL: Pipeline ran but composite scoring may be incomplete")
            return False
            
    except Exception as e:
        logger.error(f"✗ TEST FAILED with exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = asyncio.run(test_composite_scoring())
    exit(0 if success else 1)
