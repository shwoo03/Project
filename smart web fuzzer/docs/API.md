# FluxFuzzer API Reference

FluxFuzzer의 핵심 패키지 및 API에 대한 문서입니다.

## 목차

- [state 패키지](#state-패키지)
- [mutator 패키지](#mutator-패키지)
- [analyzer 패키지](#analyzer-패키지)
- [scenario 패키지](#scenario-패키지)
- [report 패키지](#report-패키지)
- [ui 패키지](#ui-패키지)

---

## state 패키지

동적 값 관리 및 템플릿 치환을 담당합니다.

### TemplateEngine

```go
import "github.com/fluxfuzzer/fluxfuzzer/internal/state"

engine := state.NewTemplateEngine()

// 변수 설정
engine.SetVariable("token", "abc123")

// 템플릿 치환
result := engine.Substitute("Bearer {{token}}")
// Result: "Bearer abc123"
```

#### 지원 기능
| 기능 | 구문 | 설명 |
|-----|------|------|
| 변수 | `{{name}}` | 변수 값 치환 |
| 기본값 | `{{name\|default}}` | 값이 없으면 기본값 사용 |
| 내장 함수 | `{{uuid()}}` | UUID 생성 |
| 환경 변수 | `{{env.PATH}}` | 환경 변수 참조 |

### Pool

```go
pool := state.NewPool(state.PoolConfig{
    MaxSize: 1000,
    TTL:     5 * time.Minute,
})

// 값 추가
pool.Add("user_id", "12345")

// 값 조회
value, ok := pool.Get("user_id")
```

---

## mutator 패키지

요청 데이터 변이(mutation)를 담당합니다.

### Mutator 인터페이스

```go
type Mutator interface {
    Name() string
    Mutate(data []byte) ([]byte, error)
    Category() string
}
```

### 기본 제공 Mutators

| 이름 | 설명 | 카테고리 |
|-----|------|----------|
| BitFlipMutator | 비트 플립 변이 | afl |
| ByteFlipMutator | 바이트 플립 변이 | afl |
| ArithmeticMutator | 산술 연산 변이 | afl |
| SQLiMutator | SQL 인젝션 페이로드 | smart |
| XSSMutator | XSS 페이로드 | smart |
| CommandInjectionMutator | 명령어 삽입 | smart |

### Registry 사용법

```go
registry := mutator.NewRegistry()

// Mutator 등록
registry.Register(mutator.NewBitFlipMutator())
registry.Register(mutator.NewSQLiMutator())

// Mutator 선택
m := registry.GetRandom()
mutated, _ := m.Mutate(data)
```

---

## analyzer 패키지

응답 분석 및 이상 탐지를 담당합니다.

### Analyzer 인터페이스

```go
type Analyzer interface {
    Analyze(baseline, current *types.Response) (*types.AnomalyResult, error)
}
```

### TLSH 유사도 분석

```go
analyzer := analyzer.NewTLSHAnalyzer(analyzer.TLSHConfig{
    Threshold: 50.0,
})

result, _ := analyzer.Analyze(baseline, response)
if result.IsAnomaly {
    fmt.Printf("이상 탐지: %s (유사도: %.2f)\n", 
        result.Description, result.Similarity)
}
```

---

## scenario 패키지

YAML 기반 시나리오 실행을 담당합니다.

### 시나리오 파싱

```go
parser := scenario.NewParser()
s, err := parser.ParseFile("login_flow.yaml")
```

### 시나리오 실행

```go
executor := scenario.NewExecutor(httpClient, substitutor,
    scenario.WithMaxSteps(100),
    scenario.WithTimeout(5*time.Minute),
)

result, err := executor.Execute(s)
if result.Success {
    fmt.Println("시나리오 실행 성공!")
}
```

### YAML 시나리오 형식

```yaml
name: Login Flow
variables:
  base_url: "http://localhost:8080"

steps:
  - name: login
    request:
      method: POST
      url: "{{base_url}}/api/login"
      body: '{"username": "admin", "password": "secret"}'
    extract:
      - name: token
        type: jsonpath
        pattern: "access_token"
    assert:
      - type: status
        expected: "200"
    on_success: fetch_data
```

---

## report 패키지

리포트 생성을 담당합니다.

### Report 생성

```go
report := report.NewReport("Fuzzing Report", "http://target.com")

report.SetStatistics(report.Statistics{
    TotalRequests:  1000,
    SuccessCount:   950,
    Duration:       10 * time.Minute,
})

report.AddAnomaly(report.Anomaly{
    Type:        report.AnomalyStatusCode,
    Severity:    report.SeverityHigh,
    Description: "SQL Injection detected",
})
```

### 리포트 출력

```go
manager := report.NewManager("./output")

// 단일 형식
path, _ := manager.Generate(r, "html")

// 모든 형식
paths, _ := manager.GenerateAll(r)
```

---

## ui 패키지

TUI 대시보드를 담당합니다.

### Dashboard 실행

```go
dashboard := ui.NewDashboard()
dashboard.SetTargetURL("http://target.com")
dashboard.Start()

// TUI 실행
if err := ui.Run(dashboard); err != nil {
    log.Fatal(err)
}
```

### 키보드 단축키

| 키 | 동작 |
|----|------|
| `p` | 일시정지 |
| `r` | 재개 |
| `s` | 정지 |
| `q` | 종료 |

---

## 공통 타입

### types.Response

```go
type Response struct {
    StatusCode  int
    Headers     map[string]string
    Body        []byte
    Duration    time.Duration
    ContentType string
}
```

### types.FuzzTarget

```go
type FuzzTarget struct {
    URL     string
    Method  string
    Headers map[string]string
    Body    []byte
}
```
