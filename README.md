# 📁 Project
---

## 1. BOB 공지사항 알림 
- BOB 게시판에서 새로운 게시물이 존재하는지 팔로우
- 새로운 게시물이 존재하면 알림을 울립니다. 
<br>

---  
## 2. 인스타그램 팔로우 정리
인스타그램 팔로워/팔로잉 관계를 추적하고, 맞팔 여부를 분석하여 정리할 수 있는 웹 대시보드 애플리케이션입니다.

### 🌟 주요 기능
- **Web Dashboard**: FastAPI & Jinja2 기반의 직관적인 반응형 웹 인터페이스 제공
- **실시간 로그 및 진행률**: WebSocket을 통한 작업 진행 상황 및 로그 실시간 모니터링
- **Discord 알림**: 작업 완료 결과 및 팔로워 변동 사항(New/Lost)을 Discord Webhook으로 전송
- **히스토리 관리**: MongoDB를 사용하여 일별 팔로워 수 및 변동 기록 저장/조회
- **스케줄링**: 백그라운드 스케줄러를 통해 매일 정해진 시간에 자동 실행 가능

### 🛠️ 기술 스택
- **Python 3.11**
- **FastAPI**: 웹 서버 및 API
- **Playwright**: 인스타그램 로그인 및 데이터 크롤링 (비동기 처리)
- **MongoDB**: 데이터 및 히스토리 저장
- **Docker & Docker Compose**: 컨테이너 기반 배포

### 🚀 설치 및 실행 (Docker)
가장 간편한 실행 방법입니다.

1. `Instagram` 디렉토리로 이동
2. `.env` 파일 설정:
   ```bash
   cp .env.example .env
   # .env 파일 내 USERNAME, PASSWORD, MONGO_URI, DISCORD_WEBHOOK 등 설정
   ```
3. Docker Compose 실행:
   ```bash
   docker-compose up -d --build
   ```
4. 브라우저에서 `http://localhost:8000` 접속

### 🐍 설치 및 실행 (Python)
로컬 Python 환경에서 실행할 경우:

1. 의존성 설치:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. 실행:
   ```bash
   python dashboard.py
   ```
<br>

---
## 3. 깃허브 레포 업데이트 추적
- 특정 깃허브 레포에 tags를 추적하여 새로운 업데이트가 존재하면 디스코드 웹 훅으로 알려주는 기능 
<br>

--- 
## 4. 노션 DB 정리 
- 프로젝트 진행 중 CVE 관리 및 취약점 리스트 관리를 편리하게 하기 위해서 Notion API 사용해서 DB 관리하는 기능
<br>

---
## 5. K-CTF 대회 알림
- K-CTF 사이트에서 새로운 대회가 등록되면 디스코드 웹훅으로 알림을 보냅니다.
- 하루 1회 실행되며, 중복 알림을 방지합니다.
<br>

---
## 6. Enki 채용 공고 알림
- Enki 채용 사이트에서 인턴 공고를 크롤링하여 새로운 공고가 올라오면 디스코드 웹훅으로 알림을 보냅니다.
- Playwright를 사용하여 동적 페이지를 파싱하며, 하루 1회 실행됩니다.
<br>

---
