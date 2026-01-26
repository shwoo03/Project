
from core.ai_analyzer import AIAnalyzer
from dotenv import load_dotenv
import os

# Manually load .env from root
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

analyzer = AIAnalyzer()
print(f"API Key present: {bool(analyzer.api_key)}")
if analyzer.api_key:
    print(f"API Key prefix: {analyzer.api_key[:5]}...")

code = "def check_xss(param): return eval(param)"
print("Testing analysis...")
result = analyzer.analyze_code(code, "test context")
print(result)
