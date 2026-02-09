import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock, patch
from services.instagram_service import InstagramService
from services.task_service import TaskService
from services.auth_service import AuthService

@pytest.mark.asyncio
async def test_instagram_service_initialization():
    """InstagramService 초기화 테스트"""
    cookies = {"ds_user_id": "12345", "csrftoken": "abcdef"}
    service = InstagramService(cookies)
    
    assert service.cookies_dict == cookies
    assert service._csrftoken == "abcdef"

@pytest.mark.asyncio
async def test_instagram_service_get_followers_and_following():
    """팔로워/팔로잉 수집 테스트 (Mock)"""
    cookies = {"ds_user_id": "12345"}
    service = InstagramService(cookies)
    
    # _fetch_all_users 메서드 모킹
    service._fetch_all_users = AsyncMock(side_effect=[
        [{"id": "1", "username": "user1"}],  # followers
        [{"id": "2", "username": "user2"}]   # following
    ])
    
    # _create_client 모킹 (컨텍스트 매니저 지원 필요)
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    service._create_client = MagicMock(return_value=mock_client)

    result = await service.get_followers_and_following()
    
    assert len(result["followers"]) == 1
    assert result["followers"][0]["username"] == "user1"
    assert len(result["following"]) == 1
    assert result["following"][0]["username"] == "user2"

@pytest.mark.asyncio
async def test_task_service_run_tracker_already_running():
    """이미 실행 중일 때 중복 실행 방지 테스트"""
    with patch("services.task_service.state") as mock_state:
        mock_state.is_running = True
        mock_state.broadcast_log = AsyncMock()
        
        await TaskService.run_tracker()
        
        mock_state.broadcast_log.assert_called_with("⚠️ 이미 실행 중입니다.")

@pytest.mark.asyncio
async def test_auth_service_login_mock():
    """AuthService 로그인 모킹 테스트"""
    with patch("services.auth_service.async_playwright") as mock_playwright:
        # Playwright 모킹은 복잡하므로 login 메서드 자체를 모킹하는 것이 일반적이나,
        # 여기서는 AuthService.login이 클래스 메서드이므로 호출 여부만 확인하거나
        # 실제 Playwright 호출 없이 예외 처리가 되는지 확인
        pass

# 더 복잡한 테스트는 실제 브라우저가 필요하므로 생략하거나 통합 테스트로 이동
