import asyncio
import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
from .docker_client import docker_manager
from .websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)

class DockerMonitor:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DockerMonitor, cls).__new__(cls)
            cls._instance.is_running = False
            cls._instance._task = None
        return cls._instance

    async def start(self):
        """백그라운드 모니터링 시작"""
        if self.is_running:
            return
            
        self.is_running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Docker Monitor started")

    async def stop(self):
        """모니터링 중지"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Docker Monitor stopped")

    async def _monitor_loop(self):
        """주기적으로 Docker 상태를 조회하고 WebSocket으로 브로드캐스트"""
        while self.is_running:
            try:
                # 연결된 클라이언트가 없으면 폴링 일시 중지 (부하 감소)
                if not ws_manager.active_connections:
                    await asyncio.sleep(2)
                    continue

                # Docker 연결 상태 확인
                if not await docker_manager.ensure_connected():
                    error_payload = {
                        "type": "error",
                        "message": "Docker daemon is not available",
                        "docker_connected": False
                    }
                    await ws_manager.broadcast(json.dumps(error_payload))
                    await asyncio.sleep(5)
                    continue

                # 1. 컨테이너 목록
                containers = await docker_manager.list_containers()
                
                # 2. 실행 중인 컨테이너 Stats (병렬 수집)
                stats_data = []
                running_containers = [c for c in containers if c['status'] == 'running']
                
                if running_containers:
                    stats_coroutines = [docker_manager.get_container_stats(c['id']) for c in running_containers]
                    stats_results = await asyncio.gather(*stats_coroutines, return_exceptions=True)
                    
                    for i, stat in enumerate(stats_results):
                        if isinstance(stat, dict) and stat:
                            stat['name'] = running_containers[i]['name']
                            stats_data.append(stat)

                # 3. 브로드캐스트
                payload = {
                    "type": "stats_update",
                    "docker_connected": True,
                    "containers": containers,
                    "stats": stats_data
                }
                
                await ws_manager.broadcast(json.dumps(payload))
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                
            await asyncio.sleep(2)

monitor = DockerMonitor()
