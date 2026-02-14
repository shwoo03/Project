"""
뷰 라우터 - HTML 페이지 렌더링
"""
import logging
import datetime
import hmac
import hashlib
import base64

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config import get_settings
from dependencies import get_user_repo
from repositories.user_repository import UserRepository
from services.auth_utils import hash_email

logger = logging.getLogger(f"instagram.{__name__}")

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def verify_token(token: str) -> str | None:
    """토큰 검증 - 유효하면 이메일 반환, 아니면 None"""
    settings = get_settings()
    
    try:
        logger.debug(f"Received token: {token[:50]}...")
        
        # Base64 URL-safe 디코딩 (패딩 추가)
        padding = 4 - len(token) % 4
        if padding != 4:
            token = token + '=' * padding
        
        decoded = base64.urlsafe_b64decode(token).decode()
        logger.debug(f"Decoded token: {decoded}")
        
        parts = decoded.split(":")
        
        if len(parts) != 3:
            logger.debug(f"Invalid parts count: {len(parts)}")
            return None
        
        email, timestamp_str, signature = parts
        logger.debug(f"Email: {email}, Timestamp: {timestamp_str}")
        
        # 서명 검증
        data = f"{email}:{timestamp_str}"
        expected_signature = hmac.new(
            settings.instagram_token_secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.debug("Signature mismatch!")
            return None
        
        # 시간 검증
        timestamp = int(timestamp_str)
        current_time = datetime.datetime.now().timestamp() * 1000
        time_diff = current_time - timestamp
        
        if time_diff > settings.token_expiry_seconds * 1000:
            logger.debug("Token expired!")
            return None
        
        # 허용된 이메일인지 확인
        if email not in settings.allowed_emails:
            logger.debug(f"Email not allowed: {email}")
            return None
        
        logger.debug(f"Token valid for email: {email}")
        return email
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None




@router.get("/auth")
async def auth_callback(request: Request, token: str = None):
    """토큰 기반 인증 콜백 - shwoo_server에서 리다이렉트됨"""
    settings = get_settings()
    
    if not token:
        return RedirectResponse(settings.shwoo_url, status_code=302)
    
    email = verify_token(token)
    
    if not email:
        return templates.TemplateResponse(
            "access_denied.html",
            {"request": request, "shwoo_url": settings.shwoo_url},
            status_code=403
        )
    
    # 인증 성공 - 세션 쿠키 설정 후 대시보드로 리다이렉트
    response = RedirectResponse("/", status_code=302)
    session_token = hash_email(email)
    response.set_cookie(
        key="instagram_auth",
        value=session_token,
        httponly=True,
        max_age=86400 * 7  # 7일
    )
    return response


@router.get("/login")
async def login_redirect(request: Request):
    """로그인 페이지 - shwoo_server로 리다이렉트"""
    settings = get_settings()
    return RedirectResponse(settings.shwoo_url, status_code=302)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, repo: UserRepository = Depends(get_user_repo)):
    """메인 대시보드 HTML"""
    settings = get_settings()
    data = None
    
    if settings.user_id:
        try:
            data = repo.get_analysis(settings.user_id)
        except Exception as e:
            logger.error(f"Dashboard data error: {e}")

    followers_count = len(data.get("followers", [])) if data else 0
    following_count = len(data.get("following", [])) if data else 0
    last_updated = data.get("last_updated", "없음") if data else "없음"

    if isinstance(last_updated, datetime.datetime):
        last_updated = last_updated.strftime('%Y-%m-%d %H:%M:%S')

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "last_updated": last_updated,
        "followers_count": followers_count,
        "following_count": following_count,
        "not_following_back_count": len(data.get("non_followers", [])) if data else 0,
        "im_not_following_count": len(data.get("fans", [])) if data else 0,
        "not_following_back_list": data.get("non_followers", []) if data else [],
        "im_not_following_list": data.get("fans", []) if data else [],
    })
