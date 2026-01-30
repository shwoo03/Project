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
import requests
import httpx

logger = logging.getLogger(__name__)


# 동기 API 호출용 재시도 데코레이터 (requests)
sync_api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        requests.RequestException,
        requests.Timeout,
        requests.ConnectionError
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)


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


# 일반적인 재시도 (모든 예외)
general_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
