"""
Test suite for LLM-based Security Analyzer.

Tests:
1. Business Logic Analysis
2. Authentication Analysis
3. API Security Analysis
4. Intelligent Remediation
"""

import unittest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from core.llm_security_analyzer import (
    LLMSecurityAnalyzer,
    LLMClient,
    BusinessLogicAnalyzer,
    AuthenticationAnalyzer,
    APISecurityAnalyzer,
    IntelligentRemediator,
    CodeContext,
    LLMAnalysisResult,
    AnalysisType,
    VulnerabilityCategory,
    get_llm_security_analyzer,
)


class MockLLMClient:
    """Mock LLM client for testing."""
    
    def __init__(self, response: str = "{}"):
        self.response = response
        self.call_count = 0
    
    def is_available(self) -> bool:
        return True
    
    def complete(self, system_prompt: str, user_prompt: str, **kwargs):
        self.call_count += 1
        return self.response, "test-model", 100


class TestCodeContext(unittest.TestCase):
    """Tests for CodeContext dataclass."""
    
    def test_create_context(self):
        """Test creating a code context."""
        context = CodeContext(
            file_path="test.py",
            code="def test(): pass",
            language="python",
            framework="flask"
        )
        
        self.assertEqual(context.file_path, "test.py")
        self.assertEqual(context.language, "python")
        self.assertEqual(context.framework, "flask")
    
    def test_context_with_related_functions(self):
        """Test context with related functions."""
        context = CodeContext(
            file_path="test.py",
            code="def main(): helper()",
            language="python",
            related_functions={
                "helper": "def helper(): return 42"
            }
        )
        
        self.assertEqual(len(context.related_functions), 1)
        self.assertIn("helper", context.related_functions)


class TestBusinessLogicAnalyzer(unittest.TestCase):
    """Tests for Business Logic Analyzer."""
    
    def test_analyze_idor_vulnerability(self):
        """Test detection of IDOR vulnerability."""
        mock_response = '''```json
{
  "vulnerabilities": [
    {
      "category": "idor",
      "severity": "high",
      "title": "Insecure Direct Object Reference",
      "description": "사용자 ID를 직접 URL에서 받아 권한 검증 없이 사용",
      "location": {"line_start": 5, "line_end": 8},
      "attack_scenario": "다른 사용자의 ID로 요청하여 데이터 접근",
      "confidence": 0.9
    }
  ],
  "risk_assessment": {
    "overall_risk": "high",
    "attack_surface": "API endpoint",
    "exploitability": "Easy"
  }
}
```'''
        
        mock_client = MockLLMClient(mock_response)
        analyzer = BusinessLogicAnalyzer(mock_client)
        
        context = CodeContext(
            file_path="test.py",
            code="""
@app.route('/user/<user_id>')
def get_user(user_id):
    user = User.query.get(user_id)  # No authorization check
    return jsonify(user.to_dict())
""",
            language="python",
            framework="flask"
        )
        
        result = analyzer.analyze(context)
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.vulnerabilities), 1)
        self.assertEqual(result.vulnerabilities[0]["category"], "idor")
        self.assertEqual(result.vulnerabilities[0]["severity"], "high")
    
    def test_analyze_race_condition(self):
        """Test detection of race condition."""
        mock_response = '''```json
{
  "vulnerabilities": [
    {
      "category": "race_condition",
      "severity": "medium",
      "title": "Race Condition in Balance Update",
      "description": "잔액 확인과 차감 사이에 경쟁 조건 발생 가능",
      "location": {"line_start": 3, "line_end": 6},
      "confidence": 0.8
    }
  ],
  "risk_assessment": {"overall_risk": "medium"}
}
```'''
        
        mock_client = MockLLMClient(mock_response)
        analyzer = BusinessLogicAnalyzer(mock_client)
        
        context = CodeContext(
            file_path="test.py",
            code="""
def transfer_money(from_user, to_user, amount):
    if from_user.balance >= amount:  # Check
        from_user.balance -= amount   # Update (race window!)
        to_user.balance += amount
        db.session.commit()
""",
            language="python"
        )
        
        result = analyzer.analyze(context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.vulnerabilities[0]["category"], "race_condition")


