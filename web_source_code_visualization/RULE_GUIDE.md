# Semgrep Rule Learning System

## 디렉터리 구조

```
plob/
├── 새싹/              # 초급 (beginner)
│   └── sample_name/
│       ├── app.py           # 취약한 코드
│       └── metadata.json    # 기대 탐지 결과
├── LEVEL1/            # 중급
├── LEVEL2/            # 고급
└── LEVEL3/            # 전문가

backend/rules/
└── custom_security.yaml   # Semgrep 규칙
```

---

## 샘플 추가 방법

### 1. 디렉터리 생성
plob/<레벨>/<문제이름>/
├── app.py (또는 .js, .php 등)
└── metadata.json

**⚠️ 중요: 불필요한 중복 파일 생성 금지**
- `e.py`, `check.php`, `test.py` 등 테스트용 임시 파일을 디렉터리에 남기지 마세요.
- 동일한 내용의 파일이 있으면 분석 도구가 중복으로 취약점을 탐지합니다.
- 반드시 문제 해결에 필요한 소스 파일 하나와 `metadata.json`만 유지하세요.
```

### 2. metadata.json 형식
```json
{
    "id": "문제이름",
    "name": "표시 이름",
    "level": "새싹|LEVEL1|LEVEL2|LEVEL3",
    "source": "dreamhack|hackthebox|ctf",
    "description": "취약점 설명",
    "vulnerabilities": [
        {
            "type": "규칙-id",
            "line": 18,
            "severity": "ERROR|WARNING",
            "description": "취약점 상세 설명"
        }
    ],
    "expected_findings": 1
}
```

### 3. custom_security.yaml에 규칙 추가
```yaml
- id: rule-id
  languages: [python]
  severity: ERROR
  message: "[ID] 취약점 설명 - 취약점 의심"
  
  # 단순 패턴
  pattern: dangerous_function(...)
  
  # 또는 Taint 모드 (인젝션용)
  mode: taint
  pattern-sources:
    - pattern: request.args.get(...)
  pattern-sinks:
    - pattern: dangerous_function($VAR)
  
  metadata:
    level: beginner
```

---

## 테스트 방법

### 1단계: 규칙 정밀도 테스트 (CLI)
```powershell
cd backend
.\venv\Scripts\python.exe test_rule_precision.py
```

**확인 항목:**
- ✅ 정탐 (True Positives): 올바르게 탐지된 취약점
- ❌ 오탐 (False Positives): 잘못 탐지된 항목
- ⚠️ 미탐 (False Negatives): 놓친 취약점
- 📊 정밀도/재현율/F1 점수

### 2단계: 시각화 도구에서 노드 확인

1. **백엔드 서버 시작**
```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

2. **프론트엔드 서버 시작**
```powershell
cd frontend
npm run dev
```

