"""
스케줄러 모듈 (APScheduler)
대시보드에서 자동 실행 시간 설정
"""
import logging
from datetime import datetime
from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 글로벌 스케줄러 인스턴스
_scheduler: Optional[AsyncIOScheduler] = None
_job_id = "instagram_tracker_job"


def get_scheduler() -> AsyncIOScheduler:
    """스케줄러 싱글톤 반환"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        _scheduler.start()
        logger.info("스케줄러 시작됨")
    return _scheduler


def schedule_daily_run(hour: int, minute: int, task_func: Callable):
    """매일 특정 시간에 작업 스케줄"""
    scheduler = get_scheduler()
    
    # 기존 작업 제거
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
    logger.info(f"스케줄 설정: 매일 {hour:02d}:{minute:02d}")
    
    return True


def remove_schedule():
    """스케줄 제거"""
    scheduler = get_scheduler()
    if scheduler.get_job(_job_id):
        scheduler.remove_job(_job_id)
        logger.info("스케줄 제거됨")
        return True
    return False


def get_schedule_info():
    """현재 스케줄 정보 반환"""
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
            for field in fields:
                if field.name == 'hour':
                    hour = str(field)
                elif field.name == 'minute':
                    minute = str(field)
            
            return {
                "enabled": True,
                "hour": int(hour) if hour and hour.isdigit() else 0,
                "minute": int(minute) if minute and minute.isdigit() else 0,
                "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else None
            }
    
    return {"enabled": False, "hour": 9, "minute": 0, "next_run": None}


def shutdown_scheduler():
    """스케줄러 종료"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("스케줄러 종료됨")
