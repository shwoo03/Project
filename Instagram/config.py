"""
환경 변수 설정 로드 (Pydantic Settings 기반)
"""
import logging
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """애플리케이션 설정 (환경 변수에서 로드)"""
    user_id: str
    user_password: str
    mongo_uri: str
    discord_webhook: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 정의되지 않은 환경 변수 무시


@lru_cache
def get_settings() -> Settings:
    """설정 싱글톤 반환 (캐시됨)"""
    try:
        return Settings()
    except Exception as e:
        logger.error(f"설정 로드 실패: {e}")
        raise


def get_env_var() -> Optional[dict]:
    """
    하위 호환성을 위한 함수 (기존 코드와 호환)
    
    return: dict
        USERNAME: str
        PASSWORD: str 
        DISCORD_WEBHOOK: str
        MONGO_URI: str
        형태로 반환 
    """
    try:
        settings = get_settings()
        return {
            "USERNAME": settings.user_id,
            "PASSWORD": settings.user_password,
            "DISCORD_WEBHOOK": settings.discord_webhook,
            "MONGO_URI": settings.mongo_uri
        }
    except Exception as e:
        logger.error(f"환경 변수 로드 실패: {e}")
        return None
