#!/usr/bin/env python3
"""텔레그램 Telethon 세션 파일 생성 스크립트.

최초 1회 로컬에서 실행하여 .session 파일을 생성합니다.
이후 Docker 컨테이너에서는 이 세션 파일을 마운트하여 인증 없이 사용.

실행:
    python scripts/create_telegram_session.py

인증 흐름:
    1. TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE 이 .env에 설정되어야 함
    2. 실행 시 텔레그램으로 인증 코드 수신
    3. 코드 입력 → 세션 파일 생성 (data/sessions/tg_user.session)
    4. 2FA 설정된 경우 비밀번호 추가 입력
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import telegram_api_id, telegram_api_hash, telegram_phone, get_base_dir


async def create_session():
    from telethon import TelegramClient

    api_id = telegram_api_id()
    api_hash = telegram_api_hash()
    phone = telegram_phone()

    if not api_id or not api_hash:
        print("❌ TELEGRAM_API_ID 와 TELEGRAM_API_HASH 를 .env에 설정해주세요.")
        print("   → https://my.telegram.org/apps 에서 발급 가능")
        sys.exit(1)

    if not phone:
        print("❌ TELEGRAM_PHONE 을 .env에 설정해주세요. (예: +821012345678)")
        sys.exit(1)

    session_dir = get_base_dir() / "data" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = str(session_dir / "tg_user")

    print(f"📱 텔레그램 세션 생성 중...")
    print(f"   API ID: {api_id}")
    print(f"   Phone: {phone}")
    print(f"   Session: {session_path}.session")
    print()

    client = TelegramClient(session_path, api_id, api_hash)
    await client.start(phone=phone)

    me = await client.get_me()
    print()
    print(f"✅ 세션 생성 성공!")
    print(f"   User: {me.first_name} {me.last_name or ''}")
    print(f"   Username: @{me.username or 'N/A'}")
    print(f"   Session file: {session_path}.session")
    print()
    print(f"⚠️  이 세션 파일을 절대 git에 커밋하지 마세요!")
    print(f"   Docker 사용 시 volume mount로 전달하세요.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(create_session())
