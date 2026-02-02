"""
Docker Monitor API 응답 스키마 정의
"""
from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """에러 상세 정보"""
    code: str
    message: str
    details: Optional[dict] = None


class APIResponse(BaseModel, Generic[T]):
    """표준 API 응답 스키마"""
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None

    @classmethod
    def ok(cls, data: T = None) -> "APIResponse[T]":
        """성공 응답 생성"""
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str, details: dict = None) -> "APIResponse":
        """실패 응답 생성"""
        return cls(
            success=False,
            data=None,
            error=ErrorDetail(code=code, message=message, details=details)
        )


# 편의 함수
def success_response(data: Any = None) -> dict:
    """성공 응답을 dict로 반환"""
    return {
        "success": True,
        "data": data,
        "error": None
    }


def error_response(code: str, message: str, details: dict = None) -> dict:
    """에러 응답을 dict로 반환"""
    return {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details
        }
    }
