---
name: instagram-maintenance
description: 인스타그램 팔로워 추적기 유지보수 스킬. 에러 발생 시 디버깅, 인스타그램 UI/API 변경 대응, 성능 최적화, 코드 리팩터링 작업에 사용. 로그인 실패, API 오류, MongoDB 연결 문제, 셀렉터 변경 등의 이슈 해결 가이드 포함.
---

# 인스타그램 팔로워 추적기 유지보수

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 목적 | 인스타그램 팔로워/팔로잉 변동 추적 자동화 |
| 스택 | Python + Playwright + Requests + MongoDB + Discord Webhook |
| 핵심 파일 | `main.py` |
| 인증 | `.env` (USER_ID, USER_PASSWORD, MONGO_URI, DISCORD_WEBHOOK) |

---

## 1. 에러 대응 가이드

### 1.1 로그인 실패

**증상:**
- `ds_user_id 쿠키가 없습니다`
- `로그인 실패 또는 쿠키 획득 시간 초과`
- `login_failed.png` 스크린샷 생성됨

**진단 순서:**
1. 스크린샷 파일 확인 (`login_*.png`)
2. `.env` 자격증명 검증
3. `cookies.json` 삭제 후 재시도
4. `headless=False`로 브라우저 직접 확인 (라인 88)

**주요 원인 & 해결:**

| 원인 | 해결 |
|------|------|
| 봇 탐지 차단 | VPN 사용, User-Agent 변경 |
| 2FA 활성화 | 인스타그램에서 2FA 비활성화 |
| 셀렉터 변경 | 아래 셀렉터 테이블 참조 |
| 세션 만료 | `cookies.json` 삭제 |

### 1.2 API 요청 실패

**증상:**
- `API 요청 실패 (Status: 401/403/429)`
- 팔로워 0명 반환

**상태 코드별 대응:**

| 코드 | 의미 | 해결 |
|------|------|------|
| 401 | 인증 실패 | cookies.json 삭제, 재로그인 |
| 403 | 권한 없음 | X-IG-App-ID 확인 (라인 265) |
| 429 | Rate Limit | 딜레이 증가 (라인 322) |

### 1.3 MongoDB 연결 실패

**증상:** `DB 저장 중 오류 발생`

**진단:**
1. `.env`의 `MONGO_URI` 형식 확인
2. MongoDB 서비스 상태 확인
3. Atlas 사용 시 IP 화이트리스트 확인

---

## 2. 인스타그램 변경 대응

### 2.1 필수 셀렉터 테이블

| 라인 | 셀렉터 | 용도 |
|------|--------|------|
| 127 | `svg[aria-label="홈"]` | 로그인 성공 확인 |
| 151 | `input[name="username"]` | 아이디 입력창 |
| 163 | `input[name="password"]` | 비밀번호 입력창 |
| 190 | `"나중에 하기"` | 팝업 닫기 버튼 |

**변경 확인 방법:**
```
1. headless=False로 실행
2. 브라우저 F12 → Elements 탭
3. 실제 셀렉터와 비교
```

### 2.2 API 엔드포인트

**현재 사용 중:**
```
/api/v1/friendships/{id}/followers/
/api/v1/friendships/{id}/following/
```

**변경 감지 시:**
1. 브라우저 Network 탭에서 실제 API 확인
2. 라인 283 URL 업데이트
3. 응답 JSON 구조 변경 시 라인 306-313 수정

### 2.3 필수 헤더

```python
# 라인 264-269
"X-IG-App-ID": "936619743392459"  # 인스타 앱 ID
"X-CSRFToken": session.cookies.get("csrftoken")
"X-Requested-With": "XMLHttpRequest"
```

---

## 3. 성능 최적화

### 3.1 Rate Limit 튜닝

| 팔로워 수 | 권장 딜레이 | 수정 라인 |
|----------|------------|----------|
| ~500명 | 1-2초 | 322 |
| ~2000명 | 2-4초 (현재) | 322 |
| 5000명+ | 4-6초 | 322 |

### 3.2 쿠키 최적화

현재 로직:
1. `cookies.json` 로드 시도
2. 유효하면 재사용
3. 무효하면 재로그인 후 저장

**개선 옵션:**
- 쿠키 만료 시간 사전 체크
- 로그인 성공 시 만료 일자 저장

---

## 4. 리팩터링 가이드

### 4.1 권장 구조 분리

```
📁 instagram_tracker/
├── config.py       # get_env_var()
├── auth.py         # 로그인, 쿠키 관리
├── api.py          # 팔로워/팔로잉 수집
├── database.py     # MongoDB 연동
├── notification.py # Discord Webhook
└── main.py         # 진입점
```

### 4.2 로깅 개선

**현재:** print문
**권장:**
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
```

### 4.3 설정 외부화 대상

| 하드코딩 값 | 위치 | 권장 |
|------------|------|------|
| X-IG-App-ID | 라인 265 | config.yaml |
| Rate Limit | 라인 322 | .env |
| DB/컬렉션명 | 라인 348-350 | .env |

---

## 5. 유지보수 체크리스트

### 정기 점검 (월 1회)
- [ ] 인스타그램 UI 변경 확인
- [ ] API 응답 정상 확인
- [ ] MongoDB 용량/연결 확인
- [ ] 의존성 보안 업데이트

### 에러 발생 시
1. [ ] 스크린샷 확인 (`*_error.png`)
2. [ ] `.env` 검증
3. [ ] `cookies.json` 삭제 후 재시도
4. [ ] `headless=False` 디버깅

### 배포 전
- [ ] `pip install -r requirements.txt`
- [ ] `playwright install chromium`
- [ ] `.env` 설정 완료
- [ ] MongoDB 연결 테스트

---

## 6. 빠른 참조

### 자주 쓰는 명령어

```bash
# 설치
pip install -r requirements.txt
playwright install chromium

# 실행
python main.py

# 디버그 (headless=False 변경 후)
python main.py
```

### 에러 → 해결 맵

| 에러 | 원인 | 해결 |
|------|------|------|
| ds_user_id 없음 | 로그인 실패 | cookies.json 삭제 |
| Status 401 | 세션 만료 | 재로그인 |
| Status 429 | Rate Limit | 딜레이 증가 |
| 페이지 로딩 초과 | 차단/네트워크 | VPN 또는 headless=False |
| DB 오류 | MongoDB 연결 | MONGO_URI 확인 |
