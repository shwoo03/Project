from fastapi import APIRouter

from core.docker_client import docker_manager

router = APIRouter(prefix="/api", tags=["networks"])


@router.get("/networks")
async def list_networks():
    """Docker 네트워크 목록 API"""
    networks = await docker_manager.list_networks()
    return networks
