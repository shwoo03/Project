# 🛠️ FluxFuzzer 개발 가이드

> AI 어시스턴트 및 개발자를 위한 개발 참조 문서

## 1. 개발 환경 설정

### 1.1 필수 요구사항

```bash
# Go 1.21+ 설치 확인
go version

# 프로젝트 클론 후 의존성 설치
go mod download
```

### 1.2 주요 의존성

```go
// go.mod에 포함될 의존성
require (
    github.com/valyala/fasthttp v1.51.0      // 고성능 HTTP
    github.com/panjf2000/ants/v2 v2.9.0      // 고루틴 풀
    github.com/glaslos/tlsh v0.2.0           // TLSH 해시
    github.com/charmbracelet/bubbletea v0.25.0 // TUI
    github.com/dlclark/regexp2 v1.10.0       // 고급 정규식
    github.com/spf13/cobra v1.8.0            // CLI
    github.com/spf13/viper v1.18.0           // 설정 관리
    gopkg.in/yaml.v3 v3.0.1                  // YAML 파싱
    github.com/stretchr/testify v1.8.4       // 테스트
)
```

## 2. 프로젝트 구조 상세

```
smart web fuzzer/
├── cmd/
│   └── fluxfuzzer/
│       └── main.go              # 엔트리포인트
│
├── internal/                    # 내부 패키지 (외부 import 불가)
│   ├── mutator/                 # 변이 엔진 ✅
│   │   ├── mutator.go          # 변이 인터페이스, Registry, Engine
│   │   ├── mutator_test.go     # 변이 엔진 테스트
│   │   ├── radamsa.go          # Radamsa 스타일 변이 (예정)
│   │   ├── afl.go              # AFL 스타일 변이 (예정)
│   │   └── smart.go            # 타입 인식 스마트 변이 (예정)
│   │
│   ├── requester/              # HTTP 요청 엔진
│   │   ├── requester.go        # 요청 처리 메인 로직
│   │   ├── worker_pool.go      # 워커 풀 관리
│   │   └── client.go           # FastHTTP 클라이언트 래퍼
│   │
│   ├── analyzer/               # 응답 분석 엔진
│   │   ├── analyzer.go         # 분석 파이프라인
│   │   ├── simhash.go          # SimHash 알고리즘
│   │   ├── tlsh.go             # TLSH 연동
│   │   ├── baseline.go         # 기준점 학습
│   │   └── filter.go           # 필터링 로직
│   │
│   ├── state/                  # 상태 관리
│   │   ├── manager.go          # 상태 관리자
│   │   ├── extractor.go        # 값 추출기
│   │   └── pool.go             # Dynamic Pool
│   │
│   ├── scenario/               # 시나리오 엔진
│   │   ├── scenario.go         # 시나리오 실행
│   │   ├── parser.go           # YAML 파서
│   │   └── flow.go             # 실행 흐름 제어
│   │
│   ├── config/                 # 설정 관리
│   │   ├── config.go           # 설정 구조체
│   │   └── loader.go           # 설정 로더
│   │
│   ├── ui/                     # TUI 인터페이스
│   │   ├── dashboard.go        # 대시보드 메인
│   │   ├── stats.go            # 통계 위젯
│   │   └── progress.go         # 진행률 위젯
│   │
│   └── report/                 # 리포트 생성
│       ├── report.go           # 리포트 생성기
│       ├── json.go             # JSON 출력
│       └── html.go             # HTML 출력
│
├── pkg/                        # 공개 패키지 (외부 import 가능)
│   ├── types/
│   │   └── types.go            # 공통 타입 정의
│   └── utils/
│       └── utils.go            # 유틸리티 함수
│
├── wordlists/                  # 워드리스트
│   ├── common.txt
│   ├── sqli.txt
│   └── xss.txt
│
├── rules/                      # 퍼징 규칙
│   └── default.yaml
│
├── scenarios/                  # 시나리오 예제
│   └── api_flow.yaml
│
├── tests/                      # 테스트
│   ├── integration/
│   └── benchmark/
│
└── docs/                       # 추가 문서
```

## 3. 코딩 컨벤션

### 3.1 패키지 구조

```go
// 각 패키지는 다음 구조를 따름
package analyzer

// 인터페이스 정의
type Analyzer interface {
    Analyze(resp *types.Response) (*types.AnomalyResult, error)
}

// 구조체 정의
type structuralAnalyzer struct {
    baseline *Baseline
    threshold int
}

// 생성자
func NewStructuralAnalyzer(opts ...Option) Analyzer {
    return &structuralAnalyzer{}
}

// 옵션 패턴
type Option func(*structuralAnalyzer)

func WithThreshold(t int) Option {
    return func(a *structuralAnalyzer) {
        a.threshold = t
    }
}
```

### 3.2 에러 처리

```go
// 커스텀 에러 정의
type FuzzerError struct {
    Op      string
    Target  string
    Err     error
}

func (e *FuzzerError) Error() string {
    return fmt.Sprintf("%s %s: %v", e.Op, e.Target, e.Err)
}

// 에러 래핑
func doSomething() error {
    if err := someOperation(); err != nil {
        return &FuzzerError{
            Op:     "analyze",
            Target: url,
            Err:    err,
        }
    }
    return nil
}
```

### 3.3 로깅

```go
// 구조화된 로깅 (slog 사용)
import "log/slog"

logger := slog.Default()

logger.Info("request sent",
    slog.String("url", url),
    slog.Int("status", resp.StatusCode),
    slog.Duration("time", responseTime),
)

logger.Error("request failed",
    slog.String("url", url),
    slog.Any("error", err),
)
```

