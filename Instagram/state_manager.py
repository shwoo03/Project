import logging
from fastapi import WebSocket

logger = logging.getLogger(f"instagram.{__name__}")


class AppState:
    """애플리케이션 상태 관리 (싱글톤 인스턴스로 사용)"""

    def __init__(self):
        self.is_running: bool = False
        self.last_log: str = ""
        self.progress: int = 0
        self.websocket_clients: list[WebSocket] = []

    async def broadcast_log(self, message: str):
        self.last_log = message
        cleanup_list = []
        for client in self.websocket_clients:
            try:
                await client.send_json({"type": "log", "message": message})
            except Exception:
                cleanup_list.append(client)
        
        for client in cleanup_list:
            if client in self.websocket_clients:
                self.websocket_clients.remove(client)

    async def broadcast_progress(self, progress: int, status: str):
        self.progress = progress
        cleanup_list = []
        for client in self.websocket_clients:
            try:
                await client.send_json({"type": "progress", "progress": progress, "status": status})
            except Exception:
                cleanup_list.append(client)
                
        for client in cleanup_list:
            if client in self.websocket_clients:
                self.websocket_clients.remove(client)

state = AppState()
