"""
Enhanced Security Analyzer 테스트

Dynamic Code Analysis + Precision Taint + Semantic Analysis 테스트
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.enhanced_security_analyzer import (
    DynamicCodeAnalyzer,
    DynamicCodeType,
    PrecisionTaintAnalyzer,
    TaintCategory,
    SemanticAnalyzer,
    EnhancedSecurityAnalyzer,
    analyze_code_semantically,
    check_dynamic_code,
    get_taint_rules,
    DYNAMIC_CODE_PATTERNS,
    TAINT_SOURCES,
    TAINT_SINKS,
    TAINT_SANITIZERS,
)


class TestDynamicCodeAnalyzer:
    """동적 코드 분석기 테스트"""
    
    def test_eval_detection(self):
        """eval() 탐지 테스트"""
        analyzer = DynamicCodeAnalyzer()
        
        finding = analyzer.analyze_call(
            func_name="eval",
            args=["user_input"],
            file_path="test.py",
            line=10,
            tainted_vars={"user_input"}
        )
        
        assert finding is not None
        assert finding.pattern.pattern_type == DynamicCodeType.EVAL
        assert finding.pattern.severity == "CRITICAL"
        assert finding.is_user_controlled == True
        assert "user_input" in finding.tainted_args
    
    def test_exec_detection(self):
        """exec() 탐지 테스트"""
        analyzer = DynamicCodeAnalyzer()
        
        finding = analyzer.analyze_call(
            func_name="exec",
            args=["code"],
            file_path="test.py",
            line=15
        )
        
        assert finding is not None
        assert finding.pattern.pattern_type == DynamicCodeType.EXEC
        assert finding.pattern.cwe_id == "CWE-95"
    
    def test_compile_detection(self):
        """compile() 탐지 테스트"""
        analyzer = DynamicCodeAnalyzer()
        
        finding = analyzer.analyze_call(
            func_name="compile",
            args=["code", "'<string>'", "'exec'"],
            file_path="test.py",
            line=20
        )
        
        assert finding is not None
        assert finding.pattern.pattern_type == DynamicCodeType.COMPILE
    
    def test_import_module_detection(self):
        """importlib.import_module() 탐지 테스트"""
        analyzer = DynamicCodeAnalyzer()
        
        finding = analyzer.analyze_call(
            func_name="importlib.import_module",
            args=["module_name"],
            file_path="test.py",
            line=25,
            tainted_vars={"module_name"}
        )
        
        assert finding is not None
        assert finding.pattern.pattern_type == DynamicCodeType.IMPORT
        assert finding.is_user_controlled == True
    
    def test_getattr_detection(self):
        """getattr() 탐지 테스트"""
        analyzer = DynamicCodeAnalyzer()
        
        finding = analyzer.analyze_call(
            func_name="getattr",
            args=["obj", "attr_name"],
            file_path="test.py",
            line=30,
            tainted_vars={"attr_name"}
        )
        
        assert finding is not None
        assert finding.pattern.pattern_type == DynamicCodeType.GETATTR
        assert finding.pattern.severity == "MEDIUM"
    
    def test_pickle_loads_detection(self):
        """pickle.loads() 탐지 테스트"""
        analyzer = DynamicCodeAnalyzer()
        
        finding = analyzer.analyze_call(
            func_name="pickle.loads",
            args=["data"],
            file_path="test.py",
            line=35,
            tainted_vars={"data"}
        )
        
        assert finding is not None
        assert finding.pattern.pattern_type == DynamicCodeType.DESERIALIZATION
        assert finding.pattern.severity == "CRITICAL"
    
    def test_yaml_safe_load_not_detected(self):
        """yaml.load with SafeLoader는 탐지하지 않음"""
        analyzer = DynamicCodeAnalyzer()
        
        # 안전한 로더 사용 시
        finding = analyzer.analyze_call(
            func_name="yaml.load",
            args=["data", "Loader=yaml.SafeLoader"],
            file_path="test.py",
            line=40
        )
        
        # SafeLoader 사용 시 탐지되지 않아야 함
        assert finding is None
    
    def test_yaml_unsafe_load_detected(self):
        """yaml.load without SafeLoader 탐지"""
        analyzer = DynamicCodeAnalyzer()
        
        finding = analyzer.analyze_call(
            func_name="yaml.load",
            args=["data"],
            file_path="test.py",
            line=45
        )
        
        assert finding is not None
        assert finding.pattern.severity == "CRITICAL"
    
    def test_setTimeout_string_detection(self):
        """setTimeout(string) 탐지 (JavaScript)"""
        analyzer = DynamicCodeAnalyzer()
        
        finding = analyzer.analyze_call(
            func_name="setTimeout",
            args=['"alert(1)"', "1000"],
            file_path="test.js",
            line=50
        )
        
        assert finding is not None
        assert finding.pattern.pattern_type == DynamicCodeType.EVAL
    
    def test_setTimeout_function_not_detected(self):
        """setTimeout(function) 탐지하지 않음"""
        analyzer = DynamicCodeAnalyzer()
        
        finding = analyzer.analyze_call(
            func_name="setTimeout",
            args=["myFunction", "1000"],  # 함수 참조
            file_path="test.js",
            line=55
        )
        
        # 함수 참조는 안전
        assert finding is None
    
    def test_get_critical_findings(self):
        """CRITICAL 결과만 필터링"""
        analyzer = DynamicCodeAnalyzer()
        
        # CRITICAL: eval
        analyzer.analyze_call("eval", ["x"], "test.py", 1)
        # MEDIUM: getattr
        analyzer.analyze_call("getattr", ["obj", "x"], "test.py", 2)
        # CRITICAL: pickle
        analyzer.analyze_call("pickle.loads", ["data"], "test.py", 3)
        
        critical = analyzer.get_critical_findings()
        assert len(critical) == 2  # eval, pickle
    
    def test_get_user_controlled_findings(self):
        """사용자 입력 도달 결과만 필터링"""
        analyzer = DynamicCodeAnalyzer()
        tainted = {"user_input"}
        
        # 오염된 입력
        analyzer.analyze_call("eval", ["user_input"], "test.py", 1, tainted_vars=tainted)
        # 오염되지 않은 입력
        analyzer.analyze_call("eval", ["safe_code"], "test.py", 2, tainted_vars=tainted)
        
        user_controlled = analyzer.get_user_controlled_findings()
        assert len(user_controlled) == 1


class TestPrecisionTaintAnalyzer:
    """정밀 테인트 분석기 테스트"""
    
    def test_source_detection(self):
        """소스 탐지 테스트"""
        analyzer = PrecisionTaintAnalyzer()
        
        # Flask request.args
        rule = analyzer.is_source("request.args.get('id')")
        assert rule is not None
        assert "xss" in rule.taint_types
        assert "sqli" in rule.taint_types
    
    def test_sink_detection(self):
        """싱크 탐지 테스트"""
        analyzer = PrecisionTaintAnalyzer()
        
        # os.system
        rule = analyzer.is_sink("os.system")
        assert rule is not None
        assert "cmdi" in rule.taint_types
    
    def test_sanitizer_detection(self):
        """새니타이저 탐지 테스트"""
        analyzer = PrecisionTaintAnalyzer()
        
        # XSS 새니타이저
        rule = analyzer.is_sanitizer("html.escape(x)", "xss")
        assert rule is not None
        assert "xss" in rule.taint_types
    
    def test_taint_variable(self):
        """변수 오염 테스트"""
        analyzer = PrecisionTaintAnalyzer()
        
        source_rule = analyzer.is_source("request.args.get('id')")
        analyzer.taint_variable("user_id", source_rule, "request.args.get('id')", 10)
        
        assert "user_id" in analyzer.taint_states
        state = analyzer.taint_states["user_id"]
        assert state.is_tainted == True
        assert "xss" in state.taint_types
    
    def test_taint_propagation(self):
        """테인트 전파 테스트"""
        analyzer = PrecisionTaintAnalyzer()
        
        # 소스에서 오염
        source_rule = analyzer.is_source("request.args.get('id')")
        analyzer.taint_variable("user_id", source_rule, "request.args.get('id')", 10)
        
        # 전파
        result = analyzer.propagate_taint("cmd", "f'ls {user_id}'", 15)
        assert result == True
        
        assert "cmd" in analyzer.taint_states
        state = analyzer.taint_states["cmd"]
        assert state.is_tainted == True
    
    def test_sanitizer_application(self):
        """새니타이저 적용 테스트"""
        analyzer = PrecisionTaintAnalyzer()
        
        # 오염
        source_rule = analyzer.is_source("request.args.get('name')")
        analyzer.taint_variable("name", source_rule, "request.args.get('name')", 10)
        
        # 새니타이저 적용
        sanitizer_rule = analyzer.is_sanitizer("html.escape(name)", "xss")
        analyzer.apply_sanitizer("name", sanitizer_rule, 15)
        
        state = analyzer.taint_states["name"]
        assert "xss" in state.sanitized_for
        assert "xss" not in state.taint_types  # XSS 타입은 제거됨
    
    def test_sink_check(self):
        """싱크 도달 검사 테스트"""
        analyzer = PrecisionTaintAnalyzer()
        
        # 오염
        source_rule = analyzer.is_source("request.args.get('cmd')")
        analyzer.taint_variable("cmd", source_rule, "request.args.get('cmd')", 10)
        
        # 싱크 검사
        sink_rule = analyzer.is_sink("os.system")
        vulns = analyzer.check_sink(
            sink_code="os.system",
            sink_rule=sink_rule,
            file_path="test.py",
            line=20,
            args=["cmd"]
        )
        
        assert len(vulns) > 0
        assert vulns[0].taint_type == "cmdi"


class TestSemanticAnalyzer:
    """의미론적 분석기 테스트"""
    
    def test_assignment_analysis(self):
        """할당문 분석 테스트"""
        analyzer = SemanticAnalyzer()
        
        # 소스 할당
        analyzer.analyze_assignment(
            target="user_input",
            value_code="request.args.get('id')",
            file_path="test.py",
            line=10
        )
        
        assert "user_input" in analyzer.taint_analyzer.taint_states
    
    def test_call_analysis_dynamic_code(self):
        """함수 호출 분석 - 동적 코드"""
        analyzer = SemanticAnalyzer()
        
        # 오염
        analyzer.analyze_assignment("user_input", "request.args.get('code')", "test.py", 10)
        
        # eval 호출
        findings = analyzer.analyze_call(
            func_name="eval",
            args=["user_input"],
            file_path="test.py",
            line=15,
            code_snippet="eval(user_input)"
        )
        
        assert len(findings) > 0
        assert findings[0].vulnerability_type == "eval"
        assert findings[0].severity == "CRITICAL"
    
    def test_call_analysis_sink(self):
        """함수 호출 분석 - 싱크"""
        analyzer = SemanticAnalyzer()
        
        # 오염
        analyzer.analyze_assignment("cmd", "request.args.get('cmd')", "test.py", 10)
        
        # 싱크 호출
        findings = analyzer.analyze_call(
            func_name="os.system",
            args=["cmd"],
            file_path="test.py",
            line=15,
            code_snippet="os.system(cmd)"
        )
        
        assert len(findings) > 0
        assert findings[0].vulnerability_type == "cmdi"
    
    def test_condition_tracking(self):
        """조건 추적 테스트"""
        analyzer = SemanticAnalyzer()
        
        analyzer.enter_condition("user.is_admin")
        assert len(analyzer.context.path_conditions) == 1
        
        analyzer.enter_condition("user.role == 'admin'")
        assert len(analyzer.context.path_conditions) == 2
        
        analyzer.exit_condition()
        assert len(analyzer.context.path_conditions) == 1
    
    def test_reachability_check(self):
        """도달 가능성 검사 테스트"""
        analyzer = SemanticAnalyzer()
        
        # 모순 없는 경로
        analyzer.enter_condition("x > 0")
        analyzer.enter_condition("y > 0")
        assert analyzer._check_reachability() == True
    
    def test_get_summary(self):
        """요약 테스트"""
        analyzer = SemanticAnalyzer()
        
        analyzer.analyze_assignment("x", "request.args.get('x')", "test.py", 1)
        analyzer.analyze_call("eval", ["x"], "test.py", 2)
        
        summary = analyzer.get_summary()
        assert summary["total_findings"] > 0
        assert "dynamic_code_issues" in summary
        assert "taint_vulnerabilities" in summary


class TestEnhancedSecurityAnalyzer:
    """통합 분석기 테스트"""
    
    def test_analyze_file(self):
        """파일 분석 테스트"""
        analyzer = EnhancedSecurityAnalyzer()
        
        code = """
