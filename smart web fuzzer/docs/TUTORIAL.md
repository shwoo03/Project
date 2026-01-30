# FluxFuzzer 튜토리얼

FluxFuzzer를 처음 사용하는 분들을 위한 단계별 가이드입니다.

## 목차

1. [시작하기](#1-시작하기)
2. [첫 번째 퍼징 실행](#2-첫-번째-퍼징-실행)
3. [시나리오 작성](#3-시나리오-작성)
4. [결과 분석](#4-결과-분석)
5. [고급 기능](#5-고급-기능)

---

## 1. 시작하기

### 설치

```bash
# Go 1.21 이상 필요
go install github.com/fluxfuzzer/fluxfuzzer/cmd/fluxfuzzer@latest

# 또는 소스에서 빌드
git clone https://github.com/fluxfuzzer/fluxfuzzer.git
cd fluxfuzzer
go build -o fluxfuzzer ./cmd/fluxfuzzer
```

### 설치 확인

```bash
fluxfuzzer --version
# FluxFuzzer v1.0.0
```

### 프로젝트 구조 이해

```
fluxfuzzer/
├── cmd/fluxfuzzer/     # CLI 진입점
├── internal/           # 내부 패키지
│   ├── analyzer/       # 응답 분석
│   ├── mutator/        # 데이터 변이
│   ├── requester/      # HTTP 요청
│   ├── scenario/       # 시나리오 엔진
│   ├── state/          # 상태 관리
│   ├── ui/             # TUI 대시보드
│   └── report/         # 리포트 생성
├── scenarios/          # 시나리오 파일
└── docs/               # 문서
```

---

## 2. 첫 번째 퍼징 실행

### 테스트 서버 준비

테스트를 위해 로컬 서버가 필요합니다. DVWA, WebGoat 등을 사용할 수 있습니다.

```bash
# 예: Python 간단 서버
python -m http.server 8080
```

### 기본 퍼징

```bash
fluxfuzzer fuzz -u http://localhost:8080/api/test
```

### 옵션 지정

```bash
fluxfuzzer fuzz \
    -u http://localhost:8080/api/users \
    --method POST \
    --header "Content-Type: application/json" \
    --body '{"id": 1, "name": "test"}' \
    --threads 5 \
    --duration 1m
```

### 결과 확인

퍼징이 완료되면 콘솔에 요약이 표시됩니다:

```
┌─────────────────────────────────────────────┐
│  퍼징 완료!                                  │
├─────────────────────────────────────────────┤
│  총 요청: 1,234                              │
│  성공: 1,200 (97.2%)                         │
│  실패: 34 (2.8%)                             │
│  이상 징후: 3                                │
│  소요 시간: 1m 5s                            │
└─────────────────────────────────────────────┘
```

---

## 3. 시나리오 작성

### 시나리오란?

시나리오는 여러 단계의 요청을 순차적으로 실행하는 YAML 파일입니다. 로그인 → 인증된 요청 → 로그아웃 같은 흐름을 테스트할 수 있습니다.

### 기본 시나리오 작성

`scenarios/my_first_scenario.yaml` 파일을 생성합니다:

```yaml
name: My First Scenario
description: 첫 번째 시나리오 테스트

# 변수 정의
variables:
  base_url: "http://localhost:8080"

# 단계 정의
steps:
  - name: health_check
    request:
      method: GET
      url: "{{base_url}}/health"
    assert:
      - type: status
        expected: "200"
```

### 시나리오 실행

```bash
fluxfuzzer scenario -f scenarios/my_first_scenario.yaml
```

### 값 추출 및 사용

이전 응답에서 값을 추출하여 다음 요청에서 사용할 수 있습니다:

```yaml
steps:
  - name: login
    request:
      method: POST
      url: "{{base_url}}/login"
      body: '{"user": "admin", "pass": "secret"}'
    extract:
      - name: auth_token
        type: jsonpath
        pattern: "token"
    assert:
      - type: status
        expected: "200"

  - name: get_profile
    request:
      method: GET
      url: "{{base_url}}/profile"
      headers:
        Authorization: "Bearer {{auth_token}}"
    assert:
      - type: status
        expected: "200"
```

### 조건부 분기

성공/실패에 따라 다른 단계로 이동할 수 있습니다:

```yaml
steps:
  - name: check_status
    request:
      method: GET
      url: "{{base_url}}/status"
    assert:
      - type: status
        expected: "200"
    on_success: proceed_normal
    on_failure: handle_error

  - name: proceed_normal
    request:
      method: GET
      url: "{{base_url}}/data"

  - name: handle_error
    request:
      method: GET
      url: "{{base_url}}/fallback"
```

---

## 4. 결과 분석

### 리포트 생성

퍼징 완료 후 다양한 형식의 리포트를 생성할 수 있습니다:

```bash
# 모든 형식 생성
fluxfuzzer report -o ./reports --all

# 특정 형식만
fluxfuzzer report -o ./reports -f html
```

### 리포트 형식

| 형식 | 파일 | 용도 |
|-----|------|------|
| JSON | report.json | 프로그래밍 방식 분석 |
| HTML | report.html | 브라우저로 시각화 |
| Markdown | report.md | 문서화, PR 첨부 |

### 이상 징후 분석

리포트에서 이상 징후를 확인합니다:

```json
{
  "anomalies": [
    {
      "type": "status_code",
      "severity": "high",
      "url": "/api/users",
      "description": "500 Internal Server Error",
      "payload": "' OR 1=1--"
    }
  ]
}
```

**심각도 레벨:**
- 🔴 **Critical**: 즉시 조치 필요 (인증 우회, 데이터 노출)
- 🟠 **High**: 보안 취약점 가능성
- 🟡 **Medium**: 검토 필요
- 🟢 **Low**: 낮은 우선순위

---

## 5. 고급 기능

### 커스텀 페이로드

자체 페이로드 목록을 사용할 수 있습니다:

```yaml
# payloads/custom.txt
<script>alert(1)</script>
' OR '1'='1
{{7*7}}
$(whoami)
```

```bash
fluxfuzzer fuzz -u http://target.com --payloads payloads/custom.txt
```

### Rate Limiting

서버 과부하 방지:

```yaml
engine:
  rps_limit: 50      # 초당 최대 50 요청
  delay: 100ms       # 요청 간 지연
```

### 인증 처리

```yaml
variables:
  api_key: "{{env.API_KEY}}"  # 환경 변수에서 로드

steps:
  - name: api_call
    request:
      headers:
        X-API-Key: "{{api_key}}"
```

### TUI 대시보드

실시간 모니터링:

```bash
fluxfuzzer fuzz -u http://target.com --ui
```

키보드 단축키:
- `p`: 일시정지
- `r`: 재개
- `s`: 정지
- `q`: 종료

---

## 다음 단계

- [API Reference](API.md) - 상세 API 문서
- [Examples](EXAMPLES.md) - 더 많은 예제
- [ARCHITECTURE.md](../ARCHITECTURE.md) - 아키텍처 이해
- [DEVELOPMENT.md](../DEVELOPMENT.md) - 기여 가이드

## 도움받기

문제가 있으면:
1. GitHub Issues에 버그 리포트
2. Discussions에서 질문
3. PR로 기여

Happy Fuzzing! 🚀
