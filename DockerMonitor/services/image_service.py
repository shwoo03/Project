from typing import List, Dict, Any
from .base_service import BaseService
import logging
from core.exceptions import ImageNotFoundError

logger = logging.getLogger(__name__)

class ImageService(BaseService):
    def _list_images_sync(self) -> List[Dict[str, Any]]:
        """동기 이미지 목록 조회"""
        images = []
        for img in self.client.images.list():
            try:
                tags = img.tags
                repo_tags = tags[0] if tags else "<none>:<none>"
                if ":" in repo_tags:
                    repo, tag = repo_tags.split(":", 1)
                else:
                    repo, tag = repo_tags, "<none>"
                
                size_mb = f"{img.attrs.get('Size', 0) / (1024 * 1024):.2f} MB"
                
                images.append({
                    "id": img.short_id.split(":")[1] if ":" in img.short_id else img.short_id,
                    "repository": repo,
                    "tag": tag,
                    "image_id": img.id.split(":")[1][:12] if ":" in img.id else img.id[:12],
                    "created": img.attrs.get("Created", "").split("T")[0],
                    "size": size_mb
                })
            except Exception as e:
                logger.warning(f"Error parsing image {img.short_id}: {e}")
                continue
        return images

    async def list_images(self) -> List[Dict[str, Any]]:
        if not await self.ensure_connected():
            return []
        
        try:
            return await self.run_sync(self._list_images_sync)
        except Exception as e:
            logger.error(f"Error listing images: {e}")
            return []

    def _remove_image_sync(self, image_id: str, force: bool) -> bool:
        try:
            self.client.images.remove(image_id, force=force)
            return True
        except Exception as e:
            if "No such image" in str(e):
                raise ImageNotFoundError(image_id)
            raise e

    async def remove_image(self, image_id: str, force: bool = False) -> bool:
        if not await self.ensure_connected():
            return False
        
        try:
            return await self.run_sync(self._remove_image_sync, image_id, force)
        except ImageNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error removing image {image_id}: {e}")
            raise e
