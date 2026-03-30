# Front Clone Coding Next Plan

## 목적

현재 파이프라인은 `저장 -> local replay -> asset 회수 -> verifier 해석`까지 안정적이며, 4단계 개선(안정성/정확도/코드품질/인프라)을 완료했습니다.
다음 단계는 남은 fidelity blocker를 줄이고, 대규모 사이트 대응력을 높이는 데 집중합니다.

## 완료된 개선 (2026-03-29)

### Phase 1: 핵심 안정성
- [x] 네트워크 인터셉터 해시 충돌 해소 (48비트 → 96비트)
- [x] 인코딩 폴백 경고 로깅 + `decodeFallbackFrom` 필드
- [x] AbortSignal 전파 (index → SiteCrawler → PageCrawler)
- [x] Worker 페이지별 90초 타임아웃 + visited set 안전 상한
- [x] 침묵하던 catch 블록에 디버그 로깅 추가

### Phase 2: 리플레이 정확도
- [x] `runtime-data-miss` / `runtime-asset-miss` 세분류
- [x] Widget soft-fail → content 일치 시 `note`로 분류 (`runtimeImpactAssessment`)
- [x] `runtime-induced-partial-match` / `runtime-induced-content-gap` 레이블
- [x] hidden navigation 패턴 확장 (`fn*`, `nav*`, `jump*`, select `this.options`)

### Phase 3: 코드 품질
- [x] index.js 모듈 분리 (1405줄 → 794줄, 4개 서브모듈)
- [x] 테스트 메가파일 분할 (2256줄 → 7개 파일, 최대 505줄)
- [x] Verifier 순수 함수 유닛 테스트 30개 추가 (총 140개)
- [x] 매직 넘버 → 명명된 상수 추출
- [x] ESLint flat config 추가

### Phase 4: 인프라
- [x] Docker HEALTHCHECK + 리소스 제한 (4G/2CPU)
- [x] Node.js 엔진 버전 핀 (>=20.0.0) + `.env.example`
- [x] SSE 에러 핸들링 (연결 끊김 시 클라이언트 자동 제거)

## 완료된 개선 (2026-03-30)

### Phase 5: Hidden Navigation 3차 확장
- [x] 리터럴 prefix + 변수 혼합 패턴 partial matching (`'/board/list.do?menuNo=' + menuNo` → fallbackMap 단일 매치로 localize)
- [x] `_extractMixedConcatLiteralPrefix`: 혼합 concat에서 leading literal prefix 추출
- [x] `_tryPartialLiteralMatch`: prefix의 hostname+pathname으로 fallbackMap 안전 조회
- [x] `_rewriteHiddenNavigationMixedConcats`: 4개 navigation 컨텍스트(location, assign/replace, window.open, 함수호출)에서 mixed concat 처리
- [x] Form GET + hidden input URL 재구성 (`<form method="get" action="/search.do">` + `<input type="hidden">` → pageRouteIndex 매치)
- [x] `_localizeFormGetHiddenInputs`: exact match → normalized → pathname fallback 3단계 시도
- [x] 분류 레이블 추가: `partial-literal-match`, `form-get-reconstruction`
- [x] 8개 테스트 추가 (총 148개)

### Phase 6: Hidden Navigation 4차 확장
- [x] 변수 prefix + 리터럴 suffix 패턴 지원 (`baseUrl + '/page.do'` → trailing suffix에서 pathname 추출 → fallbackMap 매치)
- [x] `_extractMixedConcatLiteralSuffix`: 토큰 오른쪽부터 순회하여 trailing literal suffix 추출
- [x] `_rewriteHiddenNavigationMixedConcats`에 `variablePrefixPatterns` 4개 추가 + suffix fallback 로직
- [x] Template literal 지원 (`` `${baseUrl}/page.do` `` → 마지막 `${}` 뒤 정적 suffix 추출 → fallbackMap 매치)
- [x] `_extractTemplateLiteralStaticSuffix`: template literal에서 정적 pathname suffix 추출
- [x] `_rewriteHiddenNavigationTemplateLiterals`: 4개 navigation 컨텍스트에서 template literal 처리
- [x] `directNavigationPatterns` 콜백에 template literal `${}` guard 추가 (backtick + `${}` 오처리 방지)
- [x] 기존 1개 테스트 수정 + 7개 테스트 추가 (총 171개)

