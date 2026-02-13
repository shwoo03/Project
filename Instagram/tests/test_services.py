"""
Instagram Tracker 테스트 스위트
UserRepository, ExportService, notification, views, scheduler 테스트
"""
import pytest
import sys
import os
import datetime
from io import BytesIO

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from services.instagram_service import InstagramService
from services.task_service import TaskService
from services.auth_service import AuthService
from services.export_service import ExportService
from schemas import APIResponse


# ================================================================
# InstagramService 테스트
# ================================================================

@pytest.mark.asyncio
async def test_instagram_service_initialization():
    """InstagramService 초기화 테스트"""
    cookies = {"ds_user_id": "12345", "csrftoken": "abcdef"}
    service = InstagramService(cookies)
    
    assert service.cookies_dict == cookies
    assert service._csrftoken == "abcdef"


@pytest.mark.asyncio
async def test_instagram_service_no_user_id():
    """ds_user_id가 없으면 빈 결과 반환"""
    cookies = {"csrftoken": "abcdef"}
    service = InstagramService(cookies)
    
    result = await service.get_followers_and_following()
    
    assert result == {"followers": [], "following": []}


@pytest.mark.asyncio
async def test_instagram_service_get_followers_and_following():
    """팔로워/팔로잉 수집 테스트 (Mock)"""
    cookies = {"ds_user_id": "12345"}
    service = InstagramService(cookies)
    
    service._fetch_all_users = AsyncMock(side_effect=[
        [{"id": "1", "username": "user1"}],
        [{"id": "2", "username": "user2"}]
    ])
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    service._create_client = MagicMock(return_value=mock_client)

    result = await service.get_followers_and_following()
    
    assert len(result["followers"]) == 1
    assert result["followers"][0]["username"] == "user1"
    assert len(result["following"]) == 1
    assert result["following"][0]["username"] == "user2"


# ================================================================
# TaskService 테스트
# ================================================================

@pytest.mark.asyncio
async def test_task_service_run_tracker_already_running():
    """이미 실행 중일 때 중복 실행 방지 테스트"""
    with patch("services.task_service.state") as mock_state:
        mock_state.is_running = True
        mock_state.broadcast_log = AsyncMock()
        
        await TaskService.run_tracker()
        
        mock_state.broadcast_log.assert_called_with("⚠️ 이미 실행 중입니다.")


# ================================================================
# ExportService 테스트
# ================================================================

class TestExportService:
    def test_create_csv_empty_data(self):
        """빈 데이터로 CSV 생성"""
        result = ExportService.create_csv([])
        assert isinstance(result, BytesIO)
        assert result.read() == b""

    def test_create_csv_string_list(self):
        """문자열 리스트(username)로 CSV 생성"""
        data = ["user1", "user2", "user3"]
        result = ExportService.create_csv(data)
        content = result.read().decode('utf-8-sig')
        
        assert "username" in content
        assert "user1" in content
        assert "user2" in content
        assert "user3" in content

    def test_create_csv_dict_list(self):
        """dict 리스트(followers)로 CSV 생성"""
        data = [
            {"id": "1", "username": "user1", "full_name": "User One"},
            {"id": "2", "username": "user2", "full_name": "User Two"},
        ]
        result = ExportService.create_csv(data)
        content = result.read().decode('utf-8-sig')
        
        assert "id" in content
        assert "username" in content
        assert "full_name" in content
        assert "user1" in content
        assert "User Two" in content

    def test_create_csv_unsupported_type(self):
        """지원하지 않는 데이터 타입으로 CSV 생성 시 빈 결과"""
        data = [123, 456]
        result = ExportService.create_csv(data)
        assert result.read() == b""


# ================================================================
# APIResponse 스키마 테스트
# ================================================================

class TestAPIResponse:
    def test_ok_response(self):
        """성공 응답 생성"""
        resp = APIResponse.ok("성공", data={"key": "value"})
        assert resp.success is True
        assert resp.message == "성공"
        assert resp.data == {"key": "value"}
        assert resp.error is None

    def test_fail_response(self):
        """실패 응답 생성"""
        resp = APIResponse.fail("실패", error="detail")
        assert resp.success is False
        assert resp.message == "실패"
        assert resp.error == "detail"

    def test_ok_default_message(self):
        """기본 성공 메시지"""
        resp = APIResponse.ok()
        assert resp.message == "성공"

    def test_fail_default_message(self):
        """기본 실패 메시지"""
        resp = APIResponse.fail()
        assert resp.message == "실패"


# ================================================================
# notification 테스트 (async)
# ================================================================