class TestAuthenticationAnalyzer(unittest.TestCase):
    """Tests for Authentication Analyzer."""
    
    def test_analyze_jwt_vulnerability(self):
        """Test detection of JWT vulnerability."""
        mock_response = '''```json
{
  "vulnerabilities": [
    {
      "category": "jwt_vulnerability",
      "severity": "critical",
      "title": "JWT Algorithm Confusion",
      "description": "알고리즘 지정 없이 토큰 검증",
      "cwe_id": "CWE-327",
      "location": {"line_start": 3, "line_end": 3},
      "confidence": 0.95
    }
  ],
  "auth_summary": {
    "mechanisms_found": ["jwt"],
    "security_score": 30,
    "critical_issues": 1
  }
}
```'''
        
        mock_client = MockLLMClient(mock_response)
        analyzer = AuthenticationAnalyzer(mock_client)
        
        context = CodeContext(
            file_path="auth.py",
            code="""
def verify_token(token):
    # Vulnerable: no algorithm specified
    payload = jwt.decode(token, SECRET_KEY)
    return payload
""",
            language="python",
            auth_mechanisms=["jwt"]
        )
        
        result = analyzer.analyze(context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.vulnerabilities[0]["category"], "jwt_vulnerability")
        self.assertEqual(result.vulnerabilities[0]["severity"], "critical")
    
    def test_analyze_session_management(self):
        """Test detection of session management issues."""
        mock_response = '''```json
{
  "vulnerabilities": [
    {
      "category": "session_management",
      "severity": "high",
      "title": "Session Fixation",
      "description": "로그인 후 세션 ID 미갱신",
      "location": {"line_start": 4, "line_end": 6},
      "confidence": 0.85
    }
  ],
  "auth_summary": {
    "mechanisms_found": ["session"],
    "security_score": 50
  }
}
```'''
        
        mock_client = MockLLMClient(mock_response)
        analyzer = AuthenticationAnalyzer(mock_client)
        
        context = CodeContext(
            file_path="login.py",
            code="""
def login(username, password):
    if check_password(username, password):
        session['user'] = username  # No session regeneration!
        return redirect('/')
""",
            language="python",
            auth_mechanisms=["session"]
        )
        
        result = analyzer.analyze(context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.vulnerabilities[0]["category"], "session_management")


class TestAPISecurityAnalyzer(unittest.TestCase):
    """Tests for API Security Analyzer."""
    
    def test_analyze_rate_limiting(self):
        """Test detection of missing rate limiting."""
        mock_response = '''```json
{
  "vulnerabilities": [
    {
      "category": "rate_limiting",
      "severity": "medium",
      "title": "Missing Rate Limiting",
      "description": "로그인 엔드포인트에 Rate Limit 미적용",
      "endpoint": "/api/login",
      "method": "POST",
      "location": {"line_start": 1, "line_end": 5},
      "confidence": 0.9
    }
  ],
  "api_summary": {
    "endpoints_analyzed": 1,
    "critical_issues": 0,
    "high_issues": 0
  }
}
```'''
        
        mock_client = MockLLMClient(mock_response)
        analyzer = APISecurityAnalyzer(mock_client)
        
        context = CodeContext(
            file_path="api.py",
            code="""
@app.post('/api/login')
def login():
    # No rate limiting!
    return check_credentials(request.json)
""",
            language="python",
            framework="flask"
        )
        
        result = analyzer.analyze(context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.vulnerabilities[0]["category"], "rate_limiting")
    
    def test_analyze_data_exposure(self):
        """Test detection of data exposure."""
        mock_response = '''```json
{
  "vulnerabilities": [
    {
      "category": "data_exposure",
      "severity": "high",
      "title": "Sensitive Data Exposure",
      "description": "API 응답에 비밀번호 해시 포함",
      "endpoint": "/api/users",
      "location": {"line_start": 3, "line_end": 3},
      "confidence": 0.95
    }
  ]
}
```'''
        
        mock_client = MockLLMClient(mock_response)
        analyzer = APISecurityAnalyzer(mock_client)
        
        context = CodeContext(
            file_path="api.py",
            code="""
@app.get('/api/users')
def get_users():
    return jsonify([u.__dict__ for u in User.query.all()])  # Exposes all fields!
""",
            language="python"
        )
        
        result = analyzer.analyze(context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.vulnerabilities[0]["category"], "data_exposure")


