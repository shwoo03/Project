"""
인증 미들웨어 - shwoo_server SSO 연동
"""
import hashlib
import os
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware


class AuthMiddleware(BaseHTTPMiddleware):
    """인증 미들웨어 - 보호된 경로에 대한 접근 제어"""
    
    # 인증 없이 접근 가능한 경로
    PUBLIC_PATHS = ["/login", "/auth", "/static", "/favicon.ico"]
    
    # 허용된 이메일 목록
    ALLOWED_EMAILS = ["dntmdgns03@naver.com"]
    
    # 토큰 시크릿 (shwoo_server와 동일해야 함)
    TOKEN_SECRET = os.getenv("DOCKER_TOKEN_SECRET", "shwoo-docker-secret-2026")
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 공개 경로는 인증 없이 허용
        if any(path.startswith(p) for p in self.PUBLIC_PATHS):
            return await call_next(request)
        
        # 인증 확인 - 이메일 기반 세션 토큰 검증
        session_token = request.cookies.get("docker_auth")
        
        if not session_token:
            return RedirectResponse("/login", status_code=302)
        
        # 허용된 이메일 중 하나와 일치하는지 확인
        valid_session = False
        for email in self.ALLOWED_EMAILS:
            expected_token = hashlib.sha256(f"{email}:{self.TOKEN_SECRET}".encode()).hexdigest()
            if session_token == expected_token:
                valid_session = True
                break
        
        if not valid_session:
            return RedirectResponse("/login", status_code=302)
        
        return await call_next(request)
