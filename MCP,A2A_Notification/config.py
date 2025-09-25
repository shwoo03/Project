# 설정 파일
import os

# Discord 웹훅 URL을 환경변수에서 읽음
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def _repo(key: str, tags_url: str, webhook_env: str | list[str] | None = None) -> dict[str, object]:
    """간결하게 리포지토리 구성을 정의하기 위한 헬퍼."""

    env_candidates: list[str] | None
    if webhook_env is None:
        env_candidates = None
    elif isinstance(webhook_env, str):
        env_candidates = [webhook_env]
    else:
        env_candidates = webhook_env

    return {
        "key": key,
        "tags_url": tags_url,
        "webhook_envs": env_candidates,
    }


# 저장소 설정
REPOS: dict[str, list[dict[str, object]]] = {
    "♥Ollama♥": [
        _repo(
            key="ollama",
            tags_url="https://github.com/ollama/ollama/tags",
            webhook_env="DISCORD_WEBHOOK_URL_OLLAMA",
        ),
        _repo(
            key="llama.cpp",
            tags_url="https://github.com/ggml-org/llama.cpp/tags",
            webhook_env=[
                "DISCORD_WEBHOOK_URL_LLAMA_CPP",
                "DISCORD_WEBHOOK_URL_llama_cpp",
            ],
        ),
    ],
    "Lang가문": [
        _repo(
            key="langflow",
            tags_url="https://github.com/langflow-ai/langflow/tags",
            webhook_env="DISCORD_WEBHOOK_URL_LANGFLOW",
        ),
    ],
    "n8n": [
        _repo(
            key="n8n",
            tags_url="https://github.com/n8n-io/n8n/tags",
            webhook_env="DISCORD_WEBHOOK_URL_N8N",
        ),
    ],
}
