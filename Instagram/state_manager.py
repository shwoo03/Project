from fastapi import WebSocket

class AppState:
    is_running: bool = False
    last_log: str = ""
    progress: int = 0
    websocket_clients: list[WebSocket] = []

    async def broadcast_log(self, message: str):
        self.last_log = message
        cleanup_list = []
        for client in self.websocket_clients:
            try:
                await client.send_json({"type": "log", "message": message})
            except:
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
            except:
                cleanup_list.append(client)
                
        for client in cleanup_list:
            if client in self.websocket_clients:
                self.websocket_clients.remove(client)

state = AppState()
