from fastapi import APIRouter

from core.docker_client import docker_manager
from core.schemas import success_response

router = APIRouter(prefix="/api", tags=["logs"])


@router.get("/containers/{container_id}/logs")
async def get_container_logs(container_id: str, tail: int = 100):
    """컨테이너 로그 조회 API"""
    logs = await docker_manager.get_container_logs(container_id, tail=tail)
    return success_response(data={"container_id": container_id, "logs": logs})