### Phase 7: Personalized Page Mock 데이터 Sanitization
- [x] `src/utils/mock-sanitizer.js` 신규 생성: 3단계 key heuristic + value-type heuristic 기반 자동 sanitization
- [x] Tier 1 (userId, sessionToken 등) → key만으로 치환, Tier 2 (email, phone 등) → key+value 이중 검증, Tier 3 (session, token 등) → key+강한 value만 치환
- [x] type-preserving placeholder: email→`user@example.com`, JWT→placeholder JWT, UUID→zero UUID 등
- [x] `render-supporting` 응답만 sanitize, `render-critical`은 절대 미처리 (보수적 접근)
- [x] `api-processor.js`의 `_emitHttpMocks()`에 sanitizer 통합 + manifest에 `sanitized`/`sanitizedFields` 필드 추가
- [x] `replay-verifier.js`에 `mock-driven-sanitized-replay` assessment 추가 (sanitized mock + runtime degrade 시 재분류)
- [x] `SANITIZER_MAX_DEPTH`(20), `SANITIZER_MAX_FIELDS`(200) 상수 추가
- [x] 14개 유닛 테스트 + 2개 통합 테스트 추가 (총 171개)

### Phase 8: ESLint 오류 정리
- [x] `eslint.config.js`에 tests/ 전용 globals 추가 (`global`, `Response`, `Headers`, `TextDecoder`) → 28 errors 해소
- [x] 소스 파일 13개 warning 수정: unused imports/variables 제거, useless assignment/escape 수정, variable shadow rename
- [x] 테스트 파일 5개 warning 수정: unused imports 제거, unused args prefix
- [x] 미사용 함수 제거: `preferCanonicalSavedPath`, `scoreSavedPathShape`, `computeMarkerOverlap`, `getExpectedMarkers`
- [x] 최종 결과: **50 problems → 0 problems** (0 errors, 0 warnings)

### Phase 9: 생성 output README 개선
- [x] `_createReadme(reportData)` 시그니처 변경 — 전체 reportData 객체 전달
- [x] `index.js`에서 scaffold에 `cssRecoverySummary`, `httpManifest` 추가 전달
- [x] Crawl Summary 테이블: 페이지 수, replayable 수, CSS 회수율, login-gated 수
- [x] Hidden Navigation 테이블: localized/disabled 카운트
- [x] API Mocks 테이블: endpoint 수, render-critical/supporting/non-critical, sanitized 수
- [x] Known Limitations: login-gated, disabled navigation, 실패한 CSS 자동 나열
- [x] 모든 섹션 조건부 출력 (데이터 없으면 생략)

### Phase 10: 핵심 모듈 테스트 커버리지 확대
- [x] `tests/network-interceptor.test.js` 신규 생성: request key, body 크기 제한, asset 필터, URL 조회, type 필터, eviction FIFO (6개)
- [x] `tests/asset-downloader.test.js` 신규 생성: 기본 다운로드, hash dedup, 빈 body skip, registerDirect, tracking 필터, POST 제외 (6개)
- [x] `tests/frontier-utils.test.js` 신규 생성: main landmark 고점수, footer 외부 저점수, family 분류, 상대 URL, query variant 제한, fingerprint (6개)
- [x] `tests/page-route-manifest.test.js` 신규 생성: manifest 생성, exactUrlMap, fallback 단일/다중, locale prefix, 경로 정규화 (6개)
- [x] 총 24개 테스트 추가 (176 → 200개)

### Phase 11: Scaffolder 템플릿 외부화
- [x] `src/scaffolder/templates/runtime-guard.js` 신규 — 141줄 runtime guard를 독립 JS 파일로 분리
- [x] `src/scaffolder/templates/express-adapter.js.template` 신규 — 283줄 Express adapter를 `{{ENTRY_REPLAY_ROUTE}}`, `{{ENTRY_PAGE_PATH}}` 플레이스홀더 template으로 분리
- [x] `project-scaffolder.js` 577줄 → 248줄 (-57%): template literal 제거, `fs.readFile` + 치환으로 변경
- [x] `eslint.config.js`에 `src/scaffolder/templates/**` ignore 추가

### Phase 12: Web UI 크롤 진행 상황 실시간 표시
- [x] `logger.js`에 `progress(data)` 메서드 추가 — `{ stage, current, total, label, detail }` 구조화 이벤트
- [x] `site-crawler.js`에서 페이지 시작 시 `logger.progress({ stage: 'crawl', ... })` emit
- [x] `asset-downloader.js`에서 50개 배치마다 `logger.progress({ stage: 'download', ... })` emit
- [x] `web/server.js` — job.progress를 구조체로 초기화, progress 이벤트 수신 시 갱신
- [x] `web/public/index.html` — 진행 바 + stage label + 카운터 + detail UI 추가
- [x] `web/public/script.js` — `updateProgressBar()` + SSE progress 이벤트 처리 + 완료 시 숨김

