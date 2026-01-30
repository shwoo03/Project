# 📊 FluxFuzzer 개발 로드맵

> 이 문서는 프로젝트의 단계별 개발 계획을 정의합니다.

## 전체 타임라인 개요

```
Phase 1: The Runner     [==================>    ] 1~2주 ✅
Phase 2: The Brain      [===================>    ] 2~3주 ✅
Phase 3: The Chameleon  [====================>  ] 3~4주
Phase 4: Polish         [                        ] 2주
                        ────────────────────────────────
                        Total: 8~11주
```

---

## 📦 Phase 1: The Runner (기초 체력 다지기) ✅

> **목표**: 빠르고 안정적인 요청 엔진 구축 및 웹 대시보드 연동
> **성공 기준**: 로컬 테스트 서버에 초당 1,000 RPS 달성 및 실시간 UI 모니터링

### Task 1.1: 프로젝트 초기 설정 ✅
- [x] Go 모듈 초기화
- [x] 디렉토리 구조 생성
- [x] 기본 의존성 정의

### Task 1.2: FastHTTP 기반 HTTP 클라이언트 ✅
- [x] `internal/requester/client.go` 구현
  - [x] fasthttp.Client 래퍼
  - [x] 연결 풀링 설정
  - [x] 타임아웃/재시도 로직

### Task 1.3: Worker Pool 구현 ✅
- [x] `internal/requester/worker_pool.go` 구현
  - [x] panjf2000/ants 기반 고루틴 풀
  - [x] 동적 워커 스케일링
  - [x] 우아한 종료 처리

### Task 1.4: 웹 대시보드 통합 ✅
- [x] Fiber 기반 웹 서버 구축
- [x] 실시간 WebSocket 피드 구현
- [x] 사이버펑크 스타일 UI/UX 디자인

### Task 1.5: 기본 CLI ✅
- [x] `cmd/fluxfuzzer/main.go` 구현
  - [x] Cobra 기반 명령어 확장 (web 커맨드 포함)
  - [x] ASCII 아트 배너 추가

### Task 1.6: 검증 ✅
- [x] 벤치마크 테스트 작성
- [x] 1시간 안정성 테스트
- [x] 메모리 누수 검사

---

## 🧠 Phase 2: The Brain (구조적 차분 분석)

> **목표**: 서버의 미세한 반응 변화를 감지하는 분석 엔진  
> **예상 기간**: 2~3주  
> **성공 기준**: 정상 응답과 에러 페이지를 구조적으로 구분

### Task 2.1: Baseline 학습 시스템 ✅
- [x] `internal/analyzer/baseline.go` 구현
  - [x] 초기 N회 요청으로 기준 수집
  - [x] 평균 응답 시간 계산
  - [x] 평균 응답 길이 계산
  - [x] 표준 편차 계산

### Task 2.2: SimHash 구현 ✅
- [x] `internal/analyzer/simhash.go` 구현
  - [x] HTML 구조 추출
  - [x] 토큰화 및 해시 생성
  - [x] Hamming Distance 계산

### Task 2.3: TLSH 연동 ✅
- [x] `internal/analyzer/tlsh.go` 구현
  - [x] glaslos/tlsh 라이브러리 연동
  - [x] 유사도 점수 계산
  - [x] 임계값 기반 판정

### Task 2.4: 기본 필터링 ✅
- [x] `internal/analyzer/filter.go` 구현
  - [x] 응답 길이 기반 필터
  - [x] 단어 수 기반 필터
  - [x] 상태 코드 기반 필터

### Task 2.5: 분석 통합 ✅
- [x] `internal/analyzer/analyzer.go` 구현
  - [x] 분석 파이프라인 조합
  - [x] 복합 이상 판정 로직
  - [x] 결과 집계

---

## 🦎 Phase 3: The Chameleon (상태 기반 & 변이)

> **목표**: 이전 요청의 결과값을 활용하는 지능적 퍼징  
> **예상 기간**: 3~4주  
> **성공 기준**: 다단계 API 시나리오 자동 실행

### Task 3.1: 값 추출기 ✅
- [x] `internal/state/extractor.go` 구현
  - [x] 정규식 기반 패턴 매칭
  - [x] JSON Path 지원
  - [x] 커스텀 추출 규칙

### Task 3.2: Dynamic Pool ✅
- [x] `internal/state/pool.go` 구현
  - [x] Thread-safe 저장소
  - [x] TTL 기반 만료
  - [x] 중복 제거

### Task 3.3: 템플릿 치환 ✅
- [x] `internal/state/manager.go` 구현
  - [x] `{{variable}}` 문법 지원
  - [x] 내장 함수 (random_str, timestamp 등)
  - [x] 조건부 치환

### Task 3.4: Mutator 엔진 ✅
- [x] `internal/mutator/mutator.go` 구현
  - [x] 변이 전략 인터페이스
  - [x] 랜덤 변이 선택기

