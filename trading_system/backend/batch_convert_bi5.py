#!/usr/bin/env python3
"""
Batch Dukascopy .bi5 Converter
Process multiple symbols/timeframes in one run

Usage:
    python batch_convert_bi5.py --config conversion_config.json
    
Or:
    python batch_convert_bi5.py --input-dir /data/dukascopy --output-dir /output
"""

import argparse
import json
from pathlib import Path
from dukascopy_bi5_converter import DukascopyBI5Converter
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


DEFAULT_CONVERSIONS = [
    {
        "symbol": "EURUSD",
        "input_folder": "EURUSD",
        "output_file": "eurusd_h1.csv",
        "timeframe": "1H"
    },
    {
        "symbol": "XAUUSD",
        "input_folder": "XAUUSD",
        "output_file": "xauusd_h1.csv",
        "timeframe": "1H"
    },
    {
        "symbol": "GBPUSD",
        "input_folder": "GBPUSD",
        "output_file": "gbpusd_h1.csv",
        "timeframe": "1H"
    },
    {
        "symbol": "USDJPY",
        "input_folder": "USDJPY",
        "output_file": "usdjpy_h1.csv",
        "timeframe": "1H"
    }
]


def batch_convert(
    input_dir: Path,
    output_dir: Path,
    conversions: list = None
):
    """
    Batch convert multiple symbols
    
    Args:
        input_dir: Root directory containing symbol folders
        output_dir: Output directory for CSV files
        conversions: List of conversion configs
    """
    if conversions is None:
        conversions = DEFAULT_CONVERSIONS
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        "success": [],
        "failed": []
    }
    
    for config in conversions:
        symbol = config["symbol"]
        input_folder = input_dir / config["input_folder"]
        output_file = output_dir / config["output_file"]
        timeframe = config.get("timeframe", "1H")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Converting {symbol} ({timeframe})")
        logger.info(f"{'='*60}")
        
        if not input_folder.exists():
            logger.error(f"Input folder not found: {input_folder}")
            results["failed"].append(symbol)
            continue
        
        try:
            converter = DukascopyBI5Converter(symbol=symbol)
            converter.convert(
                input_folder=input_folder,
                output_path=output_file,
                timeframe=timeframe,
                fill_missing=True
            )
            results["success"].append(symbol)
        except Exception as e:
            logger.error(f"Failed to convert {symbol}: {e}")
            results["failed"].append(symbol)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("CONVERSION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Success: {len(results['success'])} symbols")
    for symbol in results['success']:
        logger.info(f"   - {symbol}")
    
    if results['failed']:
        logger.info(f"❌ Failed: {len(results['failed'])} symbols")
        for symbol in results['failed']:
            logger.info(f"   - {symbol}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch convert Dukascopy .bi5 files to CSV'
    )
    
    parser.add_argument(
        '--input-dir', '-i',
        type=str,
        required=True,
        help='Root directory containing symbol folders'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        required=True,
        help='Output directory for CSV files'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='JSON config file with conversion settings'
    )
    
    args = parser.parse_args()
    
    # Load config if provided
    conversions = None
    if args.config:
        with open(args.config, 'r') as f:
            conversions = json.load(f)
    
    batch_convert(
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
        conversions=conversions
    )


if __name__ == '__main__':
    main()
