# K-CTF 신규 대회 알림봇

K-CTF(http://k-ctf.org) 사이트에서 신청 중인 CTF 대회를 모니터링하고, 새로운 대회가 등록되면 디스코드 웹훅으로 알림을 보내는 프로그램입니다.

## 기능

- K-CTF 사이트의 신청 중인 대회 목록 체크
- 새로운 대회 등록 시 디스코드 웹훅으로 알림 (예쁜 임베드 형식)
- `ctf_list.txt` 파일에서 CTF 목록 자동 관리
- 신청 마감된 대회 자동 감지

## 설치

필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

## 사용법

### 1. 초기 실행 (CTF 목록 초기화)
```bash
python main.py
```
처음 실행하면 현재 신청 중인 CTF 목록이 `ctf_list.txt`에 저장됩니다.

### 2. 테스트
프로그램을 여러 번 실행하여 새로운 대회 감지가 잘 되는지 확인하세요.
현재 디스코드 웹훅 코드는 주석처리되어 있어 콘솔에만 출력됩니다.

### 3. 디스코드 웹훅 활성화
테스트가 완료되면 `main.py`에서:
1. 디스코드 웹훅 URL 설정:
   ```python
   DISCORD_WEBHOOK_URL = "실제_웹훅_URL"
   ```
2. `send_discord_notification` 함수의 주석 해제 (# 제거)

### 4. 정기 실행 설정
Windows 작업 스케줄러나 cron으로 주기적 실행 설정:

**Windows (작업 스케줄러):**
- 5분마다 또는 원하는 간격으로 `python main.py` 실행

**Linux/Mac (crontab):**
```bash
# 5분마다 실행
*/5 * * * * cd /path/to/KCTF_notification && python main.py
```

## 디스코드 웹훅 설정 방법

1. 디스코드 서버 설정 → 연동 → 웹훅 생성
2. 웹훅 URL 복사
3. `main.py`의 `DISCORD_WEBHOOK_URL`에 붙여넣기
4. 주석 처리된 디스코드 전송 코드 주석 해제

## 파일 설명

- `main.py`: 메인 프로그램 (한 번 실행하고 종료)
- `ctf_list.txt`: CTF 대회 목록 저장 파일 (자동 생성/관리)
- `requirements.txt`: 필요한 Python 패키지 목록

## 주의사항

- 프로그램은 한 번 실행하고 종료되므로 정기적으로 실행하려면 스케줄러 사용 필요
- 너무 짧은 체크 간격은 서버에 부담을 줄 수 있으므로 5분 이상 권장
