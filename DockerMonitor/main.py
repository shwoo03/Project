from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import logging

from core.docker_client import docker_manager
from routers import containers, websocket, networks, images, terminal, volumes
from middleware.error_handler import register_error_handlers


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 Docker 연결 관리"""
    # 시작 시 Docker 연결
    await docker_manager.connect()
    logger.info("Application started")
    yield
    # 종료 시 연결 해제
    await docker_manager.disconnect()
    logger.info("Application shutdown")


app = FastAPI(title="Docker Monitor", lifespan=lifespan)

# Register Exception Handlers
register_error_handlers(app)

# ============ Static Files & Templates ============

# 정적 파일 및 템플릿 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 라우터 등록
app.include_router(containers.router)
app.include_router(websocket.router)
app.include_router(networks.router)
app.include_router(images.router)
app.include_router(terminal.router)
app.include_router(volumes.router)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """메인 대시보드 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/networks", response_class=HTMLResponse)
async def get_networks_page(request: Request):
    """Networks 페이지"""
    return templates.TemplateResponse("networks.html", {"request": request})


@app.get("/images", response_class=HTMLResponse)
async def get_images_page(request: Request):
    """Images 페이지"""
    return templates.TemplateResponse("images.html", {"request": request})


@app.get("/volumes", response_class=HTMLResponse)
async def get_volumes_page(request: Request):
    """Volumes 페이지"""
    return templates.TemplateResponse("volumes.html", {"request": request})


@app.get("/logs", response_class=HTMLResponse)
async def get_logs_page(request: Request):
    """Logs 페이지"""
    return templates.TemplateResponse("logs.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10002, reload=True)
