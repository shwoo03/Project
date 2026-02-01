from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from core.docker_client import docker_manager

router = APIRouter(prefix="/api", tags=["logs"])


@router.get("/containers/{container_id}/logs")
async def get_container_logs(container_id: str, tail: int = 100):
    """컨테이너 로그 조회 API"""
    logs = await docker_manager.get_container_logs(container_id, tail=tail)
    return {"container_id": container_id, "logs": logs}
