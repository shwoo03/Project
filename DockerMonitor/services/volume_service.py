from typing import List, Dict, Any
from .base_service import BaseService
import logging

logger = logging.getLogger(__name__)

class VolumeService(BaseService):
    def _list_volumes_sync(self) -> List[Dict[str, Any]]:
        """동기 볼륨 목록 조회"""
        volumes = []
        volume_list = self.client.volumes.list()
        for vol in volume_list:
            attrs = vol.attrs
            volumes.append({
                "id": vol.id,
                "name": vol.name,
                "driver": attrs.get("Driver", "local"),
                "mountpoint": attrs.get("Mountpoint", ""),
                "created": attrs.get("CreatedAt", ""),
                "labels": attrs.get("Labels", {})
            })
        return volumes

    async def list_volumes(self) -> List[Dict[str, Any]]:
        if not await self.ensure_connected():
            return []
        
        return await self.run_sync(self._list_volumes_sync)

    def _create_volume_sync(self, name: str, driver: str) -> Dict[str, Any]:
        vol = self.client.volumes.create(name=name, driver=driver)
        return {
            "id": vol.id, 
            "name": vol.name
        }

    async def create_volume(self, name: str, driver: str = 'local') -> Dict[str, Any]:
        if not await self.ensure_connected():
            return {}
        
        try:
            return await self.run_sync(self._create_volume_sync, name, driver)
        except Exception as e:
            logger.error(f"Error creating volume {name}: {e}")
            raise e

    def _remove_volume_sync(self, name: str, force: bool) -> bool:
        vol = self.client.volumes.get(name)
        vol.remove(force=force)
        return True

    async def remove_volume(self, name: str, force: bool = False) -> bool:
        if not await self.ensure_connected():
            return False
        
        try:
            return await self.run_sync(self._remove_volume_sync, name, force)
        except Exception as e:
            logger.error(f"Error removing volume {name}: {e}")
            raise e

    def _inspect_volume_sync(self, name: str) -> Dict[str, Any]:
        vol = self.client.volumes.get(name)
        return vol.attrs

    async def inspect_volume(self, name: str) -> Dict[str, Any]:
        if not await self.ensure_connected():
            return {}
        
        try:
            return await self.run_sync(self._inspect_volume_sync, name)
        except Exception as e:
            logger.error(f"Error inspecting volume {name}: {e}")
            return {}
