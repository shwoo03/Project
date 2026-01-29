---
description: FluxFuzzer 프로젝트 개발 워크플로우 - 새 세션에서 이 파일 먼저 읽기
---

# FluxFuzzer 개발 워크플로우

이 프로젝트는 Go 기반의 스마트 웹 퍼저입니다.

## 프로젝트 시작 전 확인 사항

1. 먼저 다음 문서들을 순서대로 읽으세요:
   - `README.md` - 프로젝트 개요 및 목표
   - `ARCHITECTURE.md` - 시스템 아키텍처 및 데이터 구조
   - `ROADMAP.md` - 개발 로드맵 및 진행 상황
   - `DEVELOPMENT.md` - 개발 가이드 및 코딩 컨벤션

2. 현재 진행 상황 확인:
   - `ROADMAP.md`의 체크박스 상태 확인
   - `.agent/workflows/project-status.md`에서 최근 작업 확인

## 개발 진행 방법

// turbo-all
### Phase 1: The Runner 작업 시

1. Go 모듈 확인
```bash
cd "c:\Users\dntmd\OneDrive\Desktop\my\Project\smart web fuzzer"
go mod tidy
```

2. 빌드 테스트
```bash
go build ./...
```

3. 테스트 실행
```bash
go test ./...
```

### 파일 생성 순서

Phase 1에서는 다음 순서로 파일을 생성합니다:

1. `pkg/types/types.go` - 공통 타입
2. `internal/config/config.go` - 설정
3. `internal/requester/client.go` - HTTP 클라이언트
4. `internal/requester/worker_pool.go` - 워커 풀
5. `internal/requester/requester.go` - 요청 처리
6. `cmd/fluxfuzzer/main.go` - CLI

## 코딩 가이드라인

- 인터페이스 기반 설계 유지
- 에러는 wrap하여 컨텍스트 추가
- 로깅은 slog 사용
- 테스트는 testify 사용

## 진행상황 업데이트

작업 완료 후:
1. `ROADMAP.md`의 해당 Task 체크박스 업데이트
2. `.agent/workflows/project-status.md` 업데이트
