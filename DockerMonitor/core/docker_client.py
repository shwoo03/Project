import docker
import asyncio
import logging
from typing import List, Dict, Any, AsyncGenerator

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DockerClient:
    def __init__(self):
        try:
            # Docker 데몬 연결 (Windows의 경우 기본 npipe 사용)
            self.client = docker.from_env()
            logger.info("Docker Client Connected Successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Docker Daemon: {e}")
            self.client = None

    def list_containers(self) -> List[Dict[str, Any]]:
        """모든 컨테이너(실행 중/중지됨) 목록 반환"""
        if not self.client:
            return []
        
        containers = []
        try:
            for container in self.client.containers.list(all=True):
                containers.append({
                    "id": container.short_id,
                    "name": container.name,
                    "status": container.status,
                    "image": container.image.tags[0] if container.image.tags else "none",
                    "ports": container.ports,
                    "created": container.attrs['Created']
                })
        except Exception as e:
            logger.error(f"Error listing containers: {e}")
        
        return containers

    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """특정 컨테이너의 실시간 상태(CPU, Memory) 반환 (일회성)"""
        if not self.client:
            return {}
        
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            
            # CPU 계산 로직
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                        stats['precpu_stats']['cpu_usage']['total_usage']
            system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - \
                               stats['precpu_stats']['system_cpu_usage']
            number_cpus = stats['cpu_stats']['online_cpus']
            
            cpu_usage = 0.0
            if system_cpu_delta > 0 and cpu_delta > 0:
                cpu_usage = (cpu_delta / system_cpu_delta) * number_cpus * 100.0

            # Memory 계산 로직
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_percent = (memory_usage / memory_limit) * 100.0 if memory_limit > 0 else 0.0

            return {
                "id": container_id,
                "cpu_percent": round(cpu_usage, 2),
                "memory_usage": memory_usage,
                "memory_limit": memory_limit,
                "memory_percent": round(memory_percent, 2)
            }
        except Exception as e:
            # logger.error(f"Error getting stats for {container_id}: {e}")
            return {}

    def action_container(self, container_id: str, action: str) -> bool:
        """컨테이너 제어 (start, stop, restart)"""
        if not self.client:
            return False
            
        try:
            container = self.client.containers.get(container_id)
            if action == "start":
                container.start()
            elif action == "stop":
                container.stop()
            elif action == "restart":
                container.restart()
            return True
        except Exception as e:
            logger.error(f"Error action {action} on {container_id}: {e}")
            return False

docker_manager = DockerClient()
