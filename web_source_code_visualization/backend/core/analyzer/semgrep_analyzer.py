import subprocess
import json
import os
import shutil
import tempfile
import sys
from typing import List, Dict, Any

class SemgrepAnalyzer:
    def __init__(self):
        # Use 'python -m semgrep' to avoid Korean path issues with .exe launchers
        self.python_path = sys.executable
        # Semgrep command will be: python -m semgrep scan ...

    def _has_non_ascii(self, path: str) -> bool:
        """Check if path contains non-ASCII characters (e.g., Korean)."""
        try:
            path.encode('ascii')
            return False
        except UnicodeEncodeError:
            return True

    def scan_project(self, project_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(project_path):
            return [{"error": "Project path does not exist"}]

        findings = []
        temp_dir = None
        scan_path = project_path
        
        try:
            # Handle non-ASCII paths by copying to temp directory
            if self._has_non_ascii(project_path):
                print(f"Detected non-ASCII path, copying to temp directory...")
                temp_dir = tempfile.mkdtemp(prefix="semgrep_scan_")
                scan_path = os.path.join(temp_dir, "project")
                shutil.copytree(project_path, scan_path)
                print(f"Copied to: {scan_path}")
            
            # Custom rules path
            custom_rules_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "rules", "custom_security.yaml")
            
            # If plain "semgrep scan" is run without config, it tries default. 
            # We want ONLY custom rules.
            if not os.path.exists(custom_rules_path):
                 # Create empty rules file if not exists to avoid errors
                 os.makedirs(os.path.dirname(custom_rules_path), exist_ok=True)
                 with open(custom_rules_path, 'w') as f:
                     f.write("rules: []\n")

            cmd = [
                self.python_path,
                "-m", "semgrep",
                "scan",
                "--json",
                f"--config={custom_rules_path}",
                scan_path
            ]
            
            print(f"Running Semgrep (Custom Only): {' '.join(cmd)}")
            
            # Run command
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='ignore',
                env=env
            )
            
            if result.returncode != 0 and result.stderr:
                 print(f"Semgrep Error: {result.stderr}")
            
            if result.stdout:
                data = json.loads(result.stdout)
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
                    
        except Exception as e:
            print(f"Semgrep execution failed: {e}")
            return [{"error": str(e)}]
        finally:
            # Clean up temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    print(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    print(f"Failed to clean up temp directory: {e}")
            
        return findings

semgrep_analyzer = SemgrepAnalyzer()
