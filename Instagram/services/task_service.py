"""
작업 실행 서비스
"""
import logging
from config import get_settings
from state_manager import state
from repositories.user_repository import UserRepository
from notification import send_discord_webhook, send_change_notification
from services.auth_service import AuthService
from services.instagram_service import InstagramService

logger = logging.getLogger(__name__)

class TaskService:
    @staticmethod
    async def run_tracker() -> None:
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
            
            await state.broadcast_progress(20, "인스타그램 로그인 중...")
            await state.broadcast_log("🔐 Playwright 로그인 시작...")
            
            # AuthService 사용
            cookies_dict = await AuthService.login(settings.user_id, settings.user_password)
            
            if not cookies_dict:
                await state.broadcast_log("❌ 로그인 실패")
                await state.broadcast_progress(0, "실패")
                return
            
            await state.broadcast_log("✅ 로그인 성공!")
            await state.broadcast_progress(40, "팔로워 데이터 수집 중...")
            
            # InstagramService 사용
            inst_service = InstagramService(cookies_dict)
            results = await inst_service.get_followers_and_following()
            
            await state.broadcast_log(f"📊 팔로워: {len(results['followers'])}명, 팔로잉: {len(results['following'])}명")
            await state.broadcast_progress(70, "데이터베이스 저장 중...")
            
            # DB 저장
            repo = UserRepository(settings.mongo_uri)
            diff_result = repo.save_results(settings.user_id, results)
            repo.save_history(settings.user_id, results)
            
            await state.broadcast_log("💾 DB 저장 완료! (히스토리 포함)")
            
            # 알림 로직
            new_followers = diff_result.get("new_followers", [])
            lost_followers = diff_result.get("lost_followers", [])
            
            if new_followers or lost_followers:
                await state.broadcast_log(f"🔔 변동 감지: +{len(new_followers)} / -{len(lost_followers)}")
            
            await state.broadcast_progress(85, "Discord 알림 전송 중...")
            
            if settings.discord_webhook and settings.discord_webhook.lower() not in ["none", ""]:
                send_discord_webhook(results, settings.discord_webhook)
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
