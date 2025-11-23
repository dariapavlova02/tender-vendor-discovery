#!/usr/bin/env python3
"""
Minimal test to isolate the hang
"""
import sys
sys.stdout = sys.stderr  # Force output to stderr
print("TEST 1: Starting script", flush=True)

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()
logger.info("TEST 2: Logging configured")

from pathlib import Path
logger.info("TEST 3: Imported Path")

from vendor_ai_agent.database.connection import get_session
logger.info("TEST 4: Imported get_session")

from vendor_ai_agent.ingestion.canada_contracts import load_canada_contracts
logger.info("TEST 5: Imported load_canada_contracts")

csv_file = "data/canada_history/2009-2023-contractHistoryHistorical-contratsOctroyesHistorique.csv"
logger.info(f"TEST 6: CSV file path: {csv_file}")

logger.info("TEST 7: About to call get_session()")
with get_session() as session:
    logger.info("TEST 8: Got session, about to call load_canada_contracts()")
    stats = load_canada_contracts(session, csv_file)
    logger.info(f"TEST 9: Completed! Stats: {stats}")
