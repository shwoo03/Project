"""
LLM-based Security Analyzer for Advanced Vulnerability Detection.

This module extends AI analysis capabilities for:
1. Business Logic Vulnerabilities (Broken Access Control, IDOR, Race Conditions)
2. Authentication & Authorization Issues (JWT, Session, OAuth)
3. API Security (GraphQL, REST, Rate Limiting)
4. Intelligent Remediation with context-aware fix suggestions

Based on ROADMAP2.md Phase 4.2
"""

import os
import json
import re
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import groq
from dotenv import load_dotenv


# Load environment
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))


class AnalysisType(Enum):
    """Types of LLM-based security analysis."""
    BUSINESS_LOGIC = "business_logic"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    API_SECURITY = "api_security"
    REMEDIATION = "remediation"
    GENERAL = "general"


class VulnerabilityCategory(Enum):
    """Categories of vulnerabilities detected by LLM."""
    # Business Logic
    BROKEN_ACCESS_CONTROL = "broken_access_control"
    IDOR = "insecure_direct_object_reference"
    RACE_CONDITION = "race_condition"
    STATE_MANAGEMENT = "state_management"
    BUSINESS_LOGIC_BYPASS = "business_logic_bypass"
    
    # Authentication
    JWT_VULNERABILITY = "jwt_vulnerability"
    SESSION_MANAGEMENT = "session_management"
    OAUTH_MISCONFIGURATION = "oauth_misconfiguration"
    PASSWORD_POLICY = "password_policy"
    CREDENTIAL_EXPOSURE = "credential_exposure"
    
    # Authorization
    PRIVILEGE_ESCALATION = "privilege_escalation"
    MISSING_AUTHORIZATION = "missing_authorization"
    RBAC_BYPASS = "rbac_bypass"
    
    # API Security
    GRAPHQL_COMPLEXITY = "graphql_complexity"
    RATE_LIMITING = "rate_limiting"
    API_KEY_EXPOSURE = "api_key_exposure"
    DATA_EXPOSURE = "data_exposure"
    MASS_ASSIGNMENT = "mass_assignment"
    
    # General
    GENERAL_SECURITY = "general_security"


@dataclass
class LLMAnalysisResult:
    """Result from LLM security analysis."""
    analysis_type: AnalysisType
    success: bool
    model_used: str
    
    # Findings
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)
    
    # For remediation
    fix_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Raw response
    raw_analysis: str = ""
    error: Optional[str] = None
    
    # Metadata
    tokens_used: int = 0
    analysis_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_type": self.analysis_type.value,
            "success": self.success,
            "model_used": self.model_used,
            "vulnerabilities": self.vulnerabilities,
            "risk_assessment": self.risk_assessment,
            "fix_suggestions": self.fix_suggestions,
            "raw_analysis": self.raw_analysis,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "analysis_time_ms": self.analysis_time_ms,
        }


@dataclass
class CodeContext:
    """Context information for LLM analysis."""
    file_path: str
    code: str
    language: str = "unknown"
    framework: Optional[str] = None
    
    # Related code
    imports: List[str] = field(default_factory=list)
    related_functions: Dict[str, str] = field(default_factory=dict)
    call_graph: Optional[Dict] = None
    
    # Architecture info
    architecture: Optional[str] = None
    threat_model: Optional[str] = None
    
    # Authentication context
    auth_mechanisms: List[str] = field(default_factory=list)
    api_endpoints: List[Dict] = field(default_factory=list)


