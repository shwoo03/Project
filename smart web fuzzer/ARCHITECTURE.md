# 🏗️ FluxFuzzer 아키텍처 상세 문서

## 1. 시스템 개요

FluxFuzzer는 4단계 파이프라인 구조로 설계된 스마트 웹 퍼저입니다.

```
┌────────────────────────────────────────────────────────────────────┐
│                        FluxFuzzer Core                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Mutator  │─▶│Requester │─▶│ Analyzer │─▶│  State Manager   │   │
│  │  Engine  │  │  Engine  │  │  Engine  │  │                  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │
│       ▲                                           │                │
│       └───────────────────────────────────────────┘                │
│                    Feedback Loop                                    │
└────────────────────────────────────────────────────────────────────┘
```

## 2. 핵심 모듈 상세

### 2.1 Mutator Engine (변이 엔진)

**역할**: 입력값(Seed)을 다양한 방법으로 변형하여 새로운 페이로드 생성

**핵심 인터페이스**:
```go
// Mutator 인터페이스 - 모든 변이기 구현의 기본
type Mutator interface {
    Name() string                                        // 변이기 이름
    Description() string                                 // 설명
    Mutate(input []byte) ([]byte, error)                // 기본 변이
    MutateWithType(input []byte, t InputType) ([]byte, error)  // 타입 인식 변이
    Type() types.MutationType                           // 변이 타입
}

// MutationStrategy 인터페이스 - 변이 선택 전략
type MutationStrategy interface {
    SelectMutator(mutators []Mutator) Mutator  // 변이기 선택
    ShouldMutate(probability float64) bool     // 변이 여부 결정
    Reset()                                     // 상태 초기화
}
```

**변이 타입 정의**:
```go
// 변이 타입 정의
type MutationType int

const (
    BitFlip       MutationType = iota  // AFL 스타일 비트 플립
    ByteSwap                           // 바이트 위치 교환
    ArithmeticAdd                      // 산술 연산 (오버플로우 유도)
    InterestingValues                  // 경계값 (0, -1, MAX_INT 등)
    DictionaryInsert                   // 워드리스트 기반 삽입
    StructureAware                     // JSON/XML 구조 인식 변이
)
```

**MutatorEngine 구조**:
```go
type MutatorEngine struct {
    registry        *Registry          // 변이기 등록소
    strategy        MutationStrategy   // 선택 전략
    probability     float64            // 변이 확률 (0.0-1.0)
    maxMutations    int                // 최대 연쇄 변이 횟수
    typeDetectors   []TypeDetector     // 입력 타입 감지기
}
```

**변이 선택 전략**:
| 전략 | 설명 |
|------|------|
| RandomSelector | 무작위 선택 |
| WeightedSelector | 가중치 기반 선택 |

**타입별 스마트 변이**:
| 입력 타입 | 변이 전략 | 예시 |
|-----------|----------|------|
| Integer | 오버플로우, 음수, 경계값 | `2147483647`, `-1`, `0` |
| String | SQLi, XSS, 특수문자 주입 | `' OR 1=1--`, `<script>` |
| UUID | 형식 유지, 부분 변조 | `00000000-0000-0000-...` |
| JSON | 타입 혼란, 키 조작 | `{"id": "string"}` → `{"id": 999}` |

### 2.2 Requester Engine (요청 엔진)

**역할**: 초당 수천 건의 HTTP 요청을 비동기로 전송

**기술 스택**:
- `valyala/fasthttp`: net/http 대비 10배 고속
- `panjf2000/ants`: 고루틴 풀 관리

**Worker Pool 구조**:
```go
type RequestEngine struct {
    pool       *ants.Pool           // 고루틴 풀
    client     *fasthttp.Client     // HTTP 클라이언트
    rateLimit  *rate.Limiter        // 속도 제한
    results    chan *Response       // 결과 채널
    maxWorkers int                  // 최대 워커 수
}

// 요청 처리 흐름
func (r *RequestEngine) Process(targets <-chan *FuzzTarget) {
    for target := range targets {
        r.pool.Submit(func() {
            resp := r.sendRequest(target)
            r.results <- resp
        })
    }
}
```