class TestIntelligentRemediator(unittest.TestCase):
    """Tests for Intelligent Remediator."""
    
    def test_generate_fix_for_sqli(self):
        """Test fix generation for SQL injection."""
        mock_response = '''```json
{
  "fix_suggestions": [
    {
      "title": "Use Parameterized Query",
      "description": "파라미터화된 쿼리로 SQL Injection 방지",
      "confidence": "high",
      "original_code": "cursor.execute('SELECT * FROM users WHERE id=' + user_id)",
      "fixed_code": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
      "explanation": "문자열 연결 대신 파라미터 바인딩을 사용하여 SQL Injection 방지",
      "security_pattern": "Parameterized Queries",
      "framework_specific": false,
      "test_cases": [
        {
          "name": "test_sql_injection_prevented",
          "type": "security",
          "code": "assert not is_vulnerable_to_sqli(get_user)"
        }
      ]
    }
  ],
  "additional_recommendations": [
    "ORM 사용 권장",
    "입력 검증 추가"
  ]
}
```'''
        
        mock_client = MockLLMClient(mock_response)
        remediator = IntelligentRemediator(mock_client)
        
        vulnerability = {
            "category": "sql_injection",
            "severity": "critical",
            "title": "SQL Injection",
            "description": "문자열 연결로 인한 SQL Injection"
        }
        
        context = CodeContext(
            file_path="db.py",
            code="""
def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE id=' + user_id)
    return cursor.fetchone()
""",
            language="python"
        )
        
        result = remediator.generate_fix(vulnerability, context)
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.fix_suggestions), 1)
        self.assertEqual(result.fix_suggestions[0]["confidence"], "high")
        self.assertIn("parameterized", result.fix_suggestions[0]["title"].lower())


class TestLLMSecurityAnalyzer(unittest.TestCase):
    """Tests for main LLM Security Analyzer."""
    
    def test_detect_auth_mechanisms(self):
        """Test authentication mechanism detection."""
        analyzer = LLMSecurityAnalyzer()
        
        # JWT detection
        jwt_code = "import jwt\ntoken = jwt.encode(payload, secret)"
        mechanisms = analyzer.detect_auth_mechanisms(jwt_code)
        self.assertIn("jwt", mechanisms)
        
        # Session detection
        session_code = "session['user'] = username"
        mechanisms = analyzer.detect_auth_mechanisms(session_code)
        self.assertIn("session", mechanisms)
        
        # OAuth detection
        oauth_code = "from authlib.integrations.flask_client import OAuth"
        mechanisms = analyzer.detect_auth_mechanisms(oauth_code)
        self.assertIn("oauth", mechanisms)
        
        # API Key detection
        api_key_code = "api_key = request.headers.get('X-API-Key')"
        mechanisms = analyzer.detect_auth_mechanisms(api_key_code)
        self.assertIn("api_key", mechanisms)
    
    def test_detect_framework(self):
        """Test framework detection."""
        analyzer = LLMSecurityAnalyzer()
        
        # Flask
        flask_code = "from flask import Flask\napp = Flask(__name__)"
        self.assertEqual(analyzer.detect_framework(flask_code, "python"), "flask")
        
        # Django
        django_code = "from django.http import HttpResponse"
        self.assertEqual(analyzer.detect_framework(django_code, "python"), "django")
        
        # FastAPI
        fastapi_code = "from fastapi import FastAPI\napp = FastAPI()"
        self.assertEqual(analyzer.detect_framework(fastapi_code, "python"), "fastapi")
        
        # Express
        express_code = "const app = express();"
        self.assertEqual(analyzer.detect_framework(express_code, "javascript"), "express")
        
        # Spring
        spring_code = "@RestController\npublic class UserController {}"
        self.assertEqual(analyzer.detect_framework(spring_code, "java"), "spring")
    
    def test_statistics_tracking(self):
        """Test statistics tracking."""
        analyzer = LLMSecurityAnalyzer()
        
        # Mock a result
        result = LLMAnalysisResult(
            analysis_type=AnalysisType.BUSINESS_LOGIC,
            success=True,
            model_used="test-model",
            vulnerabilities=[{"test": "vuln"}],
            tokens_used=100
        )
        
        # Update stats
        analyzer._update_stats(result)
        
        stats = analyzer.get_statistics()
        self.assertEqual(stats["total_analyses"], 1)
        self.assertEqual(stats["successful_analyses"], 1)
        self.assertEqual(stats["total_vulnerabilities"], 1)
        self.assertEqual(stats["total_tokens"], 100)


