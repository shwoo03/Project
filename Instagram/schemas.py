"""
API 응답 및 데이터 스키마 정의
"""
from pydantic import BaseModel
from typing import Any, Optional, List


class APIResponse(BaseModel):
    """표준 API 응답 모델"""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, message: str = "성공", data: Any = None) -> "APIResponse":
        """성공 응답 생성"""
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str = "실패", error: Optional[str] = None) -> "APIResponse":
        """실패 응답 생성"""
        return cls(success=False, message=message, error=error)


class ScheduleInfo(BaseModel):
    """스케줄 정보"""
    enabled: bool
    hour: int
    minute: int
    next_run: Optional[str] = None


class StatusResponse(BaseModel):
    """상태 응답"""
    is_running: bool
    progress: int
    last_log: str
    has_data: bool
    last_updated: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0


class HistoryRecord(BaseModel):
    """히스토리 레코드"""
    date: Optional[str] = None
    followers: int = 0
    following: int = 0


class LatestDataResponse(BaseModel):
    """최신 데이터 응답"""
    last_updated: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    not_following_back: List[str] = []
    im_not_following: List[str] = []
