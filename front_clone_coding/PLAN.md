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

## 현재 기준 요약

- route/replay 계약: 안정적
- CSS asset recovery: 강함
- strict vs supporting runtime 분류: false blocker 대부분 정리됨
- runtime evidence: `runtime-data-miss`, `runtime-asset-miss`, `runtime-script-failed`, `runtime-style-failed`로 세분류
- content verification: title/text/content 비교 노이즈 완화 + runtime-induced 갭 분리 완료
- 파이프라인 안정성: abort signal, worker 타임아웃, 해시 충돌 해소
- 코드 품질: 140개 테스트, ESLint, 모듈 분리

현재 대표 baseline인 `jongno.go.kr`에서는:

- `routeReached=true`
- `responseStatus=200`
- main page title 비교 정상
- marker overlap이 크게 개선됨
- `runtime-widget-soft-fail`은 content 일치 시 `note`로 분류되어 false-positive 감소

## 다음 우선순위

### 1. Hidden Navigation 3차 확장 (변수 기반 동적 경로)

목표:

- `goPage(baseUrl + param)` 같은 변수 결합 패턴을 정적으로 해석 가능한 범위 확대
- 현재 disabled 처리되는 hidden navigation 중 안전하게 localize 가능한 비율 증가

구현 방향:

- 문자열 리터럴 + 변수 조합 패턴에서 리터럴 부분만으로 pageRouteIndex 대조 시도
- 안전하게 해석 불가한 패턴은 여전히 disabled 유지
- form GET action에 hidden input으로 구성된 query parameter 조합 해석

성공 기준:

- Jongno 등 portal의 `localizedHiddenNavigationCount` 추가 증가
- live leakage 증가 없이 `disabledHiddenNavigationCount` 감소

### 2. Personalized Page Mock 데이터 전략

목표:

- personalized page에서 `runtime-induced-partial-match`가 뜰 때 실질적 해결 경로 제공

구현 방향:

- 캡처된 XHR/fetch 응답에서 user-specific 필드를 generic placeholder로 치환한 mock 자동 생성
- mock fallback 적용 시 verifier가 mock-driven replay임을 명시

성공 기준:

- personalized page에서 mock 적용 후 content gap이 `partial-match` → `content-match`로 개선되는 케이스 확인

### 3. 대규모 사이트 성능 최적화

목표:

- 100+ 페이지 크롤에서도 안정적 처리 시간과 메모리 사용

구현 방향:

- CSS/JS 프로세서의 순차 처리를 병렬 배치로 전환
- Cheerio DOM traversal 배칭 (selector별 개별 순회 → 통합 순회)
- Docker multi-stage build로 이미지 크기 최적화

성공 기준:

- 50페이지 크롤 기준 처리 시간 20% 단축
- Docker 이미지 크기 감소

### 4. Scaffolder 템플릿 외부화

목표:

- 150줄+ 템플릿 리터럴을 별도 파일로 분리하여 유지보수성 향상

구현 방향:

- `src/scaffolder/templates/` 디렉토리에 `.js.template` 파일로 이동
- 플레이스홀더 치환 방식으로 생성

성공 기준:

- `tests/scaffolder.test.js` 통과, 생성 파일 바이트 동일

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
- 코드 품질이 지속 개발에 적합한 수준 (140개 테스트, ESLint, 모듈 분리)
- 다만 변수 기반 동적 경로와 personalized page mock은 아직 미해결

다음 단계의 핵심은 `hidden navigation 3차 확장`과 `personalized page mock 전략`입니다.
