from fastapi import APIRouter
from pydantic import BaseModel

from core.docker_client import docker_manager
from core.schemas import success_response
from core.exceptions import VolumeNotFoundError, VolumeOperationError

router = APIRouter(prefix="/api/volumes", tags=["volumes"])


class VolumeCreateRequest(BaseModel):
    name: str
    driver: str = "local"


@router.get("")
async def list_volumes():
    """볼륨 목록 조회"""
    volumes = await docker_manager.list_volumes()
    return success_response(data=volumes)


@router.post("")
async def create_volume(request: VolumeCreateRequest):
    """볼륨 생성"""
    try:
        result = await docker_manager.create_volume(request.name, request.driver)
        return success_response(data=result)
    except Exception as e:
        raise VolumeOperationError(operation="create", volume_name=request.name, reason=str(e))


@router.get("/{name}")
async def inspect_volume(name: str):
    """볼륨 상세 정보 조회"""
    result = await docker_manager.inspect_volume(name)
    if not result:
        raise VolumeNotFoundError(volume_name=name)
    return success_response(data=result)


@router.delete("/{name}")
async def delete_volume(name: str, force: bool = False):
    """볼륨 삭제"""
    try:
        success = await docker_manager.remove_volume(name, force)
        if success:
            return success_response(data={"name": name, "deleted": True})
        raise VolumeOperationError(operation="delete", volume_name=name)
    except VolumeOperationError:
        raise
    except Exception as e:
        raise VolumeOperationError(operation="delete", volume_name=name, reason=str(e))
