"""
Custom Logging Handler — MongoDB에 로그 저장
"""
import logging
import datetime
import socket
from repositories.base import BaseRepository
from config import get_settings


class MongoHandler(logging.Handler):
    """
    Custom Logging Handler to save logs to MongoDB
    """
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self._collection = None
        self._initialized = False
        self.hostname = socket.gethostname()
        self.username = "system"

    def _initialize_db(self) -> bool:
        if self._initialized:
            return True

        try:
            settings = get_settings()
            if not settings.mongo_uri:
                return False

            self.username = settings.user_id or "system"

            repo = BaseRepository(settings.mongo_uri)
            client = repo._get_client()
            if client:
                self._collection = client.get_database('webhook').get_collection('Instagram_Logs')
                self._initialized = True
                return True
        except Exception:
            pass
        return False

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not self._initialized:
                if not self._initialize_db():
                    return

            if self._collection is None:
                return

            log_entry = {
                "timestamp": datetime.datetime.now(),
                "level": record.levelname,
                "message": self.format(record),
                "logger": record.name,
                "module": record.module,
                "line": record.lineno,
                "username": self.username,
                "hostname": self.hostname
            }

            self._collection.insert_one(log_entry)

        except Exception:
            self.handleError(record)
