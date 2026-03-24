"""Pipeline — CRAWL → SUMMARIZE → SEND 전체 파이프라인."""

import asyncio
import logging
from datetime import datetime

from config import max_items_per_digest, timezone_str

logger = logging.getLogger(__name__)


async def run_pipeline():
    """전체 파이프라인 실행: 크롤링 → 요약 → 텔레그램 전송."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone_str())
    now = datetime.now(tz)
    logger.info(f"[Pipeline] Starting at {now.strftime('%Y-%m-%d %H:%M %Z')}")

    # --- 1. CRAWL ---
    logger.info("[Pipeline] Phase 1: Crawling...")
    try:
        from crawlers import crawl_all
        results = crawl_all()
    except Exception as e:
        logger.error(f"[Pipeline] Crawl failed: {e}")
        from bot import send_status
        await send_status(f"⚠️ 크롤링 실패: {e}")
        return

    if not results:
        logger.info("[Pipeline] No new items found")
        from bot import send_status
        await send_status("📭 새로운 뉴스가 없습니다.")
        return

    # --- 2. SUMMARIZE ---
    logger.info(f"[Pipeline] Phase 2: Summarizing {len(results)} items...")
    try:
        from storage import get_unsummarized_items, create_digest
        from summarizer import summarize_items

        items = get_unsummarized_items(limit=max_items_per_digest())
        if not items:
            logger.info("[Pipeline] No unsummarized items")
            return

        summary = summarize_items(items)

        # DB에 다이제스트 기록
        item_ids = [item["id"] for item in items if "id" in item]
        if item_ids:
            digest_id = create_digest(item_ids, summary)
            logger.info(f"[Pipeline] Digest #{digest_id} created with {len(item_ids)} items")

    except Exception as e:
        logger.error(f"[Pipeline] Summarize failed: {e}")
        from bot import send_status
        await send_status(f"⚠️ 요약 실패: {e}")
        return

    # --- 3. SEND ---
    logger.info("[Pipeline] Phase 3: Sending to Telegram...")
    try:
        from bot import send_digest
        from storage import mark_digest_sent

        # 헤더 추가
        time_label = _get_time_label(now.hour)
        header = f"🤖 *AI 뉴스 다이제스트* — {now.strftime('%m/%d')} {time_label}\n\n"
        full_message = header + summary

        success = await send_digest(full_message, item_count=len(items))

        if success and item_ids:
            mark_digest_sent(digest_id)
            logger.info("[Pipeline] Digest sent and marked")
        else:
            logger.warning("[Pipeline] Digest send failed")

    except Exception as e:
        logger.error(f"[Pipeline] Send failed: {e}")

    logger.info("[Pipeline] Complete")


def _get_time_label(hour: int) -> str:
    if hour < 10:
        return "🌅 아침"
    elif hour < 15:
        return "☀️ 점심"
    else:
        return "🌙 저녁"


def run_pipeline_sync():
    """Sync wrapper for the async pipeline."""
    asyncio.run(run_pipeline())
