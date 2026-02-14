"""
환경 변수 설정 로드 (Pydantic Settings 기반)
"""
import logging
from functools import lru_cache

from pydantic_settings import BaseSettings

logger = logging.getLogger(f"instagram.{__name__}")


class Settings(BaseSettings):
    """애플리케이션 설정 (환경 변수에서 로드)"""
    user_id: str
    user_password: str
    mongo_uri: str
    discord_webhook: str | None = None
    access_password: str  # .env 필수
    shwoo_url: str = "https://xn--9t4ba122aba.site"

    # SSO 인증 관련 설정
    instagram_token_secret: str  # .env 필수
    allowed_emails: list[str] = []
    token_expiry_seconds: int = 300  # 5분

    # API 설정
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    api_timeout: float = 30.0
    request_headers: dict = {
        "Accept-Language": "ko-KR",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

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