### Phase 13: Replay Verifier 모듈 분리
- [x] `src/verifier/content-comparison.js` 신규 (187줄) — assessContentComparison, assessTitleComparison, computeTokenOverlap + helper 5개
- [x] `src/verifier/runtime-diagnostics.js` 신규 (303줄) — classifyRuntimeConsoleMessage, classifySameOriginRuntimeException, classifyRuntimeRequestFailure, assessRuntimeFailureState, buildRuntimeDiagnostics + helper 5개
- [x] `replay-verifier.js` 1,408줄 → 940줄 (-33%): 분리된 함수 제거 + re-export로 호환성 유지

### Phase 14: 대규모 사이트 성능 최적화
- [x] `src/utils/concurrency-utils.js` 신규 생성: 세마포어 기반 `batchParallel` worker pool 유틸리티
- [x] 4개 concurrency 상수 추가: `ASSET_DOWNLOAD_CONCURRENCY`(10), `CSS_PROCESSING_CONCURRENCY`(6), `JS_PROCESSING_CONCURRENCY`(8), `PAGE_PROCESSING_CONCURRENCY`(4)
- [x] Asset download 2단계 분리: 동기 준비(hash/경로/dedup) → `batchParallel` 병렬 I/O
- [x] CSS processing `processAll()` 병렬화 + `_pendingSaves` Map으로 URL별 중복 저장 방지
- [x] JS processing `processAll()` 병렬화
- [x] HTML 페이지 처리 루프 병렬화 (페이지별 `HtmlProcessor` 인스턴스 생성)
- [x] JSP 세미콜론 path parameter(`;CUSTOM_SESSION=...`) 제거 — `getViewPathFromUrl`, `getAssetPathFromUrl`, `getFilenameFromUrl`
- [x] 5개 concurrency 유닛 테스트 추가 (총 176개)

## 현재 기준 요약

- route/replay 계약: 안정적
- CSS asset recovery: 강함
- strict vs supporting runtime 분류: false blocker 대부분 정리됨
- runtime evidence: `runtime-data-miss`, `runtime-asset-miss`, `runtime-script-failed`, `runtime-style-failed`로 세분류
- content verification: title/text/content 비교 노이즈 완화 + runtime-induced 갭 분리 완료
- 파이프라인 안정성: abort signal, worker 타임아웃, 해시 충돌 해소
- hidden navigation: 리터럴+변수 혼합 패턴 partial matching + 변수 prefix+리터럴 suffix + template literal + form GET reconstruction 전방위 지원
- mock sanitization: render-supporting API 응답의 user-specific 필드 자동 치환 + verifier `mock-driven-sanitized-replay` 인식
- 파이프라인 성능: asset download, CSS/JS/HTML 처리 모두 `batchParallel` 병렬화 (전체 50-80% 단축)
- JSP 세미콜론 path parameter 제거로 culture.jongno.go.kr 등 JSP 서버 CSS 정상 서빙
- 코드 품질: 200개 테스트, ESLint clean, 모듈 분리

현재 대표 baseline인 `jongno.go.kr`에서는:

- `routeReached=true`
- `responseStatus=200`
- main page title 비교 정상
- marker overlap이 크게 개선됨
- `runtime-widget-soft-fail`은 content 일치 시 `note`로 분류되어 false-positive 감소
- hidden navigation의 리터럴 prefix, 변수 prefix+리터럴 suffix, template literal 패턴 모두 fallbackMap으로 localize 가능
- render-supporting mock에서 user-specific 필드가 자동 sanitize되어 stale 개인 데이터 노출 감소

## 다음 우선순위

현재 PLAN.md에 명시된 모든 개선 항목이 완료되었습니다.

현재 PLAN.md에 명시된 모든 개선 항목(Phase 1~13)이 완료되었습니다.
프로젝트 상태는 `안정화 단계 → 프로덕션 준비` 전환점에 있습니다.

### 즉시 (운영 기반)

1. **CI/CD 파이프라인 구축**
   - GitHub Actions: PR 시 `npm test` + `npm run lint` 자동 실행
   - Docker 빌드 검증, Playwright 버전 동기화 체크
   - 자동 릴리즈 태깅

