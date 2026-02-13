# Instagram Follower Tracker

인스타그램 팔로워/팔로잉 변동을 자동으로 추적하고 Discord로 알림을 보내는 대시보드 앱.

## 주요 기능

- **자동 크롤링**: Playwright + httpx로 팔로워/팔로잉 데이터 수집
- **변동 감지**: 새 팔로워, 언팔로우 자동 비교
- **Discord 알림**: 일일 리포트 + 변동 즉시 알림
- **대시보드**: 실시간 WebSocket 진행 상태 + 분석 결과 표시
- **스케줄러**: APScheduler 기반 매일 자동 실행
- **CSV 내보내기**: 팔로워/팔로잉/맞팔 안 함/팬 데이터 다운로드
- **SSO 인증**: shwoo_server 토큰 기반 접근 제어

## 프로젝트 구조

```
Instagram/
├── dashboard.py          # FastAPI 메인 앱 (lifespan, 미들웨어, WebSocket)
├── config.py             # Pydantic Settings 환경 변수 관리
├── scheduler.py          # APScheduler 스케줄 관리
├── state_manager.py      # WebSocket 브로드캐스트 상태 관리
├── dependencies.py       # FastAPI Depends 의존성 주입
├── notification.py       # Discord Webhook 알림 (async httpx)
├── retry.py              # tenacity 재시도 데코레이터
├── schemas.py            # Pydantic API 응답 스키마
├── utils.py              # 공통 유틸리티
├── log_handler.py        # MongoDB 로그 핸들러
│
├── services/
│   ├── auth_service.py       # Playwright 로그인 + 쿠키 관리
│   ├── instagram_service.py  # httpx 팔로워/팔로잉 API 크롤링
│   ├── task_service.py       # 추적 작업 오케스트레이션
│   └── export_service.py     # CSV 내보내기
│
├── repositories/
│   ├── base.py               # MongoDB 싱글톤 클라이언트
│   ├── user_repository.py    # 팔로워 데이터 CRUD + 분석
│   └── log_repository.py     # 로그 조회
│
├── routers/
│   ├── api.py                # REST API 엔드포인트
│   └── views.py              # HTML 뷰 + SSO 인증
│
├── templates/                # Jinja2 HTML 템플릿
├── static/                   # CSS/JS 정적 파일
├── tests/                    # pytest 테스트
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                      # 환경 변수 (git 미포함)
```

## 환경 변수 (.env)

| 변수 | 필수 | 설명 |
|------|:----:|------|
| `USER_ID` | ✅ | 인스타그램 아이디 |
| `USER_PASSWORD` | ✅ | 인스타그램 비밀번호 |
| `MONGO_URI` | ✅ | MongoDB 연결 URI |
| `ACCESS_PASSWORD` | ✅ | 대시보드 접근 비밀번호 |
| `INSTAGRAM_TOKEN_SECRET` | ✅ | SSO 토큰 서명 시크릿 |
| `ALLOWED_EMAILS` | ❌ | SSO 허용 이메일 (JSON 배열) |
| `DISCORD_WEBHOOK` | ❌ | Discord Webhook URL |
| `SHWOO_URL` | ❌ | SSO 리다이렉트 URL |

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/run` | 팔로워 추적 실행 |
| `GET` | `/api/status` | 현재 상태 조회 |
| `GET` | `/api/latest` | 최신 데이터 조회 |
| `GET` | `/api/history?days=30` | 히스토리 조회 |
| `GET` | `/api/changes` | 변동 요약 |
| `GET` | `/api/logs?limit=100` | 로그 조회 |
| `GET/POST/DELETE` | `/api/schedule` | 스케줄 관리 |
| `GET` | `/api/export/{type}` | CSV 내보내기 |
| `GET` | `/auth?token=...` | SSO 인증 콜백 |
| `GET` | `/` | 대시보드 HTML |
| `WebSocket` | `/ws` | 실시간 로그/진행 상태 |

## 실행

### Docker (권장)

```bash
# .env 파일 설정 후
docker-compose up -d --build
# http://localhost:10000 접속
```

### 로컬 개발

```bash
pip install -r requirements.txt
playwright install chromium
python dashboard.py
```

## 기술 스택

- **Backend**: FastAPI, Uvicorn, Pydantic Settings
- **크롤링**: Playwright (로그인), httpx (API)
- **DB**: MongoDB (pymongo)
- **스케줄러**: APScheduler
- **알림**: Discord Webhook (httpx async)
- **재시도**: tenacity
- **테스트**: pytest, pytest-asyncio
