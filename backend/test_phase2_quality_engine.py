"""
Phase 2 Quality Engine - Demonstration Script
Shows examples of accepted vs rejected strategies with detailed feedback
"""

from scoring_engine import QualityFilters, StrategyGrader, Grade


def test_strategy_validation():
    """Test Phase 2 validation with example strategies"""
    
    print("="*100)
    print("PHASE 2 STRATEGY QUALITY ENGINE - VALIDATION EXAMPLES")
    print("="*100)
    print()
    
    # Example 1: Excellent Strategy (Grade A)
    print("Example 1: EXCELLENT STRATEGY")
    print("-" * 100)
    strategy_a = {
        'profit_factor': 2.5,
        'max_drawdown_pct': 8.0,
        'sharpe_ratio': 2.0,
        'total_trades': 250,
        'stability_score': 90.0,
        'net_profit': 15000
    }
    
    passes, reasons = QualityFilters.passes_all(strategy_a)
    grade, desc, details = StrategyGrader.calculate_grade(92.5, strategy_a)
    emoji = StrategyGrader.get_grade_emoji(grade)
    
    print(f"Metrics: PF={strategy_a['profit_factor']}, DD={strategy_a['max_drawdown_pct']}%, "
          f"Sharpe={strategy_a['sharpe_ratio']}, Trades={strategy_a['total_trades']}")
    print(f"Status: {'ACCEPTED ✓' if passes else 'REJECTED ✗'}")
    print(f"Grade: {emoji} {grade.value} - {desc}")
    print(f"Composite Score: {details['score']}")
    print(f"Quality: {details['quality']}")
    print(f"Recommendation: {details['recommendation']}")
    print()
    
    # Example 2: Good Strategy (Grade B)
    print("Example 2: GOOD STRATEGY")
    print("-" * 100)
    strategy_b = {
        'profit_factor': 1.8,
        'max_drawdown_pct': 12.0,
        'sharpe_ratio': 1.4,
        'total_trades': 180,
        'stability_score': 80.0,
        'net_profit': 8000
    }
    
    passes, reasons = QualityFilters.passes_all(strategy_b)
    grade, desc, details = StrategyGrader.calculate_grade(84.0, strategy_b)
    emoji = StrategyGrader.get_grade_emoji(grade)
    
    print(f"Metrics: PF={strategy_b['profit_factor']}, DD={strategy_b['max_drawdown_pct']}%, "
          f"Sharpe={strategy_b['sharpe_ratio']}, Trades={strategy_b['total_trades']}")
    print(f"Status: {'ACCEPTED ✓' if passes else 'REJECTED ✗'}")
    print(f"Grade: {emoji} {grade.value} - {desc}")
    print(f"Composite Score: {details['score']}")
    print(f"Quality: {details['quality']}")
    print(f"Recommendation: {details['recommendation']}")
    print()
    
    # Example 3: Acceptable Strategy (Grade C)
    print("Example 3: ACCEPTABLE STRATEGY (Borderline Pass)")
    print("-" * 100)
    strategy_c = {
        'profit_factor': 1.5,
        'max_drawdown_pct': 15.0,
        'sharpe_ratio': 1.0,
        'total_trades': 100,
        'stability_score': 70.0,
        'net_profit': 5000
    }
    
    passes, reasons = QualityFilters.passes_all(strategy_c)
    grade, desc, details = StrategyGrader.calculate_grade(72.0, strategy_c)
    emoji = StrategyGrader.get_grade_emoji(grade)
    
    print(f"Metrics: PF={strategy_c['profit_factor']}, DD={strategy_c['max_drawdown_pct']}%, "
          f"Sharpe={strategy_c['sharpe_ratio']}, Trades={strategy_c['total_trades']}")
    print(f"Status: {'ACCEPTED ✓' if passes else 'REJECTED ✗'}")
    print(f"Grade: {emoji} {grade.value} - {desc}")
    print(f"Composite Score: {details['score']}")
    print(f"Quality: {details['quality']}")
    print(f"Recommendation: {details['recommendation']}")
    print()
    
    # Example 4: REJECTED - Low Profit Factor
    print("Example 4: REJECTED STRATEGY - Low Profit Factor")
    print("-" * 100)
    strategy_reject_1 = {
        'profit_factor': 1.23,
        'max_drawdown_pct': 12.0,
        'sharpe_ratio': 1.2,
        'total_trades': 150,
        'stability_score': 75.0,
        'net_profit': 3000
    }
    
    passes, reasons = QualityFilters.passes_all(strategy_reject_1)
    report = QualityFilters.get_detailed_rejection_report(strategy_reject_1)
    
    print(f"Metrics: PF={strategy_reject_1['profit_factor']}, DD={strategy_reject_1['max_drawdown_pct']}%, "
          f"Sharpe={strategy_reject_1['sharpe_ratio']}, Trades={strategy_reject_1['total_trades']}")
    print(f"Status: {'ACCEPTED ✓' if passes else 'REJECTED ✗'}")
    print(f"Failed Filters: {report['failed_filter_count']}")
    print()
    print("Detailed Rejection Reasons:")
    for failure in report['detailed_failures']:
        print(f"  • Filter: {failure['filter']}")
        print(f"    Value: {failure['value']} | Threshold: {failure['threshold']}")
        print(f"    Reason: {failure['reason']}")
        print(f"    Improvement Needed: {failure['improvement_needed']}")
        print(f"    Recommendation: {failure['recommendation']}")
        print()
    
    # Example 5: REJECTED - High Drawdown
    print("Example 5: REJECTED STRATEGY - High Drawdown")
    print("-" * 100)
    strategy_reject_2 = {
        'profit_factor': 1.8,
        'max_drawdown_pct': 22.0,
        'sharpe_ratio': 1.1,
        'total_trades': 120,
        'stability_score': 65.0,
        'net_profit': 6000
    }
    
    passes, reasons = QualityFilters.passes_all(strategy_reject_2)
    report = QualityFilters.get_detailed_rejection_report(strategy_reject_2)
    
    print(f"Metrics: PF={strategy_reject_2['profit_factor']}, DD={strategy_reject_2['max_drawdown_pct']}%, "
          f"Sharpe={strategy_reject_2['sharpe_ratio']}, Trades={strategy_reject_2['total_trades']}")
    print(f"Status: {'ACCEPTED ✓' if passes else 'REJECTED ✗'}")
    print(f"Failed Filters: {report['failed_filter_count']}")
    print()
    print("Detailed Rejection Reasons:")
    for failure in report['detailed_failures']:
        print(f"  • Filter: {failure['filter']}")
        print(f"    Value: {failure['value']} | Threshold: {failure['threshold']}")
        print(f"    Reason: {failure['reason']}")
        print(f"    Improvement Needed: {failure['improvement_needed']}")
        print(f"    Recommendation: {failure['recommendation']}")
        print()
    
    # Example 6: REJECTED - Multiple Failures
    print("Example 6: REJECTED STRATEGY - Multiple Failures")
    print("-" * 100)
    strategy_reject_3 = {
        'profit_factor': 1.1,
        'max_drawdown_pct': 25.0,
        'sharpe_ratio': 0.5,
        'total_trades': 45,
        'stability_score': 50.0,
        'net_profit': 1000
    }
    
    passes, reasons = QualityFilters.passes_all(strategy_reject_3)
    report = QualityFilters.get_detailed_rejection_report(strategy_reject_3)
    
    print(f"Metrics: PF={strategy_reject_3['profit_factor']}, DD={strategy_reject_3['max_drawdown_pct']}%, "
          f"Sharpe={strategy_reject_3['sharpe_ratio']}, Trades={strategy_reject_3['total_trades']}")
    print(f"Status: {'ACCEPTED ✓' if passes else 'REJECTED ✗'}")
    print(f"Failed Filters: {report['failed_filter_count']}")
    print()
    print("Detailed Rejection Reasons:")
    for failure in report['detailed_failures']:
        print(f"  • Filter: {failure['filter']}")
        print(f"    Value: {failure['value']} | Threshold: {failure['threshold']}")
        print(f"    Reason: {failure['reason']}")
        print(f"    Improvement Needed: {failure['improvement_needed']}")
        print(f"    Recommendation: {failure['recommendation']}")
        print()
    
    print("="*100)
    print("SUMMARY")
    print("="*100)
    print("Phase 2 filters enforce strict quality standards:")
    print("  • Profit Factor ≥ 1.5")
    print("  • Max Drawdown ≤ 15%")
    print("  • Sharpe Ratio ≥ 1.0")
    print("  • Minimum Trades ≥ 100")
    print("  • Stability Score ≥ 70%")
    print()
    print("Only 30-45% of strategies are expected to pass (vs. ~70% in Phase 1)")
    print("QUALITY OVER QUANTITY - Production-grade strategies only!")
    print("="*100)


if __name__ == "__main__":
    test_strategy_validation()
