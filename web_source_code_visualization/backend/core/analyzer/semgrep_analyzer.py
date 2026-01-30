import subprocess
import json
import os
import shutil
import tempfile
import sys
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

logger = logging.getLogger(__name__)

class SemgrepAnalyzer:
    """
    Semgrep 보안 스캐너 래퍼 클래스.
    
    Semgrep 1.38.0+ 에서 `python -m semgrep`이 deprecated되어
    semgrep.cli 모듈을 직접 호출하는 방식으로 변경.
    
    한글 경로 문제 해결:
    1. 임시 디렉토리로 복사 후 스캔
    2. 규칙 파일도 임시 디렉토리로 복사 (인코딩 문제 방지)
    """
    
    def __init__(self):
        self.python_path = sys.executable
        
    def _has_non_ascii(self, path: str) -> bool:
        """Check if path contains non-ASCII characters (e.g., Korean)."""
        try:
            path.encode('ascii')
            return False
        except UnicodeEncodeError:
            return True
            
    def _get_rules_path(self) -> str:
        """Get or create custom rules path."""
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "rules"
        )
        custom_rules_path = os.path.join(rules_dir, "custom_security.yaml")
        
        if not os.path.exists(custom_rules_path):
            os.makedirs(rules_dir, exist_ok=True)
            with open(custom_rules_path, 'w', encoding='utf-8') as f:
                f.write("rules: []\n")
        
        return custom_rules_path

    def _run_semgrep_cli(self, config_path: str, target_path: str, timeout: int = 300) -> Dict[str, Any]:
        """
        Semgrep CLI를 subprocess로 실행.
        
        semgrep.cli.cli()를 직접 호출하는 방식으로 deprecated 경고 회피.
        """
        # Windows 경로를 forward slash로 변환 (Python 문자열 이스케이프 문제 방지)
        config_path_safe = config_path.replace('\\', '/')
        target_path_safe = target_path.replace('\\', '/')
        
        # Python 코드로 semgrep CLI 직접 호출
        code = f'''
import sys
import os
import json

# UTF-8 모드 강제
os.environ['PYTHONUTF8'] = '1'

# sys.argv 설정
sys.argv = ['semgrep', 'scan', '--config={config_path_safe}', '--json', '--quiet', '{target_path_safe}']

# stdout을 캡처하기 위해 redirect
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

stdout_capture = StringIO()
stderr_capture = StringIO()

try:
    from semgrep.cli import cli
    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
        cli(standalone_mode=False)
except SystemExit:
    pass
except Exception as e:
    print(json.dumps({{"error": str(e)}}))

# JSON 출력만 추출
output = stdout_capture.getvalue()
# JSON 부분만 추출 (첫 번째 {{ 부터)
if '{{' in output:
    json_start = output.find('{{')
    print(output[json_start:])
'''
        
        try:
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            
            result = subprocess.run(
                [self.python_path, '-X', 'utf8', '-c', code],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                timeout=timeout,
                cwd=os.path.dirname(target_path) if os.path.isdir(target_path) else os.path.dirname(os.path.dirname(target_path))
            )
            
            # stdout에서 JSON 추출
            stdout = result.stdout.strip()
            if stdout and '{' in stdout:
                # JSON 시작 위치 찾기
                json_start = stdout.find('{')
                json_str = stdout[json_start:]
                return json.loads(json_str)
            
            # JSON이 없으면 빈 결과
            return {"results": [], "errors": []}
            
        except subprocess.TimeoutExpired:
            logger.error(f"Semgrep scan timed out after {timeout} seconds")
            return {"error": f"Scan timed out after {timeout} seconds"}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Semgrep JSON output: {e}")
            return {"error": f"JSON parse error: {e}"}
        except Exception as e:
            logger.error(f"Semgrep execution failed: {e}")
            return {"error": str(e)}

    def scan_project(self, project_path: str, timeout: int = 300) -> List[Dict[str, Any]]:
        """
        프로젝트 스캔 실행.
        
        Args:
            project_path: 스캔할 프로젝트 경로
            timeout: 최대 실행 시간 (초)
            
        Returns:
            발견된 취약점 목록
        """
        if not os.path.exists(project_path):
            return [{"error": "Project path does not exist"}]

        findings = []
        temp_dir = None
        scan_path = project_path
        rules_path = self._get_rules_path()
        temp_rules_path = rules_path
        
        try:
            # 임시 디렉토리 생성 (한글 경로 문제 해결)
            temp_dir = tempfile.mkdtemp(prefix="semgrep_scan_")
            
            # 규칙 파일 복사 (인코딩 문제 방지)
            temp_rules_path = os.path.join(temp_dir, "rules.yaml")
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules_content = f.read()
            with open(temp_rules_path, 'w', encoding='utf-8') as f:
                f.write(rules_content)
            
            # 프로젝트 복사 (한글 경로 또는 항상)
            scan_path = os.path.join(temp_dir, "project")
            shutil.copytree(project_path, scan_path, 
                          ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git', 'node_modules', 'venv', '.venv'))
            logger.info(f"Copied project to: {scan_path}")
            
            # Semgrep 실행
            data = self._run_semgrep_cli(temp_rules_path, scan_path, timeout)
            
            if "error" in data:
                return [{"error": data["error"]}]
            
            results = data.get("results", [])
            
            for r in results:
                # 원래 경로로 복원
                file_path = r.get("path", "")
                if file_path.startswith(scan_path):
                    relative_path = os.path.relpath(file_path, scan_path)
                    file_path = os.path.join(project_path, relative_path)
                
                findings.append({
                    "check_id": r.get("check_id"),
                    "path": file_path,
                    "line": r.get("start", {}).get("line"),
                    "col": r.get("start", {}).get("col"),
                    "message": r.get("extra", {}).get("message"),
                    "severity": r.get("extra", {}).get("severity"),
                    "lines": r.get("extra", {}).get("lines"),
                    "metadata": r.get("extra", {}).get("metadata", {})
                })
                    
        except Exception as e:
            logger.error(f"Semgrep execution failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [{"error": str(e)}]
        finally:
            # Clean up temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
            
        return findings
    
    def scan_with_registry(self, project_path: str, registry_rules: str = "p/python", 
                           timeout: int = 300) -> List[Dict[str, Any]]:
        """
        Semgrep 레지스트리 규칙으로 스캔.
        
        Args:
            project_path: 스캔할 프로젝트 경로
            registry_rules: Semgrep 레지스트리 규칙 (예: "p/python", "p/flask")
            timeout: 최대 실행 시간 (초)
        """
        if not os.path.exists(project_path):
            return [{"error": "Project path does not exist"}]
            
        findings = []
        temp_dir = None
        scan_path = project_path
        
        try:
            # 임시 디렉토리로 복사
            temp_dir = tempfile.mkdtemp(prefix="semgrep_scan_")
            scan_path = os.path.join(temp_dir, "project")
            shutil.copytree(project_path, scan_path,
                          ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git', 'node_modules', 'venv', '.venv'))
            
            # Windows 경로를 forward slash로 변환
            scan_path_safe = scan_path.replace('\\', '/')
            
            # Registry 규칙으로 스캔 (subprocess 사용)
            code = f'''
import sys
import os
import json
os.environ['PYTHONUTF8'] = '1'
sys.argv = ['semgrep', 'scan', '--config={registry_rules}', '--json', '--quiet', '{scan_path_safe}']
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
stdout_capture = StringIO()
stderr_capture = StringIO()
try:
    from semgrep.cli import cli
    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
        cli(standalone_mode=False)
except SystemExit:
    pass
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
output = stdout_capture.getvalue()
if '{{' in output:
    json_start = output.find('{{')
    print(output[json_start:])
'''
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1'
            
            result = subprocess.run(
                [self.python_path, '-X', 'utf8', '-c', code],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                timeout=timeout
            )
            
            stdout = result.stdout.strip()
            if stdout and '{' in stdout:
                json_start = stdout.find('{')
                data = json.loads(stdout[json_start:])
                
                for r in data.get("results", []):
                    file_path = r.get("path", "")
                    if file_path.startswith(scan_path):
                        relative_path = os.path.relpath(file_path, scan_path)
                        file_path = os.path.join(project_path, relative_path)
                    
                    findings.append({
                        "check_id": r.get("check_id"),
                        "path": file_path,
                        "line": r.get("start", {}).get("line"),
                        "col": r.get("start", {}).get("col"),
                        "message": r.get("extra", {}).get("message"),
                        "severity": r.get("extra", {}).get("severity"),
                        "lines": r.get("extra", {}).get("lines"),
                        "metadata": r.get("extra", {}).get("metadata", {})
                    })
                    
        except Exception as e:
            logger.error(f"Registry scan failed: {e}")
            return [{"error": str(e)}]
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        return findings


semgrep_analyzer = SemgrepAnalyzer()