## 4. 빌드 및 실행

### 4.1 개발 빌드

```bash
# 빌드
go build -o bin/fluxfuzzer ./cmd/fluxfuzzer

# 실행
./bin/fluxfuzzer -h
```

### 4.2 프로덕션 빌드

```bash
# 최적화 빌드
CGO_ENABLED=0 go build -ldflags="-s -w" -o bin/fluxfuzzer ./cmd/fluxfuzzer
```

### 4.3 테스트

```bash
# 단위 테스트
go test ./...

# 벤치마크
go test -bench=. ./internal/requester/

# 커버리지
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

## 5. 핵심 알고리즘 구현 가이드

### 5.1 SimHash 구현

```go
// internal/analyzer/simhash.go

package analyzer

import (
    "hash/fnv"
    "strings"
)

const hashBits = 64

// SimHash 계산
func ComputeSimHash(features []string) uint64 {
    var vector [hashBits]int
    
    for _, feature := range features {
        hash := hashFeature(feature)
        for i := 0; i < hashBits; i++ {
            if hash&(1<<i) != 0 {
                vector[i]++
            } else {
                vector[i]--
            }
        }
    }
    
    var simhash uint64
    for i := 0; i < hashBits; i++ {
        if vector[i] > 0 {
            simhash |= 1 << i
        }
    }
    return simhash
}

// Hamming Distance 계산
func HammingDistance(a, b uint64) int {
    diff := a ^ b
    count := 0
    for diff != 0 {
        count++
        diff &= diff - 1
    }
    return count
}

func hashFeature(s string) uint64 {
    h := fnv.New64a()
    h.Write([]byte(s))
    return h.Sum64()
}
```

### 5.2 HTML 구조 추출

```go
// internal/analyzer/structure.go

package analyzer

import (
    "strings"
    "golang.org/x/net/html"
)

// HTML에서 태그 구조만 추출
func ExtractHTMLStructure(htmlContent string) []string {
    var features []string
    tokenizer := html.NewTokenizer(strings.NewReader(htmlContent))
    
    var path []string
    for {
        tt := tokenizer.Next()
        switch tt {
        case html.ErrorToken:
            return features
        case html.StartTagToken:
            name, _ := tokenizer.TagName()
            path = append(path, string(name))
            features = append(features, strings.Join(path, ">"))
        case html.EndTagToken:
            if len(path) > 0 {
                path = path[:len(path)-1]
            }
        }
    }
}
```

### 5.3 Worker Pool 패턴

```go
// internal/requester/worker_pool.go

package requester

import (
    "sync"
    "github.com/panjf2000/ants/v2"
)

type WorkerPool struct {
    pool    *ants.Pool
    results chan *Result
    wg      sync.WaitGroup
}

func NewWorkerPool(size int) (*WorkerPool, error) {
    pool, err := ants.NewPool(size, ants.WithPreAlloc(true))
    if err != nil {
        return nil, err
    }
    
    return &WorkerPool{
        pool:    pool,
        results: make(chan *Result, size*2),
    }, nil
}

func (wp *WorkerPool) Submit(task func()) error {
    wp.wg.Add(1)
    return wp.pool.Submit(func() {
        defer wp.wg.Done()
        task()
    })
}

func (wp *WorkerPool) Wait() {
    wp.wg.Wait()
}

func (wp *WorkerPool) Close() {
    wp.pool.Release()
    close(wp.results)
}
```

## 6. AI 어시스턴트 가이드

### 6.1 개발 진행 시 체크리스트

1. **작업 전 확인**
   - [ ] ROADMAP.md에서 현재 Phase 확인
   - [ ] 해당 Task의 파일 위치 확인
   - [ ] 의존성 있는 다른 Task 확인

2. **코드 작성 시**
   - [ ] ARCHITECTURE.md의 데이터 구조 참조
   - [ ] 인터페이스 기반 설계 유지
   - [ ] 에러 처리 및 로깅 포함

3. **작업 후**
   - [ ] ROADMAP.md 진행상황 업데이트
   - [ ] 테스트 코드 작성/실행
   - [ ] 필요시 문서 업데이트

### 6.2 파일 생성 순서 (Phase 1 기준)

```
1. pkg/types/types.go          # 공통 타입 정의 먼저
2. internal/config/config.go   # 설정 구조체
3. internal/requester/client.go # HTTP 클라이언트
4. internal/requester/worker_pool.go # 워커 풀
5. internal/requester/requester.go # 요청 처리 통합
6. cmd/fluxfuzzer/main.go      # CLI 엔트리포인트
```

### 6.3 테스트 서버 (개발용)

```bash
# DVWA (Damn Vulnerable Web Application)
docker run -d -p 80:80 vulnerables/web-dvwa

# httpbin (간단한 테스트)
docker run -d -p 80:80 kennethreitz/httpbin
```

## 7. 자주 묻는 질문 (FAQ)

**Q: fasthttp vs net/http?**
A: fasthttp는 메모리 재사용으로 초당 수천 요청 처리 가능. 단, API가 다르므로 주의.

**Q: 왜 SimHash와 TLSH 둘 다?**
A: SimHash는 빠른 1차 필터, TLSH는 정밀 분석용. 상황에 따라 선택.

**Q: 상태 관리의 Thread-safety?**
A: sync.Map 사용으로 경쟁 조건 방지. 성능 중요하면 샤딩 고려.
