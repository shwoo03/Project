import logging
import datetime
from typing import List, Dict, Any, Optional
from .base import BaseRepository

logger = logging.getLogger(__name__)

class LogRepository(BaseRepository):
    def __init__(self, mongo_uri: str):
        super().__init__(mongo_uri)
        self.col_logs = self.db['Instagram_Logs']

    def get_logs(self, username: str, limit: int = 100, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """로그 조회"""
        try:
            query = {"username": username}
            if level:
                query["level"] = level
                
            cursor = self.col_logs.find(query).sort("timestamp", -1).limit(limit)
            
            logs = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                if "timestamp" in doc and isinstance(doc["timestamp"], datetime.datetime):
                    doc["timestamp"] = doc["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                logs.append(doc)
                
            return logs
        except Exception as e:
            logger.error(f"로그 조회 오류: {e}")
            return []
