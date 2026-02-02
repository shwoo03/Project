import logging
from config import get_settings
from auth_async import login_async
from api_async import get_followers_and_following_async
from repositories.user_repository import UserRepository
from notification import send_discord_webhook, send_change_notification
from state_manager import state

logger = logging.getLogger(__name__)

async def run_tracker_task():
    """백그라운드에서 팔로워 추적 실행"""
    if state.is_running:
        await state.broadcast_log("⚠️ 이미 실행 중입니다.")
        return
    
    state.is_running = True
    
    try:
        await state.broadcast_progress(5, "환경 변수 로드 중...")
        settings = get_settings()
        if not settings.user_id or not settings.user_password:
            await state.broadcast_log("❌ 환경 변수 로드 실패")
            return
        
        await state.broadcast_progress(10, "오늘 실행 여부 확인 중...")
        # 중복 실행 체크는 웹에서 실행 시 생략 가능하거나 로직 추가 가능
        
        await state.broadcast_progress(20, "인스타그램 로그인 중...")
        await state.broadcast_log("🔐 Playwright 로그인 시작...")
        cookies_dict = await login_async(settings.user_id, settings.user_password)
        
        if not cookies_dict:
            await state.broadcast_log("❌ 로그인 실패")
            await state.broadcast_progress(0, "실패")
            return
        
        await state.broadcast_log("✅ 로그인 성공!")
        await state.broadcast_progress(40, "팔로워 데이터 수집 중...")
        
        results = await get_followers_and_following_async(cookies_dict)
        
        await state.broadcast_log(f"📊 팔로워: {len(results['followers'])}명, 팔로잉: {len(results['following'])}명")
        await state.broadcast_progress(70, "데이터베이스 저장 중...")
        
        repo = UserRepository(settings.mongo_uri)
        diff_result = repo.save_results(settings.user_id, results)
        repo.save_history(settings.user_id, results)
        
        await state.broadcast_log("💾 DB 저장 완료! (히스토리 포함)")
        
        # 변동 사항 알림
        new_followers = diff_result.get("new_followers", [])
        lost_followers = diff_result.get("lost_followers", [])
        
        if new_followers or lost_followers:
            await state.broadcast_log(f"🔔 변동 감지: +{len(new_followers)} / -{len(lost_followers)}")
        
        await state.broadcast_progress(85, "Discord 알림 전송 중...")
        
        if settings.discord_webhook and settings.discord_webhook.lower() not in ["none", ""]:
            # 전체 리포트
            send_discord_webhook(results, settings.discord_webhook)
            # 변동 알림 (변동이 있을 때만)
            if new_followers or lost_followers:
                send_change_notification(new_followers, lost_followers, settings.discord_webhook)
            await state.broadcast_log("📨 Discord 전송 완료!")
        else:
            await state.broadcast_log("ℹ️ Discord Webhook 미설정")
        
        await state.broadcast_progress(100, "완료!")
        await state.broadcast_log("🎉 모든 작업이 완료되었습니다!")
        
    except Exception as e:
        await state.broadcast_log(f"❌ 오류 발생: {str(e)}")
        await state.broadcast_progress(0, "오류")
        logger.error(f"Tracker 실행 오류: {e}")
    finally:
        state.is_running = False
