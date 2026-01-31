"""
인스타그램 팔로워 추적기 - 통합 웹 대시보드
웹에서 모든 기능 제어 가능
"""
import asyncio
import logging
import datetime
import os
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('instagram_tracker.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 모듈 import
from config import get_env_var
from auth_async import login_async
from api_async import get_followers_and_following_async
from database import get_mongo_client, check_last_run, save_and_get_results_to_db, save_history, get_history, get_change_summary
from notification import send_discord_webhook, send_change_notification
from scheduler import get_scheduler, schedule_daily_run, remove_schedule, get_schedule_info, shutdown_scheduler

# 템플릿 설정
templates = Jinja2Templates(directory="templates")


# 상태 관리
class AppState:
    is_running: bool = False
    last_log: str = ""
    progress: int = 0
    websocket_clients: list = []

state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    logger.info("대시보드 서버 시작")
    get_scheduler()  # 스케줄러 초기화
    yield
    shutdown_scheduler()  # 스케줄러 종료
    logger.info("대시보드 서버 종료")


app = FastAPI(
    title="Instagram Follower Tracker",
    description="인스타그램 팔로워 추적 대시보드",
    version="2.0.0",
    lifespan=lifespan
)


# WebSocket 클라이언트에 메시지 브로드캐스트
async def broadcast_log(message: str):
    state.last_log = message
    for client in state.websocket_clients:
        try:
            await client.send_json({"type": "log", "message": message})
        except:
            pass


async def broadcast_progress(progress: int, status: str):
    state.progress = progress
    for client in state.websocket_clients:
        try:
            await client.send_json({"type": "progress", "progress": progress, "status": status})
        except:
            pass


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


async def run_tracker_task():
    """백그라운드에서 팔로워 추적 실행"""
    if state.is_running:
        await broadcast_log("⚠️ 이미 실행 중입니다.")
        return
    
    state.is_running = True
    
    try:
        await broadcast_progress(5, "환경 변수 로드 중...")
        env_vars = get_env_var()
        if not env_vars:
            await broadcast_log("❌ 환경 변수 로드 실패")
            return
        
        await broadcast_progress(10, "오늘 실행 여부 확인 중...")
        # 중복 실행 체크 (웹에서는 건너뛰기 옵션 제공)
        
        await broadcast_progress(20, "인스타그램 로그인 중...")
        await broadcast_log("🔐 Playwright 로그인 시작...")
        cookies_dict = await login_async(env_vars["USERNAME"], env_vars["PASSWORD"])
        
        if not cookies_dict:
            await broadcast_log("❌ 로그인 실패")
            await broadcast_progress(0, "실패")
            return
        
        await broadcast_log("✅ 로그인 성공!")
        await broadcast_progress(40, "팔로워 데이터 수집 중...")
        
        results = await get_followers_and_following_async(cookies_dict)
        
        await broadcast_log(f"📊 팔로워: {len(results['followers'])}명, 팔로잉: {len(results['following'])}명")
        await broadcast_progress(70, "데이터베이스 저장 중...")
        
        diff_result = save_and_get_results_to_db(results, env_vars["USERNAME"], env_vars["MONGO_URI"])
        save_history(results, env_vars["USERNAME"], env_vars["MONGO_URI"])
        await broadcast_log("💾 DB 저장 완료! (히스토리 포함)")
        
        # 변동 사항 알림
        new_followers = diff_result.get("new_followers", [])
        lost_followers = diff_result.get("lost_followers", [])
        
        if new_followers or lost_followers:
            await broadcast_log(f"🔔 변동 감지: +{len(new_followers)} / -{len(lost_followers)}")
        
        await broadcast_progress(85, "Discord 알림 전송 중...")
        
        if env_vars.get("DISCORD_WEBHOOK") and env_vars["DISCORD_WEBHOOK"].lower() not in ["none", ""]:
            # 전체 리포트
            send_discord_webhook(results, env_vars["DISCORD_WEBHOOK"])
            # 변동 알림 (변동이 있을 때만)
            if new_followers or lost_followers:
                send_change_notification(new_followers, lost_followers, env_vars["DISCORD_WEBHOOK"])
            await broadcast_log("📨 Discord 전송 완료!")
        else:
            await broadcast_log("ℹ️ Discord Webhook 미설정")
        
        await broadcast_progress(100, "완료!")
        await broadcast_log("🎉 모든 작업이 완료되었습니다!")
        
    except Exception as e:
        await broadcast_log(f"❌ 오류 발생: {str(e)}")
        await broadcast_progress(0, "오류")
        logger.error(f"Tracker 실행 오류: {e}")
    finally:
        state.is_running = False


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 로그 WebSocket"""
    await websocket.accept()
    state.websocket_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 클라이언트 메시지 처리 (핑 등)
    except WebSocketDisconnect:
        state.websocket_clients.remove(websocket)


def render_user_list(users: list, limit: int = 100) -> str:
    """유저 리스트 HTML 렌더링"""
    if not users:
        return '<div class="empty">모두 맞팔 중! ✅</div>'
    html = '<ul class="user-list">'
    for user in users[:limit]:
        html += f'<li><a href="https://www.instagram.com/{user}/" target="_blank">{user}</a></li>'
    if len(users) > limit:
        html += f'<li class="more">...외 {len(users) - limit}명</li>'
    html += '</ul>'
    return html


@app.get("/", response_class=HTMLResponse)
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
        "not_following_back_html": render_user_list(not_following_back_list),
        "im_not_following_html": render_user_list(im_not_following_list),
    })


@app.post("/api/run")
async def api_run(background_tasks: BackgroundTasks):
    """팔로워 추적 실행 API"""
    if state.is_running:
        return JSONResponse({"status": "error", "message": "이미 실행 중입니다"}, status_code=409)
    
    background_tasks.add_task(run_tracker_task)
    return {"status": "started", "message": "🚀 팔로워 추적을 시작합니다..."}


@app.get("/api/status")
async def api_status():
    """상태 API"""
    data = get_db_data()
    return {
        "is_running": state.is_running,
        "progress": state.progress,
        "last_log": state.last_log,
        "has_data": data is not None,
        "last_updated": data.get("last_updated") if data else None,
        "followers_count": len(data.get("followers", [])) if data else 0,
        "following_count": len(data.get("following", [])) if data else 0
    }


@app.get("/api/latest")
async def api_latest():
    """최신 데이터 API"""
    data = get_db_data()
    if not data:
        return {"error": "데이터가 없습니다"}
    
    followers = data.get("followers", [])
    following = data.get("following", [])
    followers_set = {u['username'] for u in followers}
    following_set = {u['username'] for u in following}
    
    return {
        "last_updated": data.get("last_updated"),
        "followers_count": len(followers),
        "following_count": len(following),
        "not_following_back": sorted(list(following_set - followers_set)),
        "im_not_following": sorted(list(followers_set - following_set))
    }


@app.get("/api/history")
async def api_history(days: int = 30):
    """히스토리 데이터 API"""
    env_vars = get_env_var()
    if not env_vars:
        return {"error": "환경 변수 로드 실패"}
    
    history = get_history(env_vars["USERNAME"], env_vars["MONGO_URI"], days)
    
    # 날짜를 문자열로 변환
    formatted = []
    for record in history:
        formatted.append({
            "date": record["date"].strftime("%Y-%m-%d") if record.get("date") else None,
            "followers": record.get("followers_count", 0),
            "following": record.get("following_count", 0)
        })
    
    return {"history": formatted}


@app.get("/api/changes")
async def api_changes():
    """변동 요약 API"""
    env_vars = get_env_var()
    if not env_vars:
        return {"error": "환경 변수 로드 실패"}
    
    summary = get_change_summary(env_vars["USERNAME"], env_vars["MONGO_URI"])
    return summary or {"has_change": False, "message": "데이터 없음"}


@app.get("/api/schedule")
async def api_get_schedule():
    """현재 스케줄 정보 조회"""
    return get_schedule_info()


@app.post("/api/schedule")
async def api_set_schedule(hour: int = 9, minute: int = 0):
    """스케줄 설정"""
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return {"error": "잘못된 시간 형식"}
    
    success = schedule_daily_run(hour, minute, run_tracker_task)
    if success:
        return {"status": "success", "message": f"스케줄 설정: 매일 {hour:02d}:{minute:02d}"}
    return {"status": "error", "message": "스케줄 설정 실패"}


@app.delete("/api/schedule")
async def api_delete_schedule():
    """스케줄 삭제"""
    success = remove_schedule()
    if success:
        return {"status": "success", "message": "스케줄이 삭제되었습니다"}
    return {"status": "info", "message": "삭제할 스케줄이 없습니다"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
