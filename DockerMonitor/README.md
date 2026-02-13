# Docker Monitor Dashboard

Docker 컨테이너, 이미지, 네트워크, 볼륨, Compose 프로젝트를 실시간으로 모니터링하고 제어하는 웹 대시보드.

## 주요 기능

| 기능 | 설명 |
|------|------|
| **실시간 모니터링** | WebSocket 기반 컨테이너 상태, CPU/메모리 사용량 실시간 업데이트 |
| **CPU/메모리 차트** | Chart.js 시계열 그래프 (30포인트 rolling window) |
| **컨테이너 제어** | Start / Stop / Restart, 리소스(CPU/Memory) 제한 설정 |
| **컨테이너 Inspect** | 환경변수, 볼륨 마운트, 네트워크, 포트, 라벨 상세 조회 |
| **웹 터미널** | xterm.js 기반 컨테이너 내부 셸 접속 |
| **이미지 관리** | 로컬 이미지 목록, 삭제, Pull |
| **네트워크/볼륨** | Docker 네트워크 및 볼륨 조회 |
| **Compose 관리** | Compose 프로젝트 목록, UP/DOWN/RESTART/PULL 제어 |
| **검색/필터** | 이름, 이미지, ID 기준 컨테이너 실시간 필터링 |
| **브라우저 알림** | 컨테이너 상태 변경 시 Notification API 데스크탑 알림 |
| **SSO 인증** | shwoo_server 연동 HMAC 기반 SSO 인증 |

## 기술 스택

- **Backend**: FastAPI + Uvicorn
- **Frontend**: Jinja2 + Vanilla JS + Chart.js + xterm.js
- **Docker SDK**: `docker-py` (python docker SDK)
- **설정 관리**: `pydantic-settings` (.env 기반)
- **테스트**: `pytest` + `httpx`

## 프로젝트 구조

```
DockerMonitor/
├── main.py                   # FastAPI 앱 + 라우트 등록
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── .env.example              # 환경변수 템플릿
│
├── core/
│   ├── config.py             # pydantic-settings 중앙 설정
│   ├── connection.py         # Docker 클라이언트 싱글턴
│   ├── monitor.py            # 백그라운드 모니터링 + 상태 변경 감지
│   ├── websocket_manager.py  # WebSocket 매니저
│   ├── auth.py               # SSO 인증 로직
│   ├── schemas.py            # 공통 응답 스키마
│   └── exceptions.py         # 커스텀 예외 클래스
│
├── services/
│   ├── base_service.py       # 서비스 베이스 클래스
│   ├── container_service.py  # 컨테이너 서비스 (목록, 제어, Inspect, Stats)
│   ├── image_service.py      # 이미지 서비스 (목록, 삭제, Pull)
│   ├── network_service.py    # 네트워크 서비스
│   ├── volume_service.py     # 볼륨 서비스
│   └── compose_service.py    # Compose 서비스
│
├── routers/
│   ├── containers.py         # /api/containers
│   ├── images.py             # /api/images
│   ├── networks.py           # /api/networks
│   ├── volumes.py            # /api/volumes
│   ├── compose.py            # /api/compose
│   ├── websocket.py          # /ws
│   └── terminal.py           # /ws/terminal
│
├── middleware/
│   ├── auth_middleware.py     # 인증 미들웨어
│   └── error_handler.py      # 전역 예외 핸들러
│
├── templates/                # Jinja2 HTML
│   ├── base.html
│   ├── index.html            # 대시보드 (차트, 검색, 컨테이너 카드)
│   ├── inspect.html          # 컨테이너 상세
│   ├── images.html           # 이미지 관리 (Pull 포함)
│   ├── networks.html
│   ├── volumes.html
│   ├── compose.html
│   └── logs.html
│
├── static/
│   ├── app.js                # WebSocket, 알림, 대시보드 로직
│   └── style.css
│
└── tests/
    ├── conftest.py           # pytest fixture (모킹, 클라이언트)
    ├── test_api.py           # API 엔드포인트 테스트
    ├── test_config.py        # 설정 모듈 테스트
    └── test_monitor.py       # 모니터 상태 변경 감지 테스트
```

## 빠른 시작

### Docker Compose (권장)

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일 편집 (시크릿, 이메일 등)

# 2. 빌드 & 실행
docker compose up -d --build

# 3. 접속
open http://localhost:10002
```

### 로컬 개발

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경 변수 설정
cp .env.example .env

# 3. 서버 실행
python main.py
```

## 환경 변수

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `ALLOWED_EMAILS` | `dntmdgns03@naver.com` | SSO 허용 이메일 (콤마 구분) |
| `DOCKER_TOKEN_SECRET` | `shwoo-docker-secret-2026` | JWT 토큰 시크릿 |
| `SHWOO_URL` | `https://xn--9t4ba122aba.site` | SSO 서버 URL |
| `TOKEN_EXPIRY_SECONDS` | `300` | 토큰 유효 시간 (초) |
| `MONITOR_INTERVAL` | `5` | 모니터링 폴링 간격 (초) |

## 테스트

```bash
# 전체 테스트 실행
pytest

# 상세 출력
pytest -v

# 특정 파일
pytest tests/test_api.py
```

## API 엔드포인트

### Containers
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/containers` | 컨테이너 목록 |
| POST | `/api/containers/{id}/action` | 컨테이너 제어 (start/stop/restart) |
| GET | `/api/containers/{id}/logs` | 컨테이너 로그 |
| GET | `/api/containers/{id}/inspect` | 컨테이너 상세 Inspect |
| POST | `/api/containers/{id}/resources` | 리소스 제한 업데이트 |
| GET | `/api/containers/status` | Docker 데몬 상태 |

### Images
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/images` | 이미지 목록 |
| POST | `/api/images/pull` | 이미지 Pull |
| DELETE | `/api/images/{id}` | 이미지 삭제 |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `/ws` | 실시간 모니터링 (stats_update + status_events) |
| `/ws/terminal/{id}` | 컨테이너 터미널 |

## 라이선스

MIT
