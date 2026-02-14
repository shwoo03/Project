import logging
from fastapi import WebSocket

logger = logging.getLogger(f"instagram.{__name__}")


class AppState:
    """애플리케이션 상태 관리 (싱글톤 인스턴스로 사용)"""

    def __init__(self):
        self.is_running: bool = False
        self.last_log: str = ""
        self.progress: int = 0
        self.cancellation_requested: bool = False
        self.websocket_clients: list[WebSocket] = []

    async def _broadcast(self, data: dict):
        """WebSocket 클라이언트에 메시지 브로드캐스트 (공통 헬퍼)"""
        cleanup_list = []
        for client in self.websocket_clients:
            try:
                await client.send_json(data)
            except Exception:
                cleanup_list.append(client)
        for client in cleanup_list:
            if client in self.websocket_clients:
                self.websocket_clients.remove(client)

    async def broadcast_log(self, message: str):
        self.last_log = message
        await self._broadcast({"type": "log", "message": message})

    async def broadcast_progress(self, progress: int, status: str):
        self.progress = progress
        await self._broadcast({"type": "progress", "progress": progress, "status": status})

    def request_cancel(self):
        """작업 취소 요청"""
        if self.is_running:
            self.cancellation_requested = True
            logger.info("작업 취소 요청됨")

    def reset_cancel(self):
        """취소 상태 초기화"""
        self.cancellation_requested = False

state = AppState()
