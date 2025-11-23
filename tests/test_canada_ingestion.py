#!/usr/bin/env python3
"""
Test Canada contracts ingestion with explicit logging
"""
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

logger.info("Starting Canada contracts ingestion test...")

from vendor_ai_agent.database.connection import get_session
from vendor_ai_agent.ingestion.canada_contracts import load_canada_contracts

csv_file = "data/canada_history/2009-2023-contractHistoryHistorical-contratsOctroyesHistorique.csv"

logger.info(f"CSV file: {csv_file}")
logger.info(f"File exists: {Path(csv_file).exists()}")
logger.info(f"File size: {Path(csv_file).stat().st_size / 1024 / 1024:.1f} MB")

try:
    with get_session() as session:
        logger.info("Got database session successfully")
        stats = load_canada_contracts(session, csv_file)
        logger.info("Loading completed!")
        print(f"\nSuccess! Stats:")
        print(f"  Vendors created: {stats['vendors_created']}")
        print(f"  Vendors updated: {stats['vendors_updated']}")
        print(f"  GSIN codes added: {stats['gsin_codes_added']}")
        print(f"  UNSPSC codes added: {stats['unspsc_codes_added']}")
        print(f"  Contacts added: {stats['contacts_added']}")
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    sys.exit(1)
