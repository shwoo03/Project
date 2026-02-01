import docker
import asyncio
import logging
from typing import List, Dict, Any, Optional
from functools import partial
from concurrent.futures import ThreadPoolExecutor

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ThreadPoolExecutor for running sync docker calls
executor = ThreadPoolExecutor(max_workers=4)


class AsyncDockerClient:
    """Windows 호환 비동기 Docker 클라이언트 (동기 docker 라이브러리 + executor)"""
    
    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._connected: bool = False
    
    async def connect(self) -> bool:
        """Docker 데몬에 연결"""
        try:
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(executor, docker.from_env)
            # 연결 테스트
            await loop.run_in_executor(executor, self._client.ping)
            self._connected = True
            logger.info("Docker Client Connected Successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Docker Daemon: {e}")
            self._connected = False
            self._client = None
            return False
    
    async def disconnect(self):
        """Docker 연결 종료"""
        if self._client:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(executor, self._client.close)
            self._client = None
            self._connected = False
    
    async def ensure_connected(self) -> bool:
        """연결 확인 및 재연결 시도"""
        if self._client and self._connected:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(executor, self._client.ping)
                return True
            except Exception:
                self._connected = False
        
        return await self.connect()
    
    @property
    def is_connected(self) -> bool:
        """연결 상태 반환"""
        return self._connected
    
    async def get_status(self) -> Dict[str, Any]:
        """Docker 데몬 상태 정보 반환"""
        if not await self.ensure_connected():
            return {"connected": False, "error": "Cannot connect to Docker daemon"}
        
        try:
            loop = asyncio.get_event_loop()
            version = await loop.run_in_executor(executor, self._client.version)
            info = await loop.run_in_executor(executor, self._client.info)
            return {
                "connected": True,
                "version": version.get("Version", "unknown"),
                "api_version": version.get("ApiVersion", "unknown"),
                "containers_running": info.get("ContainersRunning", 0),
                "containers_total": info.get("Containers", 0),
                "images": info.get("Images", 0)
            }
        except Exception as e:
            logger.error(f"Error getting Docker status: {e}")
            return {"connected": False, "error": str(e)}

    def _list_containers_sync(self) -> List[Dict[str, Any]]:
        """동기 컨테이너 목록 조회"""
        containers = []
        for container in self._client.containers.list(all=True):
            image_tags = container.image.tags
            image_name = image_tags[0] if image_tags else "none"
            
            containers.append({
                "id": container.short_id,
                "name": container.name,
                "status": container.status,
                "image": image_name,
                "ports": container.ports,
                "created": container.attrs.get('Created', '')
            })
        return containers

    async def list_containers(self) -> List[Dict[str, Any]]:
        """모든 컨테이너(실행 중/중지됨) 목록 반환"""
        if not await self.ensure_connected():
            return []
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(executor, self._list_containers_sync)
        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            return []

    def _get_container_stats_sync(self, container_id: str) -> Dict[str, Any]:
        """동기 컨테이너 stats 조회"""
        container = self._client.containers.get(container_id)
        stats = container.stats(stream=False)
        
        # CPU 계산 로직
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                    stats['precpu_stats']['cpu_usage']['total_usage']
        system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - \
                           stats['precpu_stats']['system_cpu_usage']
        number_cpus = stats['cpu_stats'].get('online_cpus', 1)
        
        cpu_usage = 0.0
        if system_cpu_delta > 0 and cpu_delta > 0:
            cpu_usage = (cpu_delta / system_cpu_delta) * number_cpus * 100.0

        # Memory 계산 로직
        memory_usage = stats['memory_stats'].get('usage', 0)
        memory_limit = stats['memory_stats'].get('limit', 1)
        memory_percent = (memory_usage / memory_limit) * 100.0 if memory_limit > 0 else 0.0

        return {
            "id": container_id,
            "cpu_percent": round(cpu_usage, 2),
            "memory_usage": memory_usage,
            "memory_limit": memory_limit,
            "memory_percent": round(memory_percent, 2)
        }

    async def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """특정 컨테이너의 실시간 상태(CPU, Memory) 반환"""
        if not await self.ensure_connected():
            return {}
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                executor, 
                partial(self._get_container_stats_sync, container_id)
            )
        except Exception as e:
            # logger.error(f"Error getting stats for {container_id}: {e}")
            return {}

    def _action_container_sync(self, container_id: str, action: str) -> bool:
        """동기 컨테이너 제어"""
        container = self._client.containers.get(container_id)
        if action == "start":
            container.start()
        elif action == "stop":
            container.stop()
        elif action == "restart":
            container.restart()
        return True

    async def action_container(self, container_id: str, action: str) -> bool:
        """컨테이너 제어 (start, stop, restart)"""
        if not await self.ensure_connected():
            return False
            
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                executor,
                partial(self._action_container_sync, container_id, action)
            )
        except Exception as e:
            logger.error(f"Error action {action} on {container_id}: {e}")
            return False

    def _list_networks_sync(self) -> List[Dict[str, Any]]:
        """동기 네트워크 목록 조회"""
        networks = []
        for network in self._client.networks.list():
            info = network.attrs
            
            # 연결된 컨테이너 정보 파싱
            containers = []
            container_info = info.get("Containers", {}) or {}
            for cid, cdata in container_info.items():
                containers.append({
                    "id": cid[:12],
                    "name": cdata.get("Name", "unknown"),
                    "ipv4": cdata.get("IPv4Address", ""),
                    "ipv6": cdata.get("IPv6Address", ""),
                    "mac": cdata.get("MacAddress", "")
                })
            
            # IPAM 설정
            ipam = info.get("IPAM", {})
            ipam_config = ipam.get("Config", [])
            subnet = ""
            gateway = ""
            if ipam_config:
                subnet = ipam_config[0].get("Subnet", "")
                gateway = ipam_config[0].get("Gateway", "")
            
            networks.append({
                "id": info.get("Id", "")[:12],
                "name": info.get("Name", "unknown"),
                "driver": info.get("Driver", "unknown"),
                "scope": info.get("Scope", "local"),
                "internal": info.get("Internal", False),
                "subnet": subnet,
                "gateway": gateway,
                "containers": containers,
                "container_count": len(containers),
                "created": info.get("Created", "")
            })
        return networks

    async def list_networks(self) -> List[Dict[str, Any]]:
        """Docker 네트워크 목록 반환"""
        if not await self.ensure_connected():
            return []
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(executor, self._list_networks_sync)
        except Exception as e:
            logger.error(f"Error listing networks: {e}")
            return []

    def _list_images_sync(self) -> List[Dict[str, Any]]:
        """동기 이미지 목록 조회"""
        images = []
        for image in self._client.images.list():
            tags = image.tags or ["<none>"]
            size_bytes = image.attrs.get("Size", 0)
            size_mb = round(size_bytes / (1024 * 1024), 2)
            
            images.append({
                "id": image.short_id.replace("sha256:", ""),
                "tags": tags,
                "size": size_bytes,
                "size_human": f"{size_mb} MB" if size_mb < 1024 else f"{round(size_mb/1024, 2)} GB",
                "created": image.attrs.get("Created", ""),
                "containers": 0
            })
        return images

    async def list_images(self) -> List[Dict[str, Any]]:
        """Docker 이미지 목록 반환"""
        if not await self.ensure_connected():
            return []
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(executor, self._list_images_sync)
        except Exception as e:
            logger.error(f"Error listing images: {e}")
            return []

    def _delete_image_sync(self, image_id: str, force: bool) -> bool:
        """동기 이미지 삭제"""
        self._client.images.remove(image_id, force=force)
        return True

    async def delete_image(self, image_id: str, force: bool = False) -> bool:
        """Docker 이미지 삭제"""
        if not await self.ensure_connected():
            return False
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                executor,
                partial(self._delete_image_sync, image_id, force)
            )
        except Exception as e:
            logger.error(f"Error deleting image {image_id}: {e}")
            return False

    def _get_container_logs_sync(self, container_id: str, tail: int) -> str:
        """동기 로그 조회"""
        container = self._client.containers.get(container_id)
        logs = container.logs(stdout=True, stderr=True, tail=tail)
        return logs.decode('utf-8', errors='replace')

    async def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """컨테이너 로그 조회"""
        if not await self.ensure_connected():
            return ""
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                executor,
                partial(self._get_container_logs_sync, container_id, tail)
            )
        except Exception as e:
            logger.error(f"Error getting logs for {container_id}: {e}")
            return f"Error: {str(e)}"


# 싱글톤 인스턴스
docker_manager = AsyncDockerClient()
