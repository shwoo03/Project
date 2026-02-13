"""
API 엔드포인트 테스트
"""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_list_containers(client, mock_container_service):
    """GET /api/containers — 컨테이너 목록 조회"""
    resp = await client.get("/api/containers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert data["data"][0]["name"] == "test-nginx"


@pytest.mark.asyncio
async def test_container_action_start(client, mock_container_service):
    """POST /api/containers/{id}/action — start"""
    resp = await client.post(
        "/api/containers/abc123def456/action",
        json={"action": "start"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["action"] == "start"


@pytest.mark.asyncio
async def test_container_action_invalid(client, mock_container_service):
    """POST /api/containers/{id}/action — invalid action → 400"""
    resp = await client.post(
        "/api/containers/abc123def456/action",
        json={"action": "destroy"}
    )
    assert resp.status_code in [400, 422]


@pytest.mark.asyncio
async def test_container_logs(client, mock_container_service):
    """GET /api/containers/{id}/logs — 로그 조회"""
    resp = await client.get("/api/containers/abc123def456/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "logs" in data["data"]


@pytest.mark.asyncio
async def test_container_inspect(client, mock_container_service):
    """GET /api/containers/{id}/inspect — 상세 Inspect"""
    resp = await client.get("/api/containers/abc123def456/inspect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "test-nginx"
    assert "env" in data["data"]
    assert "mounts" in data["data"]
    assert "networks" in data["data"]


@pytest.mark.asyncio
async def test_docker_status(client, mock_connection):
    """GET /api/containers/status — Docker 상태"""
    resp = await client.get("/api/containers/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["connected"] is True


@pytest.mark.asyncio
async def test_list_images(client, mock_image_service):
    """GET /api/images — 이미지 목록"""
    resp = await client.get("/api/images")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["repository"] == "nginx"


@pytest.mark.asyncio
async def test_pull_image(client, mock_image_service):
    """POST /api/images/pull — 이미지 Pull"""
    resp = await client.post(
        "/api/images/pull",
        json={"image": "nginx:latest"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "tags" in data["data"]


@pytest.mark.asyncio
async def test_delete_image(client, mock_image_service):
    """DELETE /api/images/{id} — 이미지 삭제"""
    resp = await client.delete("/api/images/sha256:abc123?force=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["deleted"] is True
