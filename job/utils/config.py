import os
from pathlib import Path

# Base Directory (parent of utils/)
SCRIPT_DIR = Path(__file__).resolve().parent.parent
ENV_PATHS = [SCRIPT_DIR / ".env"]

def load_env() -> None:
    """Load key=value pairs from known .env files into os.environ."""
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        with env_path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                cleaned_key = key.strip().lstrip("\ufeff")
                os.environ.setdefault(cleaned_key, value.strip())

# Load environment variables immediately
load_env()

# MongoDB Settings
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "webhook")
MONGO_COLLECTION_NAME = "jobs"

# Notion Settings
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_SOURCE_PROP = os.getenv("NOTION_SOURCE_PROP", "선택")

# Notion Property Mapping
NOTION_PROPS = {
    "link": os.getenv("NOTION_LINK_PROP", "Link"),
    "company": os.getenv("NOTION_COMPANY_PROP", "회사"),
    "team": os.getenv("NOTION_TEAM_PROP", "팀"),
    "role": os.getenv("NOTION_ROLE_PROP", "직무"),
    "employment": os.getenv("NOTION_EMPLOYMENT_PROP", "고용형태"),
    "experience": os.getenv("NOTION_EXPERIENCE_PROP", "경력"),
    "location": os.getenv("NOTION_LOCATION_PROP", "근무지"),
    "detail_location": os.getenv("NOTION_DETAIL_LOCATION_PROP", "상세 근무지"),
    "due_date": os.getenv("NOTION_DEADLINE_PROP", "날짜"),
    "tags": os.getenv("NOTION_TAGS_PROP", "태그"),
    "job_id": os.getenv("NOTION_JOB_ID_PROP", "Job ID"),
    "source": NOTION_SOURCE_PROP,
}

# Discord Settings
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Scraper Settings
ENKI_GUIDE_URL = os.getenv("ENKI_GUIDE_URL", "https://enki.career.greetinghr.com/ko/guide")
ENKI_SOURCE_LABEL = os.getenv("ENKI_SOURCE_LABEL", "엔키")
THEORI_API_URL = os.getenv("THEORI_API_URL", "https://theori.io/api/service/position")
THEORI_COMPANY_NAME = os.getenv("THEORI_COMPANY_NAME", "Theori")
THEORI_SOURCE_LABEL = os.getenv("THEORI_SOURCE_LABEL", "티오리")

# General Settings
DEFAULT_TIMEOUT = 30
