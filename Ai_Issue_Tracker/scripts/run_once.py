#!/usr/bin/env python3
"""수동 파이프라인 실행 스크립트.

테스트 및 디버깅용. 스케줄러 없이 즉시 1회 실행.

실행:
    python scripts/run_once.py              # 전체 파이프라인
    python scripts/run_once.py --crawl-only # 크롤링만
    python scripts/run_once.py --dry-run    # 요약까지만 (전송 안 함)
"""

import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_once")


async def main():
    args = set(sys.argv[1:])

    if "--crawl-only" in args:
        logger.info("=== CRAWL ONLY MODE ===")
        from crawlers import crawl_all
        results = crawl_all()
        logger.info(f"Crawled {len(results)} items")

        for r in results[:10]:
            print(f"  [{r.source_type}] {r.source}: {r.title[:80]}")
        if len(results) > 10:
            print(f"  ... and {len(results) - 10} more")
        return

    if "--dry-run" in args:
        logger.info("=== DRY RUN MODE (no send) ===")
        from crawlers import crawl_all
        from storage import get_unsummarized_items
        from summarizer import summarize_items

        results = crawl_all()
        items = get_unsummarized_items(limit=30)
        logger.info(f"Items to summarize: {len(items)}")

        if items:
            summary = summarize_items(items)
            print("\n" + "=" * 60)
            print("GENERATED SUMMARY:")
            print("=" * 60)
            print(summary)
            print("=" * 60)
        return

    # 전체 파이프라인
    logger.info("=== FULL PIPELINE ===")
    from scheduler.pipeline import run_pipeline
    await run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())
