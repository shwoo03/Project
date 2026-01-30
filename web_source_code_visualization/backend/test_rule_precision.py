#!/usr/bin/env python3
"""
Semgrep 규칙 정밀도 테스트 프레임워크

워게임/CTF 샘플을 기반으로 규칙의 정확도를 측정합니다.
"""

import json
import os
import sys

# Windows UTF-8 설정
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Finding:
    """탐지 결과"""
    rule_id: str
    line: int
    severity: str
    message: str
    code_snippet: str = ""


@dataclass
class TestResult:
    """테스트 결과"""
    sample_id: str
    sample_name: str
    level: str
    description: str
    expected_vulns: list
    detected_findings: list
    true_positives: list = field(default_factory=list)
    false_positives: list = field(default_factory=list)
    false_negatives: list = field(default_factory=list)


def load_metadata(sample_dir: Path) -> Optional[dict]:
    """metadata.json 로드"""
    metadata_path = sample_dir / "metadata.json"
    if not metadata_path.exists():
        return None
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_source_lines(sample_dir: Path) -> dict:
    """소스 코드 라인 읽기"""
    lines = {}
    for ext in ["*.py", "*.php", "*.js", "*.java", "*.html", "*.htm", "*.ts", "*.jsx", "*.tsx"]:
        for f in sample_dir.glob(ext):
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    lines[f.name] = file.readlines()
            except:
                pass
        # 하위 폴더도 검색
        for f in sample_dir.glob(f"**/{ext}"):
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    lines[f.name] = file.readlines()
            except:
                pass
    return lines


