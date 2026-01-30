# File Download #1 - Path Traversal

## 개요
- **레벨**: 새싹 (beginner) / LEVEL1
- **출처**: Dreamhack
- **취약점**: Path Traversal (CWE-22)
- **난이도**: ⭐ (초급)

## 취약점 설명

파일 업로드/다운로드 기능에서 경로 검증이 불완전하여 Path Traversal 공격이 가능합니다.

### 취약한 코드

```python
# /upload 엔드포인트 (Line 32)
filename = request.form.get('filename')
if filename.find('..') != -1:  # 필터링 있음
    return render_template('upload_result.html', data='bad characters,,')
with open(f'{UPLOAD_DIR}/{filename}', 'wb') as f:
    f.write(content)

# /read 엔드포인트 (Line 50) - 실제 취약점
filename = request.args.get('name', '')  # 필터링 없음!
with open(f'{UPLOAD_DIR}/{filename}', 'rb') as f:
    data = f.read()
```

## 공격 시나리오

1. `/upload`에는 `..` 필터링이 있어서 직접 공격 불가
2. `/read`에는 필터링이 없어서 Path Traversal 가능
3. 공격자는 `../`를 사용해 상위 디렉터리 접근

### 공격 예시

```
GET /read?name=../flag.py
```

이를 통해 `flag.py` 파일의 내용을 읽을 수 있습니다:
```
DH{uploading_webshell_in_python_program_is_my_dream}
```

## Root Cause

- **Line 49-50**: `request.args.get('name')`으로 받은 사용자 입력을 검증 없이 `open()` 함수에 직접 사용
- `..` 문자열 검증이 없어서 디렉터리 탐색 가능
- 경로 정규화 및 범위 검증 부재

## 방어법

### ❌ 잘못된 방어 (우회 가능)

```python
if '..' in filename:  # 단순 문자열 검사
    return "Invalid", 403
```

**우회**: URL 인코딩 `%2e%2e/`, 이중 인코딩 등

### ✅ 올바른 방어

```python
import os

filename = request.args.get('name', '')
base_dir = os.path.abspath(UPLOAD_DIR)
target_path = os.path.abspath(os.path.join(base_dir, filename))

# 절대 경로 검증
if not target_path.startswith(base_dir):
    return "Invalid Access", 403

with open(target_path, 'rb') as f:
    data = f.read()
```

**핵심**:
1. `os.path.abspath()`: 상대 경로를 절대 경로로 변환 (../ 해석 포함)
2. `startswith()`: 정규화된 경로가 허용된 디렉터리 내부인지 확인
3. 모든 경로 조작 시도 차단

## Semgrep 탐지

### 규칙: path-traversal-taint-flask

```yaml
- id: path-traversal-taint-flask
  languages: [python]
  severity: ERROR
  message: "[PATH-001] 사용자 입력이 파일 경로에 사용됨 - 경로 탐색 취약점 의심"
  mode: taint
  pattern-sources:
    - patterns:
        - pattern-either:
            - pattern: request.args.get(...)
            - pattern: request.form.get(...)
  pattern-sinks:
    - patterns:
        - pattern-either:
            - pattern: open($PATH, ...)
  pattern-sanitizers:
    - patterns:
        - pattern-either:
            - pattern: os.path.basename($VAR)
```

### 탐지 결과

- ✅ **Line 32**: `/upload` - 필터링 있으나 Semgrep이 정적 분석으로 탐지
- ✅ **Line 50**: `/read` - **실제 취약점** 탐지

## 테스트

```powershell
cd backend
python test_file_download_1.py
```

**기대 결과**: 2개 탐지 (Line 32, Line 50)

## 참고

- **CWE-22**: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
- **OWASP A01:2021**: Broken Access Control
- **MITRE ATT&CK**: T1083 (File and Directory Discovery)

## 학습 포인트

1. ⚠️ 단순 문자열 필터링(`find('..')`)은 우회 가능
2. ✅ `os.path.abspath()` + `startswith()` 조합으로 안전한 검증
3. 📝 입력 검증은 모든 엔드포인트에서 일관되게 수행
4. 🔍 정적 분석 도구(Semgrep)는 방어 코드를 완전히 이해하지 못할 수 있음 → 수동 검증 필요
