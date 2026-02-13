import asyncio
import logging
import json
from typing import Dict, Any
from services import container_service
from core.websocket_manager import manager as ws_manager
from core import connection
from core.config import MONITOR_INTERVAL

logger = logging.getLogger(__name__)


class DockerMonitor:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DockerMonitor, cls).__new__(cls)
            cls._instance.is_running = False
            cls._instance._task = None
            cls._instance._prev_statuses: Dict[str, str] = {}
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

    def _detect_status_changes(self, containers) -> list:
        """컨테이너 상태 변경 감지 — 브라우저 알림용"""
        events = []
        current: Dict[str, str] = {}

        for c in containers:
            cid = c["id"]
            name = c["name"]
            status = c["status"]
            current[cid] = status

            prev = self._prev_statuses.get(cid)
            if prev is not None and prev != status:
                events.append({
                    "name": name,
                    "from": prev,
                    "to": status,
                })

        # 새로 나타난 컨테이너 (이전 tick에서 없었던 경우)
        for cid in list(self._prev_statuses.keys()):
            if cid not in current:
                events.append({
                    "name": cid[:12],
                    "from": self._prev_statuses[cid],
                    "to": "removed",
                })

        self._prev_statuses = current
        return events

    async def _monitor_loop(self):
        """주기적으로 Docker 상태를 조회하고 WebSocket으로 브로드캐스트"""
        while self.is_running:
            try:
                # 연결된 클라이언트가 없으면 폴링 일시 중지 (부하 감소)
                if not ws_manager.active_connections:
                    await asyncio.sleep(2)
                    continue

                # Docker 연결 상태 확인
                if not await connection.ensure_connected():
                    error_payload = {
                        "type": "error",
                        "message": "Docker daemon is not available",
                        "docker_connected": False,
                    }
                    await ws_manager.broadcast(json.dumps(error_payload))
                    await asyncio.sleep(5)
                    continue

                # 1. 컨테이너 목록
                containers = await container_service.list_containers()

                # 2. 상태 변경 감지
                status_events = self._detect_status_changes(containers)

                # 3. 실행 중인 컨테이너 Stats (병렬 수집)
                stats_data = []
                running_containers = [c for c in containers if c["status"] == "running"]

                if running_containers:
                    stats_coroutines = [
                        container_service.get_container_stats(c["id"])
                        for c in running_containers
                    ]
                    stats_results = await asyncio.gather(
                        *stats_coroutines, return_exceptions=True
                    )

                    for i, stat in enumerate(stats_results):
                        if isinstance(stat, dict) and stat:
                            stat["name"] = running_containers[i]["name"]
                            stats_data.append(stat)

                # 4. 브로드캐스트
                payload = {
                    "type": "stats_update",
                    "docker_connected": True,
                    "containers": containers,
                    "stats": stats_data,
                }

                # 상태 변경 이벤트가 있으면 포함
                if status_events:
                    payload["status_events"] = status_events

                await ws_manager.broadcast(json.dumps(payload))

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            await asyncio.sleep(MONITOR_INTERVAL)


monitor = DockerMonitor()