3. **브라우저에서 확인** (http://localhost:3000)
   - 프로젝트 경로에 샘플 폴더 입력 (예: `plob/새싹/cookie`)
   - **▶ 시각화** 버튼 클릭 → 노드 그래프 생성
   - **🛡️ 보안 스캔** 버튼 클릭 → 취약점 탐지

4. **탐지 결과 확인**
     - 🔴 **빨간 노드**: 취약점이 발견된 파일
     - 노드 클릭 시 **상세 패널**에서:
       - 🚨 보안 취약점 발견 (N개)
       - 규칙 ID, 심각도, 메시지, 라인 번호

5. **오탐 및 중복 관찰 (Observation)**
   - 예: `AUTH-001`이 정상적인 세션 조회 코드에서 발생하는지 확인
   - 예: 동일한 취약점이 여러 번 중복되어 뜨는지 확인 (중복 파일 여부 체크)
   - 잘못된 사용자 입력 값 결과가 나오는지 확인
   - 발견된 문제는 즉시 수정하고 `metadata.json`이나 규칙을 업데이트하여 반영

---

## 전체 검증 체크리스트

테스트 시 반드시 다음을 확인하세요:

| 확인 항목 | 방법 | 기대 결과 |
|-----------|------|----------|
| CLI 탐지 정확도 | `test_rule_precision.py` 실행 | 100% 정밀도/재현율 |
| 노드 그래프 표시 | 시각화 버튼 클릭 | 모든 파일이 노드로 표시됨 |
| 취약점 노드 강조 | 보안 스캔 클릭 | 취약 파일이 빨간색으로 변경 |
| 상세 패널 정보 | 빨간 노드 클릭 | 취약점 목록, 라인 번호 표시 |
| 메시지 한국어 | 상세 패널 확인 | "취약점 의심" 형식 메시지 |

---

## 규칙 레벨

| 레벨 | 취약점 유형 | 샘플 예제 |
|------|------------|-----------|
| 새싹 (beginner) | Cookie, Debug, Hardcoded, 주석 정보노출 | cookie, file-download-1 |
| LEVEL1 | SQLi, XSS, CMDI, Path Traversal | file-download-1 |
| LEVEL2 | Deserialization, SSRF | - |
| LEVEL3 | Race Condition, Complex chains | - |

### 샘플 예제 설명

#### file-download-1 (새싹/LEVEL1)
- **취약점**: Path Traversal (CWE-22)
- **설명**: 파일 다운로드 기능에서 경로 검증 누락
- **탐지 규칙**: `path-traversal-taint-flask`
- **탐지 라인**: Line 32 (/upload - 필터링 있음), Line 50 (/read - 필터링 없음, 실제 취약점)
- **공격 예시**: `/read?name=../flag.py`
- **테스트**: `python test_file_download_1.py`

---

## 문제 해결

### 노드가 안 보일 때
1. 프로젝트 경로가 올바른지 확인
2. 파일 확장자가 지원되는지 확인 (.py, .js, .php, .html 등)
3. 백엔드 콘솔에서 오류 메시지 확인

### 취약점이 탐지 안 될 때
1. `test_rule_precision.py`로 규칙이 동작하는지 확인
2. `custom_security.yaml`에 해당 언어가 포함되어 있는지 확인
3. Semgrep 버전 확인: `semgrep --version` (1.149.0+ 권장)

### 한글 인코딩 오류
스크립트 시작 부분에 다음 환경변수 설정:
```python
import os
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
```

---

## 파서 검증 (Parser Validation)

Semgrep 규칙 외에도 파서가 올바르게 동작하는지 확인이 필요합니다.

### 파서 검증 항목

| 검증 항목 | 설명 | 예시 |
|-----------|------|------|
| **사용자 입력 감지** | `request.form.get('param')` 등에서 'param' 추출 | `content`, `filename` |
| **체이닝 메서드 무시** | `.encode()`, `.strip()` 등 후처리 메서드의 인자 제외 | `'utf-8'`은 제외 |
| **소스 유형 구분** | GET/POST/COOKIE/HEADER 등 정확한 분류 | `request.args.get` → GET |
| **경로 파라미터 감지** | URL 패턴에서 `<param>` 추출 | `/user/<id>` → PATH |

### 파서 테스트 스크립트

```python
# backend/test_parser_validation.py
"""파서 정확도 테스트"""
from core.parser.python import PythonParser

def test_chained_method_call():
    """체이닝된 메서드 호출에서 잘못된 입력 감지 방지"""
    code = '''
from flask import Flask, request
app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload():
    content = request.form.get('content').encode('utf-8')
    filename = request.form.get('filename').strip()
    return "OK"
'''
    parser = PythonParser()
    endpoints = parser.parse("test.py", code)
    
    all_inputs = []
    for ep in endpoints:
        for child in ep.children:
            if child.type == 'input':
                all_inputs.append(child.path)
    
    # 올바른 입력만 감지되어야 함
    assert 'content' in all_inputs, "content 입력이 감지되어야 함"
    assert 'filename' in all_inputs, "filename 입력이 감지되어야 함"
    assert 'utf-8' not in all_inputs, "utf-8은 입력이 아님 (오탐)"
    assert len([x for x in all_inputs if x not in ['content', 'filename']]) == 0, \
        "예상치 못한 입력이 있음"
    
    print("✅ 체이닝 메서드 테스트 통과")

def test_source_type_classification():
    """소스 유형 분류 정확도"""
    code = '''
from flask import Flask, request
app = Flask(__name__)

@app.route('/test')
def test():
    get_param = request.args.get('query')
    post_param = request.form.get('data')
    cookie = request.cookies.get('session')
    header = request.headers.get('X-Token')
    return "OK"
'''
    parser = PythonParser()
    endpoints = parser.parse("test.py", code)
    
    source_map = {}
    for ep in endpoints:
        for child in ep.children:
            if child.type == 'input':
                source_map[child.path] = child.method
    
    assert source_map.get('query') == 'GET', "query는 GET 소스여야 함"
    assert source_map.get('data') == 'POST', "data는 POST 소스여야 함"
    assert source_map.get('session') == 'COOKIE', "session은 COOKIE 소스여야 함"
    assert source_map.get('X-Token') == 'HEADER', "X-Token은 HEADER 소스여야 함"
    
    print("✅ 소스 유형 분류 테스트 통과")

if __name__ == "__main__":
    test_chained_method_call()
    test_source_type_classification()
    print("\n🎉 모든 파서 검증 테스트 통과!")
```

### 실행 방법

```powershell
cd backend
python test_parser_validation.py
```

**기대 결과:**
```
✅ 체이닝 메서드 테스트 통과
✅ 소스 유형 분류 테스트 통과

🎉 모든 파서 검증 테스트 통과!
```

### 알려진 오탐 패턴 (수정됨)

| 코드 패턴 | 이전 (버그) | 현재 (수정됨) |
|-----------|-------------|---------------|
| `request.form.get('x').encode('utf-8')` | 'utf-8' 감지 ❌ | 'x'만 감지 ✅ |
| `request.args.get('q').strip()` | strip 관련 오류 | 'q'만 감지 ✅ |
| `request.cookies.get('s').lower()` | lower 관련 오류 | 's'만 감지 ✅ |

---

## 샘플별 테스트 스크립트

### file-download-1 테스트

```powershell
cd backend
python test_file_download_1.py
```

**기대 결과:**
```
=== Testing file-download-1 ===
Expected findings: 2
  - [path-traversal-taint-flask] Line 32: /upload 엔드포인트 (필터링 있음)
  - [path-traversal-taint-flask] Line 50: /read 엔드포인트 (실제 취약점)

=== Scan Results (2 findings) ===
  [ERROR] path-traversal-taint-flask @ line 32
      [PATH-001] 사용자 입력이 파일 경로에 사용됨 - 경로 탐색 취약점 의심
  [ERROR] path-traversal-taint-flask @ line 50
      [PATH-001] 사용자 입력이 파일 경로에 사용됨 - 경로 탐색 취약점 의심

=== Validation ===
✅ PASS: Found 2 vulnerabilities (expected 2)
✅ PASS: Path Traversal rule detected
```

---

## 시각화 결과 확인 체크리스트 (Visual Verification)

노드 그래프에서 다음을 확인하세요:

### 1. 사용자 입력 (USER INPUTS) 섹션
- ✅ 올바른 파라미터 이름만 표시 (예: `content`, `filename`, `name`)
- ❌ 메서드 인자가 표시되면 안됨 (예: `utf-8`, `strict`)

### 2. 노드 그래프
- 🔴 취약점 노드: 빨간색으로 강조
- 🟢 안전한 노드: 기본 색상
- 📊 Call Graph: 함수 호출 관계 시각화

### 3. 상세 패널
- 취약점 메시지가 한국어로 표시되는지 확인
- 라인 번호가 정확한지 확인
- 심각도가 올바르게 분류되는지 확인
