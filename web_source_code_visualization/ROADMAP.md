# 🗺️ Development Roadmap: Enterprise-Scale Code Analysis

> **목표**: Google 규모의 대형 오픈소스 프로젝트(수만 개 파일, 수백만 LOC)를 분석할 수 있는 웹 소스코드 시각화 도구

**Last Updated**: 2026-01-30

---

## 📊 Current State

현재 프로젝트는 중소규모 웹 애플리케이션 분석에 적합합니다:
- ✅ Multi-language parsing (Python, JS/TS, PHP, Java, Go)
- ✅ Framework detection (Flask, FastAPI, Express, Spring, etc.)
- ✅ Basic taint analysis (source → sink)
- ✅ Inter-procedural taint analysis (Phase 2.1 완료)
- ✅ Enhanced import resolution (Phase 2.2 완료, 86.7% 해석률)
- ✅ Type inference (Phase 2.3 완료)
- ✅ Class hierarchy analysis (Phase 2.4 완료)
- ✅ Call graph visualization
- ✅ Security scanning (Semgrep integration)
- ✅ Parallel file processing (Phase 1.1 완료)
- ✅ Analysis caching (Phase 1.2 완료, 23x 속도 향상)
- ✅ UI virtualization (Phase 1.3 완료)
- ✅ Streaming API (Phase 1.4 완료)

**한계점**:
- ❌ 마이크로서비스 API 추적 미지원 → Phase 3 예정
- ❌ 분산 분석 아키텍처 미구현 → Phase 3 예정

---

## 🚀 Phase 1: Performance Foundation ✅ COMPLETE

> **목표**: 대용량 프로젝트의 기본적인 파싱 및 렌더링 지원

### 1.1 병렬 파싱 ✅ DONE
- [x] `concurrent.futures` 기반 병렬 파일 분석
- [x] `ThreadPoolExecutor`로 I/O 바운드 작업 최적화
- [x] 워커 수 자동 조절 (CPU 코어 기반)
- [x] 자동 모드 선택 (파일 <100개: 순차, ≥100개: 병렬)
- [x] 분석 통계 수집 및 API 엔드포인트

**구현 파일**: 
- `backend/core/parallel_analyzer.py` - 병렬 분석 엔진
- `backend/benchmark_parallel.py` - 벤치마크 도구

### 1.2 분석 결과 캐싱 ✅ DONE
- [x] SQLite 기반 분석 결과 저장
- [x] 파일 해시(SHA256) 기반 변경 감지
- [x] 증분 분석 - 변경된 파일만 재파싱
- [x] 캐시 무효화 전략 (파일별, 프로젝트별, 전체)
- [x] 캐시 통계 API 엔드포인트

**성능 결과**: 23x 속도 향상 (591ms → 26ms), 95.7% 시간 절약

**구현 파일**:
- `backend/core/analysis_cache.py` - SQLite 캐시 엔진
- `backend/test_cache.py` - 캐시 테스트 스크립트

**API 엔드포인트**:
- `GET /api/cache/stats` - 캐시 통계 조회
- `POST /api/cache/invalidate` - 선택적 캐시 무효화
- `DELETE /api/cache` - 전체 캐시 삭제

### 1.3 UI 가상화 (Virtual Rendering) ✅ DONE
- [x] `@tanstack/react-virtual` 적용
- [x] 파일 트리 가상화 (VirtualizedFileTree)
- [x] 대용량 코드 뷰어 가상화 (VirtualizedCodeViewer)
- [x] 성능 모니터 컴포넌트 (PerformanceMonitor)
- [x] 점진적 노드 로딩 (Progressive Loading)
- [x] 뷰포트 최적화 훅 (useViewportOptimization)
- [x] ReactFlow 성능 최적화 (드래그/연결 조건부 비활성화)

**성능 기능**:
- 10,000+ 파일 목록 부드러운 스크롤
- 100+ 노드 그래프에서 자동 최적화 활성화
- 실시간 FPS 모니터링

**구현 파일**:
- `frontend/components/panels/VirtualizedFileTree.tsx` - 가상화된 파일 트리
- `frontend/components/virtualized/VirtualizedCodeViewer.tsx` - 가상화된 코드 뷰어
- `frontend/components/feedback/PerformanceMonitor.tsx` - 성능 모니터
- `frontend/hooks/useViewportOptimization.ts` - 뷰포트 최적화 훅

