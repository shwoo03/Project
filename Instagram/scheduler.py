"""
스케줄러 모듈 (APScheduler)
대시보드에서 자동 실행 시간 설정
"""
import logging
import asyncio
from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES

logger = logging.getLogger(__name__)

# 글로벌 스케줄러 인스턴스
_scheduler: Optional[AsyncIOScheduler] = None
_job_id = "instagram_tracker_job"


def _scheduler_listener(event):
    """스케줄러 이벤트 리스너"""
    if event.exception:
        logger.error(f"스케줄러 작업 오류: {event.exception}")
    elif event.code == EVENT_JOB_MISSED:
        logger.warning("스케줄러 작업을 놓쳤습니다 (실행 시간 경과)")
    elif event.code == EVENT_JOB_MAX_INSTANCES:
        logger.warning("스케줄러 작업 중복 실행 방지됨 (Max instances reached)")


def get_scheduler() -> AsyncIOScheduler:
    """스케줄러 싱글톤 반환"""
    global _scheduler
    if _scheduler is None:
        # JobDefaults 설정: 중복 실행 방지
        _scheduler = AsyncIOScheduler(job_defaults={
            'coalesce': True,             # 밀린 작업 하나로 병합
            'max_instances': 1,           # 동시 실행 방지
            'misfire_grace_time': 3600    # 1시간 정도 늦어도 실행 허용
        })
        
        # 리스너 등록
        _scheduler.add_listener(
            _scheduler_listener, 
            EVENT_JOB_ERROR | EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES
        )
        
        _scheduler.start()
        logger.info("스케줄러 시작됨 (안정성 강화 모드)")
    return _scheduler


def schedule_daily_run(hour: int, minute: int, task_func: Callable) -> bool:
    """매일 특정 시간에 작업 스케줄"""
    try:
        scheduler = get_scheduler()
        
        # 기존 작업 안전하게 제거
        if scheduler.get_job(_job_id):
            scheduler.remove_job(_job_id)
            logger.info(f"기존 스케줄 제거: {_job_id}")
        
        # 새 작업 추가
        trigger = CronTrigger(hour=hour, minute=minute)
        scheduler.add_job(
            task_func,
            trigger=trigger,
            id=_job_id,
            name="Instagram Daily Tracker",
            replace_existing=True
        )
        logger.info(f"스케줄 설정 완료: 매일 {hour:02d}:{minute:02d}")
        return True
        
    except Exception as e:
        logger.error(f"스케줄 설정 실패: {e}")
        return False


def remove_schedule() -> bool:
    """스케줄 제거"""
    try:
        scheduler = get_scheduler()
        if scheduler.get_job(_job_id):
            scheduler.remove_job(_job_id)
            logger.info("스케줄 제거됨")
            return True
        return False
    except Exception as e:
        logger.error(f"스케줄 제거 오류: {e}")
        return False


def get_schedule_info():
    """현재 스케줄 정보 반환"""
    try:
        scheduler = get_scheduler()
        job = scheduler.get_job(_job_id)
        
        if job:
            next_run = job.next_run_time
            trigger = job.trigger
            
            # CronTrigger에서 시간 추출
            if isinstance(trigger, CronTrigger):
                fields = trigger.fields
                hour = None
                minute = None
                
                # APScheduler 버전에 따라 필드 접근 방식이 다를 수 있음
                # 안전한 방식으로 시간 정보 추출
                for field in fields:
                    if field.name == 'hour':
                        hour = str(field)
                    elif field.name == 'minute':
                        minute = str(field)
                
                return {
                    "enabled": True,
                    "hour": int(hour) if hour and str(hour).isdigit() else 0,
                    "minute": int(minute) if minute and str(minute).isdigit() else 0,
                    "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else None
                }
        
        return {"enabled": False, "hour": 9, "minute": 0, "next_run": None}
        
    except Exception as e:
        logger.error(f"스케줄 정보 조회 오류: {e}")
        return {"enabled": False, "hour": 9, "minute": 0, "next_run": None, "error": str(e)}


def shutdown_scheduler():
    """스케줄러 종료"""
    global _scheduler
    if _scheduler:
        try:
            _scheduler.shutdown(wait=False)
            logger.info("스케줄러 종료됨")
        except Exception as e:
            logger.error(f"스케줄러 종료 중 오류: {e}")
        finally:
            _scheduler = None
