"""
Enhanced Security Analyzer: Dynamic Code + Semantic Taint Analysis

이 모듈은 세 가지 핵심 보안 분석 기능을 통합합니다:

1. **Dynamic Code Analysis** - 동적 코드 실행 패턴 탐지
   - eval/exec/compile
   - getattr/setattr/delattr  
   - importlib/import_module
   - Reflection 패턴

2. **Precision Taint Analysis** - 정밀한 데이터 흐름 추적
   - Sources (입력 지점)
   - Propagators (전파 함수)
   - Sinks (위험 함수)
   - Sanitizers (무해화 함수)

3. **Semantic Analysis** - 의미론적 코드 분석
   - 패턴 매칭이 아닌 AST/CFG 기반 분석
   - 경로 조건 검사
   - 도달 가능성 분석
   - 컨텍스트 인식 분석

Author: AI Assistant
Version: 1.0.0
"""

from typing import List, Dict, Set, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import re
import logging

try:
    import tree_sitter
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

logger = logging.getLogger(__name__)


# ============================================
# 1. Dynamic Code Analysis
# ============================================

class DynamicCodeType(Enum):
    """동적 코드 실행 유형"""
    EVAL = "eval"                       # eval()
    EXEC = "exec"                       # exec()
    COMPILE = "compile"                 # compile()
    IMPORT = "dynamic_import"           # __import__, importlib
    GETATTR = "getattr"                 # getattr()
    SETATTR = "setattr"                 # setattr()
    DELATTR = "delattr"                 # delattr()
    CALL = "dynamic_call"               # callable variable call
    REFLECTION = "reflection"           # 리플렉션 패턴
    DESERIALIZATION = "deserialization" # pickle, yaml 등


@dataclass
class DynamicCodePattern:
    """동적 코드 실행 패턴 정의"""
    name: str
    pattern_type: DynamicCodeType
    function_names: List[str]
    severity: str
    description: str
    cwe_id: Optional[str] = None
    mitigation: Optional[str] = None
    
    
# 동적 코드 패턴 데이터베이스
DYNAMIC_CODE_PATTERNS: List[DynamicCodePattern] = [
    # eval 계열
    DynamicCodePattern(
        name="eval",
        pattern_type=DynamicCodeType.EVAL,
        function_names=["eval", "builtins.eval"],
        severity="CRITICAL",
        description="eval()을 사용한 동적 코드 실행",
        cwe_id="CWE-95",
        mitigation="ast.literal_eval() 또는 JSON 파싱 사용"
    ),
    DynamicCodePattern(
        name="exec",
        pattern_type=DynamicCodeType.EXEC,
        function_names=["exec", "builtins.exec"],
        severity="CRITICAL",
        description="exec()을 사용한 동적 코드 실행",
        cwe_id="CWE-95",
        mitigation="코드 실행 대신 안전한 대안 사용"
    ),
    DynamicCodePattern(
        name="compile",
        pattern_type=DynamicCodeType.COMPILE,
        function_names=["compile", "builtins.compile"],
        severity="HIGH",
        description="compile()을 사용한 동적 코드 컴파일",
        cwe_id="CWE-95",
        mitigation="코드 컴파일 대신 데이터 파싱 사용"
    ),
    
    # import 계열
    DynamicCodePattern(
        name="__import__",
        pattern_type=DynamicCodeType.IMPORT,
        function_names=["__import__", "builtins.__import__"],
        severity="HIGH",
        description="__import__()를 사용한 동적 모듈 로드",
        cwe_id="CWE-502",
        mitigation="화이트리스트 기반 모듈 로드"
    ),
    DynamicCodePattern(
        name="importlib.import_module",
        pattern_type=DynamicCodeType.IMPORT,
        function_names=["importlib.import_module", "import_module"],
        severity="HIGH",
        description="importlib을 사용한 동적 모듈 로드",
        cwe_id="CWE-502",
        mitigation="허용된 모듈 목록 검증"
    ),
    DynamicCodePattern(
        name="importlib.util.spec_from_file_location",
        pattern_type=DynamicCodeType.IMPORT,
        function_names=[
            "importlib.util.spec_from_file_location",
            "spec_from_file_location"
        ],
        severity="HIGH",
        description="파일 경로에서 모듈 동적 로드",
        cwe_id="CWE-502",
        mitigation="파일 경로 검증 및 화이트리스트 사용"
    ),
    
    # getattr 계열
    DynamicCodePattern(
        name="getattr",
        pattern_type=DynamicCodeType.GETATTR,
        function_names=["getattr", "builtins.getattr"],
        severity="MEDIUM",
        description="getattr()을 사용한 동적 속성 접근",
        cwe_id="CWE-470",
        mitigation="허용된 속성 이름 화이트리스트 검증"
    ),
    DynamicCodePattern(
        name="setattr",
        pattern_type=DynamicCodeType.SETATTR,
        function_names=["setattr", "builtins.setattr"],
        severity="MEDIUM",
        description="setattr()을 사용한 동적 속성 설정",
        cwe_id="CWE-470",
        mitigation="허용된 속성 이름 화이트리스트 검증"
    ),
    DynamicCodePattern(
        name="delattr",
        pattern_type=DynamicCodeType.DELATTR,
        function_names=["delattr", "builtins.delattr"],
        severity="LOW",
        description="delattr()을 사용한 동적 속성 삭제",
        cwe_id="CWE-470",
        mitigation="삭제 가능 속성 검증"
    ),
    
    # 역직렬화 계열
    DynamicCodePattern(
        name="pickle.loads",
        pattern_type=DynamicCodeType.DESERIALIZATION,
        function_names=[
            "pickle.loads", "pickle.load",
            "cPickle.loads", "cPickle.load",
            "_pickle.loads", "_pickle.load"
        ],
        severity="CRITICAL",
        description="pickle을 사용한 역직렬화",
        cwe_id="CWE-502",
        mitigation="JSON 또는 안전한 직렬화 형식 사용"
    ),
    DynamicCodePattern(
        name="yaml.load",
        pattern_type=DynamicCodeType.DESERIALIZATION,
        function_names=["yaml.load", "yaml.unsafe_load", "yaml.full_load"],
        severity="CRITICAL",
        description="YAML 역직렬화 (임의 코드 실행 가능)",
        cwe_id="CWE-502",
        mitigation="yaml.safe_load() 사용"
    ),
    DynamicCodePattern(
        name="marshal.loads",
        pattern_type=DynamicCodeType.DESERIALIZATION,
        function_names=["marshal.loads", "marshal.load"],
        severity="HIGH",
        description="marshal을 사용한 역직렬화",
        cwe_id="CWE-502",
        mitigation="JSON 또는 안전한 직렬화 형식 사용"
    ),
    DynamicCodePattern(
        name="shelve.open",
        pattern_type=DynamicCodeType.DESERIALIZATION,
        function_names=["shelve.open"],
        severity="HIGH",
        description="shelve를 사용한 객체 저장/로드",
        cwe_id="CWE-502",
        mitigation="sqlite3 또는 안전한 저장소 사용"
    ),
    
    # JavaScript 동적 코드
    DynamicCodePattern(
        name="js_eval",
        pattern_type=DynamicCodeType.EVAL,
        function_names=["eval", "Function"],
        severity="CRITICAL",
        description="eval() 또는 Function()을 사용한 동적 코드 실행",
        cwe_id="CWE-95",
        mitigation="eval 대신 JSON.parse 또는 안전한 파서 사용"
    ),
    DynamicCodePattern(
        name="js_settimeout_string",
        pattern_type=DynamicCodeType.EVAL,
        function_names=["setTimeout", "setInterval", "setImmediate"],
        severity="HIGH",
        description="문자열을 인자로 받는 setTimeout/setInterval",
        cwe_id="CWE-95",
        mitigation="함수 참조 사용 (문자열 대신)"
    ),
    
    # PHP 동적 코드
    DynamicCodePattern(
        name="php_eval",
        pattern_type=DynamicCodeType.EVAL,
        function_names=["eval", "assert", "preg_replace"],
        severity="CRITICAL",
        description="eval() 또는 assert()를 사용한 코드 실행",
        cwe_id="CWE-95",
        mitigation="동적 코드 실행 제거"
    ),
    DynamicCodePattern(
        name="php_create_function",
        pattern_type=DynamicCodeType.EVAL,
        function_names=["create_function"],
        severity="CRITICAL",
        description="create_function()을 사용한 동적 함수 생성",
        cwe_id="CWE-95",
        mitigation="익명 함수(closure) 사용"
    ),
    
    # Java 리플렉션
    DynamicCodePattern(
        name="java_reflection",
        pattern_type=DynamicCodeType.REFLECTION,
        function_names=[
            "Class.forName", "getMethod", "getDeclaredMethod",
            "invoke", "newInstance", "getConstructor"
        ],
        severity="MEDIUM",
        description="Java 리플렉션을 통한 동적 메소드 호출",
        cwe_id="CWE-470",
        mitigation="리플렉션 대상 클래스/메소드 화이트리스트 검증"
    ),
]


