"""Telegram channel/group crawler — Telethon (MTProto) 기반.

인증 방식:
  1. my.telegram.org 접속 → API Development Tools → App 생성
     → API_ID, API_HASH 발급
  2. 최초 실행 시 전화번호 인증 (scripts/create_telegram_session.py)
     → data/sessions/ 에 .session 파일 생성됨
  3. 이후 .session 파일로 자동 인증 (비밀번호/코드 불필요)

주의사항:
  - Bot API (TELEGRAM_BOT_TOKEN) 와 별개의 인증 체계
  - Bot API: 봇이 추가된 채널만 읽기 가능, 히스토리 제한적
  - Telethon (User API): 가입된 모든 채널/그룹 읽기 가능, 풀 히스토리 접근
  - FloodWaitError 발생 시 자동 대기 (과도한 요청 방지)
  - .session 파일은 절대 git에 커밋하지 말 것 (.gitignore에 추가됨)
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import (
    load_sources,
    telegram_api_id,
    telegram_api_hash,
    telegram_phone,
    get_base_dir,
)
from crawlers.base import CrawlResult

logger = logging.getLogger(__name__)

SESSION_DIR = get_base_dir() / "data" / "sessions"


def _get_session_path() -> str:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return str(SESSION_DIR / "tg_user")


class TelegramCrawler:
    """Telethon 기반 텔레그램 크롤러.

    Note: Telethon은 asyncio 기반이므로 BaseCrawler를 상속하지 않고
    별도로 구현. orchestrator에서 async로 호출.
    """

    def __init__(self):
        cfg = load_sources().get("crawl_settings", {})
        self.lookback_hours = cfg.get("tg_hours_lookback", 8)

    def fetch(self) -> list[CrawlResult]:
        """Sync wrapper for async fetch."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 이미 이벤트 루프가 돌고 있으면 새 루프 생성
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(self._async_fetch())).result()
            return loop.run_until_complete(self._async_fetch())
        except RuntimeError:
            return asyncio.run(self._async_fetch())

    async def _async_fetch(self) -> list[CrawlResult]:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError

        api_id = telegram_api_id()
        api_hash = telegram_api_hash()
        if not api_id or not api_hash:
            logger.error("[TG] TELEGRAM_API_ID or TELEGRAM_API_HASH not set")
            return []

        session_path = _get_session_path()
        client = TelegramClient(session_path, api_id, api_hash)

        results: list[CrawlResult] = []
        try:
            await client.start(phone=telegram_phone())

            sources = load_sources()
            channels = [
                ch for ch in sources.get("telegram_channels", [])
                if ch.get("enabled", True)
            ]

            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

            for ch_cfg in channels:
                channel_name = ch_cfg["channel"]
                category = ch_cfg.get("category", "")
                limit = ch_cfg.get("limit", 50)

                try:
                    entity = await client.get_entity(channel_name)
                    messages = await client.get_messages(
                        entity,
                        limit=limit,
                        offset_date=None,
                    )

                    for msg in messages:
                        # 시간 필터
                        if msg.date and msg.date.replace(tzinfo=timezone.utc) < cutoff:
                            break

                        if not msg.text:
                            continue

                        # 메시지 URL 생성
                        if hasattr(entity, "username") and entity.username:
                            url = f"https://t.me/{entity.username}/{msg.id}"
                        else:
                            url = f"tg://channel/{entity.id}/{msg.id}"

                        results.append(CrawlResult(
                            url=url,
                            title=msg.text[:120],
                            content=msg.text,
                            source=channel_name,
                            source_type="telegram",
                            category=category,
                            created_at=msg.date.isoformat() if msg.date else "",
                            metadata={
                                "message_id": msg.id,
                                "views": getattr(msg, "views", 0),
                                "forwards": getattr(msg, "forwards", 0),
                            },
                        ))

                    logger.info(f"[TG] {channel_name}: collected {len(messages)} messages")

                except FloodWaitError as e:
                    logger.warning(f"[TG] FloodWait: sleeping {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"[TG] Failed to crawl {channel_name}: {e}")

        except Exception as e:
            logger.error(f"[TG] Client error: {e}")
        finally:
            await client.disconnect()

        logger.info(f"[TG] Total collected: {len(results)} messages")
        return results
