# PHASE 2A OPTIMIZER - ARGUMENT PARSING MODIFICATION

**File to modify:** `/app/trading_system/backend/phase2a_optimizer.py`

---

## ADD AT THE TOP (After imports):

```python
import argparse

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Phase 2A Optimizer - Controlled Rollout')
    parser.add_argument(
        '--csv',
        type=str,
        required=False,
        default='/app/trading_system/data/EURUSD_H1.csv',
        help='Path to CSV file with H1 candle data'
    )
    return parser.parse_args()
```

---

## MODIFY THE __main__ SECTION:

**FIND THIS (at the bottom of file):**
```python
if __name__ == "__main__":
    # Configuration
    CSV_PATH = "/path/to/your/EURUSD_H1.csv"  # UPDATE THIS
    
    print("⚠️  IMPORTANT: Update CSV_PATH in the script before running")
    print()
    
    # Run optimization
    optimizer = Phase2AOptimizer(CSV_PATH)
    results = optimizer.run_optimization()
    
    # Save results
    output_file = "phase2a_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to {output_file}")
```

**REPLACE WITH:**
```python
if __name__ == "__main__":
    # Parse arguments
    args = parse_args()
    CSV_PATH = args.csv
    
    print()
    print("╔" + "="*78 + "╗")
    print("║" + " "*25 + "PHASE 2A OPTIMIZER" + " "*35 + "║")
    print("║" + " "*15 + "Controlled Rollout - Validation Phase" + " "*24 + "║")
    print("╚" + "="*78 + "╝")
    print()
    print(f"CSV Path: {CSV_PATH}")
    print()
    
    # Validate CSV exists
    if not os.path.exists(CSV_PATH):
        print(f"❌ ERROR: CSV file not found: {CSV_PATH}")
        sys.exit(1)
    
    # Run optimization
    optimizer = Phase2AOptimizer(CSV_PATH)
    results = optimizer.run_optimization()
    
    # Save results to fixed filename for API consumption
    output_file = "results.json"  # Fixed name for API
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to {output_file}")
    print()
```

---

## ADD IMPORTS (if not already present):

```python
import sys
import os
```

---

## COMPLETE MINIMAL EXAMPLE:

If you're creating the file from scratch, here's the minimal structure:

```python
import pandas as pd
import json
import os
import sys
import argparse
from datetime import datetime
from typing import List, Dict

# ... (your existing Phase2AOptimizer class here)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Phase 2A Optimizer')
    parser.add_argument(
        '--csv',
        type=str,
        required=False,
        default='/app/trading_system/data/EURUSD_H1.csv',
        help='Path to CSV file'
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    CSV_PATH = args.csv
    
    print()
    print("PHASE 2A OPTIMIZER")
    print(f"CSV Path: {CSV_PATH}")
    print()
    
    if not os.path.exists(CSV_PATH):
        print(f"❌ ERROR: CSV file not found: {CSV_PATH}")
        sys.exit(1)
    
    # Run optimization
    optimizer = Phase2AOptimizer(CSV_PATH)
    results = optimizer.run_optimization()
    
    # Save to results.json (fixed name for API)
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("✅ Results saved to results.json")
```

---

## TEST THE CHANGES:

```bash
# Test with explicit CSV path
python phase2a_optimizer.py --csv /app/trading_system/data/EURUSD_H1.csv

# Test with default
python phase2a_optimizer.py

# Should output:
# PHASE 2A OPTIMIZER
# CSV Path: /app/trading_system/data/EURUSD_H1.csv
# ...
# ✅ Results saved to results.json
```

---

## KEY CHANGES:

1. ✅ Added `argparse` for command-line arguments
2. ✅ CSV path now comes from `--csv` argument
3. ✅ Output filename changed to `results.json` (fixed name)
4. ✅ Added file existence validation
5. ✅ Added proper error handling

This makes the script compatible with backend API execution.
