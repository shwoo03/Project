import subprocess
import json
import os
import shutil
from typing import List, Dict, Any

class SemgrepAnalyzer:
    def __init__(self):
        # Check if semgrep is available in path
        self.semgrep_path = shutil.which("semgrep")
        if not self.semgrep_path:
            # Try to use the one in venv if not found globally
            venv_semgrep = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "venv", "Scripts", "semgrep.exe")
            if os.path.exists(venv_semgrep):
                self.semgrep_path = venv_semgrep
            else:
                 # Fallback to just 'semgrep' command hope it works
                self.semgrep_path = "semgrep"

    def scan_project(self, project_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(project_path):
            return [{"error": "Project path does not exist"}]

        findings = []
        try:
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
                self.semgrep_path,
                "scan",
                "--json",
                f"--config={custom_rules_path}",
                project_path
            ]
            
            print(f"Running Semgrep (Custom Only): {' '.join(cmd)}")
            
            # Run command
            # Creation flags for hiding console window on Windows if needed, but subprocess usually fine
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='ignore', # Handle encoding issues
                env=env
            )
            
            if result.returncode != 0 and result.stderr:
                 print(f"Semgrep Error: {result.stderr}")
                 # Sometimes semgrep returns exit code 1 if findings are found? 
                 # No, usually 0 success, 1 error. finding triggers exit code if --error flag used.
                 # Let's check output regardless.
            
            if result.stdout:
                data = json.loads(result.stdout)
                results = data.get("results", [])
                
                for r in results:
                    # Parse interesting fields
                    findings.append({
                        "check_id": r.get("check_id"),
                        "path": r.get("path"), # Relative path usually
                        "line": r.get("start", {}).get("line"),
                        "col": r.get("start", {}).get("col"),
                        "message": r.get("extra", {}).get("message"),
                        "severity": r.get("extra", {}).get("severity"), # ERROR, WARNING
                        "lines": r.get("extra", {}).get("lines")
                    })
                    
        except Exception as e:
            print(f"Semgrep execution failed: {e}")
            return [{"error": str(e)}]
            
        return findings

semgrep_analyzer = SemgrepAnalyzer()
