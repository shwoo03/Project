# FluxFuzzer 사용 예제

FluxFuzzer의 다양한 사용 예제입니다.

## 목차

- [기본 사용법](#기본-사용법)
- [시나리오 기반 퍼징](#시나리오-기반-퍼징)
- [커스텀 Mutator](#커스텀-mutator)
- [리포트 생성](#리포트-생성)
- [TUI 대시보드](#tui-대시보드)

---

## 기본 사용법

### CLI로 퍼징 실행

```bash
# 단일 URL 퍼징
fluxfuzzer fuzz -u http://example.com/api/users

# 설정 파일 사용
fluxfuzzer fuzz -c config.yaml

# 옵션 지정
fluxfuzzer fuzz -u http://example.com/api \
    --method POST \
    --header "Content-Type: application/json" \
    --body '{"id": 1}' \
    --threads 10 \
    --duration 5m
```

### 설정 파일 (config.yaml)

```yaml
target:
  url: "http://localhost:8080"
  method: "POST"
  headers:
    Content-Type: "application/json"
    Authorization: "Bearer {{token}}"

engine:
  threads: 10
  rps_limit: 100
  timeout: 10s

analyzer:
  similarity_threshold: 85.0
  baseline_samples: 5

state:
  pool_size: 1000
  ttl: 5m

output:
  directory: "./reports"
  formats:
    - json
    - html
    - markdown
```

---

## 시나리오 기반 퍼징

### 로그인 후 API 테스트

```yaml
# scenarios/auth_test.yaml
name: Authentication Test
description: 로그인 후 인증된 API 테스트

variables:
  base_url: "http://localhost:8080"
  username: "testuser"
  password: "testpass"

steps:
  - name: login
    request:
      method: POST
      url: "{{base_url}}/api/auth/login"
      headers:
        Content-Type: application/json
      body: |
        {
          "username": "{{username}}",
          "password": "{{password}}"
        }
    extract:
      - name: access_token
        type: jsonpath
        pattern: "token"
      - name: user_id
        type: jsonpath
        pattern: "user.id"
    assert:
      - type: status
        expected: "200"
      - type: jsonpath
        target: "success"
        expected: "true"
    on_success: get_profile
    on_failure: handle_error

  - name: get_profile
    request:
      method: GET
      url: "{{base_url}}/api/users/{{user_id}}"
      headers:
        Authorization: "Bearer {{access_token}}"
    assert:
      - type: status
        expected: "200"
    on_success: update_profile

  - name: update_profile
    request:
      method: PUT
      url: "{{base_url}}/api/users/{{user_id}}"
      headers:
        Authorization: "Bearer {{access_token}}"
        Content-Type: application/json
      body: |
        {"name": "{{fuzz:string}}"}
    assert:
      - type: status
        expected: "200"

  - name: handle_error
    request:
      method: GET
      url: "{{base_url}}/api/health"
```

### 시나리오 실행

```bash
fluxfuzzer scenario -f scenarios/auth_test.yaml
```

---

## 커스텀 Mutator

### Go 코드로 Mutator 구현

```go
package main

import (
    "github.com/fluxfuzzer/fluxfuzzer/internal/mutator"
)

// CustomMutator 구현
type CustomMutator struct {
    patterns []string
}

func NewCustomMutator() *CustomMutator {
    return &CustomMutator{
        patterns: []string{
            "{{payload1}}",
            "{{payload2}}",
            "{{payload3}}",
        },
    }
}

func (m *CustomMutator) Name() string {
    return "custom"
}

func (m *CustomMutator) Category() string {
    return "custom"
}

func (m *CustomMutator) Mutate(data []byte) ([]byte, error) {
    // 변이 로직 구현
    idx := rand.Intn(len(m.patterns))
    return []byte(m.patterns[idx]), nil
}

func main() {
    registry := mutator.NewRegistry()
    registry.Register(NewCustomMutator())
    
    // 사용
    m, _ := registry.GetByName("custom")
    result, _ := m.Mutate([]byte("original"))
}
```

---

## 리포트 생성

### 프로그래밍 방식

```go
package main

import (
    "time"
    "github.com/fluxfuzzer/fluxfuzzer/internal/report"
)

func main() {
    // 리포트 생성
    r := report.NewReport("Security Scan", "http://target.com")
    
    // 통계 설정
    r.SetStatistics(report.Statistics{
        TotalRequests:   5000,
        SuccessCount:    4800,
        FailureCount:    200,
        Duration:        10 * time.Minute,
        RequestsPerSec:  8.3,
        AvgResponseTime: 120 * time.Millisecond,
    })
    
    // 이상 징후 추가
    r.AddAnomaly(report.Anomaly{
        ID:          "1",
        Type:        report.AnomalyStatusCode,
        Severity:    report.SeverityCritical,
        URL:         "http://target.com/api/admin",
        Method:      "POST",
        Payload:     "' OR 1=1--",
        Description: "Possible SQL Injection",
        StatusCode:  500,
        Timestamp:   time.Now(),
    })
    
    // 리포트 저장
    manager := report.NewManager("./output")
    paths, _ := manager.GenerateAll(r)
    
    for _, p := range paths {
        fmt.Println("Generated:", p)
    }
}
```

### CLI로 리포트 생성

```bash
fluxfuzzer report -i results.json -o ./reports -f html,md,json
```

---

## TUI 대시보드

### 대시보드 시작

```go
package main

import (
    "github.com/fluxfuzzer/fluxfuzzer/internal/ui"
)

func main() {
    dashboard := ui.NewDashboard()
    dashboard.SetTargetURL("http://target.com")
    
    // 퍼징 시작
    dashboard.Start()
    
    // 통계 업데이트 (별도 고루틴에서)
    go func() {
        stats := dashboard.GetStats()
        for {
            stats.RecordRequest(true, 100*time.Millisecond, false)
            time.Sleep(10 * time.Millisecond)
        }
    }()
    
    // TUI 실행
    ui.Run(dashboard)
}
```

### 키보드 조작

```
┌─ FluxFuzzer ─────────────────────────────────────────────┐
│                                                          │
│  ⚡ FluxFuzzer  ● RUNNING     Target: http://target.com  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  📊 Statistics          │  📝 Activity Log              │
│                         │                               │
│  Total Requests: 1.5K   │  15:23:45 INFO  Request #1523 │
│  Success: 1.4K          │  15:23:44 WARN  Slow response │
│  Failed: 100            │  15:23:43 INFO  Request #1522 │
│                         │                               │
├──────────────────────────────────────────────────────────┤
│  📈 Progress                                             │
│  ████████████████░░░░░░░░░░░░░░░░░░░░░  45.2%  ETA: 3m  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  [p] pause  [r] resume  [s] stop  [q] quit               │
└──────────────────────────────────────────────────────────┘
```