@pytest.mark.asyncio
async def test_send_discord_webhook_success():
    """Discord 웹훅 전송 (성공 Mock)"""
    from notification import send_discord_webhook
    
    data = {
        "followers": [{"username": "user1"}, {"username": "user2"}],
        "following": [{"username": "user2"}, {"username": "user3"}]
    }
    
    mock_response = MagicMock()
    mock_response.status_code = 204
    
    with patch("notification.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        MockClient.return_value = mock_client
        
        await send_discord_webhook(data, "https://discord.com/api/webhooks/test")
        
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["username"] == "Insta"
        assert len(payload["embeds"]) == 1


@pytest.mark.asyncio
async def test_send_change_notification_no_webhook():
    """Webhook URL이 없으면 아무것도 하지 않음"""
    from notification import send_change_notification
    
    # 함수가 에러 없이 조기 반환되면 성공
    await send_change_notification([], [], None)
    await send_change_notification([], [], "none")
    await send_change_notification([], [], "")


@pytest.mark.asyncio
async def test_send_change_notification_no_changes():
    """변동 없으면 전송하지 않음"""
    from notification import send_change_notification
    
    with patch("notification.httpx.AsyncClient") as MockClient:
        await send_change_notification([], [], "https://discord.com/api/webhooks/test")
        MockClient.assert_not_called()


# ================================================================
# UserRepository 테스트 (Mock MongoDB)
# ================================================================

class TestUserRepository:
    def _make_repo(self):
        """Mock MongoDB로 UserRepository 생성"""
        with patch("repositories.base.BaseRepository._get_client") as mock_client:
            mock_db = MagicMock()
            mock_client.return_value.get_database.return_value = mock_db
            
            from repositories.user_repository import UserRepository
            repo = UserRepository("mongodb://mock:27017/")
            repo.col_latest = MagicMock()
            repo.col_history = MagicMock()
            return repo

    def test_check_last_run_no_data(self):
        """데이터 없으면 False 반환"""
        repo = self._make_repo()
        repo.col_latest.find_one.return_value = None
        assert repo.check_last_run("testuser") is False

    def test_check_last_run_today(self):
        """오늘 실행했으면 True 반환"""
        repo = self._make_repo()
        repo.col_latest.find_one.return_value = {
            "last_updated": datetime.datetime.now()
        }
        assert repo.check_last_run("testuser") is True

    def test_check_last_run_yesterday(self):
        """어제 실행했으면 False 반환"""
        repo = self._make_repo()
        repo.col_latest.find_one.return_value = {
            "last_updated": datetime.datetime.now() - datetime.timedelta(days=1)
        }
        assert repo.check_last_run("testuser") is False

    def test_save_results_first_run(self):
        """첫 실행 시 변동 없음"""
        repo = self._make_repo()
        repo.col_latest.find_one.return_value = None
        
        results = {
            "followers": [{"id": "1", "username": "u1"}],
            "following": [{"id": "2", "username": "u2"}]
        }
        diff = repo.save_results("testuser", results)
        
        assert diff["new_followers"] == []
        assert diff["lost_followers"] == []
        repo.col_latest.replace_one.assert_called_once()

    def test_save_results_with_changes(self):
        """변동 감지 테스트"""
        repo = self._make_repo()
        repo.col_latest.find_one.return_value = {
            "followers": [
                {"id": "1", "username": "old_user"},
                {"id": "2", "username": "staying_user"}
            ]
        }
        
        results = {
            "followers": [
                {"id": "2", "username": "staying_user"},
                {"id": "3", "username": "new_user"}
            ],
            "following": []
        }
        diff = repo.save_results("testuser", results)
        
        assert len(diff["new_followers"]) == 1
        assert diff["new_followers"][0]["username"] == "new_user"
        assert len(diff["lost_followers"]) == 1
        assert diff["lost_followers"][0]["username"] == "old_user"

    def test_get_analysis_no_data(self):
        """데이터 없으면 빈 분석 반환"""
        repo = self._make_repo()
        repo.col_latest.find_one.return_value = None
        
        analysis = repo.get_analysis("testuser")
        assert analysis["followers"] == []
        assert analysis["following"] == []
        assert analysis["non_followers"] == []
        assert analysis["fans"] == []

    def test_get_analysis_with_data(self):
        """분석 데이터 계산 테스트"""
        repo = self._make_repo()
        repo.col_latest.find_one.return_value = {
            "followers": [
                {"username": "mutual"},
                {"username": "fan_only"}
            ],
            "following": [
                {"username": "mutual"},
                {"username": "not_following_back"}
            ],
            "last_updated": datetime.datetime.now()
        }
        
        analysis = repo.get_analysis("testuser")
        assert "not_following_back" in analysis["non_followers"]
        assert "fan_only" in analysis["fans"]
        assert "mutual" not in analysis["non_followers"]
        assert "mutual" not in analysis["fans"]


# ================================================================
# Scheduler 테스트
# ================================================================

def test_schedule_info_no_scheduler():
    """스케줄러가 없을 때 정보 조회"""
    with patch("scheduler._scheduler", None):
        from scheduler import get_schedule_info
        info = get_schedule_info()
        assert info["enabled"] is False
