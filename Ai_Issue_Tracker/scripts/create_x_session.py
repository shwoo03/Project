#!/usr/bin/env python3
"""X (Twitter) 웹 세션 생성 스크립트.

로컬에서 headful(보이는) 브라우저로 실행하여 로그인 + 2FA 처리.
생성된 세션 파일을 Docker에 마운트하면 headless 환경에서 재사용 가능.

실행:
    python scripts/create_x_session.py

흐름:
    1. 브라우저가 열리며 X 로그인 페이지 표시
    2. 자동으로 username, password 입력
    3. 2FA가 있으면 브라우저에서 직접 입력 (60초 대기)
    4. 로그인 완료 후 세션 상태 저장 → data/sessions/x_state.json
"""

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import env, get_base_dir


STATE_PATH = get_base_dir() / "data" / "sessions" / "x_state.json"

SELECTORS = {
    "login_username_input": 'input[autocomplete="username"]',
    "login_next_button": '[role="button"]:has-text("Next"), [role="button"]:has-text("다음")',
    "login_password_input": 'input[name="password"], input[type="password"]',
    "login_submit_button": '[data-testid="LoginForm_Login_Button"]',
    "login_email_input": 'input[data-testid="ocfEnterTextTextInput"]',
    "login_email_confirm": '[data-testid="ocfEnterTextNextButton"]',
}


async def create_session():
    from playwright.async_api import async_playwright

    username = env("X_USERNAME")
    password = env("X_PASSWORD")
    email = env("X_EMAIL")

    if not username or not password:
        print("❌ X_USERNAME 과 X_PASSWORD 를 .env에 설정해주세요.")
        sys.exit(1)

    print(f"🐦 X 웹 세션 생성 시작")
    print(f"   Username: @{username}")
    print(f"   Email: {email or '(미설정)'}")
    print()

    async with async_playwright() as p:
        # headful 모드 — 2FA 수동 입력 가능
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # 1) 로그인 페이지
        print("📌 로그인 페이지 로딩...")
        await page.goto("https://x.com/i/flow/login", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # 2) Username
        print("📌 Username 입력 중...")
        uinput = await page.wait_for_selector(
            SELECTORS["login_username_input"], timeout=15000
        )
        await uinput.fill(username)
        await page.wait_for_timeout(500)

        nbtn = await page.wait_for_selector(
            SELECTORS["login_next_button"], timeout=5000
        )
        await nbtn.click()
        await page.wait_for_timeout(2000)

        # 3) Email challenge
        try:
            einput = await page.wait_for_selector(
                SELECTORS["login_email_input"], timeout=3000
            )
            if einput:
                print("📌 Email challenge 감지 — email 입력 중...")
                await einput.fill(email or username)
                ec = await page.wait_for_selector(
                    SELECTORS["login_email_confirm"], timeout=5000
                )
                await ec.click()
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        # 4) Password
        print("📌 Password 입력 중...")
        pinput = await page.wait_for_selector(
            SELECTORS["login_password_input"], timeout=10000
        )
        await pinput.fill(password)
        await page.wait_for_timeout(500)

        lbtn = await page.wait_for_selector(
            SELECTORS["login_submit_button"], timeout=5000
        )
        await lbtn.click()

        # 5) 로그인 완료 대기 (2FA 포함)
        home_pattern = re.compile(r"https://x\.com/(home|[^/]+)$")
        print()
        print("⏳ 로그인 완료 대기 중...")
        print("   2FA가 설정되어 있으면 브라우저에서 직접 입력하세요.")
        print("   (최대 120초 대기)")
        print()

        try:
            await page.wait_for_url(home_pattern, timeout=120000)
        except Exception:
            print("❌ 로그인 타임아웃. 브라우저를 확인해주세요.")
            await browser.close()
            sys.exit(1)

        # 6) 세션 저장
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state = await context.storage_state()
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

        print(f"✅ 세션 생성 성공!")
        print(f"   저장 위치: {STATE_PATH}")
        print()
        print(f"⚠️  주의사항:")
        print(f"   - 이 파일은 X 계정 전체 접근 권한과 동일합니다")
        print(f"   - 절대 git에 커밋하지 마세요 (.gitignore에 추가됨)")
        print(f"   - Docker 사용 시 volume mount로 전달하세요")

        # 세션 유효성 간단 확인
        await page.goto("https://x.com/home", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        articles = await page.query_selector_all('article[data-testid="tweet"]')
        print(f"   - 홈 피드 확인: {len(articles)}개 트윗 로딩됨")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(create_session())
