from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
import logging

from core.docker_client import docker_manager
from core.exceptions import (
    DockerMonitorException,
    DockerConnectionError,
    ContainerNotFoundError,
    ImageNotFoundError,
    VolumeNotFoundError,
    NetworkNotFoundError,
    InvalidActionError,
)
from core.schemas import error_response
from routers import containers, websocket, networks, images, logs, terminal, volumes


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


# ============ Global Exception Handlers ============

@app.exception_handler(DockerMonitorException)
async def docker_monitor_exception_handler(request: Request, exc: DockerMonitorException):
    """커스텀 예외 핸들러"""
    logger.error(f"DockerMonitorException: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=400,
        content=error_response(code=exc.code, message=exc.message)
    )


@app.exception_handler(DockerConnectionError)
async def docker_connection_exception_handler(request: Request, exc: DockerConnectionError):
    """Docker 연결 에러 핸들러"""
    logger.error(f"DockerConnectionError: {exc.message}")
    return JSONResponse(
        status_code=503,
        content=error_response(code=exc.code, message=exc.message)
    )


@app.exception_handler(ContainerNotFoundError)
async def container_not_found_handler(request: Request, exc: ContainerNotFoundError):
    """컨테이너 없음 에러 핸들러"""
    return JSONResponse(
        status_code=404,
        content=error_response(code=exc.code, message=exc.message)
    )


@app.exception_handler(ImageNotFoundError)
async def image_not_found_handler(request: Request, exc: ImageNotFoundError):
    """이미지 없음 에러 핸들러"""
    return JSONResponse(
        status_code=404,
        content=error_response(code=exc.code, message=exc.message)
    )


@app.exception_handler(VolumeNotFoundError)
async def volume_not_found_handler(request: Request, exc: VolumeNotFoundError):
    """볼륨 없음 에러 핸들러"""
    return JSONResponse(
        status_code=404,
        content=error_response(code=exc.code, message=exc.message)
    )


@app.exception_handler(NetworkNotFoundError)
async def network_not_found_handler(request: Request, exc: NetworkNotFoundError):
    """네트워크 없음 에러 핸들러"""
    return JSONResponse(
        status_code=404,
        content=error_response(code=exc.code, message=exc.message)
    )


@app.exception_handler(InvalidActionError)
async def invalid_action_handler(request: Request, exc: InvalidActionError):
    """유효하지 않은 액션 에러 핸들러"""
    return JSONResponse(
        status_code=400,
        content=error_response(code=exc.code, message=exc.message)
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 예외 핸들러"""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code="HTTP_ERROR", message=exc.detail)
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 핸들러"""
    logger.error(f"Unhandled exception: {type(exc).__name__} - {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=error_response(code="INTERNAL_ERROR", message="내부 서버 오류가 발생했습니다")
    )


# ============ Static Files & Templates ============

# 정적 파일 및 템플릿 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 라우터 등록
app.include_router(containers.router)
app.include_router(websocket.router)
app.include_router(networks.router)
app.include_router(images.router)
app.include_router(logs.router)
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
