import docker
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

# 로깅 설정
logger = logging.getLogger(__name__)

# 공유 Executor (모든 서비스에서 공유)
shared_executor = ThreadPoolExecutor(max_workers=4)


class BaseService:
    """모든 서비스의 기본 클래스"""
    
    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._connected: bool = False
    
    @property
    def client(self) -> docker.DockerClient:
        if not self._client:
            raise Exception("Docker client not connected")
        return self._client
    
    @property
    def executor(self) -> ThreadPoolExecutor:
        return shared_executor

    async def connect(self) -> bool:
        """Docker 데몬에 연결"""
        try:
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(self.executor, docker.from_env)
            # 연결 테스트
            await loop.run_in_executor(self.executor, self._client.ping)
            self._connected = True
            logger.info(f"{self.__class__.__name__} connected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect in {self.__class__.__name__}: {e}")
            self._connected = False
            self._client = None
            return False
            
    async def disconnect(self):
        """Docker 연결 종료"""
        if self._client:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self.executor, self._client.close)
            except Exception as e:
                logger.warning(f"Error closing client in {self.__class__.__name__}: {e}")
            finally:
                self._client = None
                self._connected = False

    async def ensure_connected(self) -> bool:
        """연결 확인 및 재연결 시도"""
        if self._client and self._connected:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self.executor, self._client.ping)
                return True
            except Exception:
                self._connected = False
        
        return await self.connect()

    async def run_sync(self, func, *args, **kwargs):
        """동기 함수를 비동기로 실행"""
        loop = asyncio.get_event_loop()
        from functools import partial
        return await loop.run_in_executor(self.executor, partial(func, *args, **kwargs))