### Task 3.5: AFL 스타일 변이 ✅
- [x] `internal/mutator/afl.go` 구현
  - [x] Bit flip (1, 2, 4 bits)
  - [x] Byte flip (1, 2, 4 bytes)
  - [x] Arithmetic operations (8, 16, 32 bit)
  - [x] Interesting values (8, 16, 32 bit)
  - [x] Byte swap (2, 4 bytes)
  - [x] Random byte mutation
  - [x] Delete/Insert/Clone mutations

### Task 3.6: 타입 인식 변이 ✅
- [x] `internal/mutator/smart.go` 구현
  - [x] 자료형 추론 (TypeInferrer)
  - [x] 타입별 페이로드 선택 (SQLi, XSS, 등)
  - [x] JSON/XML 구조 보존
  - [x] 경계값 변이 (BoundaryMutator)
  - [x] 유니코드 공격 (UnicodeAttackMutator)

### Task 3.7: 시나리오 엔진 ✅
- [x] `internal/scenario/scenario.go` 구현
  - [x] YAML 기반 시나리오 정의
  - [x] 순차 실행 지원
  - [x] 조건부 분기

---

## 💎 Phase 4: Polish (마무리)

> **목표**: 사용성 및 안정성 강화  
> **예상 기간**: 2주

### Task 4.1: TUI 대시보드 ✅
- [x] `internal/ui/dashboard.go` 구현
  - [x] bubbletea 기반 UI
  - [x] 실시간 통계 표시
  - [x] 진행률 바

### Task 4.2: 리포트 생성 ✅
- [x] `internal/report/report.go` 구현
  - [x] JSON 출력
  - [x] HTML 리포트 (템플릿)
  - [x] Markdown 요약

### Task 4.3: 문서화 ✅
- [x] API 문서 작성
- [x] 사용 예제 추가
- [x] 튜토리얼 작성

### Task 4.4: 테스트 강화 ✅
- [x] 단위 테스트 커버리지 80% 이상
- [x] 통합 테스트 작성
- [x] 성능 회귀 테스트

---

## 📈 진행 상황 기록

| 날짜 | Phase | 완료 항목 | 비고 |
|------|-------|----------|------|
| 2026-01-30 | 1 | 프로젝트 초기화, 문서 작성 | 시작 |
| 2026-01-30 | 1 | Task 1.6 검증 구현 | 벤치마크, 안정성, 메모리 테스트 완료 |
| 2026-01-30 | 2 | Task 2.1 Baseline 학습 시스템 | 통계 분석, 이상 탐지 기능 구현 |
| 2026-01-30 | 2 | Task 2.2 SimHash 구현 | HTML 구조 추출, Hamming Distance |
| 2026-01-30 | 2 | Task 2.3 TLSH 연동 | glaslos/tlsh 라이브러리 연동 |
| 2026-01-30 | 2 | Task 2.4 기본 필터링 | 상태코드, 길이, 단어수, 정규식 필터 |
| 2026-01-30 | 2 | Task 2.5 분석 통합 | 분석 파이프라인, 복합 이상 판정, 결과 집계 |
| 2026-01-30 | 3 | Task 3.1 값 추출기 | 정규식, JSON Path, 헤더, 쿠키 추출 |
| 2026-01-30 | 3 | Task 3.2 Dynamic Pool | Thread-safe 저장소, TTL 만료, 중복 제거 |
| 2026-01-30 | 3 | Task 3.3 템플릿 치환 | 변수 치환, 내장 함수, 조건부 치환 |
| 2026-01-30 | 3 | Task 3.4 Mutator 엔진 | Mutator 인터페이스, Registry, 랜덤/가중치 선택기 |
| 2026-01-30 | 3 | Task 3.5 AFL 스타일 변이 | BitFlip, ByteFlip, Arithmetic, InterestingValue, 기타 |
| 2026-01-30 | 3 | Task 3.6 타입 인식 변이 | SmartMutator, JSON/XML 변이, TypeInferrer, Unicode 공격 |
| 2026-01-30 | 3 | Task 3.7 시나리오 엔진 | YAML 파서, 순차 실행, 조건부 분기, 어서션 검증 |
| 2026-01-30 | 4 | Task 4.1 TUI 대시보드 | bubbletea UI, 실시간 통계, 진행률 바, 사이버펑크 스타일 |
| 2026-01-30 | 4 | Task 4.2 리포트 생성 | JSON/HTML/Markdown 리포트, 사이버펑크 HTML 템플릿 |
| 2026-01-30 | 4 | Task 4.3 문서화 | API 문서, 사용 예제, 튜토리얼 |
| 2026-01-30 | 4 | Task 4.4 테스트 강화 | 통합 테스트, 성능 회귀 테스트 |

---

## 🎯 마일스톤

### v0.1.0 - Runner 완성
- FastHTTP 기반 고속 요청 엔진
- 기본 CLI 인터페이스
- 워드리스트 지원

### v0.2.0 - Brain 완성
- 구조적 차분 분석
- Baseline 자동 학습
- 이상 탐지 알림

### v0.3.0 - Chameleon 완성
- 상태 기반 퍼징
- 스마트 변이
- 시나리오 지원

### v1.0.0 - 정식 출시
- TUI 대시보드
- 리포트 생성
- 완전한 문서화