### 1.4 스트리밍 API 응답 ✅ DONE
- [x] FastAPI StreamingResponse 활용
- [x] SSE(Server-Sent Events) 및 NDJSON 포맷 지원
- [x] 실시간 진행률 이벤트 전송
- [x] 대용량 결과 청크 단위 전송
- [x] 프론트엔드 점진적 렌더링
- [x] 스트리밍 취소 기능 (AbortController)
- [x] StreamingProgress UI 컴포넌트

**이벤트 타입**:
- `init` - 분석 초기화 정보
- `progress` - 진행률 업데이트 (파일 수, 퍼센트)
- `symbols` - 심볼 테이블 청크
- `endpoints` - 엔드포인트 배치 전송
- `taint` - 오염 흐름 분석 결과
- `stats` - 최종 통계
- `complete` - 분석 완료
- `error` - 에러 정보

**구현 파일**:
- `backend/core/streaming_analyzer.py` - 스트리밍 분석 엔진
- `frontend/hooks/useStreamingAnalysis.ts` - 스트리밍 소비 훅
- `frontend/components/feedback/StreamingProgress.tsx` - 진행률 UI

**API 엔드포인트**:
- `POST /api/analyze/stream` - 스트리밍 분석 (format: sse/ndjson)
- `POST /api/analyze/stream/cancel` - 스트리밍 취소

---

## 🔧 Phase 2: Core Analysis Enhancement ✅ COMPLETE

> **목표**: 정확한 코드 분석과 함수 간 데이터 흐름 추적

### 2.1 Inter-Procedural Taint Analysis ✅ DONE
- [x] 함수 호출을 통한 taint 전파 추적
- [x] 함수 요약(Function Summaries) 생성
- [x] Context-sensitive 분석
- [x] `TaintSummary` 클래스 - 함수의 input→output 매핑
- [x] Call Graph 기반 taint 전파
- [x] 재귀 호출 처리 (감지 및 무한 루프 방지)
- [x] 최대 깊이 제한 설정 (기본값 10)

```
예시:
def get_user_input():
    return request.args.get('id')  # Source

def process(data):
    return data.upper()

def execute(cmd):
    os.system(cmd)  # Sink

# 추적: get_user_input() → process() → execute()
```

**핵심 기능**:
- **TaintSummary**: 함수별 taint 동작 요약 (파라미터→반환값, 파라미터→싱크)
- **InterProceduralFlow**: 함수 간 taint 흐름 표현 (call chain 포함)
- **PropagationMode**: DIRECT, TRANSFORMED, SANITIZED, BLOCKED
- **자동 소스 감지**: request.args, request.form, request.json 등
- **자동 싱크 감지**: os.system, eval, cursor.execute 등
- **새니타이저 인식**: html.escape, shlex.quote 등

**구현 파일**:
- `backend/core/interprocedural_taint.py` - Inter-Procedural 분석 엔진
- `backend/test_interprocedural.py` - 테스트 스크립트

**API 엔드포인트**:
- `POST /api/taint/interprocedural` - Inter-Procedural 분석 실행
- `POST /api/taint/interprocedural/full` - 전체 결과 (summaries 포함)
- `POST /api/taint/paths` - Taint 경로 조회

### 2.2 Enhanced Import Resolution ✅ DONE
- [x] 모듈 의존성 그래프 구축
- [x] 상대/절대 import 완전 해석
- [x] Alias 처리 (`from x import y as z`)
- [x] Dynamic import 탐지 (`__import__`, `importlib`, `require()`)
- [x] Package `__init__.py` 처리
- [x] JavaScript ES6/CommonJS import 지원
- [x] TypeScript import 지원
- [x] Circular dependency 감지

**지원 언어 및 Import 유형**:
| 언어 | Import 유형 |
|------|------------|
| **Python** | `import`, `from...import`, relative (`.`, `..`), alias, dynamic |
| **JavaScript** | ES6 (`import`), CommonJS (`require`), dynamic (`import()`) |
| **TypeScript** | ES6, type imports, path aliases |

**성능 결과**: 86.7% 해석률 (backend 프로젝트 기준)

**구현 파일**:
- `backend/core/import_resolver.py` - Import 해석 엔진
- `backend/test_import_resolver.py` - 테스트 스크립트

**API 엔드포인트**:
- `POST /api/imports/resolve` - 전체 import 해석 및 의존성 그래프
- `POST /api/imports/graph` - 시각화용 의존성 그래프
- `POST /api/imports/symbol` - 심볼 정의 위치 해석
- `POST /api/imports/module` - 모듈 상세 정보

