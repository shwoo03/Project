# Source Index

## 핵심 자료

- Playwright
  - https://playwright.dev/docs/api/class-browsercontext
  - https://playwright.dev/docs/api/class-page
  - https://playwright.dev/docs/api/class-request
  - https://playwright.dev/docs/api/class-response
  - https://playwright.dev/docs/browser-contexts
  - https://playwright.dev/docs/network
  - https://playwright.dev/docs/navigations
  - https://playwright.dev/docs/service-workers
  - https://playwright.dev/docs/mock
  - https://playwright.dev/docs/api/class-websocket
  - https://playwright.dev/docs/api/class-websocketroute
  - https://playwright.dev/docs/test-snapshots
  - https://playwright.dev/docs/aria-snapshots
  - https://playwright.dev/docs/api/class-pageassertions
  - https://playwright.dev/docs/api/class-locatorassertions
  - https://playwright.dev/docs/auth
  - https://playwright.dev/docs/trace-viewer
- OpenAPI
  - https://spec.openapis.org/oas/latest.html
- AsyncAPI
  - https://www.asyncapi.com/docs/reference/specification/latest
- GraphQL
  - https://graphql.org/learn/serving-over-http
  - https://graphql.org/learn/response
  - https://graphql.org/learn/debug-errors
  - https://graphql.org/learn/introspection
  - https://graphql.github.io/graphql-over-http/draft/
  - https://spec.graphql.org/draft/
- Redocly
  - https://redocly.com/docs/cli/commands/build-docs
- tldts
  - https://github.com/remusao/tldts
- Cheerio
  - https://cheerio.js.org/
- PostCSS URL
  - https://github.com/postcss/postcss-url
- Babel Parser
  - https://babeljs.io/docs/babel-parser

## 구현 매핑

- 캡처 엔진: Playwright
- 도메인 스코프 계산: tldts
- HTML 재작성: Cheerio
- CSS 재작성: PostCSS / postcss-url
- JS 재작성: Babel parser 기반 AST
- 스펙 생성: OpenAPI / AsyncAPI
- 문서 생성: Redocly
