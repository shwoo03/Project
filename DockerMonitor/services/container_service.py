from typing import List, Dict, Any, Optional
from .base_service import BaseService
import logging
from core.exceptions import ContainerNotFoundError, InvalidActionError

logger = logging.getLogger(__name__)

class ContainerService(BaseService):
    def _list_containers_sync(self) -> List[Dict[str, Any]]:
        """동기 컨테이너 목록 조회"""
        containers = []
        for container in self.client.containers.list(all=True):
            try:
                # 포트 정보 파싱
                ports = container.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
                formatted_ports = {}
                for k, v in ports.items():
                    if v:
                        formatted_ports[k] = f"{v[0]['HostIp']}:{v[0]['HostPort']}"
                    else:
                        formatted_ports[k] = None
                
                containers.append({
                    "id": container.short_id,
                    "name": container.name,
                    "image": container.image.tags[0] if container.image.tags else container.attrs['Config']['Image'],
                    "status": container.status,
                    "ports": formatted_ports,
                    "created": container.attrs.get("Created", "")
                })
            except Exception as e:
                logger.warning(f"Error parsing container {container.short_id}: {e}")
                continue
        return containers

    async def list_containers(self) -> List[Dict[str, Any]]:
        if not await self.ensure_connected():
            return []
        
        try:
            return await self.run_sync(self._list_containers_sync)
        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            return []

    def _get_container_action_sync(self, container_id: str, action: str) -> bool:
        try:
            container = self.client.containers.get(container_id)
            if action == "start":
                container.start()
            elif action == "stop":
                container.stop()
            elif action == "restart":
                container.restart()
            else:
                raise InvalidActionError(action)
            return True
        except Exception as e:
            if "No such container" in str(e):
                raise ContainerNotFoundError(container_id)
            raise e

    async def perform_action(self, container_id: str, action: str) -> bool:
        if not await self.ensure_connected():
            return False
            
        return await self.run_sync(self._get_container_action_sync, container_id, action)

    def _update_container_resources_sync(self, container_id: str, cpu_quota: int, memory_limit: str) -> bool:
        try:
            container = self.client.containers.get(container_id)
            # kwargs 딕셔너리 구성 (None이 아닌 값만 포함)
            update_kwargs = {}
            if cpu_quota is not None:
                update_kwargs['cpu_quota'] = cpu_quota
            if memory_limit is not None:
                update_kwargs['mem_limit'] = memory_limit
                
            if update_kwargs:
                container.update(**update_kwargs)
            return True
        except Exception as e:
            if "No such container" in str(e):
                raise ContainerNotFoundError(container_id)
            logger.error(f"Error updating container {container_id}: {e}")
            raise e

    async def update_container_resources(self, container_id: str, cpu_quota: int = None, memory_limit: str = None) -> bool:
        """컨테이너 리소스 제한 업데이트"""
        if not await self.ensure_connected():
            return False
            
        return await self.run_sync(self._update_container_resources_sync, container_id, cpu_quota, memory_limit)

    def _get_logs_sync(self, container_id: str, tail: int) -> str:
        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail).decode('utf-8')
        except Exception as e:
            if "No such container" in str(e):
                raise ContainerNotFoundError(container_id)
            raise e

    async def get_logs(self, container_id: str, tail: int = 100) -> str:
        if not await self.ensure_connected():
            return ""
        
        return await self.run_sync(self._get_logs_sync, container_id, tail)

    def _get_single_container_stats_sync(self, container_id: str) -> Dict[str, Any]:
        """단일 컨테이너 통계 수집"""
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            return self._parse_stats(container, stats)
        except Exception as e:
            logger.warning(f"Error getting stats for {container_id}: {e}")
            return {}

    def _parse_stats(self, container, stats) -> Dict[str, Any]:
        """stats 딕셔너리 파싱 헬퍼"""
        # CPU 계산
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                   stats['precpu_stats']['cpu_usage']['total_usage']
        system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - \
                         stats['precpu_stats']['system_cpu_usage']
        number_cpus = stats['cpu_stats'].get('online_cpus', 1)
        
        cpu_percent = 0.0
        if system_cpu_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100.0

        # 메모리 계산
        memory_usage = stats['memory_stats'].get('usage', 0)
        memory_limit = stats['memory_stats'].get('limit', 0)
        memory_percent = 0.0
        if memory_limit > 0:
            memory_percent = (memory_usage / memory_limit) * 100.0

        return {
            "id": container.short_id,
            "cpu_percent": round(cpu_percent, 2),
            "memory_usage": memory_usage,
            "memory_limit": memory_limit,
            "memory_percent": round(memory_percent, 2)
        }

    def _get_stats_sync(self) -> List[Dict[str, Any]]:
        """모든 실행 중인 컨테이너의 통계 수집"""
        stats_list = []
        for container in self.client.containers.list():
            try:
                stats = container.stats(stream=False)
                stats_list.append(self._parse_stats(container, stats))
            except Exception:
                continue
        return stats_list

    async def get_stats(self) -> List[Dict[str, Any]]:
        if not await self.ensure_connected():
            return []
        
        try:
            return await self.run_sync(self._get_stats_sync)
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return []

    async def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        if not await self.ensure_connected():
            return {}
            
        try:
            return await self.run_sync(self._get_single_container_stats_sync, container_id)
        except Exception as e:
            logger.error(f"Error getting stats for {container_id}: {e}")
            return {}

    def _inspect_container_sync(self, container_id: str) -> Dict[str, Any]:
        """컨테이너 상세 정보 조회"""
        try:
            container = self.client.containers.get(container_id)
            attrs = container.attrs
            config = attrs.get("Config", {})
            host_config = attrs.get("HostConfig", {})
            network_settings = attrs.get("NetworkSettings", {})
            state = attrs.get("State", {})

            # Mounts 파싱
            mounts = []
            for m in attrs.get("Mounts", []):
                mounts.append({
                    "type": m.get("Type", ""),
                    "source": m.get("Source", ""),
                    "destination": m.get("Destination", ""),
                    "mode": m.get("Mode", ""),
                    "rw": m.get("RW", False),
                })

            # Networks 파싱
            networks = {}
            for name, net in network_settings.get("Networks", {}).items():
                networks[name] = {
                    "ip_address": net.get("IPAddress", ""),
                    "gateway": net.get("Gateway", ""),
                    "mac_address": net.get("MacAddress", ""),
                    "network_id": net.get("NetworkID", "")[:12],
                }

            # Ports 파싱
            ports = {}
            for k, v in (network_settings.get("Ports") or {}).items():
                if v:
                    ports[k] = [f"{b['HostIp']}:{b['HostPort']}" for b in v]
                else:
                    ports[k] = []

            return {
                "id": container.id[:12],
                "full_id": container.id,
                "name": container.name,
                "image": config.get("Image", ""),
                "status": container.status,
                "created": attrs.get("Created", ""),
                "started_at": state.get("StartedAt", ""),
                "finished_at": state.get("FinishedAt", ""),
                "restart_count": attrs.get("RestartCount", 0),
                "platform": attrs.get("Platform", ""),
                "env": config.get("Env", []),
                "cmd": config.get("Cmd", []),
                "entrypoint": config.get("Entrypoint", []),
                "working_dir": config.get("WorkingDir", ""),
                "labels": config.get("Labels", {}),
                "mounts": mounts,
                "networks": networks,
                "ports": ports,
                "restart_policy": {
                    "name": host_config.get("RestartPolicy", {}).get("Name", ""),
                    "max_retry": host_config.get("RestartPolicy", {}).get("MaximumRetryCount", 0),
                },
                "resources": {
                    "cpu_shares": host_config.get("CpuShares", 0),
                    "cpu_quota": host_config.get("CpuQuota", 0),
                    "memory": host_config.get("Memory", 0),
                    "memory_swap": host_config.get("MemorySwap", 0),
                },
            }
        except Exception as e:
            if "No such container" in str(e) or "404" in str(e):
                raise ContainerNotFoundError(container_id)
            raise e

    async def inspect_container(self, container_id: str) -> Dict[str, Any]:
        """컨테이너 상세 Inspect"""
        if not await self.ensure_connected():
            return {}
        return await self.run_sync(self._inspect_container_sync, container_id)
