from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import asyncio
import logging
import json

from core.docker_client import docker_manager

app = FastAPI(title="Docker Monitor")

# 정적 파일 및 템플릿 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 로깅
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# WebSocket 연결 관리
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """메인 대시보드 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/containers")
async def api_list_containers():
    """컨테이너 목록 API"""
    return docker_manager.list_containers()


class ActionRequest(BaseModel):
    action: str

@app.post("/api/containers/{container_id}/action")
async def api_container_action(container_id: str, req: ActionRequest):
    """컨테이너 제어 API"""
    success = docker_manager.action_container(container_id, req.action)
    if success:
        return {"status": "success", "message": f"Container {req.action} successful"}
    return JSONResponse(status_code=500, content={"status": "error", "message": "Action failed"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 상태 브로드캐스트용 소켓"""
    await manager.connect(websocket)
    try:
        while True:
            # 1. 컨테이너 목록 가져오기
            containers = docker_manager.list_containers()
            
            # 2. 실행 중인 컨테이너들의 Stats 가져오기
            stats_data = []
            for c in containers:
                if c['status'] == 'running':
                    stat = docker_manager.get_container_stats(c['id'])
                    if stat:
                        stat['name'] = c['name'] # 이름도 같이 보냄
                        stats_data.append(stat)
            
            # 3. 데이터 전송
            payload = {
                "type": "stats_update",
                "containers": containers, # 상태 업데이트용
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10002, reload=True)
