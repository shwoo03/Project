from fastapi import APIRouter

from core.docker_client import docker_manager
from core.schemas import success_response
from core.exceptions import ImageDeleteError

router = APIRouter(prefix="/api/images", tags=["images"])


@router.get("")
async def list_images():
    """Docker 이미지 목록 API"""
    images = await docker_manager.list_images()
    return success_response(data=images)


@router.delete("/{image_id}")
async def delete_image(image_id: str, force: bool = False):
    """Docker 이미지 삭제 API"""
    success = await docker_manager.delete_image(image_id, force=force)
    if success:
        return success_response(data={"image_id": image_id, "deleted": True})
    
    raise ImageDeleteError(image_id=image_id)
