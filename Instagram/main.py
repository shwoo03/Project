"""
인스타그램 팔로워 추적기 - 메인 진입점
"""
import logging
import datetime

# 로깅 설정 (다른 모듈 import 전에 설정)
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
from auth import set_playwright_and_login
from api import create_requests_session, requests_and_get_followers_and_following
from database import check_last_run, save_and_get_results_to_db
from notification import send_discord_webhook


def main():
    """메인 실행 함수"""
    logger.info("=" * 50)
    logger.info("인스타그램 팔로워 추적기 시작")
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
    
    # 3. Playwright 실행 및 로그인 후 쿠키 추출
    cookies_dict = set_playwright_and_login(env_vars["USERNAME"], env_vars["PASSWORD"])
    
    if not cookies_dict:
        logger.error("로그인 실패. 프로그램을 종료합니다.")
        return 1
    
    # 4. 추출한 쿠키로 requests 세션 생성
    session = create_requests_session(cookies_dict)
    logger.info("Requests 세션 생성 완료!")

    # 5. 세션으로 인스타그램 팔로워, 팔로잉 정보 가져오기
    results = requests_and_get_followers_and_following(session)
    logger.info(f"[결과] 팔로워 수: {len(results['followers'])}")
    logger.info(f"[결과] 팔로잉 수: {len(results['following'])}")

    # 6. 결과를 DB에 저장
    save_and_get_results_to_db(results, env_vars["USERNAME"], env_vars["MONGO_URI"])
    logger.info("모든 작업 완료!")

    # 7. 결과 디스코드로 보내기
    if env_vars.get("DISCORD_WEBHOOK"):
        send_discord_webhook(results, env_vars["DISCORD_WEBHOOK"])
    else:
        logger.info("DISCORD_WEBHOOK이 설정되지 않아 전송을 건너뜁니다.")
    
    return 0


if __name__ == "__main__":
    exit(main())
