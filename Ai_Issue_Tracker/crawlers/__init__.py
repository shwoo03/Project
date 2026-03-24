"""Crawlers — multi-platform news collection layer."""

from crawlers.base import CrawlResult, BaseCrawler
from crawlers.orchestrator import crawl_all

__all__ = ["CrawlResult", "BaseCrawler", "crawl_all"]
