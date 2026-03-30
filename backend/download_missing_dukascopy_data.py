#!/usr/bin/env python3
"""
Dukascopy Missing Data Downloader

Downloads ONLY missing data identified in gap analysis.
Includes retry logic, validation, and progress tracking.

Usage:
    python download_missing_dukascopy_data.py
"""

import os
import sys
import json
import lzma
import struct
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from urllib.parse import urljoin

# Configuration
GAP_ANALYSIS_FILE = "/app/trading_system/DATA_GAP_ANALYSIS.json"
OUTPUT_DIR = Path("/app/trading_system/dukascopy_data/EURUSD")
SYMBOL = "EURUSD"

# Dukascopy settings
BASE_URL = "https://datafeed.dukascopy.com/datafeed/"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
TIMEOUT = 30  # seconds
MIN_FILE_SIZE = 100  # bytes (valid bi5 files are typically > 1KB)

# Progress tracking
CHECKPOINT_FILE = "/app/trading_system/download_checkpoint.json"


class DukascopyDownloader:
    """Download missing Dukascopy data"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.stats = {
            "total_files": 0,
            "downloaded": 0,
            "skipped": 0,
            "failed": 0,
            "validated": 0,
            "invalid": 0
        }
    
    def construct_url(self, dt: datetime) -> str:
        """
        Construct Dukascopy URL for given datetime
        
        Format: https://datafeed.dukascopy.com/datafeed/EURUSD/YYYY/MM/DD/HHh_ticks.bi5
        Note: Month is 0-indexed (January = 00)
        """
        year = dt.year
        month = dt.month - 1  # 0-indexed
        day = dt.day
        hour = dt.hour
        
        url = f"{BASE_URL}{SYMBOL}/{year:04d}/{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5"
        return url
    
    def get_output_path(self, dt: datetime) -> Path:
        """Get output file path for given datetime"""
        filename = f"{dt.year:04d}_{dt.month:02d}_{dt.day:02d}_{dt.hour}.bi5"
        return OUTPUT_DIR / filename
    
    def file_exists_and_valid(self, filepath: Path) -> bool:
        """Check if file exists and is valid"""
        if not filepath.exists():
            return False
        
        # Check file size
        if filepath.stat().st_size < MIN_FILE_SIZE:
            print(f"      ⚠️  File too small ({filepath.stat().st_size} bytes), will redownload")
            return False
        
        # Try to decompress
        try:
            with open(filepath, 'rb') as f:
                compressed = f.read()
            lzma.decompress(compressed)
            return True
        except Exception as e:
            print(f"      ⚠️  File corrupted ({e}), will redownload")
            return False
    
    def validate_bi5_file(self, filepath: Path) -> bool:
        """Validate bi5 file by decompressing and checking structure"""
        try:
            # Read and decompress
            with open(filepath, 'rb') as f:
                compressed = f.read()
            
            if len(compressed) < MIN_FILE_SIZE:
                return False
            
            decompressed = lzma.decompress(compressed)
            
            # Check if decompressed data has valid structure
            # Dukascopy tick format: 20 bytes per tick
            if len(decompressed) % 20 != 0:
                print(f"      ❌ Invalid structure (size not multiple of 20)")
                return False
            
            # Try to parse first tick
            if len(decompressed) >= 20:
                try:
                    struct.unpack('>IIIII', decompressed[:20])
                except struct.error:
                    print(f"      ❌ Cannot parse tick data")
                    return False
            
            return True
            
        except lzma.LZMAError as e:
            print(f"      ❌ LZMA decompression failed: {e}")
            return False
        except Exception as e:
            print(f"      ❌ Validation failed: {e}")
            return False
    
    def download_file(self, url: str, output_path: Path) -> bool:
        """Download file with retry logic"""
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"      Attempt {attempt}/{MAX_RETRIES}...", end=" ")
                
                response = self.session.get(url, timeout=TIMEOUT, stream=True)
                
                if response.status_code == 200:
                    # Save to temporary file first
                    temp_path = output_path.with_suffix('.bi5.tmp')
                    
                    with open(temp_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # Validate before moving
                    if self.validate_bi5_file(temp_path):
                        temp_path.rename(output_path)
                        print(f"✅ Success ({output_path.stat().st_size} bytes)")
                        self.stats["downloaded"] += 1
                        self.stats["validated"] += 1
                        return True
                    else:
                        temp_path.unlink()
                        print(f"❌ Validation failed")
                        self.stats["invalid"] += 1
                        return False
                
                elif response.status_code == 404:
                    print(f"⚠️  Not found (404) - Data may not exist")
                    self.stats["failed"] += 1
                    return False
                
                else:
                    print(f"❌ HTTP {response.status_code}")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                        continue
                    else:
                        self.stats["failed"] += 1
                        return False
            
            except requests.exceptions.Timeout:
                print(f"⏱️  Timeout")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    self.stats["failed"] += 1
                    return False
            
            except Exception as e:
                print(f"❌ Error: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    self.stats["failed"] += 1
                    return False
        
        return False
    
    def load_checkpoint(self) -> set:
        """Load checkpoint of already processed files"""
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, 'r') as f:
                    data = json.load(f)
                return set(data.get("completed", []))
            except:
                return set()
        return set()
    
    def save_checkpoint(self, completed: set):
        """Save checkpoint"""
        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump({
                "completed": list(completed),
                "last_updated": datetime.utcnow().isoformat()
            }, f, indent=2)
    
    def download_missing_data(self):
        """Main download function"""
        
        print("="*80)
        print("DUKASCOPY MISSING DATA DOWNLOADER")
        print("="*80)
        print()
        
        # Load gap analysis
        if not os.path.exists(GAP_ANALYSIS_FILE):
            print(f"❌ Gap analysis file not found: {GAP_ANALYSIS_FILE}")
            print(f"   Please run analyze_data_gaps.py first!")
            return
        
        with open(GAP_ANALYSIS_FILE, 'r') as f:
            gap_data = json.load(f)
        
        # Parse all gaps into list of missing timestamps
        missing_timestamps = []
        
        for gap in gap_data["all_gaps"]:
            start = datetime.fromisoformat(gap["start"])
            end = datetime.fromisoformat(gap["end"])
            
            # Generate all hours in gap
            current = start
            while current <= end:
                missing_timestamps.append(current)
                current += timedelta(hours=1)
        
        # Remove duplicates and sort
        missing_timestamps = sorted(list(set(missing_timestamps)))
        
        self.stats["total_files"] = len(missing_timestamps)
        
        print(f"📊 Gap Analysis Summary:")
        print(f"   Total missing files: {len(missing_timestamps)}")
        print(f"   Date range: {missing_timestamps[0]} to {missing_timestamps[-1]}")
        print(f"   Output directory: {OUTPUT_DIR}")
        print()
        
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load checkpoint
        completed = self.load_checkpoint()
        print(f"📁 Checkpoint loaded: {len(completed)} files already processed")
        print()
        
        # Confirm before starting
        print("="*80)
        response = input("Start downloading? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Cancelled.")
            return
        
        print()
        print("="*80)
        print("DOWNLOADING MISSING FILES")
        print("="*80)
        print()
        
        start_time = time.time()
        
        for i, dt in enumerate(missing_timestamps, 1):
            timestamp_str = dt.isoformat()
            
            # Check if already processed
            if timestamp_str in completed:
                print(f"[{i}/{len(missing_timestamps)}] {dt.strftime('%Y-%m-%d %H:%M')} - Skipped (in checkpoint)")
                self.stats["skipped"] += 1
                continue
            
            output_path = self.get_output_path(dt)
            
            # Check if file already exists and is valid
            if self.file_exists_and_valid(output_path):
                print(f"[{i}/{len(missing_timestamps)}] {dt.strftime('%Y-%m-%d %H:%M')} - ✅ Already exists (valid)")
                self.stats["skipped"] += 1
                completed.add(timestamp_str)
                
                # Save checkpoint every 10 files
                if i % 10 == 0:
                    self.save_checkpoint(completed)
                
                continue
            
            # Download
            print(f"[{i}/{len(missing_timestamps)}] {dt.strftime('%Y-%m-%d %H:%M')} - Downloading...")
            url = self.construct_url(dt)
            
            success = self.download_file(url, output_path)
            
            if success:
                completed.add(timestamp_str)
            
            # Save checkpoint every 10 files
            if i % 10 == 0:
                self.save_checkpoint(completed)
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining = len(missing_timestamps) - i
                eta = remaining / rate if rate > 0 else 0
                print(f"   Progress: {i}/{len(missing_timestamps)} ({i/len(missing_timestamps)*100:.1f}%) "
                      f"| Rate: {rate:.1f} files/sec | ETA: {eta/60:.1f} min")
                print()
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
        
        # Final checkpoint save
        self.save_checkpoint(completed)
        
        # Summary
        elapsed = time.time() - start_time
        
        print()
        print("="*80)
        print("DOWNLOAD COMPLETE")
        print("="*80)
        print()
        print(f"📊 Statistics:")
        print(f"   Total files to download: {self.stats['total_files']}")
        print(f"   Successfully downloaded:  {self.stats['downloaded']}")
        print(f"   Skipped (already exist):  {self.stats['skipped']}")
        print(f"   Failed:                   {self.stats['failed']}")
        print(f"   Validated:                {self.stats['validated']}")
        print(f"   Invalid:                  {self.stats['invalid']}")
        print()
        print(f"⏱️  Time elapsed: {elapsed/60:.1f} minutes")
        print(f"📈 Download rate: {self.stats['downloaded']/(elapsed/60):.1f} files/min")
        print()
        
        if self.stats['failed'] > 0:
            print(f"⚠️  {self.stats['failed']} files failed to download.")
            print(f"   You can re-run this script to retry failed downloads.")
            print()
        
        if self.stats['invalid'] > 0:
            print(f"❌ {self.stats['invalid']} files failed validation.")
            print(f"   These files could not be decompressed or have invalid structure.")
            print()
        
        # Suggest next steps
        print("="*80)
        print("NEXT STEPS")
        print("="*80)
        print()
        print("1. Verify downloaded files:")
        print("   python analyze_data_gaps.py")
        print()
        print("2. Process bi5 to candles:")
        print("   python process_bi5_to_candles.py")
        print()
        print("3. Re-run validation:")
        print("   python incremental_validation.py")
        print()


def main():
    """Main entry point"""
    downloader = DukascopyDownloader()
    
    try:
        downloader.download_missing_data()
    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
        print("   Progress has been saved. You can resume by running this script again.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
