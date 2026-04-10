"""
Phase 3 Batch Generation - Test Script
Demonstrates batch strategy generation with Phase 2 filtering
"""

from phase3_batch_generator import Phase3BatchGenerator, format_batch_report
import json


def test_phase3_batch_generation():
    """Run Phase 3 batch generation test"""
    
    print("="*100)
    print("PHASE 3: STRATEGY DISCOVERY SCALING TEST")
    print("="*100)
    print("")
    
    # Initialize generator (150 strategies)
    generator = Phase3BatchGenerator(batch_size=150)
    
    print(f"Generating batch of {generator.batch_size} strategies...")
    print("Applying Phase 2 quality filters...")
    print("Only keeping grades A, B, C (tradeable)")
    print("")
    
    # Generate batch
    result = generator.generate_batch(
        symbol="EURUSD",
        min_grade='C'  # Accept A, B, C
    )
    
    # Print formatted report
    print(format_batch_report(result))
    print("")
    
    # Save detailed JSON
    with open('/tmp/phase3_batch_result.json', 'w') as f:
        json.dump(result.to_dict(), f, indent=2)
    
    print("Detailed results saved to: /tmp/phase3_batch_result.json")
    print("")
    
    # Print key insights
    print("KEY INSIGHTS")
    print("-"*100)
    print(f"✓ Generated {result.total_generated} diverse strategies")
    print(f"✓ Acceptance rate: {result.acceptance_rate:.1f}% (Phase 2 filters)")
    
    top_score = result.top_by_score[0].get('phase2', {}).get('composite_score', 0) if result.top_by_score else 0
    print(f"✓ Top strategy score: {top_score:.1f}/100")
    
    print(f"✓ Grade A count: {result.grade_a_count} ({result.grade_a_count/result.total_generated*100:.1f}%)")
    print(f"✓ Grade B count: {result.grade_b_count} ({result.grade_b_count/result.total_generated*100:.1f}%)")
    print(f"✓ Rejected (D/F): {result.rejected_count} ({result.rejected_count/result.total_generated*100:.1f}%)")
    print("")
    print("Phase 3 scaling successful! ✅")


if __name__ == "__main__":
    test_phase3_batch_generation()
