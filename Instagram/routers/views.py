"""
뷰 라우터 - HTML 페이지 렌더링
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import datetime

from config import get_settings
from repositories.user_repository import UserRepository
from utils import get_db_data

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """메인 대시보드 HTML"""
    settings = get_settings()
    data = None
    
    if settings.mongo_uri and settings.user_id:
        try:
            repo = UserRepository(settings.mongo_uri)
            data = repo.get_analysis(settings.user_id)
        except Exception as e:
            print(f"Error: {e}")

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
