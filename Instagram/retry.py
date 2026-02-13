"""
재시도 로직 (tenacity)
"""
import logging
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log
)
import httpx

logger = logging.getLogger(f"instagram.{__name__}")


# 비동기 API 호출용 재시도 데코레이터 (httpx)
async_api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        httpx.RequestError,
        httpx.TimeoutException,
        httpx.ConnectError
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
