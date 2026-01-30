"""
인스타그램 팔로워 추적기 - 비동기 메인 진입점
"""
import asyncio
import logging
import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('instagram_tracker.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 모듈 import
from config import get_env_var
from auth_async import login_async
from api_async import get_followers_and_following_async
from database import check_last_run, save_and_get_results_to_db
from notification import send_discord_webhook


async def main():
    """비동기 메인 실행 함수"""
    logger.info("=" * 50)
    logger.info("인스타그램 팔로워 추적기 시작 (비동기 모드)")
    logger.info("=" * 50)

    # 1. 계정 정보 로드
    env_vars = get_env_var()
    if not env_vars:
        logger.error("프로그램을 종료합니다.")
        return 1

    # 2. 오늘 이미 실행했는지 확인
    if check_last_run(env_vars["USERNAME"], env_vars["MONGO_URI"]):
        logger.info(f"오늘({datetime.datetime.now().strftime('%Y-%m-%d')}) 이미 실행된 기록이 있습니다.")
        logger.info("스크립트를 종료합니다.")
        return 0

    # 3. Playwright 비동기 로그인
    cookies_dict = await login_async(env_vars["USERNAME"], env_vars["PASSWORD"])

    if not cookies_dict:
        logger.error("로그인 실패. 프로그램을 종료합니다.")
        return 1

    logger.info("로그인 성공! 비동기 API 호출 시작...")

    # 4. 비동기로 팔로워/팔로잉 수집
    results = await get_followers_and_following_async(cookies_dict)
    logger.info(f"[결과] 팔로워 수: {len(results['followers'])}")
    logger.info(f"[결과] 팔로잉 수: {len(results['following'])}")

    # 5. 결과를 DB에 저장
    save_and_get_results_to_db(results, env_vars["USERNAME"], env_vars["MONGO_URI"])
    logger.info("모든 작업 완료!")

    # 6. 결과 디스코드로 보내기
    if env_vars.get("DISCORD_WEBHOOK") and env_vars["DISCORD_WEBHOOK"].lower() != "none":
        send_discord_webhook(results, env_vars["DISCORD_WEBHOOK"])
    else:
        logger.info("DISCORD_WEBHOOK이 설정되지 않아 전송을 건너뜁니다.")

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
