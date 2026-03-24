"""Crawler orchestrator — runs all enabled crawlers and stores results."""

import logging

from crawlers.base import CrawlResult
from storage import insert_items_bulk

logger = logging.getLogger(__name__)


def crawl_all() -> list[CrawlResult]:
    """Run all crawlers, deduplicate, and store to DB.

    Returns list of newly added CrawlResults.
    """
    all_results: list[CrawlResult] = []

    # --- X (Twitter) — Playwright 웹 크롤링 ---
    try:
        from crawlers.sources.x_crawler import XWebCrawler
        crawler = XWebCrawler()
        results = crawler.fetch()
        all_results.extend(results)
    except Exception as e:
        logger.error(f"[Orchestrator] X crawler failed: {e}")

    # --- Telegram ---
    try:
        from crawlers.sources.telegram_crawler import TelegramCrawler
        crawler = TelegramCrawler()
        results = crawler.fetch()
        all_results.extend(results)
    except Exception as e:
        logger.error(f"[Orchestrator] Telegram crawler failed: {e}")

    # --- RSS ---
    try:
        from crawlers.sources.rss_crawler import RSSCrawler
        crawler = RSSCrawler()
        results = crawler.fetch()
        all_results.extend(results)
    except Exception as e:
        logger.error(f"[Orchestrator] RSS crawler failed: {e}")

    # --- Web ---
    try:
        from crawlers.sources.web_crawler import WebCrawler
        crawler = WebCrawler()
        results = crawler.fetch()
        all_results.extend(results)
    except Exception as e:
        logger.error(f"[Orchestrator] Web crawler failed: {e}")

    # --- URL 기준 중복 제거 ---
    seen: set[str] = set()
    unique: list[CrawlResult] = []
    for r in all_results:
        if r.url and r.url not in seen:
            seen.add(r.url)
            unique.append(r)

    logger.info(f"[Orchestrator] Total: {len(all_results)}, Unique: {len(unique)}")

    # --- DB 저장 ---
    storage_items = [r.to_storage_dict() for r in unique]
    added, skipped = insert_items_bulk(storage_items)
    logger.info(f"[Orchestrator] DB: {added} added, {skipped} skipped (already exist)")

    return unique
