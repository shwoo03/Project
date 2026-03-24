"""Generic website crawler — requests + BeautifulSoup.

CSS 셀렉터 기반으로 뉴스 항목을 추출.
JS 렌더링이 필요한 사이트는 playwright 사용 (config에서 use_playwright: true).
"""

import logging
import re

from bs4 import BeautifulSoup

from config import load_sources
from crawlers.base import BaseCrawler, CrawlResult

logger = logging.getLogger(__name__)


class WebCrawler(BaseCrawler):
    def fetch(self) -> list[CrawlResult]:
        sources = load_sources()
        sites = [s for s in sources.get("websites", []) if s.get("enabled", True)]

        results: list[CrawlResult] = []

        for site in sites:
            url = site["url"]
            name = site.get("name", url)
            category = site.get("category", "")
            selectors = site.get("selectors", {})
            keywords = [kw.lower() for kw in site.get("keywords", [])]
            use_playwright = site.get("use_playwright", False)

            try:
                html = self._fetch_html(url, use_playwright)
                if not html:
                    continue

                items = self._extract_items(html, url, selectors, keywords)
                for item in items:
                    item.source = name
                    item.source_type = "web"
                    item.category = category

                results.extend(items)
                logger.info(f"[Web] {name}: {len(items)} items")
                self._sleep()

            except Exception as e:
                logger.error(f"[Web] Failed to crawl {name} ({url}): {e}")

        logger.info(f"[Web] Total collected: {len(results)} items")
        return results

    def _fetch_html(self, url: str, use_playwright: bool = False) -> str | None:
        if use_playwright:
            return self._fetch_with_playwright(url)

        resp = self._safe_get(url)
        return resp.text if resp else None

    def _fetch_with_playwright(self, url: str) -> str | None:
        """Playwright를 사용한 JS 렌더링 페이지 크롤링."""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                html = page.content()
                browser.close()
                return html
        except ImportError:
            logger.error("[Web] playwright not installed. Run: pip install playwright && playwright install chromium")
            return None
        except Exception as e:
            logger.error(f"[Web] Playwright error for {url}: {e}")
            return None

    def _extract_items(
        self,
        html: str,
        base_url: str,
        selectors: dict,
        keywords: list[str],
    ) -> list[CrawlResult]:
        soup = BeautifulSoup(html, "lxml")
        results: list[CrawlResult] = []

        item_selector = selectors.get("item", "article")
        title_selector = selectors.get("title", "h2")
        link_selector = selectors.get("link", "a::attr(href)")

        for element in soup.select(item_selector):
            # 제목 추출
            title_el = element.select_one(title_selector.replace("::attr(href)", ""))
            title = title_el.get_text(strip=True) if title_el else ""

            # 링크 추출
            link = self._extract_link(element, link_selector, base_url)

            if not title or not link:
                continue

            # 키워드 필터 (설정된 경우)
            if keywords and not self._matches_keywords(title, keywords):
                continue

            # 본문 미리보기 (있으면)
            content = element.get_text(strip=True)[:500]

            results.append(CrawlResult(
                url=link,
                title=title,
                content=content,
                created_at=self._now_iso(),
            ))

        return results

    @staticmethod
    def _extract_link(element, selector: str, base_url: str) -> str:
        """CSS 셀렉터에서 href 추출."""
        # ::attr(href) 패턴 처리
        if "::attr(" in selector:
            attr_match = re.search(r"::attr\((\w+)\)", selector)
            attr_name = attr_match.group(1) if attr_match else "href"
            css = selector.split("::attr(")[0] or "a"
        else:
            css = selector
            attr_name = "href"

        el = element.select_one(css)
        if not el:
            # fallback: 첫 번째 <a> 태그
            el = element.select_one("a")

        if not el:
            return ""

        link = el.get(attr_name, "")
        if not link:
            return ""

        # 상대 URL → 절대 URL
        if link.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            link = f"{parsed.scheme}://{parsed.netloc}{link}"
        elif not link.startswith("http"):
            link = f"{base_url.rstrip('/')}/{link}"

        return link

    @staticmethod
    def _matches_keywords(text: str, keywords: list[str]) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)