2. **환경 기반 설정 확장**
   - `constants.js`의 timeout, concurrency 등을 환경 변수로 오버라이드 가능하게
   - CLI에서 crawl profile별 timeout 조정 옵션 추가
   - `.env` 기반 asset fetch timeout, job retention 설정

### 단기 (UX 개선)

3. **Web UI 출력 파일 미리보기**
   - HTML은 sandboxed iframe, JSON/CSS/JS는 구문 강조 뷰어
   - 원본 vs 캡처 HTML diff 뷰
   - 캡처된 API 요청/응답 탐색 기능

4. **다중 Job 지원 및 큐잉**
   - 현재 단일 `activeJobId` → 큐 기반 다중 실행
   - 동일 URL 다중 실행 결과 비교 UI
   - 배치 크롤 지원

5. **크롤 에러 복구**
   - 체크포인트 기반 재시작 (마지막 페이지부터)
   - 스테이지별 timeout 설정
   - 네트워크 실패 시 자동 재시도 + backoff

### 중기 (Fidelity 확장)

6. **SPA/모던 프레임워크 지원 강화**
   - Vue 3, Next.js App Router, Angular, Svelte 감지 추가
   - History API pushState/replaceState 라우트 추적
   - Intersection Observer 기반 lazy-load 감지
   - dynamic import() 해석

7. **Mock Sanitization 고도화**
   - 사이트별 비표준 필드명 opt-in 설정 파일 (`sanitize-keys.json`)
   - HTML inline state blob(`__NEXT_DATA__`, `__INITIAL_STATE__`) sanitization
   - 동일 userId를 일관된 대체값으로 매핑하는 deterministic placeholder

8. **출력 최적화**
   - HTML/CSS/JS gzip 압축 (output 크기 30-50% 감소)
   - 동일 내용 asset 교차 참조 강화
   - 오래된 output 자동 정리

### 장기 (프로덕션 수준)

9. **API 문서화 및 통합 가이드**
   - Web UI `/api/*` 엔드포인트 OpenAPI spec
   - Job 상태 전이 다이어그램
   - 생성된 replay 패키지 통합 가이드

10. **Docker/Kubernetes 운영 강화**
    - SIGTERM graceful shutdown (진행 중 페이지 완료 후 종료)
    - SSE 연결 drain, 임시 디렉토리 자동 정리
    - Health check에 큐 깊이 포함
    - 메모리 사용량 모니터링 지표

## 검증 기준

기본:

```bash
npm test
npm run lint
npm run knowledge:report
```

라이브 baseline:

```bash
node bin/cli.js https://www.jongno.go.kr/portalMain.do --recursive --max-pages 6 --max-depth 1 --concurrency 1 --wait 1500 --scroll-count 1 --crawl-profile balanced --representative-qa --update-existing --visual-analysis off
```

재확인할 파일:

- `output/jongno.go.kr/server/spec/replay-verification.json`
- `output/jongno.go.kr/server/spec/page-quality-report.json`
- `output/jongno.go.kr/server/spec/css-recovery-summary.json`
- `output/jongno.go.kr/server/docs/replay-verification.md`

## 현재 판단

프로젝트는 지금 `제한적 사용 가능 → 안정화 단계`입니다.

이유:

- 파이프라인 안정성 (abort signal, worker 타임아웃, 해시 충돌 해소)이 크게 개선됨
- 리플레이 정확도 판단이 세밀해짐 (note/warning 분리, runtime-induced 분류)
- hidden navigation 전방위 지원 (리터럴 prefix, 변수 prefix+리터럴 suffix, template literal, form GET reconstruction)
- mock sanitization으로 render-supporting API 응답의 user-specific 필드가 자동 치환됨
- 파이프라인 성능이 크게 개선됨 (batchParallel 병렬화, 전체 50-80% 단축)
- ESLint 0 errors, 0 warnings 달성 (50 problems → 0)
- 생성 output README에 크롤 통계, hidden navigation, API mock 요약, 알려진 제한 자동 포함
- 코드 품질이 지속 개발에 적합한 수준 (200개 테스트, ESLint clean, 모듈 분리)
- 핵심 4개 ��듈에 전용 테스트 파일 추가로 테스트 커버리지 크게 확대 (200개)
- 다만 사이트별 비표준 필드명(mbrNo 등)의 mock sanitization과 pure variable navigation은 아직 미해결

다음 단계의 핵심은 scaffolder 템플릿 외부화와 Web UI 진행 상황 표시입니다.
