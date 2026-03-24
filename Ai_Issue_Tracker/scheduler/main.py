"""Scheduler — APScheduler 기반 cron 스케줄링.

매일 지정된 시간(기본: 07:00, 12:00, 20:00 KST)에 파이프라인 실행.
Docker 컨테이너 내에서 상시 구동.
"""

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import schedule_hours, timezone_str

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")


def _job():
    """스케줄러에서 호출되는 파이프라인 작업."""
    from scheduler.pipeline import run_pipeline_sync
    try:
        run_pipeline_sync()
    except Exception as e:
        logger.error(f"[Scheduler] Pipeline error: {e}", exc_info=True)


def main():
    hours = schedule_hours()
    tz = timezone_str()

    logger.info(f"AI News Digest Bot starting...")
    logger.info(f"Schedule: {hours} ({tz})")

    scheduler = BlockingScheduler(timezone=tz)

    # 각 시간에 대해 cron job 등록
    for hour in hours:
        trigger = CronTrigger(hour=hour, minute=0, timezone=tz)
        scheduler.add_job(_job, trigger=trigger, id=f"digest_{hour}", replace_existing=True)
        logger.info(f"  → Registered job at {hour:02d}:00 {tz}")

    # 시작 시 즉시 1회 실행 (옵션)
    if "--run-now" in sys.argv:
        logger.info("Running pipeline immediately (--run-now)")
        _job()

    # Graceful shutdown
    def _shutdown(signum, frame):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
