from fastapi import APIRouter
from pydantic import BaseModel

from core.docker_client import docker_manager
from core.schemas import success_response
from core.exceptions import InvalidActionError, ContainerActionError

router = APIRouter(prefix="/api/containers", tags=["containers"])


class ActionRequest(BaseModel):
    action: str


@router.get("")
async def list_containers():
    """컨테이너 목록 API"""
    containers = await docker_manager.list_containers()
    return success_response(data=containers)


@router.post("/{container_id}/action")
async def container_action(container_id: str, req: ActionRequest):
    """컨테이너 제어 API (start, stop, restart)"""
    valid_actions = ["start", "stop", "restart"]
    if req.action not in valid_actions:
        raise InvalidActionError(action=req.action, valid_actions=valid_actions)
    
    success = await docker_manager.action_container(container_id, req.action)
    if success:
        return success_response(data={"container_id": container_id, "action": req.action})
    
    raise ContainerActionError(container_id=container_id, action=req.action)


@router.get("/{container_id}/logs")
async def get_container_logs(container_id: str, tail: int = 100):
    """컨테이너 로그 조회 API"""
    logs = await docker_manager.get_container_logs(container_id, tail=tail)
    return success_response(data={"container_id": container_id, "logs": logs})


@router.get("/status")
async def get_docker_status():
    """Docker 데몬 상태 API"""
    status = await docker_manager.get_status()
    return success_response(data=status)
