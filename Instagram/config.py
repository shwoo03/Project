"""
환경 변수 설정 로드
"""
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def get_env_var():
    """
    .env 파일에서 ID, PW, Webhook URL, MONGO_URI 불러오기 
    
    return: dict
        USERNAME: str
        PASSWORD: str 
        DISCORD_WEBHOOK: str
        MONGO_URI: str
        형태로 반환 
    """
    env_vars = {}
    try:
        with open(".env", "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        logger.info(".env 파일이 없습니다. 시스템 환경변수를 사용합니다.")
        load_dotenv()
        env_vars = dict(os.environ)
    except Exception as e:
        logger.warning(f".env 파일 읽기 실패: {e}")
        load_dotenv()
        env_vars = dict(os.environ)

    user_id = env_vars.get("USER_ID")
    user_password = env_vars.get("USER_PASSWORD")
    webhook = env_vars.get("DISCORD_WEBHOOK")
    mongo_uri = env_vars.get("MONGO_URI")
    
    if not user_id or not user_password:
        logger.error(".env 파일에서 USER_ID 또는 USER_PASSWORD를 찾을 수 없습니다.")
        return None 

    return {
        "USERNAME": user_id,
        "PASSWORD": user_password,
        "DISCORD_WEBHOOK": webhook,
        "MONGO_URI": mongo_uri
    }
