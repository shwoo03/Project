import subprocess
import json
import os
import shutil
import tempfile
import sys
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SemgrepAnalyzer:
    """
    Semgrep 보안 스캐너 래퍼 클래스.
    
    한글 경로 문제 해결:
    1. 임시 디렉토리로 복사 후 스캔
    2. --quiet 플래그로 stderr 경고 무시
    3. 직접 실행 파일 찾기 (semgrep.exe vs python -m semgrep)
    """
    
    def __init__(self):
        self.python_path = sys.executable
        self._semgrep_cmd = self._detect_semgrep_command()
        
    def _detect_semgrep_command(self) -> List[str]:
        """
        사용 가능한 Semgrep 실행 방법을 감지합니다.
        우선순위:
        1. 시스템 PATH의 semgrep (ASCII 경로에서만)
        2. python -m semgrep (deprecated 경고 있지만 작동)
        """
        # 현재 Python 경로가 ASCII인지 확인
        try:
            self.python_path.encode('ascii')
            python_is_ascii = True
        except UnicodeEncodeError:
            python_is_ascii = False
            
        # semgrep 실행 파일 검색
        semgrep_exe = shutil.which("semgrep")
        
        if semgrep_exe and python_is_ascii:
            # 직접 semgrep 실행 가능
            logger.info(f"Using direct semgrep: {semgrep_exe}")
            return [semgrep_exe]
        else:
            # python -m semgrep 사용 (fallback)
            logger.info("Using python -m semgrep (fallback mode)")
            return [self.python_path, "-m", "semgrep"]

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
        
        try:
            # Handle non-ASCII paths by copying to temp directory
            if self._has_non_ascii(project_path):
                logger.info(f"Detected non-ASCII path, copying to temp directory...")
                temp_dir = tempfile.mkdtemp(prefix="semgrep_scan_")
                scan_path = os.path.join(temp_dir, "project")
                shutil.copytree(project_path, scan_path, 
                              ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git', 'node_modules'))
                logger.info(f"Copied to: {scan_path}")
            
            custom_rules_path = self._get_rules_path()

            # Build command with --quiet to suppress deprecation warnings
            cmd = self._semgrep_cmd + [
                "scan",
                "--json",
                "--quiet",  # Suppress stderr warnings
                f"--config={custom_rules_path}",
                scan_path
            ]
            
            logger.info(f"Running Semgrep: {' '.join(cmd)}")
            
            # Run command with proper encoding
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace',  # Replace undecodable chars instead of ignoring
                env=env,
                timeout=timeout
            )
            
            # Handle errors - only log actual errors, ignore deprecation warnings
            if result.returncode != 0:
                stderr = result.stderr or ""
                # Filter out known non-critical warnings
                critical_errors = [
                    line for line in stderr.split('\n') 
                    if line.strip() and 
                    not any(w in line.lower() for w in ['deprecat', 'warning', 'info:'])
                ]
                if critical_errors:
                    logger.error(f"Semgrep errors: {critical_errors}")
            
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Semgrep output: {e}")
                    return [{"error": f"JSON parse error: {e}"}]
                    
                results = data.get("results", [])
                
                for r in results:
                    # Get path and restore original path if we used temp dir
                    file_path = r.get("path", "")
                    if temp_dir and file_path.startswith(scan_path):
                        # Replace temp path with original path
                        relative_path = os.path.relpath(file_path, scan_path)
                        file_path = os.path.join(project_path, relative_path)
                    
                    findings.append({
                        "check_id": r.get("check_id"),
                        "path": file_path,
                        "line": r.get("start", {}).get("line"),
                        "col": r.get("start", {}).get("col"),
                        "message": r.get("extra", {}).get("message"),
                        "severity": r.get("extra", {}).get("severity"),
                        "lines": r.get("extra", {}).get("lines")
                    })
                    
        except subprocess.TimeoutExpired:
            logger.error(f"Semgrep scan timed out after {timeout} seconds")
            return [{"error": f"Scan timed out after {timeout} seconds"}]
        except Exception as e:
            logger.error(f"Semgrep execution failed: {e}")
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
            if self._has_non_ascii(project_path):
                temp_dir = tempfile.mkdtemp(prefix="semgrep_scan_")
                scan_path = os.path.join(temp_dir, "project")
                shutil.copytree(project_path, scan_path,
                              ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git', 'node_modules'))
            
            cmd = self._semgrep_cmd + [
                "scan",
                "--json",
                "--quiet",
                f"--config={registry_rules}",
                scan_path
            ]
            
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                timeout=timeout
            )
            
            if result.stdout:
                data = json.loads(result.stdout)
                for r in data.get("results", []):
                    file_path = r.get("path", "")
                    if temp_dir and file_path.startswith(scan_path):
                        relative_path = os.path.relpath(file_path, scan_path)
                        file_path = os.path.join(project_path, relative_path)
                    
                    findings.append({
                        "check_id": r.get("check_id"),
                        "path": file_path,
                        "line": r.get("start", {}).get("line"),
                        "col": r.get("start", {}).get("col"),
                        "message": r.get("extra", {}).get("message"),
                        "severity": r.get("extra", {}).get("severity"),
                        "lines": r.get("extra", {}).get("lines")
                    })
                    
        except Exception as e:
            logger.error(f"Registry scan failed: {e}")
            return [{"error": str(e)}]
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        return findings


semgrep_analyzer = SemgrepAnalyzer()
