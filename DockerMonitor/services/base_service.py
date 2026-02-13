import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import docker

logger = logging.getLogger(__name__)


class BaseService:
    """모든 서비스의 기본 클래스 - 외부에서 클라이언트를 주입받음"""

    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._executor: Optional[ThreadPoolExecutor] = None

    def set_client(self, client: docker.DockerClient, executor: ThreadPoolExecutor):
        """Docker 클라이언트와 executor를 외부에서 주입"""
        self._client = client
        self._executor = executor

    @property
    def client(self) -> docker.DockerClient:
        if not self._client:
            raise RuntimeError("Docker client not injected. Call set_client() first.")
        return self._client

    @property
    def executor(self) -> ThreadPoolExecutor:
        if not self._executor:
            raise RuntimeError("Executor not injected. Call set_client() first.")
        return self._executor

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    async def ensure_connected(self) -> bool:
        """연결 확인 (재연결은 connection 모듈에서 처리)"""
        if not self._client:
            return False
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self.executor, self._client.ping)
            return True
        except Exception:
            return False

    async def run_sync(self, func, *args, **kwargs):
        """동기 함수를 비동기로 실행"""
        loop = asyncio.get_running_loop()
        from functools import partial
        return await loop.run_in_executor(self.executor, partial(func, *args, **kwargs))
