from fastapi import APIRouter

from services import system_service
from core.schemas import success_response

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("")
async def get_system_info():
    """Docker 시스템 정보 API (디스크 사용량, 호스트 정보)"""
    data = await system_service.get_system_info()
    return success_response(data=data)
