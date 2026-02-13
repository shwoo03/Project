"""
FastAPI 의존성 주입 모듈
"""
from functools import lru_cache
from config import get_settings, Settings
from repositories.user_repository import UserRepository
from repositories.log_repository import LogRepository


@lru_cache
def get_user_repo() -> UserRepository:
    """UserRepository 싱글톤 의존성"""
    settings = get_settings()
    return UserRepository(settings.mongo_uri)


@lru_cache
def get_log_repo() -> LogRepository:
    """LogRepository 싱글톤 의존성"""
    settings = get_settings()
    return LogRepository(settings.mongo_uri)
