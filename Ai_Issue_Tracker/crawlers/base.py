"""Base crawler interface and shared data model."""

from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import requests

from config import load_sources

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Normalized crawl result — all crawlers output this format."""
    url: str
    title: str
    content: str = ""
    source: str = ""          # e.g. "@OpenAI", "Hacker News"
    source_type: str = ""     # x | telegram | rss | web
    category: str = ""
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_storage_dict(self) -> dict:
        return asdict(self)


class BaseCrawler(ABC):
    """Abstract base for all crawlers."""

    def __init__(self):
        cfg = load_sources().get("crawl_settings", {})
        self.delay = cfg.get("request_delay", 2.0)
        self.timeout = cfg.get("request_timeout", 15)
        self.user_agent = cfg.get("user_agent", "ai-news-bot/1.0")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    @abstractmethod
    def fetch(self) -> list[CrawlResult]:
        """Crawl and return normalized results."""
        ...

    def _sleep(self):
        """Rate limit between requests."""
        time.sleep(self.delay)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_get(self, url: str, **kwargs) -> requests.Response | None:
        """GET with error handling."""
        try:
            resp = self.session.get(url, timeout=self.timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.error(f"[{self.__class__.__name__}] GET {url} failed: {e}")
            return None
