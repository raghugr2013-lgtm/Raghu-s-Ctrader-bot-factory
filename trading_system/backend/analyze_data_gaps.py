"""
Analyze Dukascopy Dataset for Missing Data

Scans bi5 files and identifies gaps in the data.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import json

# Path to bi5 files
BI5_DIR = Path("/app/trading_system/dukascopy_data/EURUSD")

def parse_bi5_filename(filename):
    """
    Parse bi5 filename to datetime
    Format: YYYY_MM_DD_HH.bi5
    Example: 2025_01_02_22.bi5
    """
    parts = filename.replace('.bi5', '').split('_')
    year = int(parts[0])
    month = int(parts[1])
    day = int(parts[2])
    hour = int(parts[3])
    
    return datetime(year, month, day, hour)


def is_forex_trading_hour(dt):
    """
    Check if datetime is during forex trading hours
    Forex trades 24/5: Sunday 22:00 UTC to Friday 22:00 UTC
    """
    weekday = dt.weekday()  # 0=Monday, 6=Sunday
    hour = dt.hour
    
    # Friday after 22:00 UTC - closed
    if weekday == 4 and hour >= 22:
        return False
    
    # Saturday - closed all day
    if weekday == 5:
        return False
    
    # Sunday before 22:00 UTC - closed
    if weekday == 6 and hour < 22:
        return False
    
    return True


def get_expected_hours(start_date, end_date):
    """
    Generate list of all expected trading hours between two dates
    """
    expected = []
    current = start_date.replace(minute=0, second=0, microsecond=0)
    
    while current <= end_date:
        if is_forex_trading_hour(current):
            expected.append(current)
        current += timedelta(hours=1)
    
    return expected


def analyze_gaps():
    """
    Main analysis function
    """
    print("="*80)
    print("DUKASCOPY DATASET GAP ANALYSIS")
    print("="*80)
    print()
    
    # Get all bi5 files
    bi5_files = sorted(list(BI5_DIR.glob("*.bi5")))
    
    if not bi5_files:
        print("❌ No bi5 files found!")
        return
    
    print(f"📁 Found {len(bi5_files)} bi5 files")
    print()
    
    # Parse all file timestamps
    actual_hours = []
    for filepath in bi5_files:
        try:
            dt = parse_bi5_filename(filepath.name)
            actual_hours.append(dt)
        except Exception as e:
            print(f"⚠️  Failed to parse {filepath.name}: {e}")
    
    actual_hours.sort()
    
    if not actual_hours:
        print("❌ No valid timestamps parsed!")
        return
    
    # Dataset range
    start_date = actual_hours[0]
    end_date = actual_hours[-1]
    
    print(f"📊 Dataset Range:")
    print(f"   Start: {start_date.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   End:   {end_date.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Duration: {(end_date - start_date).days} days")
    print()
    
    # Get expected hours
    expected_hours = get_expected_hours(start_date, end_date)
    
    print(f"📈 Data Coverage:")
    print(f"   Expected hours (trading): {len(expected_hours)}")
    print(f"   Actual hours (files):     {len(actual_hours)}")
    print(f"   Missing hours:            {len(expected_hours) - len(actual_hours)}")
    print(f"   Coverage:                 {len(actual_hours)/len(expected_hours)*100:.2f}%")
    print()
    
    # Find missing hours
    actual_set = set(actual_hours)
    expected_set = set(expected_hours)
    missing_hours = sorted(expected_set - actual_set)
    
    if not missing_hours:
        print("✅ No missing data! Dataset is complete.")
        return
    
    print(f"❌ Found {len(missing_hours)} missing hours")
    print()
    
    # Group missing hours into gaps
    gaps = []
    if missing_hours:
        gap_start = missing_hours[0]
        gap_end = missing_hours[0]
        
        for i in range(1, len(missing_hours)):
            current = missing_hours[i]
            prev = missing_hours[i-1]
            
            # Check if consecutive (accounting for forex hours)
            next_expected = prev + timedelta(hours=1)
            while not is_forex_trading_hour(next_expected) and next_expected < current:
                next_expected += timedelta(hours=1)
            
            if current == next_expected:
                # Continue current gap
                gap_end = current
            else:
                # Start new gap
                gaps.append((gap_start, gap_end))
                gap_start = current
                gap_end = current
        
        # Add last gap
        gaps.append((gap_start, gap_end))
    
    # Sort gaps by size
    gaps_with_size = []
    for gap_start, gap_end in gaps:
        # Count actual trading hours in gap
        gap_hours = 0
        current = gap_start
        while current <= gap_end:
            if is_forex_trading_hour(current):
                gap_hours += 1
            current += timedelta(hours=1)
        
        gaps_with_size.append((gap_start, gap_end, gap_hours))
    
    gaps_with_size.sort(key=lambda x: x[2], reverse=True)
    
    # Report gaps
    print("="*80)
    print("MISSING DATA GAPS (Largest First)")
    print("="*80)
    print()
    
    # Summary by size
    small_gaps = [g for g in gaps_with_size if g[2] <= 24]
    medium_gaps = [g for g in gaps_with_size if 24 < g[2] <= 120]
    large_gaps = [g for g in gaps_with_size if g[2] > 120]
    
    print(f"📊 Gap Distribution:")
    print(f"   Small gaps (<= 24h):      {len(small_gaps)} gaps")
    print(f"   Medium gaps (1-5 days):   {len(medium_gaps)} gaps")
    print(f"   Large gaps (> 5 days):    {len(large_gaps)} gaps")
    print()
    
    # Top 20 largest gaps
    print("="*80)
    print("TOP 20 LARGEST GAPS")
    print("="*80)
    print()
    print(f"{'#':<4} {'Start':<20} {'End':<20} {'Hours':<8} {'Days':<8}")
    print("-"*80)
    
    for i, (gap_start, gap_end, gap_hours) in enumerate(gaps_with_size[:20], 1):
        gap_days = gap_hours / 24
        print(f"{i:<4} {gap_start.strftime('%Y-%m-%d %H:%M'):<20} "
              f"{gap_end.strftime('%Y-%m-%d %H:%M'):<20} "
              f"{gap_hours:<8} {gap_days:<8.1f}")
    
    # Missing days (full 24h missing)
    print()
    print("="*80)
    print("MISSING DAYS (Full Days with No Data)")
    print("="*80)
    print()
    
    # Group by day
    missing_by_day = defaultdict(int)
    for dt in missing_hours:
        day_key = dt.date()
        if is_forex_trading_hour(dt):
            missing_by_day[day_key] += 1
    
    # Find days with >= 20 hours missing (essentially full day)
    full_missing_days = []
    for day, hours in missing_by_day.items():
        if hours >= 20:
            full_missing_days.append((day, hours))
    
    full_missing_days.sort()
    
    if full_missing_days:
        print(f"Found {len(full_missing_days)} days with >= 20 hours missing:")
        print()
        for day, hours in full_missing_days[:30]:
            print(f"   {day.strftime('%Y-%m-%d')} ({day.strftime('%A')}): {hours} hours missing")
        
        if len(full_missing_days) > 30:
            print(f"   ... and {len(full_missing_days) - 30} more days")
    else:
        print("✅ No full days missing")
    
    # Missing weeks
    print()
    print("="*80)
    print("MISSING WEEKS (Weeks with Significant Gaps)")
    print("="*80)
    print()
    
    # Group by week
    missing_by_week = defaultdict(int)
    for dt in missing_hours:
        week_key = dt.strftime('%Y-W%W')
        if is_forex_trading_hour(dt):
            missing_by_week[week_key] += 1
    
    # Find weeks with >= 60 hours missing (> 50% of week)
    problematic_weeks = []
    for week, hours in missing_by_week.items():
        if hours >= 60:
            problematic_weeks.append((week, hours))
    
    problematic_weeks.sort(key=lambda x: x[1], reverse=True)
    
    if problematic_weeks:
        print(f"Found {len(problematic_weeks)} weeks with >= 60 hours missing:")
        print()
        print(f"{'Week':<12} {'Missing Hours':<15} {'% of Week':<12}")
        print("-"*40)
        for week, hours in problematic_weeks:
            pct = hours / 120 * 100  # ~120 trading hours per week
            print(f"{week:<12} {hours:<15} {pct:<12.1f}%")
    else:
        print("✅ No weeks with significant gaps")
    
    # Final summary
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()
    
    largest_gap = gaps_with_size[0] if gaps_with_size else None
    
    print(f"📊 Dataset Quality:")
    print(f"   Total expected hours:     {len(expected_hours)}")
    print(f"   Total actual hours:       {len(actual_hours)}")
    print(f"   Missing hours:            {len(missing_hours)}")
    print(f"   Data completeness:        {len(actual_hours)/len(expected_hours)*100:.2f}%")
    print(f"   Missing data:             {len(missing_hours)/len(expected_hours)*100:.2f}%")
    print()
    
    if largest_gap:
        print(f"🔴 Largest Gap:")
        print(f"   Start:     {largest_gap[0].strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"   End:       {largest_gap[1].strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"   Duration:  {largest_gap[2]} hours ({largest_gap[2]/24:.1f} days)")
    print()
    
    print(f"📁 Gap Distribution:")
    print(f"   Total gaps:               {len(gaps_with_size)}")
    print(f"   Small gaps (<= 1 day):    {len(small_gaps)}")
    print(f"   Medium gaps (1-5 days):   {len(medium_gaps)}")
    print(f"   Large gaps (> 5 days):    {len(large_gaps)}")
    print()
    
    # Save detailed report
    report = {
        "dataset_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "duration_days": (end_date - start_date).days
        },
        "coverage": {
            "expected_hours": len(expected_hours),
            "actual_hours": len(actual_hours),
            "missing_hours": len(missing_hours),
            "completeness_pct": len(actual_hours)/len(expected_hours)*100,
            "missing_pct": len(missing_hours)/len(expected_hours)*100
        },
        "gaps": {
            "total_gaps": len(gaps_with_size),
            "small_gaps": len(small_gaps),
            "medium_gaps": len(medium_gaps),
            "large_gaps": len(large_gaps),
            "largest_gap": {
                "start": largest_gap[0].isoformat() if largest_gap else None,
                "end": largest_gap[1].isoformat() if largest_gap else None,
                "hours": largest_gap[2] if largest_gap else None,
                "days": largest_gap[2]/24 if largest_gap else None
            }
        },
        "all_gaps": [
            {
                "start": gap[0].isoformat(),
                "end": gap[1].isoformat(),
                "hours": gap[2],
                "days": gap[2]/24
            }
            for gap in gaps_with_size
        ]
    }
    
    report_path = "/app/trading_system/DATA_GAP_ANALYSIS.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"📄 Detailed report saved: {report_path}")
    print()
    print("="*80)


if __name__ == "__main__":
    analyze_gaps()
