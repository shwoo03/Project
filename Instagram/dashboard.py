"""
인스타그램 팔로워 추적기 - 통합 웹 대시보드
웹에서 모든 기능 제어 가능
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import uvicorn

# 모듈 import
from log_handler import MongoHandler
from scheduler import get_scheduler, shutdown_scheduler
from routers import views, api
from state_manager import state

# 로깅 설정
# 기존 파일 핸들러 유지 + MongoDB 핸들러 추가
logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 파일 핸들러
file_handler = logging.FileHandler('instagram_tracker.log', encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 스트림 핸들러
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# MongoDB 핸들러
mongo_handler = MongoHandler()
mongo_handler.setFormatter(formatter)
logger.addHandler(mongo_handler)

local_logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    local_logger.info("대시보드 서버 시작")
    get_scheduler()  # 스케줄러 초기화
    yield
    shutdown_scheduler()  # 스케줄러 종료
    local_logger.info("대시보드 서버 종료")


app = FastAPI(
    title="Instagram Follower Tracker",
    description="인스타그램 팔로워 추적 대시보드",
    version="2.0.0",
    lifespan=lifespan
)

# 라우터 등록
app.include_router(views.router)
app.include_router(api.router)

# 정적 파일 서빙 (PWA용)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 로그 WebSocket"""
    await websocket.accept()
    state.websocket_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
            # 클라이언트 메시지 처리 (핑 등)
    except WebSocketDisconnect:
        if websocket in state.websocket_clients:
            state.websocket_clients.remove(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
