"""
인스타그램 로그인 및 쿠키 관리
"""
import os
import json
import time
import random
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def save_cookies(context, path="cookies.json"):
    """쿠키를 파일로 저장"""
    try:
        cookies = context.cookies()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info(f"쿠키 저장 완료: {path}")
    except IOError as e:
        logger.warning(f"쿠키 저장 실패 (파일 I/O): {e}")
    except Exception as e:
        logger.warning(f"쿠키 저장 실패: {e}")


def load_cookies(context, path="cookies.json"):
    """파일에서 쿠키 불러오기"""
    if not os.path.exists(path):
        return False
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
            context.add_cookies(cookies)
        logger.info(f"쿠키 불러오기 성공: {path}")
        return True
    except json.JSONDecodeError as e:
        logger.warning(f"쿠키 파일 JSON 파싱 실패: {e}")
        return False
    except Exception as e:
        logger.warning(f"쿠키 불러오기 실패: {e}")
        return False


def set_playwright_and_login(username, password):
    """
    Playwright 셋팅 및 로그인 수행 (Stealth 적용 + 쿠키 재사용)
    """
    try:
        with sync_playwright() as p:
            # 1. 브라우저 실행
            browser = p.chromium.launch(
                headless=True,
                channel="chrome",
                args=[
                    "--disable-blink-features=AutomationControlled", 
                    "--no-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                ]
            )

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                permissions=["geolocation"],
                geolocation={"latitude": 37.5665, "longitude": 126.9780},
                java_script_enabled=True,
            )

            # Stealth 스크립트 주입
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                if (!window.chrome) { window.chrome = { runtime: {} }; }
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """)
            
            page = context.new_page()

            # 2. 쿠키 로드 및 로그인 상태 확인
            if load_cookies(context):
                logger.info("저장된 쿠키로 접속 시도...")
                page.goto("https://www.instagram.com/")
                time.sleep(3)

                try:
                    page.wait_for_selector('svg[aria-label="홈"]', timeout=5000)
                    logger.info("쿠키로 로그인 유지 확인됨!")
                    
                    cookies = context.cookies()
                    cookies_dict = {c['name']: c['value'] for c in cookies}
                    if 'ds_user_id' in cookies_dict:
                        # 브라우저는 with 블록 종료 시 자동으로 정리됨
                        return cookies_dict
                    else:
                        logger.warning("로그인 된 것 같으나 ds_user_id가 없음. 재로그인 시도.")
                except Exception as e:
                    logger.info(f"쿠키가 만료되었거나 로그인이 풀림. 다시 로그인합니다. ({e})")
            
            # 3. 직접 로그인 진행
            logger.info("인스타그램 로그인 페이지 접속...")
            try:
                page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
            except Exception as e:
                logger.error(f"페이지 접속 실패: {e}")
                return {}
            
            try:
                page.wait_for_selector('input[name="username"]', timeout=20000)
            except Exception as e:
                logger.error(f"로그인 페이지 로딩 시간 초과: {e}")
                page.screenshot(path="login_page_error.png")
                logger.info("'login_page_error.png' 스크린샷을 저장했습니다.")
                return {}

            logger.info("아이디 및 비밀번호 입력...")
            try:
                page.fill('input[name="username"]', username)
                page.fill('input[name="password"]', password)
            except Exception as e:
                logger.error(f"입력창을 찾을 수 없습니다: {e}")
                page.screenshot(path="input_error.png")
                return {}

            time.sleep(random.uniform(1, 2))
            page.keyboard.press("Enter")
            logger.info("로그인 시도 중...")

            # 4. 로그인 완료 대기
            try:
                page.wait_for_url("https://www.instagram.com/", timeout=20000)
                logger.info("메인 URL 진입 성공")
            except Exception as e:
                logger.warning(f"URL 변경 감지 실패: {e}")

            # 5. 팝업 처리
            for _ in range(3):
                try:
                    not_now_btn = page.wait_for_selector(
                        'div[role="button"]:has-text("나중에 하기"), button:has-text("나중에 하기")', 
                        timeout=3000
                    )
                    if not_now_btn:
                        logger.info("팝업 발견 ('나중에 하기'), 클릭합니다.")
                        not_now_btn.click()
                        time.sleep(2)
                    else:
                        break
                except Exception:
                    break

            # 6. 쿠키 추출 및 저장
            logger.info("로그인 프로세스 완료, 쿠키 확인 중...")
            
            cookies_dict = {}
            found_cookie = False    
            for i in range(20):
                cookies = context.cookies()
                if any(c['name'] == 'ds_user_id' for c in cookies):
                    found_cookie = True
                    for cookie in cookies:
                        cookies_dict[cookie['name']] = cookie['value']
                    break
                if i % 5 == 0:
                    logger.info(f"쿠키 생성 대기 중... ({i+1}/20)")
                time.sleep(1) 
            
            if found_cookie:
                logger.info(f"핵심 쿠키(ds_user_id) 획득 성공! (ID: {cookies_dict.get('ds_user_id')})")
                save_cookies(context)
                return cookies_dict
            else:
                logger.error("로그인 실패 또는 쿠키 획득 시간 초과.")
                page.screenshot(path="login_failed.png")
                logger.info("'login_failed.png' 스크린샷을 저장했습니다.")
                return {}
            
            # 브라우저는 with 블록 종료 시 자동으로 정리됨
                
    except Exception as e:
        logger.error(f"Playwright 실행 중 오류: {e}")
        return {}

