# 현재 진행 상태

이 문서는 `Front Clone Coding` 프로젝트의 최신 진행 상황을 빠르게 확인하기 위한 체크 문서입니다.

## 현재 방향

- 목표는 단순 HTML 저장이 아니라 `로컬에서 다시 실행 가능한 replay 패키지`를 만드는 것입니다.
- 사이트별 임시 패치보다 여러 사이트에 재사용 가능한 generic rule을 우선합니다.
- 현재는 `더 많이 크롤링`보다 `이미 저장된 페이지를 더 정확하고 안정적으로 replay`하는 쪽이 우선입니다.

## 최근까지 반영된 핵심 개선

- saved page 기준 local replay route 계약 정리
- query-addressed legacy page의 replay route 분리
- serialized navigation, hidden navigation의 local-first 재작성 강화
- bootstrap and hydration signal 추출 및 strict/supporting runtime 분류 개선
- logging envelope, secondary async module의 strict false blocker 정리
- charset/decode 진단 및 page-level encoding confidence 추가 + 폴백 경고 로깅
- legacy CSS asset recovery, canonicalization, failure summary 강화
- replay runtime error evidence 수집 강화
- replay-only runtime guard로 same-origin DOM assumption fail-soft 처리
- text/title/content fidelity 비교를 heading/main/body profile 기반으로 보강
- output finalize retry 및 numbered output directory(`-2`, `-3`) 지원
- **네트워크 인터셉터 해시 충돌 위험 해소** (48비트 → 96비트)
- **AbortSignal 전파**: Web UI Cancel → 2~3초 내 크롤 중단
- **Worker 페이지별 90초 타임아웃** + visited set 안전 상한
- **침묵하던 catch 블록에 디버그 로깅 추가** (Tier 1+2)
- **runtime-data-miss / runtime-asset-miss 세분류**: fetch 404 → data-miss, image/font 404 → asset-miss
- **Widget soft-fail → note 분류**: content 일치 + shell 정상 시 warning이 아닌 note
- **runtime-induced-partial-match / runtime-induced-content-gap**: 콘텐츠 갭과 런타임 유발 갭 분리
- **hidden navigation 패턴 확장**: `fn*`, `nav*`, `jump*` 래퍼 함수 + select `this.options[].value` 핸들러
- **hidden navigation 3차 확장**: 리터럴+변수 혼합 패턴 partial matching (`'/path?key=' + variable` → fallbackMap 매치) + form GET hidden input URL 재구성
- **hidden navigation 4차 확장**: 변수 prefix + 리터럴 suffix (`baseUrl + '/page.do'`) 및 template literal (`` `${base}/page.do` ``) 패턴 지원 + directNavigationPatterns template literal guard
- **Personalized Page Mock Sanitization**: render-supporting API 응답에서 user-specific 필드를 3단계 heuristic으로 자동 감지 → generic placeholder 치환 (email, JWT, UUID, 숫자 ID 등)
- **대규모 사이트 성능 최적화**: `batchParallel` 세마포어 worker pool로 asset download(10), CSS(6), JS(8), HTML(4) 처리 병렬화 → 전체 파이프라인 50-80% 단축
- **JSP 세미콜론 path parameter 제거**: `;CUSTOM_SESSION=...` 등 JSP 세션 파라미터가 파일명에 포함되는 문제 해결
- **ESLint 완전 정리**: 50 problems (28 errors + 22 warnings) → 0 problems. 테스트 globals 설정, unused 코드 제거
- **생성 output README 개선**: 크롤 통계, CSS 회수율, hidden navigation, API mock 요약, 알려진 제한 자동 삽입
- **Scaffolder 템플릿 외부화**: project-scaffolder.js 577줄 → 248줄 (-57%), Express adapter + runtime guard를 독립 template 파일로 분리
- **Web UI 실시간 진행 표시**: logger progress 이벤트 + SSE 전달 + 진행 바/카운터/stage label UI
- **Replay Verifier 모듈 분리**: 1,408줄 → 940줄, content-comparison.js (187줄) + runtime-diagnostics.js (303줄) 분리
- **index.js 모듈 분리** (1405줄 → 794줄): page-dedup, page-route-manifest, replay-signals, output-finalize
- **테스트 분할**: output-processors.test.js (2256줄) → 7개 파일 (최대 505줄)
- **Verifier 순수 함수 유닛 테스트 30개** + hidden navigation 3차 8개 + 4차 7개 + mock sanitizer 14개 + concurrency 5개 + 통합 2개 + 핵심 모듈 커버리지 24개 (총 200개 테스트)
- **매직 넘버 상수화**: CONTENT_GAP_CEILING, PARTIAL_MATCH_CEILING 등
- **ESLint flat config** 추가 (`npm run lint`)
- **Docker HEALTHCHECK** + 리소스 제한 (4G/2CPU)
- **Node.js 엔진 버전 핀** (>=20.0.0) + `.env.example`
- **SSE 에러 핸들링**: 연결 끊김 시 클라이언트 자동 제거

## 현재 강점