**성능 목표**: 
- RPS: 1,000~5,000 (환경에 따라)
- 메모리: 512MB 이하
- 동시 연결: 500개

### 2.3 Analyzer Engine (분석 엔진)

**역할**: 응답의 길이, 시간, 구조적 차이를 분석하여 이상 징후 탐지

#### 2.3.1 구조적 차분 분석 (Structural Differential Analysis)

**알고리즘**: SimHash 또는 TLSH

```go
// 구조적 해시 생성 과정
func GenerateStructuralHash(html string) uint64 {
    // 1. HTML → DOM 파싱
    doc := parseHTML(html)
    
    // 2. 구조만 추출 (태그 시퀀스)
    // <div><ul><li>text</li></ul></div>
    //  → "div>ul>li"
    structure := extractStructure(doc)
    
    // 3. 동적 콘텐츠 정규화
    // 타임스탬프, 사용자명 등 제거
    normalized := normalizeContent(structure)
    
    // 4. SimHash 생성
    return simhash.Compute(normalized)
}

// Hamming Distance 기반 유사도 계산
func CompareStructure(baseline, current uint64) int {
    distance := hammingDistance(baseline, current)
    // 0: 동일, 64: 완전히 다름
    return distance
}
```

**임계값 설정**:
| Distance | 의미 | 액션 |
|----------|------|------|
| 0-5 | 정상 범위 | 무시 |
| 6-15 | 경미한 변화 | 로그 기록 |
| 16-30 | 유의미한 변화 | 알림 |
| 31+ | 심각한 구조 변화 | 즉시 조사 |

#### 2.3.2 시간 기반 분석

```go
type TimeAnalysis struct {
    BaselineAvg    time.Duration  // 기준 평균 응답 시간
    BaselineStdDev time.Duration  // 표준 편차
    Threshold      float64        // 탐지 임계값 (예: 2.5배)
}

func (t *TimeAnalysis) IsAnomaly(responseTime time.Duration) bool {
    skew := float64(responseTime) / float64(t.BaselineAvg)
    return skew > t.Threshold
}
```

### 2.4 State Manager (상태 관리)

**역할**: API 간의 생산-소비 관계 추적 및 동적 값 관리

#### 2.4.1 값 추출 (Producer 식별)

```go
// 추출 패턴 정의
var extractPatterns = map[string]*regexp.Regexp{
    "uuid":      regexp.MustCompile(`[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`),
    "jwt":       regexp.MustCompile(`eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_.+/]*`),
    "numeric_id": regexp.MustCompile(`"id"\s*:\s*(\d+)`),
    "token":     regexp.MustCompile(`"token"\s*:\s*"([^"]+)"`),
}

// 응답에서 값 추출
func ExtractDynamicValues(body []byte) map[string][]string {
    results := make(map[string][]string)
    for name, pattern := range extractPatterns {
        matches := pattern.FindAllString(string(body), -1)
        if len(matches) > 0 {
            results[name] = matches
        }
    }
    return results
}
```

#### 2.4.2 Dynamic Pool

```go
type DynamicPool struct {
    values sync.Map  // Thread-safe 저장소
}

// 값 저장
func (p *DynamicPool) Store(key string, value string) {
    existing, _ := p.values.LoadOrStore(key, &[]string{})
    list := existing.(*[]string)
    *list = append(*list, value)
}

// 무작위 값 가져오기
func (p *DynamicPool) GetRandom(key string) (string, bool) {
    if values, ok := p.values.Load(key); ok {
        list := values.(*[]string)
        if len(*list) > 0 {
            return (*list)[rand.Intn(len(*list))], true
        }
    }
    return "", false
}
```

#### 2.4.3 템플릿 치환

```go
// 요청 템플릿
// "GET /files/{{file_id}} HTTP/1.1"

