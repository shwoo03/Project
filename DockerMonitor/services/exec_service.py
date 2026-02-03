from typing import Optional, Any
from .base_service import BaseService
import logging

logger = logging.getLogger(__name__)

class ExecService(BaseService):
    def _create_exec_instance_sync(self, container_id: str) -> Optional[str]:
        try:
            container = self.client.containers.get(container_id)
            exec_instance = container.client.api.exec_create(
                container.id, 
                cmd="/bin/sh",  # 기본 쉘
                stdin=True, 
                tty=True
            )
            return exec_instance['Id']
        except Exception as e:
            logger.error(f"Error creating exec instance for {container_id}: {e}")
            return None

    async def create_exec_instance(self, container_id: str) -> Optional[str]:
        if not await self.ensure_connected():
            return None
            
        try:
            return await self.run_sync(self._create_exec_instance_sync, container_id)
        except Exception:
            return None

    def _get_exec_socket_sync(self, exec_id: str) -> Any:
        try:
            # socket=True로 raw socket 반환 (docker-py 내부 구현 의존)
            sock = self.client.api.exec_start(exec_id, detach=False, tty=True, socket=True)
            return sock
        except Exception as e:
            logger.error(f"Error getting exec socket for {exec_id}: {e}")
            return None

    async def get_exec_socket(self, exec_id: str) -> Any:
        if not await self.ensure_connected():
            return None
            
        try:
            return await self.run_sync(self._get_exec_socket_sync, exec_id)
        except Exception:
            return None