def run_semgrep(target_path: str, rules_path: str) -> dict:
    """Semgrep 실행"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_target = Path(temp_dir) / "target"
        temp_rules = Path(temp_dir) / "rules.yaml"
        
        if os.path.isdir(target_path):
            shutil.copytree(target_path, temp_target)
        else:
            temp_target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target_path, temp_target / Path(target_path).name)
            temp_target = temp_target / Path(target_path).name
        
        shutil.copy2(rules_path, temp_rules)
        
        # Ensure rules file is UTF-8 encoded (fix Korean encoding issue)
        with open(rules_path, 'r', encoding='utf-8') as f:
            rules_content = f.read()
        with open(temp_rules, 'w', encoding='utf-8') as f:
            f.write(rules_content)
        
        target_str = str(temp_target).replace('\\', '/')
        rules_str = str(temp_rules).replace('\\', '/')
        
        import io
        from contextlib import redirect_stdout, redirect_stderr
        
        # Set UTF-8 encoding for Windows
        old_env = os.environ.copy()
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONUTF8'] = '1'
        
        old_argv = sys.argv
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            sys.argv = ['semgrep', 'scan', '--config', rules_str, target_str, '--json']
            from semgrep.cli import cli
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                try:
                    cli()
                except SystemExit:
                    pass
        finally:
            sys.argv = old_argv
            os.environ.clear()
            os.environ.update(old_env)
        
        output = stdout_capture.getvalue()
        
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            stderr_out = stderr_capture.getvalue()
            return {"results": [], "error": f"JSON 파싱 오류: stdout={output[:100]} stderr={stderr_out[:200]}"}


def test_sample(sample_dir: Path, rules_path: Path) -> Optional[TestResult]:
    """단일 샘플 테스트"""
    metadata = load_metadata(sample_dir)
    if not metadata:
        print(f"  ⚠️ {sample_dir.name}: metadata.json 없음")
        return None
    
    source_lines = read_source_lines(sample_dir)
    if not source_lines:
        print(f"  ⚠️ {sample_dir.name}: 소스 파일 없음")
        return None
    
    # Semgrep 실행
    scan_result = run_semgrep(str(sample_dir), str(rules_path))
    
    if "error" in scan_result and scan_result.get("error"):
        print(f"  ❌ {sample_dir.name}: Semgrep 오류 - {scan_result['error'][:100]}")
        return None
    
    # 탐지 결과 파싱
    findings = []
    detected_rules = {}
    
    for f in scan_result.get("results", []):
        rule_id = f.get("check_id", "").split(".")[-1]
        line = f.get("start", {}).get("line", 0)
        severity = f.get("extra", {}).get("severity", "UNKNOWN")
        message = f.get("extra", {}).get("message", "")
        
        # 코드 스니펫 추출
        code_snippet = ""
        filename = Path(f.get("path", "")).name
        if filename in source_lines and line > 0:
            lines = source_lines[filename]
            if line <= len(lines):
                code_snippet = lines[line - 1].strip()
        
        finding = Finding(
            rule_id=rule_id,
            line=line,
            severity=severity,
            message=message,
            code_snippet=code_snippet
        )
        findings.append(finding)
        detected_rules[rule_id] = finding
    
    # 기대 취약점
    expected_vulns = metadata.get("vulnerabilities", [])
    expected_rules = {v.get("type"): v for v in expected_vulns}
    
    # TP/FP/FN 분류
    true_positives = []
    false_positives = []
    false_negatives = []
    
    for rule_id, finding in detected_rules.items():
        if rule_id in expected_rules:
            true_positives.append((rule_id, finding, expected_rules[rule_id]))
        else:
            false_positives.append((rule_id, finding))
    
    for rule_id, vuln in expected_rules.items():
        if rule_id not in detected_rules:
            false_negatives.append((rule_id, vuln))
    
    return TestResult(
        sample_id=metadata.get("id", sample_dir.name),
        sample_name=metadata.get("name", sample_dir.name),
        level=metadata.get("level", "unknown"),
        description=metadata.get("description", ""),
        expected_vulns=expected_vulns,
        detected_findings=findings,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives
    )


def test_level(level_dir: Path, rules_path: Path) -> list[TestResult]:
    """레벨 전체 테스트"""
    results = []
    
    if not level_dir.exists():
        return results
    
    for sample_dir in level_dir.iterdir():
        if sample_dir.is_dir():
            result = test_sample(sample_dir, rules_path)
            if result:
                results.append(result)
    
    return results


def print_results(results: list[TestResult]):
    """결과 출력 (한국어)"""
    if not results:
        print("\n❌ 테스트 결과 없음")
        return
    
    print("\n" + "=" * 80)
    print("📊 Semgrep 규칙 정밀도 테스트 결과")
    print("=" * 80)
    
    total_tp, total_fp, total_fn = 0, 0, 0
    
    for r in results:
        is_perfect = len(r.false_positives) == 0 and len(r.false_negatives) == 0
        status = "✅ 완벽" if is_perfect else "⚠️ 개선필요"
        
        print(f"\n{'─' * 80}")
        print(f"{status} [{r.level}] {r.sample_name}")
        print(f"   설명: {r.description}")
        print(f"{'─' * 80}")
        
        # 정탐 (True Positives)
        if r.true_positives:
            print(f"\n   ✅ 정탐 (올바르게 탐지됨): {len(r.true_positives)}건")
            for rule_id, finding, expected in r.true_positives:
                print(f"      📍 Line {finding.line}: {finding.message}")
                if finding.code_snippet:
                    print(f"         코드: {finding.code_snippet}")
        
        # 오탐 (False Positives)
        if r.false_positives:
            print(f"\n   ❌ 오탐 (잘못 탐지됨): {len(r.false_positives)}건")
            for rule_id, finding in r.false_positives:
                print(f"      📍 Line {finding.line}: {finding.message}")
                if finding.code_snippet:
                    print(f"         코드: {finding.code_snippet}")
        
        # 미탐 (False Negatives)
        if r.false_negatives:
            print(f"\n   ⚠️ 미탐 (놓친 취약점): {len(r.false_negatives)}건")
            for rule_id, vuln in r.false_negatives:
                print(f"      📍 Line {vuln.get('line', '?')}: {rule_id}")
                print(f"         설명: {vuln.get('description', 'N/A')}")
        
        total_tp += len(r.true_positives)
        total_fp += len(r.false_positives)
        total_fn += len(r.false_negatives)
    
    # 전체 통계
    print(f"\n{'=' * 80}")
    print("📈 전체 통계")
    print("=" * 80)
    print(f"   총 샘플 수: {len(results)}개")
    print(f"   ✅ 정탐 (True Positives): {total_tp}건")
    print(f"   ❌ 오탐 (False Positives): {total_fp}건")
    print(f"   ⚠️ 미탐 (False Negatives): {total_fn}건")
    
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\n   정밀도 (Precision): {precision:.1%}")
    print(f"   재현율 (Recall): {recall:.1%}")
    print(f"   F1 점수: {f1:.1%}")
    
    if total_fp == 0 and total_fn == 0:
        print("\n   🎉 모든 취약점을 정확하게 탐지했습니다!")
    elif total_fp > 0:
        print(f"\n   ⚠️ {total_fp}건의 오탐이 있습니다. 규칙 조정이 필요합니다.")
    elif total_fn > 0:
        print(f"\n   ⚠️ {total_fn}건의 취약점을 놓쳤습니다. 규칙 추가가 필요합니다.")
    
    print("=" * 80)


def main():
    backend_dir = Path(__file__).parent
    rules_path = backend_dir / "rules" / "custom_security.yaml"
    plob_dir = backend_dir.parent / "plob"
    
    if not rules_path.exists():
        print(f"❌ 규칙 파일 없음: {rules_path}")
        sys.exit(1)
    
    print("🔍 Semgrep 규칙 정밀도 테스트 시작...")
    print(f"   규칙 파일: {rules_path}")
    print(f"   샘플 디렉토리: {plob_dir}")
    
    all_results = []
    
    levels = ["beginner", "LEVEL1", "LEVEL2", "LEVEL3"]
    korean_levels = {"beginner": "새싹", "LEVEL1": "LEVEL1", "LEVEL2": "LEVEL2", "LEVEL3": "LEVEL3"}
    
    for level in levels:
        level_dir = plob_dir / korean_levels.get(level, level)
        if level_dir.exists():
            print(f"\n📁 레벨 테스트 중: {level}")
            results = test_level(level_dir, rules_path)
            all_results.extend(results)
    
    print_results(all_results)
    
    failed = sum(1 for r in all_results if r.false_positives or r.false_negatives)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
