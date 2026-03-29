#!/usr/bin/env python3
"""
Paper Trading Service Wrapper
Runs the trading engine and updates status file periodically
"""
import sys
import time
import json
import logging
import threading
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from backend .env
env_path = Path('/app/backend/.env')
if env_path.exists():
    load_dotenv(env_path)
    logging.info(f"Loaded environment from {env_path}")

# Add backend to path
sys.path.insert(0, '/app/backend')
sys.path.insert(0, '/app/backend/paper_trading')

from paper_trading.engine import PaperTradingEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/backend/paper_trading/service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

STATUS_FILE = Path("/app/backend/paper_trading/status.json")
STATUS_UPDATE_INTERVAL = 60  # Update status every 60 seconds


class PaperTradingService:
    """
    Service wrapper for paper trading engine
    """
    
    def __init__(self):
        self.engine = PaperTradingEngine(initial_capital=10000.0)
        self.status_thread = None
        self.running = False
    
    def update_status_file(self):
        """
        Periodically update status file for API consumption
        """
        while self.running:
            try:
                status = self.engine.get_status()
                
                # Write status to file
                STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(STATUS_FILE, 'w') as f:
                    json.dump(status, f, indent=2)
                
                logger.debug("Status file updated")
                
            except Exception as e:
                logger.error(f"Failed to update status file: {e}")
            
            time.sleep(STATUS_UPDATE_INTERVAL)
    
    def start(self):
        """
        Start the paper trading service
        """
        self.running = True
        
        # Start status update thread
        self.status_thread = threading.Thread(target=self.update_status_file, daemon=True)
        self.status_thread.start()
        
        logger.info("Paper trading service started")
        
        # Run trading engine (blocks)
        self.engine.run()
    
    def stop(self):
        """
        Stop the paper trading service
        """
        self.running = False
        self.engine.stop()
        
        if self.status_thread:
            self.status_thread.join(timeout=5)
        
        logger.info("Paper trading service stopped")


def main():
    """Main entry point"""
    service = PaperTradingService()
    
    try:
        service.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        service.stop()


if __name__ == "__main__":
    main()
