import sys
import os
import logging
from unittest.mock import MagicMock, patch

# Add current directory to path
sys.path.append(os.getcwd())

def run_verification():
    # Mock settings to avoid .env requirement for syntax check
    with patch('config.get_settings') as mock_settings:
        mock_settings.return_value = MagicMock(
            mongo_uri="mongodb://localhost:27017",
            user_id="test_user",
            user_password="test_password",
            discord_webhook=None
        )
        
        # Mock pymongo.MongoClient to avoid connection timeout
        with patch('pymongo.MongoClient') as mock_mongo_client:
            mock_client_instance = MagicMock()
            mock_mongo_client.return_value = mock_client_instance
            # Mock database and collection getting
            mock_db = MagicMock()
            mock_client_instance.get_database.return_value = mock_db
            mock_client_instance.__getitem__.return_value = mock_db # for client['db']
            
            mock_collection = MagicMock()
            mock_db.get_collection.return_value = mock_collection
            mock_db.__getitem__.return_value = mock_collection # for db['col']

            try:
                print("1. Importing repositories...")
                from repositories.user_repository import UserRepository
                from repositories.log_repository import LogRepository
                print("   - Repositories imported successfully.")

                print("2. Importing utils...")
                from utils import get_db_data
                print("   - utils imported successfully.")

                print("3. Importing routers...")
                from routers.api import router
                print("   - routers imported successfully.")

                print("4. Instantiating repositories...")
                user_repo = UserRepository("mongodb://dummy:27017")
                log_repo = LogRepository("mongodb://dummy:27017")
                print("   - Repositories instantiated successfully.")
                
                print("5. Invoking utils.get_db_data (Mocked)...")
                get_db_data()
                print("   - get_db_data executed successfully.")

                print("SUCCESS: Refactoring verification passed (Static/Import check).")

            except Exception as e:
                print(f"FAILED: Verification failed with error: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    run_verification()