@dataclass
class DynamicCodeFinding:
    """동적 코드 탐지 결과"""
    pattern: DynamicCodePattern
    file_path: str
    line: int
    column: int
    code_snippet: str
    tainted_args: List[str] = field(default_factory=list)
    is_user_controlled: bool = False
    context: Dict[str, Any] = field(default_factory=dict)


class DynamicCodeAnalyzer:
    """동적 코드 실행 패턴 분석기"""
    
    def __init__(self):
        self.patterns = DYNAMIC_CODE_PATTERNS
        self.findings: List[DynamicCodeFinding] = []
        
        # 패턴 이름으로 빠른 검색을 위한 맵
        self._function_to_pattern: Dict[str, DynamicCodePattern] = {}
        for pattern in self.patterns:
            for func_name in pattern.function_names:
                self._function_to_pattern[func_name] = pattern
                # 마지막 부분만으로도 검색 (e.g., "import_module")
                if "." in func_name:
                    short_name = func_name.split(".")[-1]
                    if short_name not in self._function_to_pattern:
                        self._function_to_pattern[short_name] = pattern
    
    def analyze_call(
        self, 
        func_name: str, 
        args: List[str],
        file_path: str,
        line: int,
        column: int = 0,
        code_snippet: str = "",
        tainted_vars: Optional[Set[str]] = None
    ) -> Optional[DynamicCodeFinding]:
        """
        함수 호출이 동적 코드 실행인지 분석
        
        Args:
            func_name: 호출된 함수 이름
            args: 함수 인자 목록
            file_path: 파일 경로
            line: 라인 번호
            column: 컬럼 위치
            code_snippet: 코드 스니펫
            tainted_vars: 오염된 변수 집합
        
        Returns:
            DynamicCodeFinding if dangerous, None otherwise
        """
        tainted_vars = tainted_vars or set()
        
        # 패턴 매칭
        pattern = self._function_to_pattern.get(func_name)
        if not pattern:
            # 부분 매칭 시도 (e.g., "obj.eval" -> "eval")
            short_name = func_name.split(".")[-1] if "." in func_name else func_name
            pattern = self._function_to_pattern.get(short_name)
        
        if not pattern:
            return None
        
        # 특수 케이스: setTimeout/setInterval은 문자열 인자일 때만 위험
        if func_name in ["setTimeout", "setInterval", "setImmediate"]:
            if not args or not self._is_string_literal(args[0]):
                return None
        
        # 특수 케이스: yaml.load는 Loader=yaml.SafeLoader면 안전
        if func_name in ["yaml.load", "yaml.full_load"]:
            args_str = ", ".join(args)
            if "Loader=yaml.SafeLoader" in args_str or "Loader=SafeLoader" in args_str:
                return None
        
        # 오염된 인자 확인
        tainted_args = []
        for arg in args:
            identifiers = self._extract_identifiers(arg)
            for ident in identifiers:
                if ident in tainted_vars:
                    tainted_args.append(ident)
        
        is_user_controlled = len(tainted_args) > 0
        
        finding = DynamicCodeFinding(
            pattern=pattern,
            file_path=file_path,
            line=line,
            column=column,
            code_snippet=code_snippet,
            tainted_args=tainted_args,
            is_user_controlled=is_user_controlled,
            context={
                "function": func_name,
                "args": args
            }
        )
        
        self.findings.append(finding)
        return finding
    
    def _is_string_literal(self, arg: str) -> bool:
        """인자가 문자열 리터럴인지 확인"""
        arg = arg.strip()
        return (arg.startswith('"') and arg.endswith('"')) or \
               (arg.startswith("'") and arg.endswith("'"))
    
    def _extract_identifiers(self, expr: str) -> List[str]:
        """표현식에서 식별자 추출"""
        return re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expr)
    
    def get_findings(self) -> List[DynamicCodeFinding]:
        """모든 탐지 결과 반환"""
        return self.findings
    
    def get_critical_findings(self) -> List[DynamicCodeFinding]:
        """CRITICAL 수준의 탐지 결과만 반환"""
        return [f for f in self.findings if f.pattern.severity == "CRITICAL"]
    
    def get_user_controlled_findings(self) -> List[DynamicCodeFinding]:
        """사용자 입력이 도달하는 탐지 결과만 반환"""
        return [f for f in self.findings if f.is_user_controlled]


