from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import datetime
from database import get_mongo_client
from config import get_env_var

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_db_data():
    """MongoDB에서 최신 데이터 조회"""
    env_vars = get_env_var()
    if not env_vars or not env_vars.get("MONGO_URI"):
        return None
    
    client = get_mongo_client(env_vars["MONGO_URI"])
    if not client:
        return None
    
    db = client.get_database('webhook')
    col_latest = db['Instagram_Latest']
    doc = col_latest.find_one({"_id": env_vars["USERNAME"]})
    return doc

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """메인 대시보드 HTML"""
    data = get_db_data()
    
    followers_count = len(data.get("followers", [])) if data else 0
    following_count = len(data.get("following", [])) if data else 0
    last_updated = data.get("last_updated", "없음") if data else "없음"
    
    if isinstance(last_updated, datetime.datetime):
        last_updated = last_updated.strftime('%Y-%m-%d %H:%M:%S')
    
    # 맞팔 분석
    not_following_back_list = []
    im_not_following_list = []
    
    if data:
        followers_set = {u['username'] for u in data.get("followers", [])}
        following_set = {u['username'] for u in data.get("following", [])}
        not_following_back_list = sorted(list(following_set - followers_set))
        im_not_following_list = sorted(list(followers_set - following_set))
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "last_updated": last_updated,
        "followers_count": followers_count,
        "following_count": following_count,
        "not_following_back_count": len(not_following_back_list),
        "im_not_following_count": len(im_not_following_list),
        "not_following_back_list": not_following_back_list,  # Changed: Passing list directly
        "im_not_following_list": im_not_following_list,      # Changed: Passing list directly
    })
