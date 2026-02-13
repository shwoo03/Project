from fastapi import APIRouter
from pydantic import BaseModel

from services import image_service
from core.schemas import success_response
from core.exceptions import ImageDeleteError

router = APIRouter(prefix="/api/images", tags=["images"])


@router.get("")
async def list_images():
    """Docker 이미지 목록 API"""
    images = await image_service.list_images()
    return success_response(data=images)


class PullImageRequest(BaseModel):
    image: str  # e.g. "nginx:latest" or "python:3.12-slim"


@router.post("/pull")
async def pull_image(req: PullImageRequest):
    """Docker 이미지 Pull API"""
    parts = req.image.split(":", 1)
    repository = parts[0]
    tag = parts[1] if len(parts) > 1 else "latest"
    result = await image_service.pull_image(repository, tag)
    return success_response(data=result)


@router.delete("/{image_id}")
async def delete_image(image_id: str, force: bool = False):
    """Docker 이미지 삭제 API"""
    success = await image_service.remove_image(image_id, force=force)
    if success:
        return success_response(data={"image_id": image_id, "deleted": True})

    raise ImageDeleteError(image_id=image_id)