### 2.3 Type Inference ✅ DONE
- [x] 동적 타입 언어 변수 타입 추론
- [x] 함수 반환 타입 추론
- [x] 클래스 인스턴스 추적
- [x] Type hints 활용 (Python, TypeScript)

**지원 언어 및 기능**:
| 언어 | 타입 소스 |
|------|----------|
| **Python** | Type annotations, 리터럴 추론, docstrings |
| **JavaScript** | 리터럴 추론, JSDoc, new 표현식 |
| **TypeScript** | 전체 타입 시스템 지원 |

**타입 추론 방식**:
- 리터럴 추론: `x = "hello"` → `str`
- 어노테이션: `def foo(x: int) -> str:` → 파싱
- 표현식 분석: `x = User()` → `User` 인스턴스
- 연산자 추론: `a + b` → 피연산자 기반 결과 타입

**구현 파일**:
- `backend/core/type_inferencer.py` - 타입 추론 엔진
- `backend/test_type_inferencer.py` - 테스트 스크립트

**API 엔드포인트**:
- `POST /api/types/analyze` - 전체 프로젝트 타입 분석
- `POST /api/types/variable` - 변수 타입 조회
- `POST /api/types/function` - 함수 시그니처 조회
- `POST /api/types/class` - 클래스 타입 정보 조회

### 2.4 Class Hierarchy Analysis ✅ DONE
- [x] 상속 관계 그래프
- [x] 메서드 오버라이딩 추적
- [x] 다형성(Polymorphism) 호출 해석
- [x] Mixin/Interface 분석
- [x] Method Resolution Order (MRO) 계산
- [x] Diamond Inheritance 감지

**지원 클래스 종류**:
| 종류 | 언어 |
|------|------|
| **Class** | Python, JS, TS |
| **Abstract Class** | Python (ABC), TS |
| **Interface** | TypeScript |
| **Protocol** | Python 3.8+ |
| **Mixin** | Python (다중 상속) |
| **Enum** | TypeScript |
| **Dataclass** | Python |

**핵심 기능**:
- **상속 그래프**: 전체 프로젝트의 클래스 상속 관계 시각화
- **오버라이드 감지**: 어떤 메서드가 부모 메서드를 오버라이드하는지 추적
- **다형성 해석**: 정적 타입 기반 가능한 구현체 목록 제공
- **MRO 계산**: Python C3 linearization 알고리즘 적용
- **Diamond 감지**: 다중 상속 시 공통 조상 감지

**구현 파일**:
- `backend/core/class_hierarchy.py` - 클래스 계층 분석 엔진
- `backend/test_class_hierarchy.py` - 테스트 스크립트

**API 엔드포인트**:
- `POST /api/hierarchy/analyze` - 전체 계층 분석
- `POST /api/hierarchy/class` - 특정 클래스 상속 트리
- `POST /api/hierarchy/implementations` - 인터페이스 구현체 목록
- `POST /api/hierarchy/method` - 메서드 구현 목록
- `POST /api/hierarchy/polymorphic` - 다형성 호출 해석
- `POST /api/hierarchy/graph` - 시각화용 상속 그래프

---

## 🏗️ Phase 3: Enterprise Scale (1-2개월)

> **목표**: 대규모 분산 시스템 분석 및 프로덕션 환경 지원

### 3.1 분산 분석 아키텍처
- [ ] Celery + Redis 기반 비동기 작업 처리
- [ ] 분석 작업 큐잉 및 우선순위
- [ ] 워커 스케일 아웃
- [ ] 진행률 실시간 보고 (WebSocket)

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Frontend      │────▶│  FastAPI     │────▶│  Redis Queue    │
│   (React)       │◀────│  (Gateway)   │◀────│                 │
└─────────────────┘     └──────────────┘     └────────┬────────┘
                                                      │
                        ┌────────────────────────────┬┴───────────────────────────┐
                        ▼                            ▼                            ▼
                 ┌──────────────┐            ┌──────────────┐            ┌──────────────┐
                 │   Worker 1   │            │   Worker 2   │            │   Worker N   │
                 │   (Celery)   │            │   (Celery)   │            │   (Celery)   │
                 └──────────────┘            └──────────────┘            └──────────────┘
