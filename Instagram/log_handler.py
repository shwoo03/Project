import logging
import datetime
import socket
from database import get_mongo_client
from config import get_env_var

class MongoHandler(logging.Handler):
    """
    Custom Logging Handler to save logs to MongoDB
    """
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.mongo_uri = None
        self.username = "system"
        self._client = None
        self._collection = None
        self.hostname = socket.gethostname()
        self._initialized = False

    def _initialize_db(self):
        if self._initialized:
            return True
            
        env_vars = get_env_var()
        if not env_vars or not env_vars.get("MONGO_URI"):
            return False
            
        self.mongo_uri = env_vars["MONGO_URI"]
        self.username = env_vars.get("USERNAME", "system")
        
        try:
            client = get_mongo_client(self.mongo_uri)
            if client:
                self._collection = client.get_database('webhook').get_collection('Instagram_Logs')
                self._initialized = True
                return True
        except Exception:
            pass
        return False

    def emit(self, record):
        try:
            # Ensure DB is connected
            if not self._initialized:
                if not self._initialize_db():
                    return

            # Skip if collection is still not available
            if self._collection is None:
                return

            # Format log message
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

            # Insert into MongoDB
            self._collection.insert_one(log_entry)

        except Exception:
            self.handleError(record)
