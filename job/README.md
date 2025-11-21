# Job Scraper & Notifier

> Enki(엔키)와 Theori(티오리)의 채용 공고를 크롤링하여 Notion에 동기화하고 Discord로 알림을 보내는 자동화 도구입니다.

## 🚀 주요 기능

- **자동 크롤링**: Enki와 Theori의 최신 채용 공고를 수집합니다.
- **중복 방지**: MongoDB를 사용하여 이미 처리된 공고는 건너뜁니다.
- **Notion 동기화**: 새로운 공고를 Notion 데이터베이스에 자동으로 추가합니다.
- **Discord 알림**: 신규 공고 발견 시 Discord 웹훅으로 즉시 알림을 전송합니다.
- **자동 정리**: 채용 사이트에서 내려간 공고는 DB에서도 자동으로 정리합니다.

## 🛠️ 기술 스택

- **Language**: Python 3.8+
- **Database**: MongoDB (Firestore 호환)
- **Libraries**: `requests`, `beautifulsoup4`, `pymongo`

## ⚙️ 설치 및 설정

### 1. 필수 라이브러리 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정 (`.env`)

프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 채워주세요.

```ini
# Notion 설정
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_database_id
NOTION_SOURCE_PROP=선택  # 소스(엔키/티오리)를 구분할 Select 속성 이름

# Discord 설정
DISCORD_WEBHOOK_URL=your_discord_webhook_url

# MongoDB 설정
MONGO_URI=your_mongodb_connection_string
MONGO_DB_NAME=webhook
```

## 🏃 실행 방법

### 전체 실행

모든 크롤러(Enki, Theori)를 순차적으로 실행합니다.

```bash
python main.py
```

### 개별 실행

특정 크롤러만 실행할 수 있습니다.

```bash
python enki.py
python theori.py
```

### 테스트 실행 (Dry Run)

Notion이나 DB에 실제로 쓰지 않고 로그만 확인합니다.

```bash
python main.py --dry-run
```

## 📂 프로젝트 구조

```
.
├── main.py          # 메인 실행 파일 (모든 크롤러 관리)
├── enki.py          # Enki 크롤러
├── theori.py        # Theori 크롤러
├── sync_utils.py    # Notion 동기화 및 공통 로직 (Core Logic)
├── db_utils.py      # MongoDB 연결 및 CRUD 관리
├── requirements.txt # 의존성 패키지 목록
└── .env             # 환경 변수 (비공개)
```
