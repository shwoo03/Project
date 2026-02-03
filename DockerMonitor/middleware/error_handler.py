from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

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

logger = logging.getLogger("middleware.error_handler")

def register_error_handlers(app: FastAPI):
    """Register all exception handlers to the application"""

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
