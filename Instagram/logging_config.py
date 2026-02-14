"""
로깅 설정 모듈 — dashboard.py에서 분리
"""
import logging
from log_handler import MongoHandler


def setup_logging() -> logging.Logger:
    """앱 전용 로거 ('instagram' 네임스페이스) 초기화"""
    app_logger = logging.getLogger("instagram")
    app_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 파일 핸들러
    file_handler = logging.FileHandler('instagram_tracker.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    app_logger.addHandler(file_handler)

    # 스트림 핸들러
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    app_logger.addHandler(stream_handler)

    # MongoDB 핸들러
    mongo_handler = MongoHandler()
    mongo_handler.setFormatter(formatter)
    app_logger.addHandler(mongo_handler)

    return logging.getLogger(f"instagram.{__name__}")
