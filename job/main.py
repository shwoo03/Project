#!/usr/bin/env python3
"""
Job Scraper & Notifier

Scrapes job postings from Enki and Theori, syncs to Notion, and notifies via Discord.
"""

import sys
import argparse

from utils import database, service, config
from companies import enki, theori

SCRAPERS = {
    "enki": {
        "scraper": enki.scrape_jobs,
        "label": config.ENKI_SOURCE_LABEL,
    },
    "theori": {
        "scraper": theori.scrape_jobs,
        "label": config.THEORI_SOURCE_LABEL,
    },
}

def main() -> None:
    parser = argparse.ArgumentParser(description="Job Scraper & Notifier")
    parser.add_argument(
        "--module",
        choices=list(SCRAPERS.keys()),
        help="Run a specific scraper module",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual writes)",
    )
    args = parser.parse_args()

    # Initialize Database
    database.get_db()

    # Determine which modules to run
    modules_to_run = [args.module] if args.module else list(SCRAPERS.keys())

    for module_name in modules_to_run:
        scraper_info = SCRAPERS[module_name]
        scraper_func = scraper_info["scraper"]
        label = scraper_info["label"]

        print(f"\n{'='*50}")
        print(f"Running {label} scraper...")
        print(f"{'='*50}")

        try:
            jobs = scraper_func()
            print(f"[INFO] Found {len(jobs)} jobs from {label}.")
            
            service.sync_jobs(jobs, label, dry_run=args.dry_run)
            
        except Exception as exc:
            print(f"[ERROR] Failed to run {label} scraper: {exc}", file=sys.stderr)
            continue

    print(f"\n{'='*50}")
    print("All scrapers completed.")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
