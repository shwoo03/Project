# 인증 설정 가이드

각 플랫폼별 인증 자동화 방법을 정리합니다.

---

## 1. 텔레그램 (Telethon — MTProto User API)

### 왜 Bot API가 아닌 User API인가?

| | Bot API | User API (Telethon) |
|---|---|---|
| 인증 | BotFather 토큰 | API_ID + API_HASH + 전화번호 |
| 채널 읽기 | 봇이 추가된 채널만 | 가입한 모든 채널/그룹 |
| 메시지 히스토리 | 제한적 | 전체 접근 가능 |
| 비공개 채널 | 봇이 멤버여야 함 | 본인 계정으로 접근 |
| Rate Limit | 엄격 | 상대적으로 관대 |

→ **결론**: 크롤링 목적이면 Telethon (User API) 이 적합.

### 설정 단계

```
1. https://my.telegram.org 접속
2. "API development tools" 클릭
3. App 생성:
   - App title: ai-news-bot
   - Short name: ainewsbot
   - Platform: Desktop
4. API_ID (숫자), API_HASH (문자열) 확인
5. .env에 입력:
   TELEGRAM_API_ID=12345678
   TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
   TELEGRAM_PHONE=+821012345678
```

### 세션 생성 (최초 1회)

```bash
python scripts/create_telegram_session.py
```

실행하면:
1. 텔레그램으로 인증 코드가 전송됨
2. 터미널에 코드 입력
3. 2FA 설정 시 비밀번호 추가 입력
4. `data/sessions/tg_user.session` 파일 생성

**이후**: .session 파일만 있으면 코드/비밀번호 없이 자동 인증됨.

### 세션 보안

- .session 파일은 **텔레그램 계정 전체 접근 권한**과 동일
- 절대 git에 커밋 금지 (.gitignore에 추가됨)
- Docker 사용 시 volume mount로 전달
- 세션 탈취 시 → my.telegram.org에서 Active Sessions 에서 해당 세션 종료

### FloodWait 방지

Telethon은 과도한 요청 시 `FloodWaitError`를 발생시킴.
코드에서 자동으로 대기하도록 구현되어 있으나, 크롤링 채널 수를 적절히 조절할 것.

---

## 2. X (Twitter) — Playwright 웹 인증 자동화

### 왜 API가 아닌 웹 크롤링인가?

| | API Free Tier | 웹 크롤링 (Playwright) |
|---|---|---|
| 비용 | 무료 | 무료 |
| 읽기 제한 | 매우 제한적 (search 불가) | 제한 없음 (계정 기반) |
| 인증 | Bearer Token (Developer Portal) | username + password + 2FA |
| 설정 난이도 | Developer 승인 필요 | .env에 계정 정보만 입력 |
| 안정성 | API 안정적 | DOM 변경 시 셀렉터 업데이트 필요 |

→ **결론**: 무료로 제한 없이 읽으려면 웹 크롤링이 현실적.

### 설정 단계

```
1. .env에 X 계정 정보 입력:
   X_USERNAME=your_username   (@ 제외)
   X_PASSWORD=your_password
   X_EMAIL=your_email         (email challenge 대비)

2. 최초 세션 생성 (로컬에서 1회 실행):
   python scripts/create_x_session.py

3. 브라우저가 열리며 자동으로 로그인 진행
   → 2FA 설정 시 브라우저에서 직접 코드 입력
   → 완료 후 data/sessions/x_state.json 생성

4. Docker 배포 시 x_state.json을 volume mount
```

### 인증 흐름 상세

```
최초 실행:
  create_x_session.py (headful 브라우저)
  → x.com/i/flow/login 이동
  → username 자동 입력 → Next
  → (email challenge 시) email 자동 입력
  → password 자동 입력 → Log in
  → (2FA 시) 사용자가 브라우저에서 수동 입력
  → 홈 피드 로딩 확인
  → cookies + localStorage → x_state.json 저장

이후 실행 (Docker/headless):
  x_state.json 로드 → 세션 유효성 확인
  → 유효: 바로 크롤링 시작
  → 만료: 자동 재로그인 시도 (headless)
     → 2FA 필요하면 실패 → 로컬에서 재생성 필요
```

### 세션 관리

