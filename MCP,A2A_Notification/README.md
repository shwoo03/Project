# A2A Notification (MCP) 서비스

이 저장소는 GitHub 태그 페이지를 주기적으로 확인하고, 새로운 태그가 감지되면 Discord 웹훅으로 알림을 전송하는 간단한 모니터링 서비스입니다.

주요 기능
- 여러 그룹/리포지토리(`REPOS`)를 설정 파일에서 정의하여 태그 변경을 감지
- 각 리포지토리별로 환경변수 기반 웹훅 URL을 우선 사용
- 전역 `DISCORD_WEBHOOK_URL`이 없더라도 repo별 `DISCORD_WEBHOOK_URL_<repo>`로 동작 가능
- 변경사항이 있을 때마다 `time.txt`에 마지막 체크 시간을 저장

파일 개요
- `main.py` : 서비스 메인 스크립트(태그 체크, 웹훅 전송, time.txt 업데이트)
- `config.py` : REPOS 설정 및 전역 웹훅(선택)
- `time.txt` : 각 리포지토리의 마지막 체크 시간 저장
- `.env` / `.env.example` : 환경변수(웹훅 URL) 설정 예시
- `smoke_test.py` : 로컬에서 동작을 확인하기 위한 간단한 목업 테스트

설정(환경변수)
- 전역 웹훅(선택): `DISCORD_WEBHOOK_URL` — 모든 리포지토리의 기본 웹훅
- 리포지토리별 웹훅(권장): `DISCORD_WEBHOOK_URL_<repo>`
  - 예: `REPOS`에 `ollama`가 있으면 `DISCORD_WEBHOOK_URL_ollama` 설정
  - `llama.cpp` 같은 이름은 점(.)을 포함하므로 `DISCORD_WEBHOOK_URL_llama.cpp` 또는 `DISCORD_WEBHOOK_URL_llama_cpp` 둘 다 시도합니다.

보안 주의
- `.env` 파일에 실제 웹훅 URL을 저장할 수 있으나, 공개 저장소에 업로드하지 마세요.
- `.gitignore`에 이미 `.env`가 포함되어 있습니다.

실행 방법 (Windows cmd)
- 의존성 설치:
```bat
python -m pip install -r requirements.txt
```

- 로컬 스모크 테스트(실제 Discord 전송을 모킹):
```bat
python smoke_test.py
```

- 실제 실행:
```bat
python main.py
```

time.txt 설명
- 형식: `key = YYYY-MM-DD:HH:MM`
- `key`는 `REPOS`에 정의한 리포지토리 키와 정확히 일치해야 합니다.

권장 개선사항(추후)
- 각 리포지토리별로 커스텀 메시지/포맷 지원
- GitHub API 사용으로 HTML 파싱 대신 안정성 개선
- 단위 테스트 추가 및 CI 구성

문의
- 사용 중 문제가 발생하면 `main.py`와 `time.txt`의 내용을 첨부해 주세요.
