"""
API 라우터 - RESTful API 엔드포인트
"""
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, StreamingResponse
import datetime
import pymongo
import logging

from config import get_settings
from scheduler import schedule_daily_run, remove_schedule, get_schedule_info
from state_manager import state
from services.task_service import TaskService
from services.export_service import ExportService
from schemas import APIResponse
from dependencies import get_user_repo, get_log_repo
from repositories.user_repository import UserRepository
from repositories.log_repository import LogRepository

router = APIRouter(prefix="/api")
logger = logging.getLogger(f"instagram.{__name__}")


@router.post("/run")
async def api_run(background_tasks: BackgroundTasks):
    """팔로워 추적 실행 API"""
    if state.is_running:
        return JSONResponse(
            APIResponse.fail("이미 실행 중입니다").model_dump(),
            status_code=409
        )

    background_tasks.add_task(TaskService.run_tracker)
    return APIResponse.ok("🚀 팔로워 추적을 시작합니다...")


@router.post("/cancel")
async def api_cancel():
    """실행 중인 작업 취소 API"""
    if not state.is_running:
        return APIResponse.fail("실행 중인 작업이 없습니다")

    state.request_cancel()
    return APIResponse.ok("🛑 작업 취소를 요청했습니다")


@router.get("/health")
async def api_health():
    """Health Check API — MongoDB, 스케줄러, 앱 상태 확인"""
    checks = {}
    overall = "healthy"

    # MongoDB 연결 확인
    try:
        settings = get_settings()
        client = pymongo.MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
        client.admin.command('ping')
        checks["mongodb"] = {"status": "ok"}
        client.close()
    except Exception as e:
        checks["mongodb"] = {"status": "error", "detail": str(e)}
        overall = "unhealthy"

    # 스케줄러 상태
    schedule_info = get_schedule_info()
    checks["scheduler"] = {
        "status": "ok",
        "enabled": schedule_info.get("enabled", False),
        "next_run": schedule_info.get("next_run")
    }

    # 앱 상태
    checks["tracker"] = {
        "status": "running" if state.is_running else "idle",
        "progress": state.progress
    }

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(
        content={
            "status": overall,
            "checks": checks
        },
        status_code=status_code
    )


@router.get("/schedule")
async def api_get_schedule():
    """현재 스케줄 정보 조회"""
    info = get_schedule_info()
    return APIResponse.ok("스케줄 정보 조회 성공", data=info)


@router.post("/schedule")
async def api_set_schedule(hour: int = 9, minute: int = 0):
    """스케줄 설정"""
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return APIResponse.fail("잘못된 시간 형식", error="hour: 0-23, minute: 0-59")

    success = schedule_daily_run(hour, minute, TaskService.run_tracker)
    if success:
        return APIResponse.ok(f"스케줄 설정: 매일 {hour:02d}:{minute:02d}")
    return APIResponse.fail("스케줄 설정 실패")


@router.delete("/schedule")
async def api_delete_schedule():
    """스케줄 삭제"""
    success = remove_schedule()
    if success:
        return APIResponse.ok("스케줄이 삭제되었습니다")
    return APIResponse.ok("삭제할 스케줄이 없습니다")


@router.get("/status")
async def api_status(repo: UserRepository = Depends(get_user_repo)):
    """상태 API"""
    settings = get_settings()
    data = None
    if settings.user_id:
        try:
            data = repo.get_latest_data(settings.user_id)
        except Exception:
            pass

    return APIResponse.ok("상태 조회 성공", data={
        "is_running": state.is_running,
        "progress": state.progress,
        "last_log": state.last_log,
        "has_data": data is not None,
        "last_updated": data.get("last_updated") if data else None,
        "followers_count": len(data.get("followers", [])) if data else 0,
        "following_count": len(data.get("following", [])) if data else 0
    })


@router.get("/logs")
async def api_get_logs(
    limit: int = 100,
    level: str = None,
    repo: LogRepository = Depends(get_log_repo)
):
    """로그 조회 API"""
    settings = get_settings()
    if not settings.user_id:
        return APIResponse.fail("환경 변수 로드 실패")

    logs = repo.get_logs(settings.user_id, limit, level)
    return APIResponse.ok("로그 조회 성공", data={"logs": logs})


@router.get("/export/{export_type}")
async def api_export_csv(
    export_type: str,
    repo: UserRepository = Depends(get_user_repo)
):
    """데이터 CSV 내보내기 (followers, following, non_followers, fans)"""
    try:
        settings = get_settings()
        if not settings.user_id:
            return APIResponse.fail("환경 변수 설정 오류")

        data = repo.get_analysis(settings.user_id)
        
        target_list = data.get(export_type, [])
        
        stream = ExportService.create_csv(target_list)
        
        filename = f"instagram_{export_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            stream, 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"CSV 내보내기 실패: {e}")
        return APIResponse.fail(f"내보내기 실패: {str(e)}")


@router.get("/latest")
async def api_latest(repo: UserRepository = Depends(get_user_repo)):
    """최신 데이터 API"""
    settings = get_settings()
    if not settings.user_id:
        return APIResponse.fail("데이터가 없습니다")

    data = repo.get_latest_data(settings.user_id)
    if not data:
        return APIResponse.fail("데이터가 없습니다")

    followers = data.get("followers", [])
    following = data.get("following", [])
    followers_set = {u['username'] for u in followers}
    following_set = {u['username'] for u in following}

    return APIResponse.ok("최신 데이터 조회 성공", data={
        "last_updated": data.get("last_updated"),
        "followers_count": len(followers),
        "following_count": len(following),
        "not_following_back": sorted(list(following_set - followers_set)),
        "im_not_following": sorted(list(followers_set - following_set))
    })


@router.get("/history")
async def api_history(
    days: int = 30,
    repo: UserRepository = Depends(get_user_repo)
):
    """히스토리 데이터 API"""
    settings = get_settings()
    if not settings.user_id:
        return APIResponse.fail("환경 변수 로드 실패")

    history = repo.get_history(settings.user_id, days)

    formatted = []
    for record in history:
        formatted.append({
            "date": record["date"].strftime("%Y-%m-%d") if record.get("date") else None,
            "followers": record.get("followers_count", 0),
            "following": record.get("following_count", 0)
        })

    return APIResponse.ok("히스토리 조회 성공", data={"history": formatted})


@router.get("/changes")
async def api_changes(repo: UserRepository = Depends(get_user_repo)):
    """변동 요약 API"""
    settings = get_settings()
    if not settings.user_id:
        return APIResponse.fail("환경 변수 로드 실패")

    summary = repo.get_change_summary(settings.user_id)
    
    if summary:
        return APIResponse.ok("변동 요약 조회 성공", data=summary)
    return APIResponse.ok("변동 데이터 없음", data={"has_change": False})
