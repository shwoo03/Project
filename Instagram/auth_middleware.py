"""
인증 미들웨어 - 세션 기반 간단 인증
특정 사용자만 접근 가능하도록 보호
"""
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
import hashlib
import os

# 허용된 사용자 이메일 목록
ALLOWED_EMAILS = ["dntmdgns03@naver.com"]

# 환경변수에서 설정 로드
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "shwoo2026")
SHWOO_URL = os.getenv("SHWOO_URL", "https://shwoo.site")


def hash_password(password: str) -> str:
    """비밀번호 해시 생성"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_session(request: Request) -> bool:
    """세션에서 인증 상태 확인"""
    session_token = request.cookies.get("instagram_auth")
    expected_token = hash_password(ACCESS_PASSWORD)
    return session_token == expected_token


class AuthMiddleware(BaseHTTPMiddleware):
    """인증 미들웨어 - 보호된 경로에 대한 접근 제어"""
    
    # 인증 없이 접근 가능한 경로
    PUBLIC_PATHS = ["/login", "/static", "/favicon.ico"]
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 공개 경로는 인증 없이 허용
        if any(path.startswith(p) for p in self.PUBLIC_PATHS):
            return await call_next(request)
        
        # 인증 확인
        if not verify_session(request):
            return RedirectResponse("/login", status_code=302)
        
        return await call_next(request)


def get_login_page(error: str = None) -> str:
    """로그인 페이지 HTML 반환"""
    error_html = f'<p class="error">{error}</p>' if error else ''
    return f'''
<!DOCTYPE html>
<html lang="ko" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Instagram Insight</title>
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
        .error {{
            color: #ef4444;
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }}
    </style>
</head>
<body class="flex items-center justify-center">
    <div class="glass rounded-2xl p-8 max-w-md w-full mx-4">
        <div class="text-center mb-8">
            <h1 class="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
                Instagram Insight
            </h1>
            <p class="text-gray-400 mt-2">접근하려면 비밀번호를 입력하세요</p>
        </div>
        
        <form method="POST" action="/login" class="space-y-4">
            <div>
                <input 
                    type="password" 
                    name="password" 
                    placeholder="비밀번호"
                    class="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                    autofocus
                >
                {error_html}
            </div>
            <button 
                type="submit"
                class="w-full py-3 rounded-lg bg-gradient-to-r from-blue-500 to-purple-500 text-white font-medium hover:opacity-90 transition-opacity"
            >
                로그인
            </button>
        </form>
        
        <div class="mt-6 text-center">
            <a href="{SHWOO_URL}" class="text-gray-400 hover:text-white text-sm transition-colors">
                ← Shwoo 사이트로 돌아가기
            </a>
        </div>
    </div>
</body>
</html>
'''