class LLMClient:
    """Wrapper for LLM API calls with fallback support."""
    
    MODELS = [
        "openai/gpt-oss-120b",        # 1. 우선 사용
        "llama-3.3-70b-versatile",    # 2. Fallback
        "llama-3.1-8b-instant",       # 3. 빠른 fallback
        "qwen/qwen3-32b",             # 4. 마지막 대안
    ]
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.client = groq.Groq(api_key=self.api_key) if self.api_key else None
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def complete(
        self, 
        system_prompt: str, 
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 4096
    ) -> Tuple[str, str, int]:
        """
        Call LLM with fallback through models.
        
        Returns:
            Tuple of (response_text, model_used, tokens_used)
        """
        if not self.client:
            raise RuntimeError("GROQ_API_KEY not configured")
        
        for model in self.MODELS:
            try:
                print(f"[LLM] Attempting with model: {model}")
                response = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                content = response.choices[0].message.content
                tokens = response.usage.total_tokens if response.usage else 0
                
                # 빈 응답 체크
                if not content or not content.strip():
                    print(f"[LLM] Empty response from {model}, trying next model")
                    continue
                
                print(f"[LLM] Success with {model}, {len(content)} chars, {tokens} tokens")
                return content, model, tokens
                
            except groq.RateLimitError as e:
                print(f"[LLM] Rate limit for {model}: {str(e)[:100]}")
                continue
            except groq.NotFoundError as e:
                print(f"[LLM] Model {model} not found: {str(e)[:100]}")
                continue
            except Exception as e:
                print(f"[LLM] Error with {model}: {e}")
                continue
        
        print(f"[LLM] ❌ All models failed")
        raise RuntimeError("All LLM models failed")


class BusinessLogicAnalyzer:
    """
    Analyzes code for business logic vulnerabilities.
    
    Detects:
    - Broken Access Control
    - IDOR (Insecure Direct Object References)
    - Race Conditions
    - State Management Issues
    """
    
    SYSTEM_PROMPT = """당신은 비즈니스 로직 보안 분석 전문가입니다.
주어진 코드에서 비즈니스 로직 취약점을 분석하세요.

**분석 대상 취약점:**
1. **Broken Access Control (BAC)**: 권한 검증 누락, 수평/수직 권한 상승
2. **IDOR (Insecure Direct Object Reference)**: 직접 객체 참조로 인한 데이터 접근
3. **Race Condition**: 동시성 처리 미흡으로 인한 취약점
4. **State Management**: 상태 관리 결함 (세션, 토큰, 캐시 등)
5. **Business Logic Bypass**: 비즈니스 규칙 우회 가능성

**응답 형식 (JSON):**
```json
{
  "vulnerabilities": [
    {
      "category": "broken_access_control|idor|race_condition|state_management|business_logic_bypass",
      "severity": "critical|high|medium|low",
      "title": "취약점 제목",
      "description": "상세 설명",
      "location": {"line_start": 10, "line_end": 20, "code_snippet": "..."},
      "attack_scenario": "공격 시나리오",
      "impact": "영향도",
      "confidence": 0.0-1.0
    }
  ],
  "risk_assessment": {
    "overall_risk": "critical|high|medium|low",
    "attack_surface": "설명",
    "exploitability": "설명"
  },
  "summary": "전체 요약"
}
```

**주의사항:**
- JSON 형식으로만 응답
- 실제 취약점만 보고 (추측 금지)
- 코드 라인 번호 명시
- 한국어로 설명"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def analyze(self, context: CodeContext) -> LLMAnalysisResult:
        """Analyze code for business logic vulnerabilities."""
        import time
        start_time = time.time()
        
        user_prompt = self._build_prompt(context)
        
        try:
            response, model, tokens = self.llm.complete(
                self.SYSTEM_PROMPT,
                user_prompt,
                temperature=0.1,
                max_tokens=4096
            )
            
            parsed = self._parse_response(response)
            
            return LLMAnalysisResult(
                analysis_type=AnalysisType.BUSINESS_LOGIC,
                success=True,
                model_used=model,
                vulnerabilities=parsed.get("vulnerabilities", []),
                risk_assessment=parsed.get("risk_assessment", {}),
                raw_analysis=response,
                tokens_used=tokens,
                analysis_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return LLMAnalysisResult(
                analysis_type=AnalysisType.BUSINESS_LOGIC,
                success=False,
                model_used="",
                error=str(e),
                analysis_time_ms=(time.time() - start_time) * 1000
            )
    
    def _build_prompt(self, context: CodeContext) -> str:
        prompt = f"""**파일**: {context.file_path}
**언어**: {context.language}
**프레임워크**: {context.framework or 'Unknown'}

**분석 대상 코드:**
```{context.language}
{context.code}
```
"""
        
        if context.related_functions:
            prompt += "\n**관련 함수:**\n"
            for name, code in context.related_functions.items():
                prompt += f"```{context.language}\n# {name}\n{code}\n```\n"
        
        if context.api_endpoints:
            prompt += f"\n**API 엔드포인트:**\n{json.dumps(context.api_endpoints, indent=2)}\n"
        
        if context.auth_mechanisms:
            prompt += f"\n**인증 메커니즘:** {', '.join(context.auth_mechanisms)}\n"
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response."""
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"vulnerabilities": [], "raw_text": response}


