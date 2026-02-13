"""
인증 관련 모듈 - shwoo_server SSO 연동
"""
import hashlib
import hmac
import base64
import datetime
import logging
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core.config import ALLOWED_EMAILS, TOKEN_SECRET, SHWOO_URL, TOKEN_EXPIRY_SECONDS

logger = logging.getLogger(__name__)


def verify_token(token: str) -> str | None:
    """토큰 검증 - 유효하면 이메일 반환, 아니면 None"""
    try:
        # Base64 URL-safe 디코딩 (패딩 추가)
        padding = 4 - len(token) % 4
        if padding != 4:
            token = token + '=' * padding
        
        decoded = base64.urlsafe_b64decode(token).decode()
        parts = decoded.split(":")
        
        if len(parts) != 3:
            return None
        
        email, timestamp_str, signature = parts
        
        # 서명 검증
        data = f"{email}:{timestamp_str}"
        expected_signature = hmac.new(
            TOKEN_SECRET.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return None
        
        # 시간 검증 (5분 이내)
        timestamp = int(timestamp_str)
        current_time = datetime.datetime.now().timestamp() * 1000
        time_diff = current_time - timestamp
        
        if time_diff > TOKEN_EXPIRY_SECONDS * 1000:
            return None
        
        # 허용된 이메일인지 확인
        if email not in ALLOWED_EMAILS:
            return None
        
        return email
    except Exception as e:
        logger.warning(f"Token verification error: {e}")
        return None


def hash_email(email: str) -> str:
    """이메일 해시 생성 - 세션 토큰용"""
    return hashlib.sha256(f"{email}:{TOKEN_SECRET}".encode()).hexdigest()


async def auth_callback(request: Request, token: str = None):
    """토큰 기반 인증 콜백 - shwoo_server에서 리다이렉트됨"""
    if not token:
        return RedirectResponse(SHWOO_URL, status_code=302)
    
    email = verify_token(token)
    
    if not email:
        # 토큰이 유효하지 않음 - 접근 거부 페이지 표시
        html = f'''
<!DOCTYPE html>
<html lang="ko" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>접근 거부 - Docker Monitor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
        }}
        .glass {{
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
    </style>
</head>
<body class="flex items-center justify-center">
    <div class="glass rounded-2xl p-8 max-w-md w-full mx-4 text-center">
        <div class="text-6xl mb-4">🔒</div>
        <h1 class="text-2xl font-bold text-red-400 mb-4">접근이 거부되었습니다</h1>
        <p class="text-gray-400 mb-6">유효하지 않거나 만료된 인증 토큰입니다.</p>
        <a href="{SHWOO_URL}" 
           class="inline-block px-6 py-3 rounded-lg bg-gradient-to-r from-blue-500 to-purple-500 text-white font-medium hover:opacity-90 transition-opacity">
            Shwoo 사이트로 돌아가기
        </a>
    </div>
</body>
</html>
'''
        return HTMLResponse(content=html, status_code=403)
    
    # 인증 성공 - 세션 쿠키 설정 후 대시보드로 리다이렉트
    response = RedirectResponse("/", status_code=302)
    session_token = hash_email(email)
    response.set_cookie(
        key="docker_auth",
        value=session_token,
        httponly=True,
        max_age=86400 * 7  # 7일
    )
    return response


async def login_redirect(request: Request):
    """로그인 페이지 - shwoo_server로 리다이렉트"""
    return RedirectResponse(SHWOO_URL, status_code=302)
