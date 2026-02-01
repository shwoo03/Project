from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from core.docker_client import docker_manager

router = APIRouter(prefix="/api/volumes", tags=["volumes"])

class VolumeCreateRequest(BaseModel):
    name: str
    driver: str = "local"

@router.get("")
async def list_volumes():
    """볼륨 목록 조회"""
    return await docker_manager.list_volumes()

@router.post("")
async def create_volume(request: VolumeCreateRequest):
    """볼륨 생성"""
    try:
        result = await docker_manager.create_volume(request.name, request.driver)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/{name}")
async def inspect_volume(name: str):
    """볼륨 상세 정보 조회"""
    result = await docker_manager.inspect_volume(name)
    if not result:
        raise HTTPException(status_code=404, detail="Volume not found")
    return result

@router.delete("/{name}")
async def delete_volume(name: str, force: bool = False):
    """볼륨 삭제"""
    try:
        success = await docker_manager.remove_volume(name, force)
        if success:
            return {"status": "success"}
        else:
            return {"status": "error", "message": "Failed to remove volume"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
