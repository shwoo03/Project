from fastapi import APIRouter
from pydantic import BaseModel

from services.compose_service import compose_service
from core.schemas import success_response, error_response

router = APIRouter(prefix="/api/compose", tags=["compose"])


class ComposeActionRequest(BaseModel):
    action: str  # up, down, restart, pull, stop, start
    config_file: str  # docker-compose.yml 경로


@router.get("")
async def list_compose_projects():
    """Compose 프로젝트 목록 API"""
    projects = await compose_service.list_projects()
    return success_response(data=projects)


@router.get("/services")
async def get_project_services(config_file: str):
    """특정 프로젝트의 서비스 목록 API"""
    services = await compose_service.get_project_services(config_file)
    return success_response(data=services)


@router.post("/action")
async def compose_action(req: ComposeActionRequest):
    """Compose 프로젝트 액션 API"""
    result = await compose_service.project_action(req.config_file, req.action)
    if result["success"]:
        return success_response(data=result)
    return error_response(code="COMPOSE_ACTION_ERROR", message=result.get("error", "Unknown error"))
