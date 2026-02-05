
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.proxy_service import ProxyService, ProxyFilter

@pytest.fixture
def mock_mcp():
    mcp = AsyncMock()
    return mcp

@pytest.fixture
def proxy_service(mock_mcp):
    service = ProxyService()
    service.mcp = mock_mcp  # Inject mock
    return service

@pytest.mark.asyncio
async def test_get_history_no_filter(proxy_service, mock_mcp):
    # Setup
    mock_data = [
        {"id": "1", "method": "GET", "host": "example.com", "path": "/"},
        {"id": "2", "method": "POST", "host": "api.example.com", "path": "/login"}
    ]
    mock_mcp.get_proxy_history.return_value = mock_data

    # Execute
    result = await proxy_service.get_history(limit=10)

    # Verify
    assert result["total"] == 2
    assert len(result["entries"]) == 2
    mock_mcp.get_proxy_history.assert_called_once_with(limit=10, offset=0)

@pytest.mark.asyncio
async def test_get_history_with_filter(proxy_service, mock_mcp):
    # Setup
    mock_data = [
        {"id": "1", "method": "GET", "host": "example.com", "path": "/", "status_code": 200},
        {"id": "2", "method": "POST", "host": "api.example.com", "path": "/login", "status_code": 201}
    ]
    mock_mcp.get_proxy_history.return_value = mock_data
    
    # Filter for POST
    filters = ProxyFilter(method="POST")

    # Execute
    result = await proxy_service.get_history(limit=10, filters=filters)

    # Verify
    assert result["total"] == 1
    assert result["entries"][0]["method"] == "POST"

@pytest.mark.asyncio
async def test_get_stats(proxy_service, mock_mcp):
    # Setup
    mock_data = [
        {"method": "GET", "host": "a.com", "status_code": 200},
        {"method": "GET", "host": "a.com", "status_code": 404},
        {"method": "POST", "host": "b.com", "status_code": 200}
    ]
    mock_mcp.get_proxy_history.return_value = mock_data

    # Execute
    stats = await proxy_service.get_stats()

    # Verify
    assert stats.total_requests == 3
    assert stats.methods["GET"] == 2
    assert stats.methods["POST"] == 1
    assert stats.status_codes[200] == 2
    assert stats.status_codes[404] == 1
    assert stats.top_hosts["a.com"] == 2
