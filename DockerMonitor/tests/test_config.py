"""
설정 모듈(config) 테스트
"""
import pytest
from unittest.mock import patch
import os


def test_config_defaults():
    """기본값이 올바르게 설정되는지 확인"""
    from core.config import settings
    assert settings.docker_token_secret is not None
    assert settings.shwoo_url.startswith("http")
    assert settings.token_expiry_seconds > 0
    assert settings.monitor_interval > 0


def test_allowed_email_list():
    """콤마 구분 이메일이 리스트로 파싱되는지 확인"""
    from core.config import settings
    emails = settings.allowed_email_list
    assert isinstance(emails, list)
    assert len(emails) >= 1
    assert all("@" in e for e in emails)


def test_settings_direct_access():
    """settings 인스턴스에서 직접 접근이 정상 동작하는지 확인"""
    from core.config import settings
    assert isinstance(settings.allowed_email_list, list)
    assert isinstance(settings.docker_token_secret, str)
    assert isinstance(settings.shwoo_url, str)
    assert isinstance(settings.token_expiry_seconds, int)
    assert isinstance(settings.monitor_interval, int)


def test_config_env_override():
    """환경 변수로 설정 오버라이드 테스트"""
    with patch.dict(os.environ, {"DOCKER_TOKEN_SECRET": "test-secret-override"}):
        from pydantic_settings import BaseSettings
        from core.config import Settings
        s = Settings()
        assert s.docker_token_secret == "test-secret-override"
