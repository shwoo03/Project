# 인스타그램 팔로워 추적기

## 1. 프로젝트 개요
이 프로젝트는 인스타그램 팔로워 및 팔로잉 목록의 변경 사항을 추적하기 위해 설계된 Python 기반 자동화 도구입니다. Playwright를 사용하여 안전하게 로그인하고, Requests를 사용하여 효율적으로 데이터를 수집하는 하이브리드 방식을 사용합니다. 결과는 MongoDB 데이터베이스에 저장되며, 요약 보고서는 Webhook을 통해 디스코드 서버로 전송됩니다.

## 2. 주요 기능
1. **자동 로그인**: Playwright를 사용하여 실제 브라우저 로그인을 시뮬레이션하고 인증 쿠키를 추출합니다.
2. **데이터 수집**: 인스타그램 내부 API를 사용하여 팔로워 및 팔로잉 사용자 전체 목록을 가져옵니다.
3. **변경 감지**: 현재 상태를 데이터베이스 기록과 비교하여 새로운 팔로워와 언팔로워를 식별합니다.
4. **데이터베이스 통합**: 과거 데이터와 최신 상태를 MongoDB에 저장합니다.
5. **알림**: 클릭 가능한 프로필 링크가 포함된 형식화된 보고서를 디스코드에 전송합니다.

## 3. 프로젝트 구조

```
📁 instagram_tracker/
├── main.py          # 진입점 (오케스트레이션)
├── config.py        # 환경 변수 로드
├── auth.py          # 로그인 및 쿠키 관리
├── api.py           # 인스타그램 API 호출
├── database.py      # MongoDB 연동
├── notification.py  # Discord Webhook 알림
├── requirements.txt # 의존성 목록
├── .env             # 환경 변수 (비공개)
└── .agent/skills/   # Agent 스킬
```

## 4. 설치 및 설정

### 4.1 필수 조건
1. Python 3.10 이상
2. MongoDB (로컬 또는 Atlas)
3. Google Chrome 또는 Chromium 브라우저

### 4.2 설치 단계
```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. Playwright 브라우저 설치
playwright install chromium
```

## 5. 구성
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 변수를 구성합니다:

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `USER_ID` | 인스타그램 사용자 이름 | `your_username` |
| `USER_PASSWORD` | 인스타그램 비밀번호 | `your_password` |
| `MONGO_URI` | MongoDB 연결 문자열 | `mongodb://localhost:27017/` |
| `DISCORD_WEBHOOK` | Discord Webhook URL | `https://discord.com/api/webhooks/...` |

## 6. 사용법
```bash
python main.py
```

## 7. 출력 상세
1. **콘솔 & 로그 파일**: 실시간 진행 상황 및 `instagram_tracker.log` 파일에 기록
2. **데이터베이스**:
   - `Instagram_Latest`: 팔로워 및 팔로잉의 최신 스냅샷
3. **디스코드 Webhook**: 팔로워/팔로잉 현황 및 맞팔 분석 리포트

## 8. 로깅
- 로그 파일: `instagram_tracker.log`
- 로그 형식: `%(asctime)s - %(levelname)s - %(message)s`
- 콘솔과 파일에 동시 출력
