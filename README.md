# 📁 Project
---

## 1. 📱 인스타그램 맞팔 정리 프로그램

팔로워/팔로잉의 **맞팔 상태를 자동으로 확인**하여, 사용자가 일일이 계정을 확인하며 정리하는 수고를 덜어주는 프로그램입니다.

### 🔧 사용 기술

- **Python**
  - `selenium` – 브라우저 자동화 및 웹 페이지 동작 제어
  - `requests` – 네트워크 요청을 통한 API 데이터 처리

### ✅ 주요 기능 및 장점

- **맞팔 상태 자동 확인**  
  → 팔로워/팔로잉 리스트를 비교하여 맞팔 여부를 한눈에 확인 가능

- **사용자 정보는 로컬에서만 처리**  
  → 외부 서버로의 전송 없이 실행되므로 **개인정보 유출 가능성 낮음**

- **자동화 탐지 우회 기능 적용**  
  → 일반적인 자동화 차단을 회피할 수 있도록 설계됨

- **HTML 구조 변경에 강한 파싱 처리**  
  → API를 통해 데이터를 직접 요청하므로 구조 변경으로 인한 오류 가능성 감소

### ⚠️ 한계 및 주의사항

- **2단계 인증(2FA) 계정 지원 미완**  
  → 현재 2FA를 사용하는 계정의 로그인은 지원되지 않습니다.

- **API 구조 변경 시 유지보수 필요**  
  → 인스타그램 API나 HTML 구조가 변경되면 코드 수정이 필요할 수 있습니다.
<br>

---

## 2. 📌 BOB 공지사항 확인 프로그램
### 사용 기술
- **python**
  - requests - API 데이터 처리    

### 주요 기능
- 최신 공지사항 게시물 제목 및 날짜 확인 
- url 제공

<br>

---

## 3. 🔔 GitHub 태그 모니터링 알림 시스템

개발 관련 주요 SDK 및 라이브러리의 **새로운 태그(릴리즈) 등록을 자동으로 모니터링**하여 Discord 웹훅으로 실시간 알림을 제공하는 시스템입니다.

### 🔧 사용 기술

- **Python**
  - `requests` – GitHub 페이지 크롤링 및 Discord 웹훅 전송
  - `beautifulsoup4` – HTML 파싱을 통한 태그 정보 추출
  - `datetime` – 시간 비교 및 포맷팅

### 📊 모니터링 대상

- **MCP (Model Context Protocol)**
  - `mcp_python_sdk` – Python SDK
  - `mcp_typescript_sdk` – TypeScript SDK

- **A2A Project**
  - `a2a_python_sdk` – Python SDK
  - `a2a_js_sdk` – JavaScript SDK
  - `a2a_java_sdk` – Java SDK
  - `a2a_dotnet_sdk` – .NET SDK

- **LangChain AI**
  - `langchain` – LangChain 메인 라이브러리
  - `langgraph` – LangGraph 라이브러리

- **Google ADK**
  - `adk_python` – Python ADK
  - `adk_java` – Java ADK

- **FastMCP**
  - `fast_mcp` – FastMCP 라이브러리

### ✅ 주요 기능

- **실시간 태그 모니터링**  
  → GitHub의 태그 페이지를 주기적으로 확인하여 새로운 릴리즈 감지

- **중복 알림 방지**  
  → 이전에 확인한 태그는 `time.txt`에 기록하여 중복 알림 방지

- **Discord 실시간 알림**  
  → 새로운 태그 발견 시 Discord 웹훅을 통해 즉시 알림 전송

- **태그 페이지 링크 제공**  
  → 알림과 함께 해당 GitHub 태그 페이지 URL 제공

- **시간 비교 여유값 적용**  
  → 1분의 여유를 두어 시간 오차로 인한 오작동 방지

### 📁 파일 구조 (단일 스크립트 통합 버전)

```
MCP,A2A_Notification/
├── main.py          # 통합 모니터링 실행 스크립트
├── config.py        # 디스코드 Webhook / 모니터링 대상 저장소 설정
├── .env.example     # 환경변수 예시 (실제 .env는 제외)
├── time.txt         # 마지막 감지된 태그 시간 기록
└── cron.log         # 주기 실행 로그(선택)
```

이전 버전의 분리된 `MCP_SDK.py`, `A2A_SDK.py` 등은 `config.py`와 반복 로직 통합으로 제거되었습니다.

### 🚀 사용 방법

### 🛠 준비
1. Python 3.10+ 설치
2. 필요한 패키지 설치
  ```bash
  pip install requests beautifulsoup4 python-dotenv
  ```
3. `.env.example`을 복사해 `.env` 생성 후 Webhook URL 입력
  ```bash
  copy MCP,A2A_Notification\.env.example MCP,A2A_Notification\.env  # Windows
  ```

### ▶ 실행
```bash
python MCP,A2A_Notification/main.py
```

### ⏱ 주기 실행 (Windows 작업 스케줄러 예시)
1. 작업 스케줄러 > 작업 만들기
2. 트리거: 5분 마다
3. 동작: 프로그램 시작 > `python` 인수: `c:\path\to\Project\MCP,A2A_Notification\main.py`
4. (선택) 출력 로그를 `cron.log`로 리다이렉션하려면 배치 스크립트 사용

### ⏱ 주기 실행 (Linux / WSL cron 예시)
```bash
*/5 * * * * /usr/bin/python3 /path/to/Project/MCP,A2A_Notification/main.py >> /path/to/Project/MCP,A2A_Notification/cron.log 2>&1
```

### ⚠️ 주의사항

- **GitHub 접근 제한**  
  → 과도한 요청 시 GitHub에서 일시적으로 접근을 제한할 수 있습니다.

- **Discord 웹훅 URL 보안**  
  → 웹훅 URL이 코드에 하드코딩되어 있으므로 공개 저장소 업로드 시 주의가 필요합니다.

- **의존성 경고**  
  → `urllib3` 및 `chardet` 버전 불일치 경고가 발생할 수 있으나 기능에는 영향을 주지 않습니다.