class AuthenticationAnalyzer:
    """
    Analyzes code for authentication vulnerabilities.
    
    Detects:
    - JWT Token Issues
    - Session Management Flaws
    - OAuth/SAML Misconfigurations
    - Password Policy Violations
    - Credential Exposure
    """
    
    SYSTEM_PROMPT = """당신은 인증(Authentication) 보안 분석 전문가입니다.
주어진 코드에서 인증 관련 취약점을 분석하세요.

**분석 대상 취약점:**
1. **JWT 취약점**:
   - 알고리즘 혼동 (RS256→HS256)
   - 서명 미검증
   - 민감 정보 노출 (payload)
   - 만료 시간 미설정
   - None 알고리즘 허용

2. **세션 관리 결함**:
   - 세션 고정(Session Fixation)
   - 세션 만료 미처리
   - 안전하지 않은 세션 저장
   - 세션 ID 예측 가능

3. **OAuth/SAML 설정 오류**:
   - Redirect URI 검증 미흡
   - State 파라미터 미사용
   - Token 유출
   - PKCE 미사용

4. **비밀번호 정책 위반**:
   - 약한 해시 알고리즘 (MD5, SHA1)
   - Salt 미사용
   - 평문 저장
   - 무차별 대입 방어 없음

5. **자격 증명 노출**:
   - 하드코딩된 비밀번호
   - API 키 노출
   - 로그에 민감 정보

**응답 형식 (JSON):**
```json
{
  "vulnerabilities": [
    {
      "category": "jwt_vulnerability|session_management|oauth_misconfiguration|password_policy|credential_exposure",
      "severity": "critical|high|medium|low",
      "title": "취약점 제목",
      "description": "상세 설명",
      "location": {"line_start": 10, "line_end": 20, "code_snippet": "..."},
      "cwe_id": "CWE-XXX",
      "attack_vector": "공격 방법",
      "confidence": 0.0-1.0
    }
  ],
  "auth_summary": {
    "mechanisms_found": ["jwt", "session", "oauth"],
    "security_score": 0-100,
    "critical_issues": 0
  }
}
```

JSON 형식으로만 응답하세요. 한국어로 설명하세요."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def analyze(self, context: CodeContext) -> LLMAnalysisResult:
        """Analyze code for authentication vulnerabilities."""
        import time
        start_time = time.time()
        
        user_prompt = self._build_prompt(context)
        
        try:
            response, model, tokens = self.llm.complete(
                self.SYSTEM_PROMPT,
                user_prompt,
                temperature=0.1,
                max_tokens=4096
            )
            
            parsed = self._parse_response(response)
            
            return LLMAnalysisResult(
                analysis_type=AnalysisType.AUTHENTICATION,
                success=True,
                model_used=model,
                vulnerabilities=parsed.get("vulnerabilities", []),
                risk_assessment=parsed.get("auth_summary", {}),
                raw_analysis=response,
                tokens_used=tokens,
                analysis_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return LLMAnalysisResult(
                analysis_type=AnalysisType.AUTHENTICATION,
                success=False,
                model_used="",
                error=str(e),
                analysis_time_ms=(time.time() - start_time) * 1000
            )
    
    def _build_prompt(self, context: CodeContext) -> str:
        prompt = f"""**파일**: {context.file_path}
**언어**: {context.language}
**프레임워크**: {context.framework or 'Unknown'}

**분석 대상 코드:**
```{context.language}
{context.code}
```
"""
        if context.auth_mechanisms:
            prompt += f"\n**감지된 인증 메커니즘:** {', '.join(context.auth_mechanisms)}\n"
        
        if context.related_functions:
            prompt += "\n**관련 함수:**\n"
            for name, code in list(context.related_functions.items())[:5]:
                prompt += f"```{context.language}\n# {name}\n{code[:500]}\n```\n"
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"vulnerabilities": [], "raw_text": response}


class APISecurityAnalyzer:
    """
    Analyzes code for API security vulnerabilities.
    
    Detects:
    - GraphQL Query Complexity
    - REST API Rate Limiting Issues
    - API Key Exposure
    - Data Exposure in Responses
    - Mass Assignment
    """
    
    SYSTEM_PROMPT = """당신은 API 보안 분석 전문가입니다.
