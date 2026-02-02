"""
공통 유틸리티 함수
"""
import logging
from typing import Optional

from config import get_settings
from repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


def get_db_data() -> Optional[dict]:
    """MongoDB에서 최신 데이터 조회"""
    try:
        settings = get_settings()
    except Exception as e:
        logger.error(f"설정 로드 실패: {e}")
        return None

    if not settings.mongo_uri or not settings.user_id:
        return None

    try:
        repo = UserRepository(settings.mongo_uri)
        return repo.get_latest_data(settings.user_id)
    except Exception as e:
        logger.error(f"데이터 조회 중 오류: {e}")
        return None