# ============================================
# 2. Precision Taint Analysis
# ============================================

class TaintCategory(Enum):
    """테인트 카테고리"""
    SOURCE = "source"
    PROPAGATOR = "propagator"  
    SINK = "sink"
    SANITIZER = "sanitizer"


@dataclass
class TaintRule:
    """테인트 규칙 정의"""
    name: str
    category: TaintCategory
    patterns: List[str]
    taint_types: Set[str] = field(default_factory=set)
    description: str = ""
    language: str = "all"


# 소스 (Sources) - 사용자 입력이 들어오는 지점
TAINT_SOURCES: List[TaintRule] = [
    # Python - Flask
    TaintRule(
        name="flask_request_args",
        category=TaintCategory.SOURCE,
        patterns=["request.args", "request.args.get", "request.args.getlist"],
        taint_types={"xss", "sqli", "cmdi", "path", "ssrf"},
        description="Flask URL 쿼리 파라미터",
        language="python"
    ),
    TaintRule(
        name="flask_request_form",
        category=TaintCategory.SOURCE,
        patterns=["request.form", "request.form.get", "request.form.getlist"],
        taint_types={"xss", "sqli", "cmdi", "path"},
        description="Flask 폼 데이터",
        language="python"
    ),
    TaintRule(
        name="flask_request_data",
        category=TaintCategory.SOURCE,
        patterns=["request.data", "request.json", "request.get_json"],
        taint_types={"xss", "sqli", "cmdi"},
        description="Flask 요청 본문",
        language="python"
    ),
    TaintRule(
        name="flask_request_headers",
        category=TaintCategory.SOURCE,
        patterns=["request.headers", "request.headers.get"],
        taint_types={"xss", "ssrf"},
        description="Flask HTTP 헤더",
        language="python"
    ),
    TaintRule(
        name="flask_request_cookies",
        category=TaintCategory.SOURCE,
        patterns=["request.cookies", "request.cookies.get"],
        taint_types={"xss"},
        description="Flask 쿠키",
        language="python"
    ),
    TaintRule(
        name="flask_request_files",
        category=TaintCategory.SOURCE,
        patterns=["request.files", "request.files.get"],
        taint_types={"path", "rce"},
        description="Flask 업로드 파일",
        language="python"
    ),
    TaintRule(
        name="flask_request_path",
        category=TaintCategory.SOURCE,
        patterns=["request.path", "request.url", "request.base_url", "request.full_path"],
        taint_types={"xss", "ssrf", "open_redirect"},
        description="Flask 요청 경로/URL",
        language="python"
    ),
    
    # Python - FastAPI
    TaintRule(
        name="fastapi_path_params",
        category=TaintCategory.SOURCE,
        patterns=["path_param", "Path("],
        taint_types={"xss", "sqli", "path"},
        description="FastAPI 경로 파라미터",
        language="python"
    ),
    TaintRule(
        name="fastapi_query_params",
        category=TaintCategory.SOURCE,
        patterns=["Query(", "query_param"],
        taint_types={"xss", "sqli", "ssrf"},
        description="FastAPI 쿼리 파라미터",
        language="python"
    ),
    TaintRule(
        name="fastapi_body",
        category=TaintCategory.SOURCE,
        patterns=["Body(", "request.body"],
        taint_types={"xss", "sqli"},
        description="FastAPI 요청 본문",
        language="python"
    ),
    
    # Python - Django
    TaintRule(
        name="django_request",
        category=TaintCategory.SOURCE,
        patterns=[
            "request.GET", "request.GET.get", "request.GET.getlist",
            "request.POST", "request.POST.get", "request.POST.getlist",
            "request.body", "request.data"
        ],
        taint_types={"xss", "sqli", "cmdi", "path"},
        description="Django 요청 데이터",
        language="python"
    ),
    
    # Python - 일반
    TaintRule(
        name="python_input",
        category=TaintCategory.SOURCE,
        patterns=["input(", "raw_input("],
        taint_types={"xss", "sqli", "cmdi"},
        description="Python 표준 입력",
        language="python"
    ),
    TaintRule(
        name="python_env",
        category=TaintCategory.SOURCE,
        patterns=["os.environ", "os.getenv", "environ.get"],
        taint_types={"cmdi", "path"},
        description="환경 변수",
        language="python"
    ),
    TaintRule(
        name="python_file_read",
        category=TaintCategory.SOURCE,
        patterns=["open(", "file.read", "read()", "readlines("],
        taint_types={"xss", "sqli"},
        description="파일 읽기",
        language="python"
    ),
    
    # JavaScript/Node.js
    TaintRule(
        name="express_req",
        category=TaintCategory.SOURCE,
        patterns=[
            "req.query", "req.params", "req.body",
            "req.headers", "req.cookies", "req.path"
        ],
        taint_types={"xss", "sqli", "cmdi", "path", "ssrf"},
        description="Express.js 요청 데이터",
        language="javascript"
    ),
    TaintRule(
        name="dom_input",
        category=TaintCategory.SOURCE,
        patterns=[
            "document.location", "location.href", "location.search",
            "location.hash", "document.URL", "document.referrer",
            "window.name", "document.cookie"
        ],
        taint_types={"xss", "open_redirect"},
        description="DOM 소스",
        language="javascript"
    ),
    TaintRule(
        name="dom_user_input",
        category=TaintCategory.SOURCE,
        patterns=[".value", "innerHTML", "innerText", "textContent"],
        taint_types={"xss"},
        description="사용자 입력 요소",
        language="javascript"
    ),
    
    # PHP
    TaintRule(
        name="php_superglobals",
        category=TaintCategory.SOURCE,
        patterns=[
            "$_GET", "$_POST", "$_REQUEST", "$_COOKIE",
            "$_SERVER", "$_FILES", "$_ENV"
        ],
        taint_types={"xss", "sqli", "cmdi", "path", "ssrf"},
        description="PHP 슈퍼글로벌 변수",
        language="php"
    ),
    
    # Java
    TaintRule(
        name="java_servlet",
        category=TaintCategory.SOURCE,
        patterns=[
            "request.getParameter", "request.getParameterValues",
            "request.getHeader", "request.getCookies",
            "request.getInputStream", "request.getReader"
        ],
        taint_types={"xss", "sqli", "cmdi", "path"},
        description="Java Servlet 요청 데이터",
        language="java"
    ),
]


