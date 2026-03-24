"""RSS feed crawler — feedparser 기반.

인증: 불필요 (공개 RSS 피드)
별도 인증이 필요한 RSS는 config에서 headers 설정으로 확장 가능.
"""

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser

from config import load_sources
from crawlers.base import BaseCrawler, CrawlResult

logger = logging.getLogger(__name__)


class RSSCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        cfg = load_sources().get("crawl_settings", {})
        self.lookback_hours = cfg.get("rss_hours_lookback", 24)

    def fetch(self) -> list[CrawlResult]:
        sources = load_sources()
        feeds = [f for f in sources.get("rss_feeds", []) if f.get("enabled", True)]

        results: list[CrawlResult] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

        for feed_cfg in feeds:
            url = feed_cfg["url"]
            name = feed_cfg.get("name", url)
            category = feed_cfg.get("category", "")

            try:
                parsed = feedparser.parse(url)
                for entry in parsed.entries:
                    pub_date = self._parse_date(entry)
                    if pub_date and pub_date < cutoff:
                        continue

                    link = entry.get("link", "")
                    title = entry.get("title", "")
                    # 본문: summary > content > description
                    content = (
                        entry.get("summary", "")
                        or self._get_content(entry)
                        or entry.get("description", "")
                    )

                    if not link or not title:
                        continue

                    results.append(CrawlResult(
                        url=link,
                        title=title,
                        content=self._strip_html(content),
                        source=name,
                        source_type="rss",
                        category=category,
                        created_at=pub_date.isoformat() if pub_date else "",
                        metadata={
                            "feed_url": url,
                            "author": entry.get("author", ""),
                            "tags": [t.get("term", "") for t in entry.get("tags", [])],
                        },
                    ))

                logger.info(f"[RSS] {name}: {len(parsed.entries)} entries")
                self._sleep()

            except Exception as e:
                logger.error(f"[RSS] Failed to parse {name} ({url}): {e}")

        logger.info(f"[RSS] Total collected: {len(results)} items")
        return results

    @staticmethod
    def _parse_date(entry) -> datetime | None:
        """Parse RSS entry date."""
        for field in ("published_parsed", "updated_parsed"):
            tp = entry.get(field)
            if tp:
                try:
                    from time import mktime
                    dt = datetime.fromtimestamp(mktime(tp), tz=timezone.utc)
                    return dt
                except (ValueError, OverflowError):
                    pass

        for field in ("published", "updated"):
            raw = entry.get(field, "")
            if raw:
                try:
                    return parsedate_to_datetime(raw).replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    pass
        return None

    @staticmethod
    def _get_content(entry) -> str:
        content_list = entry.get("content", [])
        if content_list:
            return content_list[0].get("value", "")
        return ""

    @staticmethod
    def _strip_html(text: str) -> str:
        """Simple HTML tag removal."""
        import re
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:2000]  # 요약 전 본문은 2000자 제한
