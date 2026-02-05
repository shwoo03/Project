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
    """실시간 상태 브로드캐스트용 WebSocket
    
    기존의 Polling 방식에서 Passive 수신 방식으로 변경됨.
    실제 데이터는 core/monitor.py의 DockerMonitor가 주기적으로 Broadcast 함.
    """
    await manager.connect(websocket)
    try:
        # 클라이언트가 연결을 유지하도록 대기
        # 클라이언트에서 메시지를 보낼 일이 없다면 그냥 대기만 함
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
