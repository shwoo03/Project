# 설정 파일
import os

# Discord 웹훅 URL을 환경변수에서 읽음
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

if not DISCORD_WEBHOOK_URL:
    raise ValueError("DISCORD_WEBHOOK_URL 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

# 저장소 설정
REPOS = {
    "MCP_SDK": {
        "mcp_python_sdk": "https://github.com/modelcontextprotocol/python-sdk/tags",
        "mcp_typescript_sdk": "https://github.com/modelcontextprotocol/typescript-sdk/tags"
    },
    "A2A_SDK": {
        "a2a_python_sdk": "https://github.com/a2aproject/a2a-python/tags",
        "a2a_js_sdk": "https://github.com/a2aproject/a2a-js/tags",
        "a2a_java_sdk": "https://github.com/a2aproject/a2a-java/tags",
        "a2a_dotnet_sdk": "https://github.com/a2aproject/a2a-dotnet/tags"
    },
    "ADK": {
        "adk_python": "https://github.com/google/adk-python/tags",
        "adk_java": "https://github.com/google/adk-java/tags"
    },
    "FastMCP": {
        "fast_mcp": "https://github.com/jlowin/fastmcp/tags"
    },
    "GenAI": {
        "genai": "https://github.com/googleapis/python-genai/tags"
    }
}
