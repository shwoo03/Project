"""X (Twitter) crawler — Playwright 웹 인증 자동화 + DOM 크롤링.

API Free tier의 읽기 제한을 우회하여 웹 브라우저 자동화로 크롤링.

인증 흐름:
  1. 최초 실행: Playwright로 x.com 로그인
     → username 입력 → password 입력 → (2FA 있으면 수동 입력 대기)
  2. 로그인 성공 후 브라우저 상태(cookies + localStorage) 저장
     → data/sessions/x_state.json
  3. 이후 실행: 저장된 상태를 로드하여 자동 인증
     → 세션 만료 시 자동 재로그인

.env 필요 변수:
  X_USERNAME=your_username     (@ 제외)
  X_PASSWORD=your_password
  X_EMAIL=your_email           (로그인 challenge 시 사용)

보안 주의:
  - x_state.json은 X 계정 전체 세션과 동일 → 절대 git에 커밋 금지
  - Docker 사용 시 volume mount로 전달
  - 2FA 설정 강력 권장 (세션 탈취 대비)
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import load_sources, env, get_base_dir
from crawlers.base import CrawlResult

logger = logging.getLogger(__name__)

STATE_PATH = get_base_dir() / "data" / "sessions" / "x_state.json"

# X DOM selectors (2025-2026 기준, UI 변경 시 업데이트 필요)
SELECTORS = {
    # 로그인 플로우
    "login_username_input": 'input[autocomplete="username"]',
    "login_next_button": '[role="button"]:has-text("Next"), [role="button"]:has-text("다음")',
    "login_password_input": 'input[name="password"], input[type="password"]',
    "login_submit_button": '[data-testid="LoginForm_Login_Button"]',
    "login_email_input": 'input[data-testid="ocfEnterTextTextInput"]',
    "login_email_confirm": '[data-testid="ocfEnterTextNextButton"]',

    # 트윗 DOM
    "tweet_article": 'article[data-testid="tweet"]',
    "tweet_text": '[data-testid="tweetText"]',
    "tweet_time": "time",
    "tweet_link": 'a[href*="/status/"]',
}


class XWebCrawler:
    """Playwright 기반 X 웹 크롤러.

    asyncio 기반이므로 BaseCrawler를 상속하지 않고 독립 구현.
    orchestrator에서 fetch() 호출 시 내부적으로 async 실행.
    """

    def __init__(self):
        cfg = load_sources().get("crawl_settings", {})
        self.lookback_hours = cfg.get("x_hours_lookback", 8)
        self.delay = cfg.get("request_delay", 2.0)

        self.username = env("X_USERNAME")
        self.password = env("X_PASSWORD")
        self.email = env("X_EMAIL")

        if not self.username or not self.password:
            raise ValueError("X_USERNAME and X_PASSWORD must be set in .env")

    def fetch(self) -> list[CrawlResult]:
        """Sync wrapper — orchestrator에서 호출."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(self._async_fetch())).result()
            return loop.run_until_complete(self._async_fetch())
        except RuntimeError:
            return asyncio.run(self._async_fetch())

    async def _async_fetch(self) -> list[CrawlResult]:
        from playwright.async_api import async_playwright

        sources = load_sources()
        accounts = [a for a in sources.get("x_accounts", []) if a.get("enabled", True)]

        if not accounts:
            logger.info("[X-Web] No accounts configured")
            return []

        results: list[CrawlResult] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )

            context = await self._get_authenticated_context(browser)
            if not context:
                logger.error("[X-Web] Authentication failed")
                await browser.close()
                return []

            page = await context.new_page()
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
            })

            for account in accounts:
                username = account["username"]
                category = account.get("category", "")

                try:
                    tweets = await self._scrape_user_timeline(page, username)

                    for tweet in tweets:
                        results.append(CrawlResult(
                            url=tweet["url"],
                            title=tweet["text"][:120],
                            content=tweet["text"],
                            source=f"@{username}",
                            source_type="x",
                            category=category,
                            created_at=tweet.get("created_at", ""),
                            metadata={"metrics": tweet.get("metrics", {})},
                        ))

                    logger.info(f"[X-Web] @{username}: {len(tweets)} tweets")
                    await asyncio.sleep(self.delay)

                except Exception as e:
                    logger.error(f"[X-Web] Failed @{username}: {e}")

            await self._save_state(context)
            await context.close()
            await browser.close()

        logger.info(f"[X-Web] Total: {len(results)} tweets from {len(accounts)} accounts")
        return results

    # ──────────────────────────────────────────────
    #  인증 레이어
    # ──────────────────────────────────────────────

    async def _get_authenticated_context(self, browser):
        """저장된 세션 복원 → 실패 시 새 로그인."""

        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )

        # 1) 기존 세션 복원
        if STATE_PATH.exists():
            logger.info("[X-Web] Restoring saved session...")
            try:
                context = await browser.new_context(
                    storage_state=str(STATE_PATH),
                    viewport={"width": 1280, "height": 900},
                    user_agent=ua,
                )
                if await self._verify_session(context):
                    logger.info("[X-Web] Session restored OK")
                    return context
                logger.warning("[X-Web] Session expired, re-logging in...")
                await context.close()
            except Exception as e:
                logger.warning(f"[X-Web] Session restore error: {e}")

        # 2) 새 로그인
        logger.info("[X-Web] Fresh login...")
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=ua,
        )

        if await self._login(context):
            await self._save_state(context)
            return context

        await context.close()
        return None

    async def _login(self, context) -> bool:
        """X 웹 로그인 자동화.

        플로우:
          1. x.com/i/flow/login 이동
          2. username 입력 → "Next" 클릭
          3. (email challenge) → email 입력 → 확인
          4. password 입력 → "Log in" 클릭
          5. 홈 피드 로딩 확인
        """
        page = await context.new_page()

        try:
            await page.goto("https://x.com/i/flow/login", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # Username
            logger.info("[X-Web] Step 1: username")
            username_input = await page.wait_for_selector(
                SELECTORS["login_username_input"], timeout=15000
            )
            await username_input.fill(self.username)
            await page.wait_for_timeout(500)

            next_btn = await page.wait_for_selector(
                SELECTORS["login_next_button"], timeout=5000
            )
            await next_btn.click()
            await page.wait_for_timeout(2000)

            # Email challenge (의심스러운 로그인 시 X가 요청)
            try:
                email_input = await page.wait_for_selector(
                    SELECTORS["login_email_input"], timeout=3000
                )
                if email_input:
                    logger.info("[X-Web] Step 2: email challenge")
                    await email_input.fill(self.email or self.username)
                    confirm = await page.wait_for_selector(
                        SELECTORS["login_email_confirm"], timeout=5000
                    )
                    await confirm.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass  # no challenge

            # Password
            logger.info("[X-Web] Step 3: password")
            pw_input = await page.wait_for_selector(
                SELECTORS["login_password_input"], timeout=10000
            )
            await pw_input.fill(self.password)
            await page.wait_for_timeout(500)

            login_btn = await page.wait_for_selector(
                SELECTORS["login_submit_button"], timeout=5000
            )
            await login_btn.click()

            # 로그인 완료 대기 (2FA 포함 최대 120초)
            home_pattern = re.compile(r"https://x\.com/(home|[^/]+)$")
            try:
                await page.wait_for_url(home_pattern, timeout=30000)
                logger.info("[X-Web] Login OK")
                await page.close()
                return True
            except Exception:
                logger.warning("[X-Web] Waiting for 2FA (up to 90s)...")
                try:
                    await page.wait_for_url(home_pattern, timeout=90000)
                    logger.info("[X-Web] Login OK (post-2FA)")
                    await page.close()
                    return True
                except Exception:
                    logger.error("[X-Web] Login timeout. Run create_x_session.py locally.")
                    await page.close()
                    return False

        except Exception as e:
            logger.error(f"[X-Web] Login error: {e}")
            try:
                await page.close()
            except Exception:
                pass
            return False

    async def _verify_session(self, context) -> bool:
        """세션 유효성 확인 — /home 로딩 후 피드 존재 체크."""
        page = await context.new_page()
        try:
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)

            if "/login" in page.url or "/i/flow" in page.url:
                await page.close()
                return False

            await page.wait_for_selector(SELECTORS["tweet_article"], timeout=10000)
            await page.close()
            return True
        except Exception:
            try:
                await page.close()
            except Exception:
                pass
            return False

    async def _save_state(self, context):
        """브라우저 상태 저장 (cookies + localStorage)."""
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            state = await context.storage_state()
            STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
            logger.info(f"[X-Web] State saved → {STATE_PATH}")
        except Exception as e:
            logger.error(f"[X-Web] State save failed: {e}")

    # ──────────────────────────────────────────────
    #  크롤링 레이어
    # ──────────────────────────────────────────────

    async def _scrape_user_timeline(self, page, username: str) -> list[dict]:
        """유저 프로필 페이지에서 트윗을 DOM 파싱으로 추출."""
        await page.goto(f"https://x.com/{username}", wait_until="domcontentloaded")

        try:
            await page.wait_for_selector(SELECTORS["tweet_article"], timeout=15000)
        except Exception:
            logger.warning(f"[X-Web] No tweets loaded for @{username}")
            return []

        # 스크롤로 추가 로딩 (3회)
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1500)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        return await self._extract_tweets(page, username, cutoff)

    async def _extract_tweets(self, page, username: str, cutoff: datetime) -> list[dict]:
        """JS evaluate로 DOM에서 트윗 데이터 일괄 추출."""

        raw_tweets = await page.evaluate("""
            (sel) => {
                const articles = document.querySelectorAll(sel.tweet_article);
                const out = [];

                articles.forEach(a => {
                    try {
                        const textEl = a.querySelector(sel.tweet_text);
                        const text = textEl ? textEl.innerText.trim() : '';
                        if (!text) return;

                        const timeEl = a.querySelector(sel.tweet_time);
                        const dt = timeEl ? timeEl.getAttribute('datetime') : '';

                        let tweetUrl = '';
                        a.querySelectorAll(sel.tweet_link).forEach(link => {
                            const h = link.getAttribute('href') || '';
                            if (h.includes('/status/') && !tweetUrl) tweetUrl = h;
                        });

                        const metric = (tid) => {
                            const el = a.querySelector(`[data-testid="${tid}"] span`);
                            return el ? el.innerText.trim() : '0';
                        };

                        out.push({
                            text,
                            created_at: dt,
                            url_path: tweetUrl,
                            metrics: {
                                replies: metric('reply'),
                                retweets: metric('retweet'),
                                likes: metric('like'),
                            }
                        });
                    } catch(_) {}
                });
                return out;
            }
        """, SELECTORS)

        tweets: list[dict] = []
        seen: set[str] = set()

        for raw in raw_tweets:
            url_path = raw.get("url_path", "")
            full_url = f"https://x.com{url_path}" if url_path and not url_path.startswith("http") else url_path

            # 해당 유저 트윗만 필터
            if f"/{username.lower()}/status/" not in full_url.lower():
                continue

            if full_url in seen:
                continue
            seen.add(full_url)

            # 시간 필터
            created_at = raw.get("created_at", "")
            if created_at:
                try:
                    t = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if t < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

            tweets.append({
                "text": raw.get("text", ""),
                "url": full_url,
                "created_at": created_at,
                "metrics": raw.get("metrics", {}),
            })

        return tweets
