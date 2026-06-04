#!/usr/bin/env python3
"""
Main script to run the Wikipedia Citation Gap extraction pipeline.
"""

import argparse
import logging
import sys
from pathlib import Path

from zim_parser import ZIMParser, save_to_database, export_to_csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Wikipedia Citation Gap Extraction Pipeline")
    parser.add_argument("zim_file", help="Path to Wikipedia ZIM file")
    parser.add_argument("--db", default="data/citation_gaps.db", help="Output SQLite database path")
    parser.add_argument("--csv", default="data/citation_gaps.csv", help="Output CSV path")
    parser.add_argument("--skip-csv", action="store_true", help="Skip CSV export")

    args = parser.parse_args()

    # Validate ZIM file exists
    zim_path = Path(args.zim_file)
    if not zim_path.exists():
        logger.error(f"ZIM file not found: {zim_path}")
        sys.exit(1)

    # Create output directories
    db_path = Path(args.db)
    csv_path = Path(args.csv)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting citation gap extraction from {zim_path}")
    logger.info(f"Output database: {db_path}")
    if not args.skip_csv:
        logger.info(f"Output CSV: {csv_path}")

    try:
        # Parse ZIM file and extract citation gaps
        parser = ZIMParser(str(zim_path))
        gaps = parser.extract_citation_gaps()

        # Save to database
        logger.info("Saving results to database...")
        save_to_database(gaps, str(db_path))

        # Export to CSV
        if not args.skip_csv:
            logger.info("Exporting to CSV...")
            export_to_csv(str(db_path), str(csv_path))

        logger.info("✅ Citation gap extraction completed successfully!")
        logger.info(f"📊 Database ready at: {db_path}")
        if not args.skip_csv:
            logger.info(f"📄 CSV export at: {csv_path}")
        logger.info("🚀 Start the API server with: python api.py")

    except KeyboardInterrupt:
        logger.info("Extraction interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()