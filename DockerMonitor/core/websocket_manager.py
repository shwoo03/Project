from fastapi import WebSocket
from typing import List
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """새 WebSocket 연결 수락"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """WebSocket 연결 해제"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """모든 연결에 메시지 브로드캐스트"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                disconnected.append(connection)
        
        # 실패한 연결 정리
        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """특정 연결에 메시지 전송"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        """현재 연결 수 반환"""
        return len(self.active_connections)


# 싱글톤 인스턴스
manager = ConnectionManager()
