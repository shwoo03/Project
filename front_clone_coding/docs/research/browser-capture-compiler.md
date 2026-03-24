# Browser Capture Compiler

## 핵심 원칙

- 이 프로젝트는 단순 사이트 다운로드기가 아니라, 실행 중인 브라우저를 기록한 뒤 오프라인 재생 패키지로 컴파일하는 도구로 본다.
- HTML 단독 저장은 SPA와 동적 페이지에서 충분하지 않다. DOM, asset, HTTP/GraphQL/WebSocket 통신, storage 상태를 함께 캡처해야 한다.
- 페이지 추적 범위는 registrable domain 기준으로 제한하고, asset은 외부 CDN이어도 실제 참조되면 로컬로 저장한다.

## 산출물 기준 구조

```text
output/example.com/
  public/
  views/
  server/
    spec/
    mocks/
    adapters/
    docs/
  package.json
```

- `server/spec`와 `server/mocks`가 원본이다.
- `server/adapters/express`는 파생물이다.

## 캡처 규칙

- Playwright `BrowserContext`에서 `serviceWorkers: 'block'`
- HAR 기록 활성화
- `addInitScript()`로 SPA route 변화 추적
- `request`, `response`, `requestfinished`, `requestfailed`를 모두 기록
- `storageState()` 저장
- `sessionStorage`는 별도 JSON으로 저장

## 스펙 규칙

- HTTP + GraphQL over HTTP: OpenAPI `3.1.0`
- WebSocket: AsyncAPI
- GraphQL는 endpoint 기준과 operationName 기준을 둘 다 저장

## 검증 규칙

- 생성 후 로컬 adapter로 replay 가능해야 한다.
- 외부 요청 잔존, 로그인 게이트, inline handler, 미복제 동작은 `server/docs/missing-behaviors.md`에 기록한다.
