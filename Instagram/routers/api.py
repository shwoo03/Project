"""
API 라우터 - RESTful API 엔드포인트
"""
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
import datetime
import logging

from config import get_settings
from scheduler import schedule_daily_run, remove_schedule, get_schedule_info
from state_manager import state
from tasks import run_tracker_task
from schemas import APIResponse
from utils import get_db_data
from repositories.user_repository import UserRepository
from repositories.log_repository import LogRepository

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.post("/run")
async def api_run(background_tasks: BackgroundTasks):
    """팔로워 추적 실행 API"""
    if state.is_running:
        return JSONResponse(
            APIResponse.fail("이미 실행 중입니다").model_dump(),
            status_code=409
        )

    background_tasks.add_task(run_tracker_task)
    return APIResponse.ok("🚀 팔로워 추적을 시작합니다...")


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

    success = schedule_daily_run(hour, minute, run_tracker_task)
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
async def api_status():
    """상태 API"""
    data = get_db_data()
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
async def api_get_logs(limit: int = 100, level: str = None):
    """로그 조회 API"""
    settings = get_settings()
    if not settings.mongo_uri or not settings.user_id:
        return APIResponse.fail("환경 변수 로드 실패")

    repo = LogRepository(settings.mongo_uri)
    logs = repo.get_logs(settings.user_id, limit, level)
    return APIResponse.ok("로그 조회 성공", data={"logs": logs})


@router.get("/export/{export_type}")
async def api_export_csv(export_type: str):
    """데이터 CSV 내보내기 (followers, following, non_followers, fans)"""
    try:
        import pandas as pd
        from io import BytesIO
        from starlette.responses import StreamingResponse
        
        settings = get_settings()
        if not settings.mongo_uri or not settings.user_id:
            return APIResponse.fail("환경 변수 설정 오류")

        repo = UserRepository(settings.mongo_uri)
        data = repo.get_analysis(settings.user_id)
        
        target_list = data.get(export_type, [])
        if not target_list:
             # 빈 데이터라도 컬럼이 있는 CSV를 주기 위해 빈 리스트 처리
             pass
        
        # 데이터가 단순 문자열(username) 리스트인지, 객체(dict) 리스트인지 확인
        if target_list and isinstance(target_list[0], str):
            # 문자열 리스트인 경우 (non_followers, fans 등)
            df = pd.DataFrame(target_list, columns=["username"])
        else:
            # 객체 리스트인 경우 (followers, following)
            df = pd.DataFrame(target_list)
            # 필요한 컬럼만 선택 (예: id, username, full_name) - 데이터에 따라 다름
            # 일단 모든 컬럼 다 내보내기
        
        # CSV 변환
        stream = BytesIO()
        df.to_csv(stream, index=False, encoding='utf-8-sig')
        stream.seek(0)
        
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
async def api_latest():
    """최신 데이터 API"""
    data = get_db_data()
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
async def api_history(days: int = 30):
    """히스토리 데이터 API"""
    settings = get_settings()
    if not settings.mongo_uri or not settings.user_id:
        return APIResponse.fail("환경 변수 로드 실패")

    repo = UserRepository(settings.mongo_uri)
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
async def api_changes():
    """변동 요약 API"""
    settings = get_settings()
    if not settings.mongo_uri or not settings.user_id:
        return APIResponse.fail("환경 변수 로드 실패")

    repo = UserRepository(settings.mongo_uri)
    summary = repo.get_change_summary(settings.user_id)
    
    if summary:
        return APIResponse.ok("변동 요약 조회 성공", data=summary)
    return APIResponse.ok("변동 데이터 없음", data={"has_change": False})
