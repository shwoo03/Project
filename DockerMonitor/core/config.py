"""
중앙 설정 모듈 - pydantic-settings 기반
.env 파일 또는 환경 변수에서 로딩
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """애플리케이션 설정"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 허용된 이메일 목록 (콤마 구분 문자열 → 리스트)
    allowed_emails: str = "dntmdgns03@naver.com"

    # 토큰 시크릿 (shwoo_server와 동일해야 함)
    docker_token_secret: str = "shwoo-docker-secret-2026"

    # Shwoo 서버 URL
    shwoo_url: str = "https://xn--9t4ba122aba.site"

    # 토큰 유효 시간 (초)
    token_expiry_seconds: int = 300

    # 모니터링 간격 (초)
    monitor_interval: int = 5

    @property
    def allowed_email_list(self) -> List[str]:
        """콤마로 구분된 이메일 문자열을 리스트로 변환"""
        return [e.strip() for e in self.allowed_emails.split(",") if e.strip()]


# 싱글턴 인스턴스
settings = Settings()

# 하위 호환 alias
ALLOWED_EMAILS = settings.allowed_email_list
TOKEN_SECRET = settings.docker_token_secret
SHWOO_URL = settings.shwoo_url
TOKEN_EXPIRY_SECONDS = settings.token_expiry_seconds
MONITOR_INTERVAL = settings.monitor_interval
