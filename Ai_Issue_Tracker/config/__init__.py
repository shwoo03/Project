"""Config loader — reads sources.yaml and .env settings."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

_BASE_DIR = Path(__file__).resolve().parent.parent
_CONFIG_CACHE: dict | None = None


def get_base_dir() -> Path:
    return _BASE_DIR


def load_sources() -> dict:
    """Load and cache sources.yaml."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        config_path = _BASE_DIR / "config" / "sources.yaml"
        _CONFIG_CACHE = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return _CONFIG_CACHE


def reload_sources() -> dict:
    """Force reload sources.yaml (hot-reload 지원)."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
    return load_sources()


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_int(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def env_list(key: str, default: list | None = None) -> list[str]:
    """Comma-separated env var → list."""
    val = os.environ.get(key, "")
    if not val:
        return default or []
    return [v.strip() for v in val.split(",") if v.strip()]


# --- Shortcuts ---

def telegram_bot_token() -> str:
    return env("TELEGRAM_BOT_TOKEN")


def telegram_chat_id() -> str:
    return env("TELEGRAM_CHAT_ID")


def telegram_api_id() -> int:
    return env_int("TELEGRAM_API_ID")


def telegram_api_hash() -> str:
    return env("TELEGRAM_API_HASH")


def telegram_phone() -> str:
    return env("TELEGRAM_PHONE")


def x_username() -> str:
    return env("X_USERNAME")


def x_password() -> str:
    return env("X_PASSWORD")


def x_email() -> str:
    return env("X_EMAIL")


def openai_api_key() -> str:
    return env("OPENAI_API_KEY")


def codex_model() -> str:
    return env("CODEX_MODEL", "o4-mini")


def db_path() -> Path:
    p = Path(env("DB_PATH", "data/news.db"))
    if not p.is_absolute():
        p = _BASE_DIR / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def schedule_hours() -> list[int]:
    raw = env_list("SCHEDULE_HOURS", ["7", "12", "20"])
    return [int(h) for h in raw]


def timezone_str() -> str:
    return env("TIMEZONE", "Asia/Seoul")


def max_items_per_digest() -> int:
    return env_int("MAX_ITEMS_PER_DIGEST", 30)


def summary_language() -> str:
    return env("SUMMARY_LANGUAGE", "ko")