func ReplaceVariables(template string, pool *DynamicPool) string {
    re := regexp.MustCompile(`\{\{(\w+)\}\}`)
    return re.ReplaceAllStringFunc(template, func(match string) string {
        key := match[2:len(match)-2]  // {{key}} → key
        if value, ok := pool.GetRandom(key); ok {
            return value
        }
        return match  // 치환 불가시 원본 유지
    })
}
```

## 3. 데이터 구조

### 3.1 핵심 타입 정의

```go
// FuzzTarget: 공격 대상 및 상태 정의
type FuzzTarget struct {
    Method      string            // HTTP 메서드
    URL         string            // 대상 URL
    PayloadTmpl string            // "id={{user_id}}&name={{random_str}}"
    Headers     map[string]string // HTTP 헤더
    Body        []byte            // 요청 바디
    StateKeys   []string          // 응답에서 추출할 변수명
}

// Response: HTTP 응답 래퍼
type Response struct {
    RequestID    string
    StatusCode   int
    Headers      map[string][]string
    Body         []byte
    ResponseTime time.Duration
    Error        error
}

// AnomalyResult: 이상 징후 분석 결과
type AnomalyResult struct {
    RequestID    string
    Distance     int       // 구조적 거리 (0~64)
    TimeSkew     float64   // 지연율 (예: 2.5배)
    LengthDiff   int       // 길이 차이
    IsCrash      bool      // 500 에러 여부
    Evidence     string    // 탐지 이유
    Severity     Severity  // 심각도
}

type Severity int

const (
    Info Severity = iota
    Low
    Medium
    High
    Critical
)
```

### 3.2 설정 구조

```go
// Config: 전역 설정
type Config struct {
    Target      TargetConfig      `yaml:"target"`
    Engine      EngineConfig      `yaml:"engine"`
    Analyzer    AnalyzerConfig    `yaml:"analyzer"`
    State       StateConfig       `yaml:"state"`
    Output      OutputConfig      `yaml:"output"`
}

type EngineConfig struct {
    Workers    int           `yaml:"workers"`
    RPS        int           `yaml:"rps"`
    Timeout    time.Duration `yaml:"timeout"`
    MaxRetries int           `yaml:"max_retries"`
}

type AnalyzerConfig struct {
    StructureThreshold int     `yaml:"structure_threshold"`
    TimeThreshold      float64 `yaml:"time_threshold"`
    BaselineSamples    int     `yaml:"baseline_samples"`
}
```

## 4. 데이터 플로우

```
1. 초기화
   ├── 설정 로드 (YAML)
   ├── 워드리스트 로드
   ├── Worker Pool 생성
   └── Baseline 학습 (초기 N회 요청)

2. 퍼징 루프
   ┌─────────────────────────────────────────────────┐
   │ for each target:                                │
   │   1. Mutator: 페이로드 변이                      │
   │   2. State: 변수 치환 ({{var}})                  │
   │   3. Requester: HTTP 요청 전송                   │
   │   4. Analyzer: 응답 분석                         │
   │      ├── 구조적 차분 계산                        │
   │      ├── 시간 이상 탐지                          │
   │      └── 에러 코드 확인                          │
   │   5. State: 새 값 추출 및 Pool 저장              │
   │   6. 이상 발견 시 결과 저장                      │
   └─────────────────────────────────────────────────┘

3. 결과 출력
   ├── 실시간 TUI 대시보드
   ├── JSON/HTML 리포트
   └── 상세 로그
```

## 5. 확장성 고려사항

### 5.1 플러그인 시스템 (향후)

```go
// Mutator 플러그인 인터페이스
type MutatorPlugin interface {
    Name() string
    Mutate(input []byte) []byte
    SupportedTypes() []string
}

// Analyzer 플러그인 인터페이스
type AnalyzerPlugin interface {
    Name() string
    Analyze(resp *Response, baseline *Baseline) *AnomalyResult
}
```

### 5.2 분산 처리 (향후)

- Redis 기반 작업 큐
- 다중 노드 워커
- 중앙 결과 수집기