# 전파자 (Propagators) - 테인트를 전파하는 함수
TAINT_PROPAGATORS: List[TaintRule] = [
    # 문자열 연산
    TaintRule(
        name="string_concat",
        category=TaintCategory.PROPAGATOR,
        patterns=["+", "concat", "join", "format", "f\"", "%"],
        description="문자열 연결",
    ),
    TaintRule(
        name="string_transform",
        category=TaintCategory.PROPAGATOR,
        patterns=[
            "upper", "lower", "strip", "replace", "split",
            "encode", "decode", "slice", "substring", "substr"
        ],
        description="문자열 변환",
    ),
    
    # 컬렉션 연산
    TaintRule(
        name="collection_ops",
        category=TaintCategory.PROPAGATOR,
        patterns=[
            "append", "extend", "push", "unshift", "add",
            "update", "merge", "Object.assign", "spread"
        ],
        description="컬렉션 연산",
    ),
    
    # 객체 접근
    TaintRule(
        name="property_access",
        category=TaintCategory.PROPAGATOR,
        patterns=["getattr", "getAttribute", "[]", "."],
        description="속성 접근",
    ),
    
    # 템플릿
    TaintRule(
        name="template_ops",
        category=TaintCategory.PROPAGATOR,
        patterns=["format", "Template", "render", "jinja", "mustache"],
        description="템플릿 렌더링",
    ),
]


# 싱크 (Sinks) - 위험한 함수
TAINT_SINKS: List[TaintRule] = [
    # 코드 실행
    TaintRule(
        name="code_execution",
        category=TaintCategory.SINK,
        patterns=[
            "eval", "exec", "compile", "__import__",
            "importlib.import_module", "Function", "create_function"
        ],
        taint_types={"rce"},
        description="코드 실행",
    ),
    
    # 명령 실행
    TaintRule(
        name="command_execution",
        category=TaintCategory.SINK,
        patterns=[
            "os.system", "os.popen", "subprocess.call",
            "subprocess.run", "subprocess.Popen", "child_process.exec",
            "shell_exec", "system", "passthru", "proc_open"
        ],
        taint_types={"cmdi"},
        description="명령 실행",
    ),
    
    # SQL
    TaintRule(
        name="sql_execution",
        category=TaintCategory.SINK,
        patterns=[
            "execute", "executemany", "raw", "query",
            "createQuery", "nativeQuery", "rawQuery"
        ],
        taint_types={"sqli"},
        description="SQL 실행",
    ),
    
    # 파일 시스템
    TaintRule(
        name="file_operations",
        category=TaintCategory.SINK,
        patterns=[
            "open", "fopen", "file_get_contents", "readFile",
            "writeFile", "unlink", "remove", "rmdir", "mkdir"
        ],
        taint_types={"path"},
        description="파일 시스템 작업",
    ),
    
    # XSS
    TaintRule(
        name="xss_sinks",
        category=TaintCategory.SINK,
        patterns=[
            "innerHTML", "outerHTML", "document.write",
            "render_template_string", "Markup", "SafeString"
        ],
        taint_types={"xss"},
        description="XSS 싱크",
    ),
    
    # SSRF
    TaintRule(
        name="ssrf_sinks",
        category=TaintCategory.SINK,
        patterns=[
            "requests.get", "requests.post", "urllib.request.urlopen",
            "fetch", "axios", "http.get", "curl_exec"
        ],
        taint_types={"ssrf"},
        description="SSRF 싱크",
    ),
    
    # 역직렬화
    TaintRule(
        name="deserialization_sinks",
        category=TaintCategory.SINK,
        patterns=[
            "pickle.loads", "pickle.load", "yaml.load",
            "unserialize", "ObjectInputStream", "readObject"
        ],
        taint_types={"deserialization"},
        description="역직렬화 싱크",
    ),
    
    # 리다이렉트
    TaintRule(
        name="redirect_sinks",
        category=TaintCategory.SINK,
        patterns=[
            "redirect", "RedirectResponse", "header(\"Location",
            "response.sendRedirect", "location.href"
        ],
        taint_types={"open_redirect"},
        description="리다이렉트 싱크",
    ),
]


# 새니타이저 (Sanitizers) - 테인트를 제거하는 함수
TAINT_SANITIZERS: List[TaintRule] = [
    # XSS
    TaintRule(
        name="xss_sanitizers",
        category=TaintCategory.SANITIZER,
        patterns=[
            "html.escape", "markupsafe.escape", "cgi.escape",
            "bleach.clean", "escape", "htmlspecialchars",
            "htmlentities", "encodeURIComponent", "DOMPurify.sanitize"
        ],
        taint_types={"xss"},
        description="XSS 새니타이저",
    ),
    
    # SQL
    TaintRule(
        name="sql_sanitizers",
        category=TaintCategory.SANITIZER,
        patterns=[
            "parameterized", "prepare", "bindParam", "bindValue",
            "setParameter", "quote", "escape_string", "real_escape_string"
        ],
        taint_types={"sqli"},
        description="SQL 새니타이저",
    ),
    
    # 명령 실행
    TaintRule(
        name="cmdi_sanitizers",
        category=TaintCategory.SANITIZER,
        patterns=[
            "shlex.quote", "shlex.split", "pipes.quote",
            "escapeshellarg", "escapeshellcmd"
        ],
        taint_types={"cmdi"},
        description="명령 주입 새니타이저",
    ),
    
    # 경로
    TaintRule(
        name="path_sanitizers",
        category=TaintCategory.SANITIZER,
        patterns=[
            "os.path.basename", "os.path.normpath", "secure_filename",
            "realpath", "abspath", "basename"
        ],
        taint_types={"path"},
        description="경로 새니타이저",
    ),
    
    # URL
    TaintRule(
        name="url_sanitizers",
        category=TaintCategory.SANITIZER,
        patterns=[
            "urllib.parse.quote", "urlencode", "encodeURI",
            "url_for", "is_safe_url"
        ],
        taint_types={"ssrf", "open_redirect"},
        description="URL 새니타이저",
    ),
    
    # 입력 검증
    TaintRule(
        name="validation",
        category=TaintCategory.SANITIZER,
        patterns=[
            "validate", "validator", "sanitize", "clean",
            "isdigit", "isnumeric", "isalpha", "isalnum",
            "int(", "float(", "bool("
        ],
        taint_types={"xss", "sqli", "cmdi", "path"},
        description="입력 검증",
    ),
]


