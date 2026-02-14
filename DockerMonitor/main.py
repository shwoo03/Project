from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from core import connection
from core.monitor import monitor
from core.auth import auth_callback, login_redirect
from routers import containers, websocket, networks, images, terminal, volumes, compose, system
from routers.pages import router as pages_router
from middleware.error_handler import register_error_handlers
from middleware.auth_middleware import AuthMiddleware


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 Docker 연결 관리"""
    # 시작 시 Docker 연결 (단일 클라이언트 → 모든 서비스에 주입)
    await connection.connect()
    # 모니터링 시작
    await monitor.start()
    logger.info("Application started")
    yield
    # 종료 시 정리
    await monitor.stop()
    await connection.disconnect()
    logger.info("Application shutdown")


app = FastAPI(title="Docker Monitor", lifespan=lifespan)

# 인증 미들웨어 등록
app.add_middleware(AuthMiddleware)

# Register Exception Handlers
register_error_handlers(app)

# ============ Static Files ============

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# ============ Routers ============

# API 라우터 등록
app.include_router(containers.router)
app.include_router(websocket.router)
app.include_router(networks.router)
app.include_router(images.router)
app.include_router(terminal.router)
app.include_router(volumes.router)
app.include_router(compose.router)
app.include_router(system.router)

# 페이지 라우터 등록
app.include_router(pages_router)

# 인증 라우트 등록
app.get("/auth")(auth_callback)
app.get("/login")(login_redirect)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10002, reload=True)
