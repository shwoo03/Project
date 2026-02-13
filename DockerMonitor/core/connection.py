"""
Docker 연결 관리 모듈 - 단일 클라이언트 생성 및 생명주기 관리
"""
import docker
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_client: Optional[docker.DockerClient] = None
_executor = ThreadPoolExecutor(max_workers=4)


def get_client() -> docker.DockerClient:
    """현재 Docker 클라이언트 반환"""
    if not _client:
        raise RuntimeError("Docker client not connected. Call connect() first.")
    return _client


def get_executor() -> ThreadPoolExecutor:
    """공유 ThreadPoolExecutor 반환"""
    return _executor


async def connect():
    """Docker 데몬에 연결하고 모든 서비스에 클라이언트 주입"""
    global _client
    loop = asyncio.get_running_loop()
    try:
        _client = await loop.run_in_executor(_executor, docker.from_env)
        await loop.run_in_executor(_executor, _client.ping)
        
        # 모든 서비스에 클라이언트 주입
        from services import init_services
        init_services(_client)
        
        logger.info("Docker client connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Docker daemon: {e}")
        _client = None
        raise


async def disconnect():
    """Docker 연결 종료"""
    global _client
    if _client:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(_executor, _client.close)
        except Exception as e:
            logger.warning(f"Error closing Docker client: {e}")
        finally:
            _client = None
            logger.info("Docker client disconnected")


async def ensure_connected() -> bool:
    """연결 확인 및 재연결 시도"""
    global _client
    if _client:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(_executor, _client.ping)
            return True
        except Exception:
            _client = None

    try:
        await connect()
        return True
    except Exception:
        return False


async def get_status() -> Dict[str, Any]:
    """Docker 데몬 상태 정보 반환"""
    if not await ensure_connected():
        return {"connected": False, "error": "Cannot connect to Docker daemon"}

    try:
        loop = asyncio.get_running_loop()
        
        def _get_status_sync():
            version = _client.version()
            info = _client.info()
            return {
                "connected": True,
                "version": version.get("Version", "unknown"),
                "api_version": version.get("ApiVersion", "unknown"),
                "containers_running": info.get("ContainersRunning", 0),
                "containers_total": info.get("Containers", 0),
                "images": info.get("Images", 0),
            }
        
        return await loop.run_in_executor(_executor, _get_status_sync)
    except Exception as e:
        return {"connected": False, "error": str(e)}
