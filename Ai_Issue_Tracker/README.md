# AI News Digest Bot

텔레그램 봇 기반 AI 이슈 자동 크롤링 & Codex 요약 시스템

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│  Scheduler   │───▶│   Crawlers    │───▶│  Summarizer  │───▶│  Telegram  │
│  (APScheduler│    │              │    │  (Codex CLI) │    │    Bot     │
│  cron)       │    │ X / TG / RSS │    │              │    │            │
│              │    │ / Web        │    │              │    │            │
│ 07:00        │    └──────────────┘    └──────────────┘    └────────────┘
│ 12:00        │           │                   │                   │
│ 20:00        │           ▼                   ▼                   ▼
└─────────────┘    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
                   │   Storage    │    │    Data/     │    │   User     │
                   │  (SQLite)    │    │  feedback    │    │  (You)     │
                   └──────────────┘    └──────────────┘    └────────────┘
```

## Stack

| Layer | Tool | 용도 |
|-------|------|------|
| Crawling | `requests` + `BeautifulSoup` / `Telethon` / `feedparser` | 데이터 수집 |
| JS Rendering | `playwright` (필요시) | SPA 사이트 크롤링 |
| Summarization | OpenAI Codex CLI (`codex`) | AI 기반 요약 |
| Bot | `python-telegram-bot` | 텔레그램 알림 전송 |
| Scheduling | `APScheduler` | cron 기반 스케줄링 |
| Storage | SQLite | 중복 방지 및 히스토리 |
| Deployment | Docker + docker-compose | 사내망 배포 |

## Quick Start

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력

# 2. Playwright 브라우저 설치
pip install -r requirements.txt
playwright install chromium

# 3. 세션 생성 (최초 1회, 로컬에서 실행)
python scripts/create_x_session.py          # X 웹 로그인 + 2FA
python scripts/create_telegram_session.py   # 텔레그램 인증

# 4. Docker로 실행
docker-compose up -d

# 5. 수동 테스트
python scripts/run_once.py --dry-run
```

## Configuration

`config/sources.yaml` 에서 크롤링 대상을 관리합니다:

```yaml
sources:
  x_accounts:
    - username: "OpenAI"
      category: "ai_lab"
  telegram_channels:
    - channel: "@ai_news_channel"
      category: "news"
  rss_feeds:
    - url: "https://blog.openai.com/rss"
      category: "blog"
  websites:
    - url: "https://example.com/news"
      selector: "article.post"
      category: "news"
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | 텔레그램 봇 HTTP API 토큰 |
| `TELEGRAM_CHAT_ID` | ✅ | 알림 받을 채팅/채널 ID |
| `TELEGRAM_API_ID` | ✅ | Telethon용 API ID (my.telegram.org) |
| `TELEGRAM_API_HASH` | ✅ | Telethon용 API Hash |
| `TELEGRAM_PHONE` | ✅ | 텔레그램 계정 전화번호 |
| `X_USERNAME` | ✅ | X 계정 username (@ 제외) |
| `X_PASSWORD` | ✅ | X 계정 비밀번호 |
| `X_EMAIL` | ⬚ | X 로그인 challenge 시 사용할 이메일 |
| `OPENAI_API_KEY` | ✅ | Codex CLI용 OpenAI API 키 |
| `CODEX_MODEL` | ⬚ | 요약 모델 (기본: `o4-mini`) |
| `DB_PATH` | ⬚ | SQLite DB 경로 (기본: `data/news.db`) |
