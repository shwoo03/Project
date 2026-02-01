from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
import logging

from core.docker_client import docker_manager
from core.websocket_manager import manager

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 상태 브로드캐스트용 WebSocket"""
    await manager.connect(websocket)
    try:
        while True:
            # Docker 연결 상태 확인
            is_connected = await docker_manager.ensure_connected()
            
            if not is_connected:
                # Docker 데몬 오프라인
                payload = {
                    "type": "error",
                    "message": "Docker daemon is not available",
                    "docker_connected": False
                }
                await websocket.send_text(json.dumps(payload))
                await asyncio.sleep(5)  # 재연결 시도 간격
                continue
            
            # 1. 컨테이너 목록 가져오기
            containers = await docker_manager.list_containers()
            
            # 2. 실행 중인 컨테이너들의 Stats 가져오기
            stats_data = []
            for c in containers:
                if c['status'] == 'running':
                    stat = await docker_manager.get_container_stats(c['id'])
                    if stat:
                        stat['name'] = c['name']
                        stats_data.append(stat)
            
            # 3. 데이터 전송
            payload = {
                "type": "stats_update",
                "docker_connected": True,
                "containers": containers,
                "stats": stats_data
            }
            await websocket.send_text(json.dumps(payload))
            
            # 2초 대기
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
