from services import (
    container_service,
    image_service,
    network_service,
    volume_service,
    exec_service
)
from typing import List, Dict, Any, Optional

class AsyncDockerClient:
    """
    레거시 호환성을 위한 래퍼 클래스.
    실제 로직은 now services 패키지로 분리되었습니다.
    """
    
    @property
    def is_connected(self) -> bool:
        # 간단히 container_service 연결 상태 확인 (대표)
        return container_service._connected

    async def connect(self):
        # 모든 서비스 연결
        await container_service.connect()
        await image_service.connect()
        await network_service.connect()
        await volume_service.connect()
        await exec_service.connect()
        
    async def disconnect(self):
        await container_service.disconnect()
        await image_service.disconnect()
        await network_service.disconnect()
        await volume_service.disconnect()
        await exec_service.disconnect()

    async def ensure_connected(self) -> bool:
        """연결 확인 및 재연결 시도"""
        if self.is_connected:
            return True
        await self.connect()
        return self.is_connected

    async def get_status(self) -> Dict[str, Any]:
        """Docker 데몬 상태 정보 반환"""
        # 상태 정보는 docker client 직접 접근이 필요하므로 container_service를 통해 접근
        if not await container_service.ensure_connected():
            return {"connected": False, "error": "Cannot connect to Docker daemon"}
        
        try:
            return await container_service.run_sync(self._get_status_sync)
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def _get_status_sync(self):
        client = container_service.client
        version = client.version()
        info = client.info()
        return {
            "connected": True,
            "version": version.get("Version", "unknown"),
            "api_version": version.get("ApiVersion", "unknown"),
            "containers_running": info.get("ContainersRunning", 0),
            "containers_total": info.get("Containers", 0),
            "images": info.get("Images", 0)
        }

    # --- Container Methods ---
    async def list_containers(self) -> List[Dict[str, Any]]:
        return await container_service.list_containers()

    async def get_containers(self) -> List[Dict[str, Any]]:
        """Alias for list_containers"""
        return await container_service.list_containers()

    async def get_container_stats(self, container_id: str = None):
        """
        container_id 제공 시: 특정 컨테이너 stats (dict)
        미제공 시: 모든 컨테이너 stats (list) - 기존 get_container_stats() 호환
        """
        # 기존 로직: 인자 없이 호출되면 리스트 반환
        if container_id:
            return await container_service.get_container_stats(container_id)
        return await container_service.get_stats()

    async def perform_action(self, container_id: str, action: str):
        return await container_service.perform_action(container_id, action)
    
    async def action_container(self, container_id: str, action: str):
        """Alias for perform_action"""
        return await container_service.perform_action(container_id, action)

    async def get_container_logs(self, container_id: str, tail: int = 100):
        return await container_service.get_logs(container_id, tail)

    async def update_container_resources(self, container_id: str, cpu_quota: int = None, memory_limit: str = None):
        return await container_service.update_container_resources(container_id, cpu_quota, memory_limit)

    # --- Image Methods ---
    async def list_images(self):
        return await image_service.list_images()

    async def delete_image(self, image_id: str, force: bool = False):
        return await image_service.remove_image(image_id, force)

    # --- Network Methods ---
    async def list_networks(self):
        return await network_service.list_networks()

    # --- Volume Methods ---
    async def list_volumes(self):
        return await volume_service.list_volumes()

    async def create_volume(self, name: str, driver: str = 'local'):
        return await volume_service.create_volume(name, driver)

    async def delete_volume(self, name: str):
        # 기존 코드에서 delete_volume이 remove_volume 호출
        return await volume_service.remove_volume(name)
        
    async def remove_volume(self, name: str, force: bool = False):
        return await volume_service.remove_volume(name, force)

    async def inspect_volume(self, name: str):
        return await volume_service.inspect_volume(name)

    # --- Exec Methods ---
    async def create_exec_instance(self, container_id: str):
        return await exec_service.create_exec_instance(container_id)

    async def get_exec_socket(self, exec_id: str):
        return await exec_service.get_exec_socket(exec_id)

# 전역 인스턴스 (기존 코드가 이 변수를 사용함)
docker_manager = AsyncDockerClient()
