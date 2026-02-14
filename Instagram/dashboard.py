"""
인스타그램 팔로워 추적기 - 통합 웹 대시보드
웹에서 모든 기능 제어 가능
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# 모듈 import
from log_handler import MongoHandler
from logging_config import setup_logging
from scheduler import get_scheduler, shutdown_scheduler
from routers import views, api
from state_manager import state
from config import get_settings
from services.auth_utils import verify_session_token

# 로깅 설정
local_logger = setup_logging()


class AuthMiddleware(BaseHTTPMiddleware):
    """인증 미들웨어 - 보호된 경로에 대한 접근 제어"""
    
    PUBLIC_PATHS = ["/login", "/auth", "/static", "/favicon.ico", "/api/health"]
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        if any(path.startswith(p) for p in self.PUBLIC_PATHS):
            return await call_next(request)
        
        session_token = request.cookies.get("instagram_auth")
        
        if not session_token:
            return RedirectResponse("/login", status_code=302)
        
        if not verify_session_token(session_token):
            return RedirectResponse("/login", status_code=302)
        
        return await call_next(request)


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

# 인증 미들웨어 등록
app.add_middleware(AuthMiddleware)

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
