from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core.docker_client import docker_manager

router = APIRouter(prefix="/api", tags=["images"])


@router.get("/images")
async def list_images():
    """Docker 이미지 목록 API"""
    images = await docker_manager.list_images()
    return images


@router.delete("/images/{image_id}")
async def delete_image(image_id: str, force: bool = False):
    """Docker 이미지 삭제 API"""
    success = await docker_manager.delete_image(image_id, force=force)
    if success:
        return {"status": "success", "message": f"Image {image_id} deleted"}
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": f"Failed to delete image {image_id}"}
    )
