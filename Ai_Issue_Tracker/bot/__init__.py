"""Telegram Bot — 다이제스트 전송 및 사용자 인터랙션.

python-telegram-bot 라이브러리 사용.
Bot HTTP API Token은 @BotFather에서 발급.
"""

import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import telegram_bot_token, telegram_chat_id

logger = logging.getLogger(__name__)

# 텔레그램 메시지 최대 길이
MAX_MESSAGE_LENGTH = 4096


async def send_digest(summary: str, item_count: int = 0) -> bool:
    """다이제스트 요약을 텔레그램으로 전송."""
    token = telegram_bot_token()
    chat_id = telegram_chat_id()

    if not token or not chat_id:
        logger.error("[Bot] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    bot = Bot(token=token)

    try:
        # 긴 메시지는 분할 전송
        chunks = _split_message(summary)

        for i, chunk in enumerate(chunks):
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
            except TelegramError:
                # Markdown 파싱 실패 시 plain text로 재시도
                await bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    disable_web_page_preview=True,
                )

        logger.info(f"[Bot] Digest sent: {len(chunks)} message(s), {item_count} items")
        return True

    except TelegramError as e:
        logger.error(f"[Bot] Failed to send digest: {e}")
        return False


async def send_status(text: str) -> bool:
    """상태 메시지 전송 (에러, 시작/종료 알림 등)."""
    token = telegram_bot_token()
    chat_id = telegram_chat_id()
    if not token or not chat_id:
        return False

    bot = Bot(token=token)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except TelegramError as e:
        logger.error(f"[Bot] Status message failed: {e}")
        return False


def _split_message(text: str) -> list[str]:
    """긴 메시지를 텔레그램 제한(4096자)에 맞게 분할."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    chunks: list[str] = []
    lines = text.split("\n")
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line

    if current:
        chunks.append(current)

    return chunks