class TestLLMAnalysisResult(unittest.TestCase):
    """Tests for LLMAnalysisResult dataclass."""
    
    def test_to_dict(self):
        """Test result serialization."""
        result = LLMAnalysisResult(
            analysis_type=AnalysisType.AUTHENTICATION,
            success=True,
            model_used="llama-3.3-70b",
            vulnerabilities=[
                {"category": "jwt_vulnerability", "severity": "critical"}
            ],
            risk_assessment={"overall_risk": "high"},
            tokens_used=500,
            analysis_time_ms=1234.5
        )
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict["analysis_type"], "authentication")
        self.assertTrue(result_dict["success"])
        self.assertEqual(result_dict["model_used"], "llama-3.3-70b")
        self.assertEqual(len(result_dict["vulnerabilities"]), 1)
        self.assertEqual(result_dict["tokens_used"], 500)


class TestSingletonInstance(unittest.TestCase):
    """Test singleton pattern."""
    
    def test_get_llm_security_analyzer_singleton(self):
        """Test that singleton returns same instance."""
        analyzer1 = get_llm_security_analyzer()
        analyzer2 = get_llm_security_analyzer()
        self.assertIs(analyzer1, analyzer2)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def test_parse_invalid_json_response(self):
        """Test handling of invalid JSON response."""
        mock_client = MockLLMClient("This is not JSON")
        analyzer = BusinessLogicAnalyzer(mock_client)
        
        context = CodeContext(
            file_path="test.py",
            code="def test(): pass",
            language="python"
        )
        
        result = analyzer.analyze(context)
        
        # Should still succeed but with empty vulnerabilities
        self.assertTrue(result.success)
        self.assertEqual(len(result.vulnerabilities), 0)
    
    def test_parse_json_in_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        mock_response = '''Here's my analysis:

```json
{
  "vulnerabilities": [{"test": "value"}]
}
```

That's my analysis.'''
        
        mock_client = MockLLMClient(mock_response)
        analyzer = BusinessLogicAnalyzer(mock_client)
        
        context = CodeContext(
            file_path="test.py",
            code="def test(): pass",
            language="python"
        )
        
        result = analyzer.analyze(context)
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.vulnerabilities), 1)
    
    def test_empty_code(self):
        """Test handling of empty code."""
        mock_client = MockLLMClient('{"vulnerabilities": []}')
        analyzer = BusinessLogicAnalyzer(mock_client)
        
        context = CodeContext(
            file_path="empty.py",
            code="",
            language="python"
        )
        
        result = analyzer.analyze(context)
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.vulnerabilities), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