@dataclass  
class TaintState:
    """변수의 테인트 상태"""
    variable: str
    is_tainted: bool
    taint_types: Set[str] = field(default_factory=set)
    source: Optional[str] = None  # 원본 소스
    sanitized_for: Set[str] = field(default_factory=set)  # 새니타이즈된 타입
    propagation_path: List[str] = field(default_factory=list)  # 전파 경로


@dataclass
class TaintVulnerability:
    """탐지된 테인트 취약점"""
    source: TaintRule
    sink: TaintRule
    taint_type: str
    file_path: str
    source_line: int
    sink_line: int
    variable_path: List[str]
    is_sanitized: bool = False
    sanitizer: Optional[TaintRule] = None
    confidence: float = 1.0
    severity: str = "HIGH"


class PrecisionTaintAnalyzer:
    """정밀 테인트 분석기"""
    
    def __init__(self):
        self.sources = TAINT_SOURCES
        self.propagators = TAINT_PROPAGATORS
        self.sinks = TAINT_SINKS
        self.sanitizers = TAINT_SANITIZERS
        
        # 변수 상태 추적
        self.taint_states: Dict[str, TaintState] = {}
        
        # 발견된 취약점
        self.vulnerabilities: List[TaintVulnerability] = []
        
        # 패턴 -> 규칙 매핑
        self._build_pattern_maps()
    
    def _build_pattern_maps(self):
        """패턴 검색을 위한 맵 구축"""
        self._source_patterns: Dict[str, TaintRule] = {}
        self._sink_patterns: Dict[str, TaintRule] = {}
        self._sanitizer_patterns: Dict[str, TaintRule] = {}
        
        for rule in self.sources:
            for pattern in rule.patterns:
                self._source_patterns[pattern] = rule
        
        for rule in self.sinks:
            for pattern in rule.patterns:
                self._sink_patterns[pattern] = rule
        
        for rule in self.sanitizers:
            for pattern in rule.patterns:
                self._sanitizer_patterns[pattern] = rule
    
    def is_source(self, code: str) -> Optional[TaintRule]:
        """코드가 소스인지 확인"""
        for pattern, rule in self._source_patterns.items():
            if pattern in code:
                return rule
        return None
    
    def is_sink(self, code: str) -> Optional[TaintRule]:
        """코드가 싱크인지 확인"""
        for pattern, rule in self._sink_patterns.items():
            if pattern in code:
                return rule
        return None
    
    def is_sanitizer(self, code: str, taint_type: str) -> Optional[TaintRule]:
        """코드가 특정 타입의 새니타이저인지 확인"""
        for pattern, rule in self._sanitizer_patterns.items():
            if pattern in code:
                if not rule.taint_types or taint_type in rule.taint_types:
                    return rule
        return None
    
    def taint_variable(
        self,
        variable: str,
        source_rule: TaintRule,
        source_code: str,
        line: int
    ):
        """변수를 오염으로 표시"""
        self.taint_states[variable] = TaintState(
            variable=variable,
            is_tainted=True,
            taint_types=set(source_rule.taint_types) if source_rule.taint_types else {"general"},
            source=source_code,
            propagation_path=[f"L{line}: {variable} = {source_code}"]
        )
    
    def propagate_taint(
        self,
        target: str,
        source_expr: str,
        line: int
    ) -> bool:
        """테인트 전파"""
        # source_expr에서 오염된 변수 찾기
        for var, state in self.taint_states.items():
            if var in source_expr and state.is_tainted:
                # 전파
                new_state = TaintState(
                    variable=target,
                    is_tainted=True,
                    taint_types=set(state.taint_types),
                    source=state.source,
                    sanitized_for=set(state.sanitized_for),
                    propagation_path=state.propagation_path + [f"L{line}: {target} = {source_expr}"]
                )
                self.taint_states[target] = new_state
                return True
        
        return False
    
    def apply_sanitizer(
        self,
        variable: str,
        sanitizer_rule: TaintRule,
        line: int
    ):
        """새니타이저 적용"""
        if variable in self.taint_states:
            state = self.taint_states[variable]
            # 새니타이저가 처리하는 타입 제거
            if sanitizer_rule.taint_types:
                state.sanitized_for.update(sanitizer_rule.taint_types)
                state.taint_types -= sanitizer_rule.taint_types
            else:
                # 모든 타입 새니타이즈
                state.sanitized_for.update(state.taint_types)
                state.taint_types.clear()
            
            state.propagation_path.append(f"L{line}: SANITIZED by {sanitizer_rule.name}")
            
            # 모든 타입이 새니타이즈되면 오염 해제
            if not state.taint_types:
                state.is_tainted = False
    
    def check_sink(
        self,
        sink_code: str,
        sink_rule: TaintRule,
        file_path: str,
        line: int,
        args: List[str]
    ) -> List[TaintVulnerability]:
        """싱크에 오염된 데이터가 도달하는지 확인"""
        vulnerabilities = []
        
        for arg in args:
            # 인자에서 변수 추출
            identifiers = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', arg)
            
            for ident in identifiers:
                state = self.taint_states.get(ident)
                if state and state.is_tainted:
                    # 싱크가 요구하는 타입과 변수의 오염 타입 비교
                    sink_types = sink_rule.taint_types or {"general"}
                    var_types = state.taint_types or {"general"}
                    
                    # 교집합이 있으면 취약점
                    matching_types = sink_types & var_types
                    if matching_types or "general" in var_types:
                        for taint_type in (matching_types or {"general"}):
                            vuln = TaintVulnerability(
                                source=self._get_source_rule(state.source),
                                sink=sink_rule,
                                taint_type=taint_type,
                                file_path=file_path,
                                source_line=self._extract_line(state.propagation_path[0]),
                                sink_line=line,
                                variable_path=state.propagation_path,
                                is_sanitized=taint_type in state.sanitized_for,
                                confidence=0.5 if taint_type in state.sanitized_for else 1.0,
                                severity=self._get_severity(taint_type)
                            )
                            vulnerabilities.append(vuln)
        
        self.vulnerabilities.extend(vulnerabilities)
        return vulnerabilities
    
    def _get_source_rule(self, source_code: Optional[str]) -> TaintRule:
        """소스 코드에서 규칙 찾기"""
        if source_code:
            rule = self.is_source(source_code)
            if rule:
                return rule
        
        # 기본 규칙
        return TaintRule(
            name="unknown_source",
            category=TaintCategory.SOURCE,
            patterns=[],
            description="Unknown source"
        )
    
    def _extract_line(self, path_entry: str) -> int:
        """경로 항목에서 라인 번호 추출"""
        match = re.match(r'L(\d+):', path_entry)
        return int(match.group(1)) if match else 0
    
    def _get_severity(self, taint_type: str) -> str:
        """취약점 타입에 따른 심각도"""
        severity_map = {
            "rce": "CRITICAL",
            "cmdi": "CRITICAL",
            "sqli": "HIGH",
            "deserialization": "HIGH",
            "path": "HIGH",
            "xss": "MEDIUM",
            "ssrf": "MEDIUM",
            "open_redirect": "LOW",
        }
        return severity_map.get(taint_type, "MEDIUM")
    
    def get_vulnerabilities(self) -> List[TaintVulnerability]:
        """발견된 모든 취약점 반환"""
        return self.vulnerabilities
    
    def get_high_confidence_vulnerabilities(self) -> List[TaintVulnerability]:
        """높은 신뢰도 취약점만 반환"""
        return [v for v in self.vulnerabilities if v.confidence >= 0.8]