- **만료 주기**: X 세션은 보통 30일 이상 유지됨
- **재생성 필요 시**: 비밀번호 변경, 의심 활동 감지, 장기간 미사용
- **상태 확인**: `python scripts/run_once.py --crawl-only`로 테스트
- **Docker에서 세션 갱신 실패 시**: 로컬에서 `create_x_session.py` 재실행

### 봇 탐지 회피

코드에 다음 조치가 포함되어 있음:
- `--disable-blink-features=AutomationControlled` (Playwright 탐지 방지)
- 실제 Chrome User-Agent 사용
- 계정별 크롤링 간 딜레이 (`crawl_settings.request_delay`)
- 과도한 스크롤 방지 (최대 3회)

### 주의사항

- X ToS에서 자동화 크롤링은 제한될 수 있음
- 개인 학습/연구 목적 사용 권장
- 과도한 크롤링 시 계정 제한 가능 → 대상 계정 수를 적절히 조절
- 2FA 활성화 강력 권장 (세션 파일 탈취 대비)

---

## 3. RSS 피드

### 인증

대부분의 공개 RSS 피드는 인증 불필요.

### 인증이 필요한 RSS (유료 구독 등)

`config/sources.yaml`에서 `headers` 필드 확장:

```yaml
rss_feeds:
  - url: "https://premium-site.com/feed"
    name: "Premium Feed"
    enabled: true
    headers:
      Authorization: "Bearer your-token"
      Cookie: "session_id=abc123"
```

→ 이 기능은 `rss_crawler.py`에서 `feedparser.parse(url)`를
  `requests`로 먼저 fetch 후 `feedparser.parse(response.text)`로 변경하여 구현.

---

## 4. 웹사이트 크롤링

### 공개 사이트

인증 불필요. `requests` + `BeautifulSoup`로 처리.

### 로그인 필요 사이트

#### 방법 1: Cookie 기반

브라우저에서 로그인 후 Cookie 추출하여 사용:

```yaml
websites:
  - url: "https://members-only-site.com/news"
    name: "Members Site"
    enabled: true
    auth:
      method: "cookie"
      cookie: "session_id=abc123; csrf_token=xyz789"
```

Cookie 추출 방법:
1. 브라우저에서 해당 사이트 로그인
2. DevTools (F12) → Network 탭 → 아무 요청 클릭
3. Request Headers → Cookie 값 복사
4. .env 파일에 저장 (보안)

#### 방법 2: Playwright 기반 자동 로그인

JS 렌더링이 필요하거나 복잡한 로그인 플로우:

```python
# web_crawler.py에 추가 구현 가능
async def _login_with_playwright(self, url, credentials):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 로그인 페이지 이동
        await page.goto("https://site.com/login")
        await page.fill("#email", credentials["email"])
        await page.fill("#password", credentials["password"])
        await page.click("button[type=submit]")
        await page.wait_for_navigation()

        # 로그인 후 쿠키 저장
        cookies = await context.cookies()
        # cookies를 파일로 저장하여 재사용
        ...
```

---

## 5. 텔레그램 봇 (발신용)

### BotFather에서 봇 생성

```
1. 텔레그램에서 @BotFather 검색
2. /newbot 명령
3. 봇 이름, username 입력
4. HTTP API Token 복사
5. .env에 입력:
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
```

### Chat ID 확인

```
1. 봇을 시작 (/start)
2. 브라우저에서:
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
3. JSON 응답에서 "chat":{"id": 123456789} 확인
4. .env에 입력:
   TELEGRAM_CHAT_ID=123456789
```

채널로 전송하려면:
- 봇을 채널 관리자로 추가
- Chat ID = `@채널username` 또는 `-100` + 채널 숫자 ID

---

## 보안 체크리스트

- [ ] `.env` 파일이 `.gitignore`에 포함됨
- [ ] `.session` 파일이 `.gitignore`에 포함됨
- [ ] `x_state.json` 파일이 `.gitignore`에 포함됨
- [ ] Docker 사용 시 시크릿을 env_file로 전달
- [ ] 사내망 배포 시 외부 접근 차단 확인
- [ ] X 계정에 2FA 활성화됨
- [ ] 텔레그램 세션은 정기적으로 Active Sessions 확인
- [ ] Cookie 기반 인증은 만료 전 갱신 스크립트 구현
