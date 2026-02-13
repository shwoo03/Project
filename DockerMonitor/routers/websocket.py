from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

from core.websocket_manager import manager

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 상태 브로드캐스트용 WebSocket

    실제 데이터는 core/monitor.py의 DockerMonitor가 주기적으로 Broadcast 함.
    """
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