```

### 3.2 마이크로서비스 API 추적
- [ ] OpenAPI/Swagger 스펙 파싱
- [ ] gRPC proto 파일 분석
- [ ] REST 엔드포인트 간 호출 관계
- [ ] 서비스 간 데이터 흐름 시각화

### 3.3 Monorepo 지원
- [ ] 다중 프로젝트 구조 자동 감지
- [ ] 언어별 빌드 설정 파싱 (`package.json`, `pom.xml`, `go.mod`)
- [ ] 공유 라이브러리 의존성 추적
- [ ] 서비스별 분리된 분석

### 3.4 Language Server Protocol (LSP) 통합
- [ ] LSP 서버 연동으로 정확한 타입 정보 획득
- [ ] Go-to-definition 정확도 향상
- [ ] IDE 수준의 심볼 해석
- [ ] 지원 언어: Python (Pylance), TypeScript, Java

### 3.5 보안 대시보드
- [ ] 취약점 통계 차트
- [ ] 심각도별 분류
- [ ] 시간별 트렌드
- [ ] PDF/HTML 보고서 내보내기
- [ ] SARIF 포맷 지원

### 3.6 CI/CD 통합
- [ ] GitHub Actions 워크플로우 템플릿
- [ ] GitLab CI 지원
- [ ] PR 코멘트에 분석 결과 자동 게시
- [ ] 취약점 발견 시 빌드 실패 옵션

---

## 📈 Performance Targets

| Metric | Current | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|---------|
| 파일 수 | ~100 | ~1,000 | ~10,000 | ~100,000 |
| 분석 시간 | 5-10초 | 2-5초 | 10-30초 | 1-5분 |
| 메모리 | 500MB | 1GB | 2GB | 분산 |
| 그래프 노드 | ~500 | ~5,000 | ~50,000 | 가상화 |

---

## 🛠️ Tech Stack Additions

### Phase 1
- `concurrent.futures` (Python stdlib)
- `sqlite3` (Python stdlib)
- `react-window` or `@tanstack/virtual`

### Phase 2
- Enhanced Tree-sitter queries
- Custom type inference engine

### Phase 3
- `Celery` + `Redis`
- `WebSocket` (FastAPI WebSocket or Socket.IO)
- LSP client libraries

---

## 📝 Implementation Notes

### Testing Strategy
1. **Unit Tests**: 각 파서, 분석기 모듈별 테스트
2. **Integration Tests**: 전체 파이프라인 테스트
3. **Performance Tests**: 대용량 프로젝트 벤치마크
4. **Real-world Tests**: 실제 오픈소스 프로젝트 분석
   - Flask (중규모)
   - Django (대규모)
   - Kubernetes (Go, 대규모)
   - VS Code (TypeScript, 초대규모)

### Benchmark Projects
| Project | Language | Files | LOC | Target Phase |
|---------|----------|-------|-----|--------------|
| Flask | Python | ~150 | ~15K | Phase 1 |
| FastAPI | Python | ~300 | ~30K | Phase 1 |
| Express | JS | ~100 | ~10K | Phase 1 |
| Django | Python | ~2,000 | ~200K | Phase 2 |
| Spring Boot | Java | ~500 | ~50K | Phase 2 |
| Kubernetes | Go | ~10,000 | ~1M | Phase 3 |

---

## 🎯 Success Criteria

### Phase 1 완료 조건
- [ ] 1,000개 파일 프로젝트 5초 이내 분석
- [ ] 5,000개 노드 그래프 60fps 렌더링
- [ ] 재분석 시 변경 파일만 처리

### Phase 2 완료 조건
- [ ] 함수 3단계 호출 체인 taint 추적
- [ ] Import 해석 정확도 95% 이상
- [ ] Django/Spring Boot 프레임워크 완전 지원

### Phase 3 완료 조건
- [ ] 100,000개 파일 프로젝트 분석 가능
- [ ] 마이크로서비스 간 API 흐름 시각화
- [ ] CI/CD 파이프라인 통합 완료

---

## 📅 Timeline

```
2026년 2월    Phase 1 완료 (성능 기반)
2026년 3월    Phase 2 완료 (분석 강화)
2026년 4-5월  Phase 3 완료 (엔터프라이즈)
```

---

## 💡 Future Ideas (Post Phase 3)

- **AI 기반 취약점 예측**: ML 모델로 잠재적 취약점 탐지
- **자동 수정 제안**: LLM 기반 보안 패치 코드 생성
- **실시간 협업**: 팀원 간 분석 결과 공유 및 주석
- **IDE 플러그인**: VS Code, IntelliJ 확장
- **SaaS 버전**: 클라우드 호스팅 분석 서비스
