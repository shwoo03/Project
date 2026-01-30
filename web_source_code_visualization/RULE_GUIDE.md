# Semgrep Rule Learning System Guide v2.0

## 🎯 프로젝트 철학 (Project Philosophy)

이 프로젝트는 단순히 많은 취약점을 찾는 것이 아니라, **"정확한 원인(Root Cause)을 찾아내는 정밀한 탐지 규칙"**을 만드는 것을 목표로 합니다.

1.  **Precision > Quantity**: 불필요한 오탐(False Positive)을 극도로 싫어합니다. 우리가 학습시킨(추가한) 샘플 문제들을 **정확하게 잡는 것**이 최우선 목표입니다.
2.  **Taint Analysis**: 단순 패턴 매칭이 아닌, 데이터의 흐름(Flow)을 추적하여 정확도를 높입니다.
3.  **Strict Rule Tuning**: 규칙을 느슨하게 잡기보다 타이트하게 잡아, 확실한 취약점만 보고하도록 설정합니다.

---

## 🏗️ Taint Analysis (오염 분석) 개념

우리의 핵심 탐지 방법론은 **Taint Analysis**입니다.

### 1. Source (오염원)
사용자 입력이 시스템으로 들어오는 지점입니다.
- `request.args.get(...)`
- `request.cookies.get(...)`
- `request.form[...]`

### 2. Sink (도달점)
오염된 데이터가 도달했을 때 위험한 함수입니다.
- **SQLi**: `cursor.execute(...)`
- **XSS**: `return response`
- **CMDI**: `os.system(...)`

### 3. Sanitizer (정화조)
오염된 데이터를 안전하게 만드는 함수나 검증 로직입니다. **오탐을 줄이는 핵심**입니다.
- `int(...)`: 숫자로 변환되면 안전함
- `secure_filename(...)`: 경로 조작 문자 제거
- `render_template(...)`: 템플릿 엔진이 자동 이스케이프 처리 (XSS 방지)

---

## 📝 규칙 작성 워크플로우

1.  **취약점 재현 (Reproduction)**
    - `plob/` 디렉터리에 취약한 샘플 코드(`app.py`)를 작성합니다.
    - `metadata.json`에 예상되는 취약점 위치와 유형을 정의합니다.

2.  **규칙 초안 작성 (Drafting)**
    - `custom_security.yaml`에 `pattern-sources`와 `pattern-sinks`를 정의합니다.

3.  **검증 및 튜닝 (Verification & Tuning)**
    - `test_rule_precision.py` 또는 개별 테스트 스크립트로 탐지 여부를 확인합니다.
    - **오탐 발생 시**: 해당 패턴을 `pattern-sanitizers`에 추가하여 예외 처리합니다.
    - **미탐 발생 시**: `pattern-sinks`나 `pattern-sources`를 확장합니다.

---

## 🛠️ 오탐(FP) 관리 전략

### 상황 1: 안전한 함수인데 탐지될 때
예: `render_template`을 사용해서 안전한데 XSS로 탐지됨.
**해결**: `pattern-sanitizers`에 해당 함수를 추가합니다.
```yaml
pattern-sanitizers:
  - patterns:
      - pattern: render_template(...)
```

### 상황 2: 다른 취약점의 결과가 오탐지될 때
예: SQL Injection으로 DB에서 나온 값이 출력되는데, 이를 Reflected XSS로 오탐지.
**해결**: DB 조회 함수(`query_db`)를 XSS 규칙의 Sanitizer로 등록하여, "DB에서 나온 데이터는 (XSS 관점에서는) 신뢰함"으로 처리합니다.
```yaml
pattern-sanitizers:
  - patterns:
      - pattern: query_db(...) 
```

---

## 📂 디렉터리 및 파일 규칙

### 1. 디렉터리 구조
```
plob/<레벨>/<문제이름>/
├── app.py           # 핵심 소스 코드 (파일명은 app.py 권장)
└── metadata.json    # 메타데이터
```

### 2. 중요: 파일 관리 원칙
- **중복 및 임시 파일 제거**: `e.py`, `check.php` 처럼 동일하거나 유사한 코드가 포함된 파일은 분석 결과에 중복을 초래하므로 삭제합니다.
- **원본 보존 및 불필요한 수정 지양**: 원본 소스 코드(`app.py`)를 무리하게 합치거나 변경하지 않습니다. 있는 그대로의 코드를 유지하되, 분석에 방해되는 요소만 제거합니다.

---

## 🧪 테스트 가이드

### CLI 테스트
```powershell
# 전체 정밀도 테스트
cd backend
python test_rule_precision.py

# 특정 샘플 테스트 스크립트 작성 예시
python test_simple_sqli.py
```

### 시각화 확인
웹 대시보드에서 다음을 확인합니다:
1.  **Data Flow**: 빨간색 선이 Source에서 Sink로 이어지는지
2.  **Node Color**: 취약한 파일이 빨간색으로 표시되는지

---

## 📚 규칙 레벨 분류

| 레벨 | 설명 | 대상 취약점 |
|------|------|------------|
| **새싹** | 단일 함수 내의 단순한 취약점 | Hardcoded Key, Debug Mode, Comments |
| **LEVEL 1** | 기본적인 Taint Flow (입력->실행) | SQLi, Reflected XSS, CMDI, Path Traversal |
| **LEVEL 2** | 복잡한 데이터 변환이 포함된 경우 | Insecure Deserialization, SSRF |
| **LEVEL 3** | 로직 버그 및 복합 체인 | Race Condition, Auth Logic Bypass |
