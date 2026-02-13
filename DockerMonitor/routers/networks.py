from fastapi import APIRouter

from services import network_service
from core.schemas import success_response

router = APIRouter(prefix="/api/networks", tags=["networks"])


@router.get("")
async def list_networks():
    """Docker 네트워크 목록 API"""
    networks = await network_service.list_networks()
    return success_response(data=networks)