from flask import request
import os

@app.route('/exec')
def dangerous():
    cmd = request.args.get('cmd')
    os.system(cmd)
"""
        
        findings = analyzer.analyze_file("test.py", code, "python")
        
        # 동적 코드 또는 테인트 취약점 발견
        assert len(findings) > 0
    
    def test_analyze_file_with_sanitizer(self):
        """새니타이저가 있는 파일 분석"""
        analyzer = EnhancedSecurityAnalyzer()
        
        code = """
from flask import request
import html

@app.route('/safe')
def safe():
    name = request.args.get('name')
    safe_name = html.escape(name)
    return f"Hello {safe_name}"
"""
        
        findings = analyzer.analyze_file("test.py", code, "python")
        # 새니타이저 적용으로 취약점이 적거나 없어야 함
    
    def test_language_detection(self):
        """언어 감지 테스트"""
        analyzer = EnhancedSecurityAnalyzer()
        
        assert analyzer._detect_language('.py') == 'python'
        assert analyzer._detect_language('.js') == 'javascript'
        assert analyzer._detect_language('.ts') == 'typescript'
        assert analyzer._detect_language('.php') == 'php'
        assert analyzer._detect_language('.java') == 'java'
        assert analyzer._detect_language('.go') == 'go'


class TestAPIFunctions:
    """API 함수 테스트"""
    
    def test_analyze_code_semantically(self):
        """코드 의미론적 분석 API"""
        code = """