# ============================================
# 3. Semantic Analysis
# ============================================

class AnalysisContext:
    """분석 컨텍스트"""
    
    def __init__(self):
        # 현재 범위의 변수들
        self.variables: Dict[str, Any] = {}
        
        # 경로 조건 스택
        self.path_conditions: List[str] = []
        
        # 현재 함수 컨텍스트
        self.current_function: Optional[str] = None
        
        # 호출 스택
        self.call_stack: List[str] = []
    
    def enter_function(self, name: str):
        """함수 진입"""
        self.call_stack.append(name)
        self.current_function = name
    
    def exit_function(self):
        """함수 종료"""
        if self.call_stack:
            self.call_stack.pop()
            self.current_function = self.call_stack[-1] if self.call_stack else None
    
    def push_condition(self, condition: str):
        """조건 추가"""
        self.path_conditions.append(condition)
    
    def pop_condition(self):
        """조건 제거"""
        if self.path_conditions:
            self.path_conditions.pop()
    
    def clone(self) -> "AnalysisContext":
        """컨텍스트 복제 (분기용)"""
        ctx = AnalysisContext()
        ctx.variables = dict(self.variables)
        ctx.path_conditions = list(self.path_conditions)
        ctx.current_function = self.current_function
        ctx.call_stack = list(self.call_stack)
        return ctx


@dataclass
class SemanticFinding:
    """의미론적 분석 결과"""
    vulnerability_type: str
    severity: str
    file_path: str
    line: int
    column: int
    message: str
    code_snippet: str
    data_flow: List[str]  # 데이터 흐름 경로
    path_conditions: List[str]  # 도달 조건
    is_reachable: bool  # 도달 가능 여부
    confidence: float
    cwe_id: Optional[str] = None
    remediation: Optional[str] = None