주어진 코드에서 API 보안 취약점을 분석하세요.

**분석 대상 취약점:**
1. **GraphQL 보안**:
   - 쿼리 복잡도 제한 없음
   - Introspection 활성화
   - Batching 공격
   - Depth 제한 없음

2. **Rate Limiting**:
   - Rate Limit 미구현
   - 우회 가능한 Rate Limit
   - 비용 기반 Rate Limit 없음

3. **API 키 노출**:
   - 클라이언트 코드에 API 키
   - URL 쿼리 스트링에 키
   - 로그에 API 키

4. **데이터 노출**:
   - 과도한 데이터 반환
   - 민감 정보 노출
   - 에러 메시지에 정보 누출
   - 디버그 정보 노출

5. **Mass Assignment**:
   - 검증 없는 객체 바인딩
   - 숨겨진 필드 수정 가능
   - 권한 필드 조작 가능

**응답 형식 (JSON):**
```json
{
  "vulnerabilities": [
    {
      "category": "graphql_complexity|rate_limiting|api_key_exposure|data_exposure|mass_assignment",
      "severity": "critical|high|medium|low",
      "title": "취약점 제목",
      "description": "상세 설명",
      "endpoint": "/api/path",
      "method": "GET|POST|PUT|DELETE",
      "location": {"line_start": 10, "line_end": 20, "code_snippet": "..."},
      "remediation": "수정 방법",
      "confidence": 0.0-1.0
    }
  ],
  "api_summary": {
    "endpoints_analyzed": 5,
    "critical_issues": 0,
    "high_issues": 1
  }
}
```

JSON 형식으로만 응답하세요. 한국어로 설명하세요."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def analyze(self, context: CodeContext) -> LLMAnalysisResult:
        """Analyze code for API security vulnerabilities."""
        import time
        start_time = time.time()
        
        user_prompt = self._build_prompt(context)
        
        try:
            response, model, tokens = self.llm.complete(
                self.SYSTEM_PROMPT,
                user_prompt,
                temperature=0.1,
                max_tokens=4096
            )
            
            parsed = self._parse_response(response)
            
            return LLMAnalysisResult(
                analysis_type=AnalysisType.API_SECURITY,
                success=True,
                model_used=model,
                vulnerabilities=parsed.get("vulnerabilities", []),
                risk_assessment=parsed.get("api_summary", {}),
                raw_analysis=response,
                tokens_used=tokens,
                analysis_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return LLMAnalysisResult(
                analysis_type=AnalysisType.API_SECURITY,
                success=False,
                model_used="",
                error=str(e),
                analysis_time_ms=(time.time() - start_time) * 1000
            )
    
    def _build_prompt(self, context: CodeContext) -> str:
        prompt = f"""**파일**: {context.file_path}
**언어**: {context.language}
**프레임워크**: {context.framework or 'Unknown'}

**분석 대상 코드:**
```{context.language}
{context.code}
```
"""
        if context.api_endpoints:
            prompt += f"\n**API 엔드포인트:**\n```json\n{json.dumps(context.api_endpoints, indent=2)}\n```\n"
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"vulnerabilities": [], "raw_text": response}


