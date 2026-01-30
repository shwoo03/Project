# 인스타그램 팔로워 추적기

## 1. 프로젝트 개요
인스타그램 팔로워 및 팔로잉 목록의 변경 사항을 추적하는 Python 자동화 도구입니다.

## 2. 주요 기능
- **자동 로그인**: Playwright로 브라우저 로그인 및 쿠키 관리
- **데이터 수집**: 인스타그램 API로 팔로워/팔로잉 수집
- **변경 감지**: MongoDB에서 이전 데이터와 비교
- **알림**: Discord Webhook으로 리포트 전송
- **웹 대시보드**: FastAPI 기반 현황 조회 UI

## 3. 프로젝트 구조

```
📁 instagram_tracker/
├── main.py           # 동기 진입점
├── main_async.py     # 비동기 진입점 ⚡
├── config.py         # 환경 변수
├── auth.py           # 동기 로그인
├── auth_async.py     # 비동기 로그인 ⚡
├── api.py            # 동기 API
├── api_async.py      # 비동기 API ⚡
├── database.py       # MongoDB 연동
├── notification.py   # Discord 알림
├── retry.py          # 재시도 로직 🔄
├── dashboard.py      # 웹 대시보드 🌐
└── requirements.txt
```

## 4. 설치

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. Playwright 브라우저 설치
playwright install chromium
```

## 5. 구성 (.env)

| 변수명 | 설명 |
|--------|------|
| `USER_ID` | 인스타그램 사용자명 |
| `USER_PASSWORD` | 비밀번호 |
| `MONGO_URI` | MongoDB 연결 문자열 |
| `DISCORD_WEBHOOK` | Discord Webhook URL |

## 6. 사용법

### 동기 실행 (기존)
```bash
python main.py
```

### 비동기 실행 (권장 ⚡)
```bash
python main_async.py
```

### 웹 대시보드 🌐
```bash
python dashboard.py
# → http://localhost:8000
```

또는
```bash
uvicorn dashboard:app --host 0.0.0.0 --port 8000
```

## 7. API 엔드포인트

| 엔드포인트 | 설명 |
|------------|------|
| `GET /` | HTML 대시보드 |
| `GET /api/status` | 상태 JSON |
| `GET /api/latest` | 최신 데이터 JSON |

## 8. 로깅
- 로그 파일: `instagram_tracker.log`
- 콘솔 + 파일 동시 출력