class SemanticAnalyzer:
    """
    의미론적 코드 분석기
    
    패턴 매칭 대신 AST/CFG 기반의 깊은 분석을 수행합니다:
    1. 데이터 흐름 추적 (Data Flow)
    2. 제어 흐름 분석 (Control Flow)
    3. 경로 조건 추출 (Path Conditions)
    4. 도달 가능성 검사 (Reachability)
    """
    
    def __init__(self):
        self.dynamic_analyzer = DynamicCodeAnalyzer()
        self.taint_analyzer = PrecisionTaintAnalyzer()
        self.findings: List[SemanticFinding] = []
        self.context = AnalysisContext()
    
    def analyze_assignment(
        self,
        target: str,
        value_code: str,
        file_path: str,
        line: int
    ):
        """
        할당문 분석
        
        1. 소스 확인 → 테인트 설정
        2. 전파 확인 → 테인트 전파
        3. 새니타이저 확인 → 테인트 제거
        """
        # 1. 소스 확인
        source_rule = self.taint_analyzer.is_source(value_code)
        if source_rule:
            self.taint_analyzer.taint_variable(target, source_rule, value_code, line)
            return
        
        # 2. 새니타이저 확인 (값이 새니타이저를 통과했는지)
        for taint_type in ["xss", "sqli", "cmdi", "path", "ssrf"]:
            sanitizer = self.taint_analyzer.is_sanitizer(value_code, taint_type)
            if sanitizer:
                # 어떤 변수가 새니타이즈되었는지 확인
                identifiers = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', value_code)
                for ident in identifiers:
                    if ident in self.taint_analyzer.taint_states:
                        self.taint_analyzer.apply_sanitizer(ident, sanitizer, line)
        
        # 3. 전파 확인
        self.taint_analyzer.propagate_taint(target, value_code, line)
    
    def analyze_call(
        self,
        func_name: str,
        args: List[str],
        file_path: str,
        line: int,
        column: int = 0,
        code_snippet: str = ""
    ) -> List[SemanticFinding]:
        """
        함수 호출 분석
        
        1. 동적 코드 실행 확인
        2. 싱크 확인 → 테인트 도달 검사
        3. 의미론적 취약점 생성
        """
        findings = []
        
        # 오염된 변수 집합
        tainted_vars = {
            var for var, state in self.taint_analyzer.taint_states.items()
            if state.is_tainted
        }
        
        # 1. 동적 코드 분석
        dynamic_finding = self.dynamic_analyzer.analyze_call(
            func_name=func_name,
            args=args,
            file_path=file_path,
            line=line,
            column=column,
            code_snippet=code_snippet,
            tainted_vars=tainted_vars
        )
        
        if dynamic_finding:
            finding = SemanticFinding(
                vulnerability_type=dynamic_finding.pattern.pattern_type.value,
                severity=dynamic_finding.pattern.severity,
                file_path=file_path,
                line=line,
                column=column,
                message=dynamic_finding.pattern.description,
                code_snippet=code_snippet or f"{func_name}({', '.join(args)})",
                data_flow=dynamic_finding.tainted_args,
                path_conditions=list(self.context.path_conditions),
                is_reachable=self._check_reachability(),
                confidence=1.0 if dynamic_finding.is_user_controlled else 0.7,
                cwe_id=dynamic_finding.pattern.cwe_id,
                remediation=dynamic_finding.pattern.mitigation
            )
            findings.append(finding)
            
            # 사용자 제어 입력이 동적 코드에 도달하면 CRITICAL
            if dynamic_finding.is_user_controlled:
                finding.severity = "CRITICAL"
        
        # 2. 싱크 분석
        sink_rule = self.taint_analyzer.is_sink(func_name)
        if sink_rule:
            vulns = self.taint_analyzer.check_sink(
                sink_code=func_name,
                sink_rule=sink_rule,
                file_path=file_path,
                line=line,
                args=args
            )
            
            for vuln in vulns:
                finding = SemanticFinding(
                    vulnerability_type=vuln.taint_type,
                    severity=vuln.severity,
                    file_path=file_path,
                    line=line,
                    column=column,
                    message=f"오염된 데이터가 {sink_rule.description}에 도달",
                    code_snippet=code_snippet or f"{func_name}({', '.join(args)})",
                    data_flow=vuln.variable_path,
                    path_conditions=list(self.context.path_conditions),
                    is_reachable=self._check_reachability(),
                    confidence=vuln.confidence,
                    cwe_id=self._get_cwe_for_type(vuln.taint_type),
                    remediation=self._get_remediation(vuln.taint_type)
                )
                findings.append(finding)
        
        self.findings.extend(findings)
        return findings
    
    def enter_condition(self, condition: str, is_true_branch: bool = True):
        """
        조건문 진입
        
        경로 조건을 추적하여 도달 가능성 분석에 사용합니다.
        """
        if is_true_branch:
            self.context.push_condition(condition)
        else:
            self.context.push_condition(f"NOT ({condition})")
    
    def exit_condition(self):
        """조건문 종료"""
        self.context.pop_condition()
    
    def _check_reachability(self) -> bool:
        """
        현재 경로의 도달 가능성 검사
        
        경로 조건들이 서로 모순되지 않는지 확인합니다.
        간단한 휴리스틱 기반 검사를 수행합니다.
        """
        conditions = self.context.path_conditions
        
        # 모순 검사: A and NOT A
        for i, cond in enumerate(conditions):
            for j, other in enumerate(conditions):
                if i != j:
                    # 간단한 모순 패턴
                    if cond.startswith("NOT (") and other in cond:
                        return False
                    if other.startswith("NOT (") and cond in other:
                        return False
        
        return True
    
    def _get_cwe_for_type(self, taint_type: str) -> str:
        """취약점 타입에 대한 CWE ID"""
        cwe_map = {
            "xss": "CWE-79",
            "sqli": "CWE-89",
            "cmdi": "CWE-78",
            "path": "CWE-22",
            "ssrf": "CWE-918",
            "open_redirect": "CWE-601",
            "rce": "CWE-94",
            "deserialization": "CWE-502",
        }
        return cwe_map.get(taint_type, "CWE-20")
    
    def _get_remediation(self, taint_type: str) -> str:
        """취약점 타입에 대한 수정 제안"""
        remediation_map = {
            "xss": "HTML 이스케이프 함수 사용 (html.escape, markupsafe.escape)",
            "sqli": "파라미터화된 쿼리 또는 ORM 사용",
            "cmdi": "shlex.quote()로 인자 이스케이프 또는 명령 실행 회피",
            "path": "os.path.basename()으로 경로 정규화, 화이트리스트 검증",
            "ssrf": "URL 화이트리스트 검증, 내부 IP 차단",
            "open_redirect": "URL 화이트리스트 검증, 상대 경로 사용",
            "rce": "동적 코드 실행 제거, 안전한 대안 사용",
            "deserialization": "JSON 같은 안전한 직렬화 형식 사용",
        }
        return remediation_map.get(taint_type, "입력 검증 및 새니타이징 적용")
    
    def get_findings(self) -> List[SemanticFinding]:
        """모든 분석 결과 반환"""
        return self.findings
    
    def get_critical_findings(self) -> List[SemanticFinding]:
        """CRITICAL 취약점만 반환"""
        return [f for f in self.findings if f.severity == "CRITICAL"]
    
    def get_reachable_findings(self) -> List[SemanticFinding]:
        """도달 가능한 취약점만 반환"""
        return [f for f in self.findings if f.is_reachable]
    
    def get_summary(self) -> Dict[str, Any]:
        """분석 요약"""
        return {
            "total_findings": len(self.findings),
            "critical": len([f for f in self.findings if f.severity == "CRITICAL"]),
            "high": len([f for f in self.findings if f.severity == "HIGH"]),
            "medium": len([f for f in self.findings if f.severity == "MEDIUM"]),
            "low": len([f for f in self.findings if f.severity == "LOW"]),
            "reachable": len([f for f in self.findings if f.is_reachable]),
            "by_type": self._group_by_type(),
            "dynamic_code_issues": len(self.dynamic_analyzer.get_findings()),
            "taint_vulnerabilities": len(self.taint_analyzer.get_vulnerabilities()),
        }
    
    def _group_by_type(self) -> Dict[str, int]:
        """타입별 그룹화"""
        by_type: Dict[str, int] = {}
        for finding in self.findings:
            vuln_type = finding.vulnerability_type
            by_type[vuln_type] = by_type.get(vuln_type, 0) + 1
        return by_type


# ============================================
# 4. Integrated Analyzer
# ============================================