class IntelligentRemediator:
    """
    Provides intelligent remediation suggestions using LLM.
    
    Features:
    - Context-aware fix suggestions
    - Framework-specific code examples
    - Security pattern recommendations
    - Test case generation
    """
    
    SYSTEM_PROMPT = """당신은 보안 취약점 수정 전문가입니다.
주어진 취약점에 대해 안전한 수정 코드를 제안하세요.

**수정 제안 원칙:**
1. **프레임워크 고려**: 사용 중인 프레임워크의 보안 기능 활용
2. **최소 변경**: 기존 로직을 최대한 유지하며 보안만 강화
3. **베스트 프랙티스**: 업계 표준 보안 패턴 적용
4. **테스트 가능**: 수정 후 검증 가능한 테스트 케이스 제공

**응답 형식 (JSON):**
```json
{
  "fix_suggestions": [
    {
      "title": "수정 제목",
      "description": "수정 내용 설명",
      "confidence": "high|medium|low",
      "original_code": "취약한 원본 코드",
      "fixed_code": "수정된 안전한 코드",
      "explanation": "왜 이렇게 수정하는지 설명",
      "security_pattern": "적용된 보안 패턴 이름",
      "framework_specific": true|false,
      "breaking_changes": false,
      "test_cases": [
        {
          "name": "테스트 이름",
          "type": "unit|integration|security",
          "code": "테스트 코드"
        }
      ]
    }
  ],
  "additional_recommendations": [
    "추가 권장 사항 1",
    "추가 권장 사항 2"
  ]
}
```

JSON 형식으로만 응답하세요. 한국어로 설명하되, 코드는 영어로 작성하세요."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def generate_fix(
        self, 
        vulnerability: Dict[str, Any],
        context: CodeContext
    ) -> LLMAnalysisResult:
        """Generate fix suggestions for a vulnerability."""
        import time
        start_time = time.time()
        
        user_prompt = self._build_prompt(vulnerability, context)
        
        try:
            response, model, tokens = self.llm.complete(
                self.SYSTEM_PROMPT,
                user_prompt,
                temperature=0.2,  # Slightly higher for creative fixes
                max_tokens=4096
            )
            
            parsed = self._parse_response(response)
            
            return LLMAnalysisResult(
                analysis_type=AnalysisType.REMEDIATION,
                success=True,
                model_used=model,
                fix_suggestions=parsed.get("fix_suggestions", []),
                raw_analysis=response,
                tokens_used=tokens,
                analysis_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return LLMAnalysisResult(
                analysis_type=AnalysisType.REMEDIATION,
                success=False,
                model_used="",
                error=str(e),
                analysis_time_ms=(time.time() - start_time) * 1000
            )
    
    def _build_prompt(
        self, 
        vulnerability: Dict[str, Any],
        context: CodeContext
    ) -> str:
        return f"""**취약점 정보:**
```json
{json.dumps(vulnerability, indent=2, ensure_ascii=False)}
```

**파일**: {context.file_path}
**언어**: {context.language}
**프레임워크**: {context.framework or 'Unknown'}

**취약한 코드:**
```{context.language}
{context.code}
```