- 저장된 페이지는 이전보다 더 안정적으로 local route에서 열립니다.
- CSS-linked font, image, background asset 회수 품질이 좋아졌습니다.
- replay verification이 route, strict/supporting data, encoding, runtime failure를 분리해서 보여줍니다.
- boilerplate-heavy 페이지에서도 verifier가 `비교 노이즈`와 `실제 콘텐츠 차이`를 더 잘 구분합니다.
- output 충돌 시 기존 폴더를 삭제하지 않고 새 폴더를 생성할 수 있어 운영 안정성이 좋아졌습니다.
- **runtime 404를 data-miss / asset-miss / script-failed / style-failed로 세분류**하여 soft-fail 판단이 더 정확합니다.
- **content 일치 시 widget soft-fail을 note로 분류**하여 false-positive 경고가 줄었습니다.
- **runtime-induced 콘텐츠 갭이 별도 레이블로 표시**되어 실제 소싱 문제와 런타임 문제를 구분할 수 있습니다.
- **hidden navigation**이 리터럴 prefix, 변수 prefix+리터럴 suffix, template literal 모든 패턴에서 fallbackMap으로 안전하게 localize되어 disabled 비율이 크게 감소합니다.
- **form GET + hidden input 재구성**으로 query parameter 기반 navigation form이 자동으로 localize됩니다.
- **render-supporting mock sanitization**으로 personalized page의 stale 개인 데이터가 generic placeholder로 치환되어, replay 시 민감 정보 노출이 줄고 verifier가 `mock-driven-sanitized-replay`로 정확하게 분류합니다.
- **크롤 취소가 즉시 반영**되어 Web UI 운영성이 개선되었습니다.
- **index.js가 794줄로 축소**되어 코드 탐색과 유지보수가 쉬워졌습니다.
- **asset download, CSS/JS/HTML 처리가 모두 병렬화**되어 대규모 사이트(100+ 페이지) 처리 속도가 50-80% 향상되었습니다.
- **JSP 세미콜론 path parameter**가 파일명에서 자동 제거되어, culture.jongno.go.kr 같은 JSP 기반 서브도메인의 CSS가 정상 서빙됩니다.
- **Web UI에서 크롤/다운로드 진행 상황이 실시간 진행 바로 표시**되어 운영 가시성이 크게 향상되었습니다.
- **scaffolder 템플릿이 독립 파일로 분리**되어 Express adapter와 runtime guard를 별도로 편집/테스트 가능합니다.
- **replay-verifier.js가 content-comparison + runtime-diagnostics로 분리**되어 유지보수성이 향상되었습니다 (1,408줄 → 940줄).
- **200개 테스트**로 회귀 방지 범위가 확대되었습니다.

## 현재 한계

- 일부 legacy portal 페이지는 여전히 `runtime-widget-soft-fail`이 남습니다 (content 일치 시 note로 다운그레이드됨).
- same-origin runtime resource 404 중 `runtime-data-miss`나 `runtime-asset-miss`는 soft로 처리되지만, 위젯이 완전히 채워지지 않을 수 있습니다.
- hidden navigation의 pure variable 패턴(`goPage(baseUrl + menuNo)` — 리터럴 없음)은 정적 분석으로 해석 불가하여 여전히 disabled 유지됩니다.
- personalized 또는 runtime-heavy 페이지는 render-supporting mock이 자동 sanitize되지만, 사이트별 비표준 필드명(`mbrNo`, `loginHash` 등)은 generic heuristic에 감지되지 않을 수 있습니다.

## 현재 판단

- 현재 프로젝트 상태: `제한적 사용 가능 → 안정화 단계`
- 이유:
  - 파이프라인 안정성 (abort signal, worker 타임아웃, 해시 충돌 해소)이 크게 개선되었습니다.
  - 리플레이 정확도 판단이 더 세밀해졌습니다 (note/warning 분리, runtime-induced 분류).
  - hidden navigation 3차+4차 확장으로 리터럴 prefix, 변수 prefix+리터럴 suffix, template literal, form GET reconstruction이 모두 지원됩니다.
  - mock sanitization으로 render-supporting API 응답의 personalized 필드가 자동 치환됩니다.
  - 파이프라인 성능이 batchParallel 병렬화로 크게 개선되었습니다 (50-80% 단축).
  - scaffolder 템플릿 외부화, Web UI 진행 표시, verifier 모듈 분리가 완료되었습니다.
  - 코드 품질 (모듈 분리, 테스트 200개, ESLint clean)이 지속 개발에 적합한 수준입니다.
  - 다만 일부 사이트는 original runtime이 가진 DOM 가정과 pure variable 동적 경로 때문에 완전한 원본 수준 재현은 어렵습니다.

## 운영 메모

- Docker UI는 `docker compose up -d --build`로 최신 코드 기준으로 다시 올릴 수 있습니다.
- Docker 컨테이너는 HEALTHCHECK가 적용되어 30초 간격으로 상태를 확인합니다.
- 리소스 제한은 메모리 4G, CPU 2코어로 설정되어 있습니다.
- 빠른 반복은 `balanced` 또는 `lightweight`, 최종 검증은 `accurate`를 권장합니다.
- OneDrive, 탐색기, 실행 중인 replay server가 output 폴더를 잡고 있으면 finalize 단계가 실패할 수 있습니다.
- 이제 기본 실행은 기존 output 폴더를 강제로 지우지 않고, 필요하면 `jongno.go.kr-2` 같은 새 폴더를 생성합니다.
- 환경 변수는 `.env.example`을 참고하세요 (API_KEY, DEBUG, PORT).

## 다음 우선순위

- CI/CD 파이프라인 구축 (GitHub Actions: test + lint + Docker 빌드 자동화)
- 환경 기반 설정 확장 (constants.js → 환경 변수 오버라이드)
- Web UI 출력 파일 미리보기 (HTML iframe, JSON 구문 강조, diff 뷰)
- 다중 Job 지원 및 큐잉 (단일 activeJobId → 큐 기반)
- SPA/모던 프레임워크 지원 강화 (Vue 3, Next.js App Router, History API 추적)
- Mock Sanitization 고도화 (opt-in 필드명, inline state blob, deterministic placeholder)