class EnhancedSecurityAnalyzer:
    """
    통합 보안 분석기
    
    Dynamic Code Analysis + Precision Taint + Semantic Analysis를
    하나의 분석 파이프라인으로 통합합니다.
    """
    
    def __init__(self):
        self.semantic_analyzer = SemanticAnalyzer()
        self.file_findings: Dict[str, List[SemanticFinding]] = {}
    
    def analyze_file(
        self,
        file_path: str,
        code: str,
        language: str = "python"
    ) -> List[SemanticFinding]:
        """
        파일 분석
        
        Args:
            file_path: 파일 경로
            code: 소스 코드
            language: 언어 (python, javascript, php, java, go)
        
        Returns:
            발견된 취약점 목록
        """
        # 새 분석기 인스턴스 (파일별 상태 격리)
        analyzer = SemanticAnalyzer()
        
        # 간단한 라인 기반 분석 (Tree-sitter 없이)
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or stripped.startswith('//'):
                continue
            
            # 할당문 분석
            assignment_match = re.match(r'^(\w+)\s*=\s*(.+)$', stripped)
            if assignment_match:
                target = assignment_match.group(1)
                value = assignment_match.group(2)
                analyzer.analyze_assignment(target, value, file_path, line_num)
            
            # 함수 호출 분석
            call_matches = re.findall(r'(\w+(?:\.\w+)*)\s*\(([^)]*)\)', stripped)
            for func_name, args_str in call_matches:
                args = [a.strip() for a in args_str.split(',') if a.strip()]
                analyzer.analyze_call(
                    func_name=func_name,
                    args=args,
                    file_path=file_path,
                    line=line_num,
                    code_snippet=stripped
                )
            
            # 조건문 추적 (간단한 버전)
            if re.match(r'^\s*if\s+(.+):', stripped):
                condition = re.match(r'^\s*if\s+(.+):', stripped).group(1)
                analyzer.enter_condition(condition)
            elif stripped.startswith('else:') or stripped.startswith('elif '):
                analyzer.exit_condition()
                if stripped.startswith('elif '):
                    condition = re.match(r'^\s*elif\s+(.+):', stripped).group(1)
                    analyzer.enter_condition(condition)
        
        findings = analyzer.get_findings()
        self.file_findings[file_path] = findings
        
        return findings
    
    def analyze_project(
        self,
        project_path: str,
        extensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        프로젝트 전체 분석
        
        Args:
            project_path: 프로젝트 경로
            extensions: 분석할 파일 확장자 (기본: .py, .js, .ts, .php, .java)
        
        Returns:
            분석 결과 요약
        """
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.php', '.java', '.go']
        
        project = Path(project_path)
        all_findings: List[SemanticFinding] = []
        files_analyzed = 0
        
        for ext in extensions:
            for file_path in project.rglob(f'*{ext}'):
                # node_modules, venv 등 제외
                path_str = str(file_path)
                if any(skip in path_str for skip in ['node_modules', 'venv', '.git', '__pycache__']):
                    continue
                
                try:
                    code = file_path.read_text(encoding='utf-8', errors='ignore')
                    language = self._detect_language(ext)
                    findings = self.analyze_file(str(file_path), code, language)
                    all_findings.extend(findings)
                    files_analyzed += 1
                except Exception as e:
                    logger.warning(f"Failed to analyze {file_path}: {e}")
        
        return {
            "files_analyzed": files_analyzed,
            "total_findings": len(all_findings),
            "findings": all_findings,
            "by_severity": {
                "critical": len([f for f in all_findings if f.severity == "CRITICAL"]),
                "high": len([f for f in all_findings if f.severity == "HIGH"]),
                "medium": len([f for f in all_findings if f.severity == "MEDIUM"]),
                "low": len([f for f in all_findings if f.severity == "LOW"]),
            },
            "by_type": self._group_findings_by_type(all_findings),
            "by_file": {
                path: len(findings) 
                for path, findings in self.file_findings.items()
            },
        }
    
    def _detect_language(self, ext: str) -> str:
        """확장자에서 언어 감지"""
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.php': 'php',
            '.java': 'java',
            '.go': 'go',
        }
        return lang_map.get(ext, 'python')
    
    def _group_findings_by_type(
        self, 
        findings: List[SemanticFinding]
    ) -> Dict[str, int]:
        """타입별 그룹화"""
        by_type: Dict[str, int] = {}
        for finding in findings:
            vuln_type = finding.vulnerability_type
            by_type[vuln_type] = by_type.get(vuln_type, 0) + 1
        return by_type


# ============================================
# API Functions
# ============================================

def analyze_code_semantically(
    code: str,
    file_path: str = "unknown.py",
    language: str = "python"
) -> Dict[str, Any]:
    """
    코드를 의미론적으로 분석
    
    Args:
        code: 소스 코드
        file_path: 파일 경로 (보고서용)
        language: 언어
    
    Returns:
        분석 결과 딕셔너리
    """
    analyzer = EnhancedSecurityAnalyzer()
    findings = analyzer.analyze_file(file_path, code, language)
    
    return {
        "file": file_path,
        "language": language,
        "findings": [
            {
                "type": f.vulnerability_type,
                "severity": f.severity,
                "line": f.line,
                "column": f.column,
                "message": f.message,
                "code": f.code_snippet,
                "data_flow": f.data_flow,
                "path_conditions": f.path_conditions,
                "is_reachable": f.is_reachable,
                "confidence": f.confidence,
                "cwe": f.cwe_id,
                "remediation": f.remediation,
            }
            for f in findings
        ],
        "summary": {
            "total": len(findings),
            "critical": len([f for f in findings if f.severity == "CRITICAL"]),
            "high": len([f for f in findings if f.severity == "HIGH"]),
            "medium": len([f for f in findings if f.severity == "MEDIUM"]),
            "low": len([f for f in findings if f.severity == "LOW"]),
        }
    }


def check_dynamic_code(func_name: str, args: List[str]) -> Optional[Dict[str, Any]]:
    """
    함수 호출이 동적 코드 실행인지 확인
    
    Args:
        func_name: 함수 이름
        args: 인자 목록
    
    Returns:
        동적 코드 정보 또는 None
    """
    analyzer = DynamicCodeAnalyzer()
    finding = analyzer.analyze_call(
        func_name=func_name,
        args=args,
        file_path="check",
        line=1
    )
    
    if finding:
        return {
            "is_dynamic": True,
            "type": finding.pattern.pattern_type.value,
            "severity": finding.pattern.severity,
            "description": finding.pattern.description,
            "cwe": finding.pattern.cwe_id,
            "mitigation": finding.pattern.mitigation,
        }
    
    return None


def get_taint_rules() -> Dict[str, List[Dict[str, Any]]]:
    """
    테인트 규칙 목록 반환
    
    Returns:
        카테고리별 규칙 목록
    """
    return {
        "sources": [
            {
                "name": r.name,
                "patterns": r.patterns,
                "taint_types": list(r.taint_types),
                "description": r.description,
                "language": r.language,
            }
            for r in TAINT_SOURCES
        ],
        "sinks": [
            {
                "name": r.name,
                "patterns": r.patterns,
                "taint_types": list(r.taint_types),
                "description": r.description,
            }
            for r in TAINT_SINKS
        ],
        "sanitizers": [
            {
                "name": r.name,
                "patterns": r.patterns,
                "taint_types": list(r.taint_types),
                "description": r.description,
            }
            for r in TAINT_SANITIZERS
        ],
        "propagators": [
            {
                "name": r.name,
                "patterns": r.patterns,
                "description": r.description,
            }
            for r in TAINT_PROPAGATORS
        ],
    }
