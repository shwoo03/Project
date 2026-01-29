# FluxFuzzer 검증 테스트 실행 가이드

## 설치 및 준비

```powershell
# 프로젝트 루트 디렉토리로 이동
cd "c:\Users\dntmd\OneDrive\Desktop\my\Project\smart web fuzzer"

# 의존성 다운로드
go mod tidy
```

## 1. 벤치마크 테스트 (성능 측정)

```powershell
# 전체 벤치마크 실행
go test -bench=. -benchmem ./tests/benchmark/...

# RPS 목표 달성 테스트
go test -v -run TestTargetRPS ./tests/benchmark/...
```

**예상 결과:**
- `BenchmarkClientDo`: 마이크로초 단위 응답
- `BenchmarkWorkerPoolWithHTTP`: 수천 RPS 달성
- `TestTargetRPS`: 1,000 RPS 이상 달성 (80% 이상 성공률)

## 2. 안정성 테스트 (장기 실행)

```powershell
# 10분 안정성 테스트 (기본)
go test -v -timeout 15m -run TestStability_Short ./tests/stability/...

# 1시간 전체 안정성 테스트
go test -v -timeout 65m -run TestStability_Full ./tests/stability/...
```

**측정 지표:**
- 성공률 (99% 이상 목표)
- 평균/최대 레이턴시
- 메모리 사용량 추이

## 3. 메모리 누수 검사

```powershell
# 워커 풀 메모리 테스트
go test -v -run TestMemoryLeak_WorkerPool ./tests/memory/...

# HTTP 클라이언트 메모리 테스트
go test -v -run TestMemoryLeak_HTTPClient ./tests/memory/...

# 응답 바디 메모리 테스트
go test -v -run TestMemoryLeak_ResponseBody ./tests/memory/...

# 전체 메모리 테스트
go test -v -run TestMemoryLeak ./tests/memory/...
```

**검증 기준:**
- 메모리 증가량 50MB 미만 (단기 테스트)
- 메모리 증가율 2배 미만 (장기 테스트)

## 4. 전체 테스트 실행

```powershell
# 빠른 테스트 (short 모드)
go test -short ./tests/...

# 전체 테스트 (시간 소요)
go test -v -timeout 30m ./tests/...

# 테스트 커버리지
go test -coverprofile=coverage.out ./internal/requester/...
go tool cover -html=coverage.out -o coverage.html
```

## 테스트 파일 위치

```
tests/
├── benchmark/
│   └── requester_benchmark_test.go    # 성능 벤치마크
├── stability/
│   └── stability_test.go              # 안정성 테스트
└── memory/
    └── memory_leak_test.go            # 메모리 누수 검사
```