이 취약점에 대한 안전한 수정 코드를 제안해주세요.
프레임워크 특성을 고려하고, 테스트 케이스도 함께 제공해주세요."""
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"fix_suggestions": [], "raw_text": response}


class LLMSecurityAnalyzer:
    """
    Main LLM-based security analyzer combining all specialized analyzers.
    
    Provides unified interface for:
    - Business Logic Analysis
    - Authentication Analysis
    - API Security Analysis
    - Intelligent Remediation
    """
    
    def __init__(self):
        self.llm_client = LLMClient()
        
        # Initialize specialized analyzers
        self.business_logic = BusinessLogicAnalyzer(self.llm_client)
        self.authentication = AuthenticationAnalyzer(self.llm_client)
        self.api_security = APISecurityAnalyzer(self.llm_client)
        self.remediator = IntelligentRemediator(self.llm_client)
        
        # Statistics
        self.stats = {
            "total_analyses": 0,
            "successful_analyses": 0,
            "by_type": {},
            "total_vulnerabilities": 0,
            "total_tokens": 0,
        }
    
    def is_available(self) -> bool:
        """Check if LLM client is available."""
        return self.llm_client.is_available()
    
    def analyze_business_logic(self, context: CodeContext) -> LLMAnalysisResult:
        """Analyze for business logic vulnerabilities."""
        result = self.business_logic.analyze(context)
        self._update_stats(result)
        return result
    
    def analyze_authentication(self, context: CodeContext) -> LLMAnalysisResult:
        """Analyze for authentication vulnerabilities."""
        result = self.authentication.analyze(context)
        self._update_stats(result)
        return result
    
    def analyze_api_security(self, context: CodeContext) -> LLMAnalysisResult:
        """Analyze for API security vulnerabilities."""
        result = self.api_security.analyze(context)
        self._update_stats(result)
        return result
    
    def generate_remediation(
        self, 
        vulnerability: Dict[str, Any],
        context: CodeContext
    ) -> LLMAnalysisResult:
        """Generate fix suggestions for a vulnerability."""
        result = self.remediator.generate_fix(vulnerability, context)
        self._update_stats(result)
        return result
    
    def full_analysis(self, context: CodeContext) -> Dict[str, LLMAnalysisResult]:
        """
        Run all analysis types on the given code.
        
        Returns dict mapping analysis type to result.
        """
        results = {}
        
        # Run all analyses
        results["business_logic"] = self.analyze_business_logic(context)
        results["authentication"] = self.analyze_authentication(context)
        results["api_security"] = self.analyze_api_security(context)
        
        # Collect all vulnerabilities for remediation
        all_vulns = []
        for result in results.values():
            all_vulns.extend(result.vulnerabilities)
        
        # Generate fixes for critical/high severity vulnerabilities
        for vuln in all_vulns:
            if vuln.get("severity") in ["critical", "high"]:
                fix_result = self.generate_remediation(vuln, context)
                if fix_result.success:
                    vuln["fix_suggestions"] = fix_result.fix_suggestions
        
        return results
    
    def detect_auth_mechanisms(self, code: str) -> List[str]:
        """Detect authentication mechanisms in code."""
        mechanisms = []
        
        patterns = {
            "jwt": [r'jwt', r'jsonwebtoken', r'jose', r'JWTAuth', r'decode_token'],
            "session": [r'session', r'cookie', r'set_cookie', r'SESSION'],
            "oauth": [r'oauth', r'OAuth2', r'authlib', r'passport'],
            "saml": [r'saml', r'SAML', r'pysaml2'],
            "basic_auth": [r'BasicAuth', r'basic_auth', r'HTTPBasicAuth'],
            "api_key": [r'api_key', r'apikey', r'API_KEY', r'x-api-key'],
        }
        
        code_lower = code.lower()
        for mechanism, pattern_list in patterns.items():
            for pattern in pattern_list:
                if re.search(pattern, code, re.IGNORECASE):
                    mechanisms.append(mechanism)
                    break
        
        return list(set(mechanisms))
    
    def detect_framework(self, code: str, language: str) -> Optional[str]:
        """Detect web framework from code."""
        framework_patterns = {
            "python": {
                "flask": [r'from flask', r'Flask\('],
                "django": [r'from django', r'django\.'],
                "fastapi": [r'from fastapi', r'FastAPI\('],
            },
            "javascript": {
                "express": [r'express\(\)', r"require\(['\"]express"],
                "koa": [r'new Koa\(\)', r"require\(['\"]koa"],
                "fastify": [r'fastify\(\)', r"require\(['\"]fastify"],
            },
            "typescript": {
                "express": [r'express\(\)', r"from ['\"]express"],
                "nestjs": [r'@nestjs', r'NestFactory'],
            },
            "java": {
                "spring": [r'@SpringBootApplication', r'@RestController', r'@Controller'],
                "servlet": [r'HttpServlet', r'@WebServlet'],
            },
        }
        
        lang_patterns = framework_patterns.get(language.lower(), {})
        for framework, patterns in lang_patterns.items():
            for pattern in patterns:
                if re.search(pattern, code):
                    return framework
        
        return None
    
    def _update_stats(self, result: LLMAnalysisResult):
        """Update internal statistics."""
        self.stats["total_analyses"] += 1
        if result.success:
            self.stats["successful_analyses"] += 1
        
        analysis_type = result.analysis_type.value
        self.stats["by_type"][analysis_type] = self.stats["by_type"].get(analysis_type, 0) + 1
        
        self.stats["total_vulnerabilities"] += len(result.vulnerabilities)
        self.stats["total_tokens"] += result.tokens_used
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analysis statistics."""
        return {
            **self.stats,
            "success_rate": (
                self.stats["successful_analyses"] / self.stats["total_analyses"] * 100
                if self.stats["total_analyses"] > 0 else 0
            ),
        }


# Singleton instance
_llm_analyzer: Optional[LLMSecurityAnalyzer] = None

def get_llm_security_analyzer() -> LLMSecurityAnalyzer:
    """Get singleton LLMSecurityAnalyzer instance."""
    global _llm_analyzer
    if _llm_analyzer is None:
        _llm_analyzer = LLMSecurityAnalyzer()
    return _llm_analyzer