user = request.args.get('user')
eval(user)
"""
        
        result = analyze_code_semantically(code, "test.py", "python")
        
        assert "file" in result
        assert "findings" in result
        assert "summary" in result
        assert result["summary"]["total"] > 0
    
    def test_check_dynamic_code(self):
        """동적 코드 확인 API"""
        result = check_dynamic_code("eval", ["user_input"])
        
        assert result is not None
        assert result["is_dynamic"] == True
        assert result["type"] == "eval"
        assert result["severity"] == "CRITICAL"
    
    def test_check_dynamic_code_safe(self):
        """안전한 함수 확인 API"""
        result = check_dynamic_code("print", ["hello"])
        
        assert result is None
    
    def test_get_taint_rules(self):
        """테인트 규칙 목록 API"""
        rules = get_taint_rules()
        
        assert "sources" in rules
        assert "sinks" in rules
        assert "sanitizers" in rules
        assert "propagators" in rules
        
        assert len(rules["sources"]) > 0
        assert len(rules["sinks"]) > 0
        assert len(rules["sanitizers"]) > 0


class TestPatternCoverage:
    """패턴 커버리지 테스트"""
    
    def test_dynamic_code_patterns_exist(self):
        """동적 코드 패턴이 존재하는지 확인"""
        assert len(DYNAMIC_CODE_PATTERNS) >= 15
        
        types = {p.pattern_type for p in DYNAMIC_CODE_PATTERNS}
        assert DynamicCodeType.EVAL in types
        assert DynamicCodeType.EXEC in types
        assert DynamicCodeType.IMPORT in types
        assert DynamicCodeType.GETATTR in types
        assert DynamicCodeType.DESERIALIZATION in types
    
    def test_taint_sources_exist(self):
        """테인트 소스가 존재하는지 확인"""
        assert len(TAINT_SOURCES) >= 10
        
        # Flask 소스
        flask_sources = [s for s in TAINT_SOURCES if "flask" in s.name.lower()]
        assert len(flask_sources) >= 5
        
        # Django 소스
        django_sources = [s for s in TAINT_SOURCES if "django" in s.name.lower()]
        assert len(django_sources) >= 1
    
    def test_taint_sinks_exist(self):
        """테인트 싱크가 존재하는지 확인"""
        assert len(TAINT_SINKS) >= 5
        
        sink_types = set()
        for sink in TAINT_SINKS:
            sink_types.update(sink.taint_types)
        
        assert "rce" in sink_types
        assert "cmdi" in sink_types
        assert "sqli" in sink_types
        assert "xss" in sink_types
    
    def test_taint_sanitizers_exist(self):
        """테인트 새니타이저가 존재하는지 확인"""
        assert len(TAINT_SANITIZERS) >= 5
        
        sanitizer_types = set()
        for san in TAINT_SANITIZERS:
            sanitizer_types.update(san.taint_types)
        
        assert "xss" in sanitizer_types
        assert "sqli" in sanitizer_types
        assert "cmdi" in sanitizer_types


class TestEdgeCases:
    """엣지 케이스 테스트"""
    
    def test_empty_code(self):
        """빈 코드 분석"""
        analyzer = EnhancedSecurityAnalyzer()
        findings = analyzer.analyze_file("test.py", "", "python")
        assert findings == []
    
    def test_comments_only(self):
        """주석만 있는 코드"""
        analyzer = EnhancedSecurityAnalyzer()
        code = """
# This is a comment
# Another comment
"""
        findings = analyzer.analyze_file("test.py", code, "python")
        assert findings == []
    
    def test_no_vulnerabilities(self):
        """취약점 없는 코드"""
        analyzer = EnhancedSecurityAnalyzer()
        code = """
def safe_function(x):
    return x + 1

result = safe_function(10)
"""
        findings = analyzer.analyze_file("test.py", code, "python")
        assert len(findings) == 0
    
    def test_multiline_call(self):
        """여러 줄에 걸친 호출"""
        analyzer = EnhancedSecurityAnalyzer()
        code = """
cmd = request.args.get('cmd')
os.system(cmd)
"""
        findings = analyzer.analyze_file("test.py", code, "python")
        # 여러 줄 분석도 작동해야 함


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
