# Migration Plan

## 현재 구조

- `client/`, `docs/`, `mocks/`, `server/`, `manifest/` 중심
- Express scaffold가 원본처럼 보이는 구조

## 목표 구조

- `public/`, `views/`, `server/spec/`, `server/mocks/`, `server/adapters/express/`
- 원본은 `server/spec`와 `server/mocks`

## 1차 전환 순서

1. 출력 경로를 `public/views/server`로 이동
2. OpenAPI `3.1.0` / AsyncAPI 생성
3. HTTP mock manifest와 payload 분리 저장
4. Express adapter를 얇은 replay runtime으로 교체
5. HAR / storage / sessionStorage 캡처 저장
6. 누락 동작 보고서 생성

## 후속 작업

- CSS 재작성기를 PostCSS 기반으로 교체
- JS 재작성기를 AST 기반으로 교체
- offline verifier 자동화
- GraphQL introspection 캡처
