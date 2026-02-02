import logging
import pymongo
from typing import Optional

logger = logging.getLogger(__name__)

class BaseRepository:
    _client_instance = None

    def __init__(self, mongo_uri: str, db_name: str = 'webhook'):
        self.mongo_uri = mongo_uri
        self.db_name = db_name

    def _get_client(self) -> pymongo.MongoClient:
        """Singleton pattern for MongoDB client"""
        if BaseRepository._client_instance is None:
            try:
                BaseRepository._client_instance = pymongo.MongoClient(self.mongo_uri)
                BaseRepository._client_instance.admin.command('ping')
                logger.info("MongoDB connected successfully (Repository Layer)")
            except pymongo.errors.ConnectionFailure as e:
                logger.error(f"MongoDB connection failed: {e}")
                raise
        return BaseRepository._client_instance

    @property
    def db(self):
        return self._get_client().get_database(self.db_name)

    def close(self):
        """Close connection explicitly if needed"""
        if BaseRepository._client_instance:
            BaseRepository._client_instance.close()
            BaseRepository._client_instance = None
            logger.info("MongoDB connection closed")
