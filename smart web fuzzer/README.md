# 🛡️ FluxFuzzer: Smart Stateful Web Fuzzer

> **Version**: 1.0.0-draft  
> **Concept**: Coverage-guided & State-aware DAST for Modern Web Apps

FluxFuzzer는 학술계(AFL++, RESTler)의 최신 기법을 웹 퍼징에 적용한 차세대 웹 보안 퍼저입니다.

## ✨ 핵심 차별화 기술

### 1. 구조적 차분 분석 (Structural Differential Analysis)
- **문제**: 단순 텍스트 비교는 동적 웹 페이지(타임스탬프, 랜덤 토큰)로 인해 오탐 발생
- **해결**: DOM/JSON 구조 기반 해시 (SimHash/TLSH)
- **효과**: 500 에러 없이도 페이지 구조 변화 감지 (예: 로그인→관리자 페이지)

### 2. 상태 기반 퍼징 (Stateful Fuzzing)
- **기반**: RESTler (Microsoft) 논문의 Producer-Consumer 관계 추적
- **동작**: 응답에서 ID/Token 추출 → Dynamic Pool 저장 → 후속 요청에 주입
- **시나리오**: `POST /upload` → `GET /files/{file_id}` → `DELETE /files/{file_id}`

## 🏗️ 시스템 아키텍처

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌───────────────┐
│   Mutator   │───▶│  Requester  │───▶│  Analyzer   │───▶│ State Manager │
│   (변이)    │    │   (요청)    │    │   (분석)    │    │   (상태관리)  │
└─────────────┘    └─────────────┘    └─────────────┘    └───────────────┘
      │                  │                  │                    │
      │                  │                  │                    │
   Radamsa           FastHTTP          SimHash/TLSH         sync.Map
   AFL bit-flip      Worker Pool       go-diff              regexp2
```

| 모듈명 | 역할 | 핵심 기술 |
|--------|------|-----------|
| Mutator | 입력값(Seed) 변형 | Radamsa, AFL bit-flipping |
| Requester | 초당 수천 건 HTTP 요청 | valyala/fasthttp |
| Analyzer | 응답 분석 (길이/시간/구조) | SimHash, TLSH, go-diff |
| State Manager | 토큰/ID 관리 및 시퀀스 제어 | sync.Map, regexp2 |

## 📦 프로젝트 구조

```
smart web fuzzer/
├── cmd/
│   └── fluxfuzzer/          # 메인 엔트리포인트
│       └── main.go
├── internal/
│   ├── mutator/             # 변이 엔진
│   │   ├── mutator.go
│   │   ├── radamsa.go
│   │   └── afl.go
│   ├── requester/           # HTTP 요청 엔진
│   │   ├── requester.go
│   │   ├── worker_pool.go
│   │   └── client.go
│   ├── analyzer/            # 응답 분석 엔진
│   │   ├── analyzer.go
│   │   ├── simhash.go
│   │   ├── tlsh.go
│   │   └── baseline.go
│   ├── state/               # 상태 관리
│   │   ├── manager.go
│   │   ├── extractor.go
│   │   └── pool.go
│   └── config/              # 설정 관리
│       └── config.go
├── pkg/
│   ├── types/               # 공통 타입 정의
│   │   └── types.go
│   └── utils/               # 유틸리티
│       └── utils.go
├── wordlists/               # SecLists 기반 워드리스트
├── rules/                   # 퍼징 규칙 정의
├── docs/                    # 추가 문서
├── tests/                   # 테스트 케이스
├── go.mod
├── go.sum
├── README.md
├── ARCHITECTURE.md          # 상세 아키텍처 문서
├── DEVELOPMENT.md           # 개발 가이드
└── ROADMAP.md               # 개발 로드맵
```

## 🚀 빠른 시작

```bash
# 빌드
go build -o fluxfuzzer ./cmd/fluxfuzzer

# 기본 실행
./fluxfuzzer -u http://target.com/api -w wordlists/common.txt

# 상태 기반 퍼징
./fluxfuzzer -c scenario.yaml
```

## 🛠️ 개발 환경

- **Language**: Go 1.21+
- **주요 의존성**:
  - `github.com/valyala/fasthttp` - 고성능 HTTP 클라이언트
  - `github.com/panjf2000/ants` - 고루틴 풀
  - `github.com/glaslos/tlsh` - 구조적 유사도
  - `github.com/charmbracelet/bubbletea` - TUI 대시보드
  - `github.com/dlclark/regexp2` - 고급 정규식

## 📚 참고 자료

- [ffuf](https://github.com/ffuf/ffuf) - Go 기반 퍼저 구조 참고
- [Nuclei](https://github.com/projectdiscovery/nuclei) - DSL/Workflows 참고
- [RESTler Paper](https://www.microsoft.com/en-us/research/publication/restler-stateful-rest-api-fuzzing/) - 상태 기반 퍼징 이론

## 📊 개발 현황

현재 개발 단계: **Phase 3 - The Chameleon** (상태 기반 & 변이)

자세한 개발 로드맵은 [ROADMAP.md](./ROADMAP.md)를 참조하세요.

---

**License**: MIT
