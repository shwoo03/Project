from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
import datetime
import logging
from database import get_mongo_client, get_history, get_change_summary, get_logs
from config import get_env_var
from scheduler import schedule_daily_run, remove_schedule, get_schedule_info
from state_manager import state
from tasks import run_tracker_task
# Note: Cyclic import risk if we import run_tracker_task from dashboard.
# We might need to move run_tracker_task to a separate module usually, 
# but for now I will rely on importing it within the function or handling it in dashboard.py 
# Actually, the proper way is to have the task function in a separate module if possible, 
# OR inject it. 
# Let's inspect dashboard.py again. `run_tracker_task` depends on `broadcast_log` which is in `dashboard.py`.
# This indicates a strong coupling. 
# For this refactor, I will keep `run_tracker_task` in `dashboard.py` and pass it to the router or 
# keep the `/api/run` endpoint in `dashboard.py` if it's too entangled.
# BETTER: Move `run_tracker_task` and `AppState` to a `services.py` or new `state.py`.
# Let's try to extract AppState and common logic to `core.py` or `state_manager.py`.

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

@router.post("/run")
async def api_run(background_tasks: BackgroundTasks):
    """팔로워 추적 실행 API"""
    if state.is_running:
        return JSONResponse({"status": "error", "message": "이미 실행 중입니다"}, status_code=409)
    
    background_tasks.add_task(run_tracker_task)
    return {"status": "started", "message": "🚀 팔로워 추적을 시작합니다..."}


@router.get("/schedule")
async def api_get_schedule():
    """현재 스케줄 정보 조회"""
    return get_schedule_info()


@router.post("/schedule")
async def api_set_schedule(hour: int = 9, minute: int = 0):
    """스케줄 설정"""
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return {"error": "잘못된 시간 형식"}
    
    # Cyclic dependency note: run_tracker_task is safe to pass here if imported from tasks
    success = schedule_daily_run(hour, minute, run_tracker_task)
    if success:
        return {"status": "success", "message": f"스케줄 설정: 매일 {hour:02d}:{minute:02d}"}
    return {"status": "error", "message": "스케줄 설정 실패"}


@router.delete("/schedule")
async def api_delete_schedule():
    """스케줄 삭제"""
    success = remove_schedule()
    if success:
        return {"status": "success", "message": "스케줄이 삭제되었습니다"}
    return {"status": "info", "message": "삭제할 스케줄이 없습니다"}

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

@router.get("/status")
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

@router.get("/logs")
async def api_get_logs(limit: int = 100, level: str = None):
    """로그 조회 API"""
    env_vars = get_env_var()
    if not env_vars:
        return {"error": "환경 변수 로드 실패"}
    
    logs = get_logs(env_vars["USERNAME"], env_vars["MONGO_URI"], limit, level)
    return {"logs": logs}

@router.get("/latest")
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

@router.get("/history")
async def api_history(days: int = 30):
    """히스토리 데이터 API"""
    env_vars = get_env_var()
    if not env_vars:
        return {"error": "환경 변수 로드 실패"}
    
    history = get_history(env_vars["USERNAME"], env_vars["MONGO_URI"], days)
    
    formatted = []
    for record in history:
        formatted.append({
            "date": record["date"].strftime("%Y-%m-%d") if record.get("date") else None,
            "followers": record.get("followers_count", 0),
            "following": record.get("following_count", 0)
        })
    
    return {"history": formatted}

@router.get("/changes")
async def api_changes():
    """변동 요약 API"""
    env_vars = get_env_var()
    if not env_vars:
        return {"error": "환경 변수 로드 실패"}
    
    summary = get_change_summary(env_vars["USERNAME"], env_vars["MONGO_URI"])
    return summary or {"has_change": False, "message": "데이터 없음"}

# Schedule endpoints need access to run_tracker_task which is tricky.
# I will keep schedule endpoints in dashboard.py or inject the callback.
