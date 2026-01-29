# FluxFuzzer 구현 계획

## 현재 상태
- **Phase**: Phase 1 - The Runner (기초 체력 다지기)
- **목표**: 빠르고 안정적인 요청 엔진 구축
- **성공 기준**: 로컬 테스트 서버에 초당 1,000 RPS 달성

## 즉시 구현할 작업

### 1. Go 모듈 초기화
- `go mod init github.com/fluxfuzzer/fluxfuzzer`

### 2. 디렉토리 구조 생성
```
cmd/fluxfuzzer/
internal/
    requester/
    analyzer/
    mutator/
    state/
    config/
pkg/types/
wordlists/
```

### 3. 핵심 파일 구현 순서

1. **pkg/types/types.go** - 공통 타입 정의
2. **internal/config/config.go** - 설정 구조체
3. **internal/requester/client.go** - HTTP 클라이언트
4. **internal/requester/worker_pool.go** - 워커 풀
5. **internal/requester/requester.go** - 요청 처리 통합
6. **cmd/fluxfuzzer/main.go** - CLI 엔트리포인트

## 참고 문서
- README.md - 프로젝트 개요
- ARCHITECTURE.md - 상세 아키텍처
- ROADMAP.md - 개발 로드맵
- DEVELOPMENT.md - 개발 가이드
