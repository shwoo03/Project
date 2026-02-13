"""
pytest 설정 및 공통 fixture
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_docker_client():
    """Docker 클라이언트 모킹"""
    with patch("core.connection._client") as mock:
        mock.ping.return_value = True
        yield mock


@pytest.fixture
def mock_connection():
    """connection 모듈 모킹"""
    with patch("core.connection.ensure_connected", return_value=True), \
         patch("core.connection.get_status", return_value={
             "connected": True,
             "containers_running": 2,
             "containers_total": 5,
         }):
        yield


@pytest.fixture
def mock_container_service():
    """container_service 모킹"""
    mock_containers = [
        {
            "id": "abc123def456",
            "name": "test-nginx",
            "image": "nginx:latest",
            "status": "running",
            "state": "running",
            "ports": "0.0.0.0:80->80/tcp",
            "created": "2026-01-01T00:00:00",
        },
        {
            "id": "def456ghi789",
            "name": "test-redis",
            "image": "redis:alpine",
            "status": "exited",
            "state": "exited",
            "ports": "",
            "created": "2026-01-01T00:00:00",
        },
    ]
    mock_inspect = {
        "id": "abc123def456",
        "full_id": "abc123def456abc123def456",
        "name": "test-nginx",
        "image": "nginx:latest",
        "status": "running",
        "created": "2026-01-01T00:00:00",
        "started_at": "2026-01-01T00:01:00",
        "finished_at": "",
        "restart_count": 0,
        "platform": "linux",
        "env": ["PATH=/usr/local/sbin:/usr/local/bin"],
        "cmd": ["nginx", "-g", "daemon off;"],
        "entrypoint": None,
        "working_dir": "/",
        "labels": {},
        "mounts": [],
        "networks": {"bridge": {"ip_address": "172.17.0.2", "gateway": "172.17.0.1", "mac_address": "", "network_id": "abc123"}},
        "ports": {"80/tcp": ["0.0.0.0:80"]},
        "restart_policy": {"name": "no", "max_retry": 0},
        "resources": {"cpu_shares": 0, "cpu_quota": 0, "memory": 0, "memory_swap": 0},
    }
    with patch("services.container_service.list_containers", return_value=mock_containers), \
         patch("services.container_service.perform_action", return_value=True), \
         patch("services.container_service.get_logs", return_value="test log output"), \
         patch("services.container_service.inspect_container", return_value=mock_inspect):
        yield mock_containers


@pytest.fixture
def mock_image_service():
    """image_service 모킹"""
    mock_images = [
        {
            "id": "sha256:abc123",
            "image_id": "abc123",
            "repository": "nginx",
            "tag": "latest",
            "size": "142 MB",
            "created": "2026-01-01",
        },
    ]
    with patch("services.image_service.list_images", return_value=mock_images), \
         patch("services.image_service.remove_image", return_value=True), \
         patch("services.image_service.pull_image", return_value={
             "id": "sha256:abc123",
             "tags": ["nginx:latest"],
             "size": "142.00 MB",
         }):
        yield mock_images


@pytest.fixture
def mock_auth():
    """인증 미들웨어 우회"""
    with patch("middleware.auth_middleware.AuthMiddleware.__call__") as mock:
        async def passthrough(scope, receive, send):
            from main import app
            # ASGI 그대로 통과
            await app.router(scope, receive, send)
        mock.side_effect = passthrough
        yield


@pytest.fixture
async def client(mock_auth, mock_connection):
    """비동기 httpx 테스트 클라이언트 — 인증 우회"""
    # Import app after mocks are in place
    from main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
