"""
인증 유틸리티 — 세션 해시 생성 및 검증 공통 모듈
"""
import hashlib

from config import get_settings


def hash_email(email: str) -> str:
    """이메일 → 세션 토큰 해시 생성"""
    settings = get_settings()
    return hashlib.sha256(
        f"{email}:{settings.instagram_token_secret}".encode()
    ).hexdigest()


def verify_session_token(token: str) -> bool:
    """세션 토큰이 허용된 이메일 중 하나와 일치하는지 확인"""
    settings = get_settings()
    for email in settings.allowed_emails:
        if token == hash_email(email):
            return True
    return False
