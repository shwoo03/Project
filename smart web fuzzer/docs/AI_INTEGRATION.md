# 🤖 FluxFuzzer AI 통합 방안 (Groq API)

> Groq API를 활용한 AI 기능 통합 계획

## 🎯 AI 활용 시나리오

### 1. 🔍 스마트 이상 탐지 (Anomaly Explanation)

**현재**: SimHash/Baseline 기반으로 "이상이 있다"만 탐지
**AI 추가**: 이상의 원인과 보안 영향을 자연어로 설명

```go
// 예시: AI가 이상 탐지 결과를 분석
type AIAnalysis struct {
    Anomaly     AnomalyResult
    Explanation string   // "SQL 인젝션 시도로 인한 응답 시간 지연 의심"
    Severity    string   // "HIGH"
    Suggestion  string   // "해당 파라미터에 WAF 규칙 추가 권장"
}
```

### 2. 🧬 지능형 페이로드 생성 (Smart Payload Generation)

**현재**: 워드리스트 기반 정적 페이로드
**AI 추가**: 컨텍스트 인식 동적 페이로드 생성

```yaml
# AI 요청 예시
prompt: |
  Target: /api/users/{id}
  Parameter Type: integer (user ID)
  Context: REST API, returns JSON
  
  Generate 10 creative fuzzing payloads for:
  - IDOR (Insecure Direct Object Reference)
  - Type confusion
  - Boundary testing
```

### 3. 📊 응답 패턴 분석 (Response Pattern Analysis)

**현재**: 수동으로 응답 패턴 규칙 정의
**AI 추가**: 응답 변화 패턴을 자동으로 학습/분류

```go
// AI에게 응답 비교 요청
func AnalyzeResponseDiff(baseline, current *Response) AIInsight {
    prompt := fmt.Sprintf(`
        Baseline response: %s
        Current response: %s
        
        Analyze the difference and determine:
        1. Is this a security-relevant change?
        2. What vulnerability might this indicate?
        3. Recommended next fuzzing steps?
    `, baseline.Body, current.Body)
    
    return groq.Query(prompt)
}
```

### 4. 🎯 자동 취약점 분류 (Vulnerability Classification)

**AI 역할**: 발견된 이상을 OWASP Top 10 등 표준 분류에 매핑

```go
type VulnerabilityReport struct {
    Finding     string      // 발견 사항
    Category    string      // "A01:2021 - Broken Access Control"
    CVSSScore   float64     // 7.5
    Evidence    []string    // 증거 스니펫
    Remediation string      // 수정 권장사항
}
```

---

## 🛠️ 구현 계획

### Phase 1: 기본 통합 (권장 시작점)

```go
// internal/ai/groq.go

type GroqClient struct {
    apiKey     string
    baseURL    string
    model      string  // "llama-3.1-70b-versatile" 또는 "mixtral-8x7b-32768"
    httpClient *http.Client
}

type GroqRequest struct {
    Model    string    `json:"model"`
    Messages []Message `json:"messages"`
}

type Message struct {
    Role    string `json:"role"`
    Content string `json:"content"`
}
```

### Phase 2: 분석 파이프라인 연동

```
[Fuzzer] → [Analyzer] → [AI Enricher] → [Report]
              ↓
         AnomalyResult
              ↓
         AIAnalysis (선택적)
```

### Phase 3: 고급 기능

- 세션별 컨텍스트 유지 (이전 요청/응답 기억)
- 자동 페이로드 조정 (AI 피드백 기반)
- 자연어 퍼징 명령어 지원 ("로그인 폼을 SQL 인젝션으로 테스트해줘")

---

## 💰 비용 및 성능 고려

### Groq API 장점
- **초고속 추론**: LPU 기반으로 매우 빠른 응답
- **무료 티어**: 테스트/개발용 무료 사용 가능
- **다양한 모델**: Llama 3.1, Mixtral 등 선택 가능

### 최적화 전략

1. **배치 처리**: 여러 이상을 모아서 한 번에 분석
2. **캐싱**: 유사한 패턴은 캐시된 분석 결과 재사용
3. **선택적 AI**: 심각도 높은 이상에만 AI 분석 적용
4. **로컬 필터링**: 명확한 케이스는 AI 없이 처리

---

## 📝 Groq API 설정

```bash
# 환경변수 설정
export GROQ_API_KEY="gsk_..."

# 또는 config.yaml
ai:
  provider: groq
  api_key: ${GROQ_API_KEY}
  model: llama-3.1-70b-versatile
  enabled: true
  max_tokens: 1000
```

---

## 🚀 추천 시작점

1. **간단한 통합부터**: 이상 탐지 결과를 AI로 설명하는 기능
2. **CLI 옵션 추가**: `--ai-analyze` 플래그
3. **점진적 확장**: 성공하면 페이로드 생성 등 추가

```go
// 사용 예시
fluxfuzzer -u http://target.com/api -w wordlist.txt --ai-analyze
```

---

## 📚 참고 자료

- [Groq API Documentation](https://console.groq.com/docs)
- [Groq Go Client Library](https://github.com/jpoz/groq)
