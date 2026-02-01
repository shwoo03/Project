from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.docker_client import docker_manager

router = APIRouter(prefix="/api", tags=["containers"])


class ActionRequest(BaseModel):
    action: str


@router.get("/status")
async def get_docker_status():
    """Docker 데몬 상태 API"""
    status = await docker_manager.get_status()
    return status


@router.get("/containers")
async def list_containers():
    """컨테이너 목록 API"""
    containers = await docker_manager.list_containers()
    return containers


@router.post("/containers/{container_id}/action")
async def container_action(container_id: str, req: ActionRequest):
    """컨테이너 제어 API (start, stop, restart)"""
    if req.action not in ["start", "stop", "restart"]:
        raise HTTPException(status_code=400, detail=f"Invalid action: {req.action}")
    
    success = await docker_manager.action_container(container_id, req.action)
    if success:
        return {"status": "success", "message": f"Container {req.action} successful"}
    return JSONResponse(
        status_code=500, 
        content={"status": "error", "message": f"Failed to {req.action} container"}
    )
