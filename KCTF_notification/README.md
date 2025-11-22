# K-CTF Notification Bot

K-CTF 대회 정보를 크롤링하여 새로운 대회가 등록되면 디스코드 웹훅을 통해 알림을 보내는 파이썬 스크립트입니다. MongoDB를 사용하여 중복 알림을 방지하고, 하루에 한 번만 실행되도록 설계되었습니다.

## 기능

*   **크롤링**: [K-CTF](http://k-ctf.org/?status=registering) 사이트에서 '신청 중'인 대회 정보를 수집합니다.
*   **DB 동기화**: MongoDB에 대회 정보를 저장하고, 웹사이트에서 사라진 대회는 DB에서도 삭제합니다.
*   **알림**: 새로운 대회가 발견될 때만 디스코드 웹훅으로 알림을 전송합니다.
*   **중복 실행 방지**: 하루에 한 번만 실행되도록 체크하는 로직이 포함되어 있습니다.

## 설치 방법

1.  **필수 라이브러리 설치**
    ```bash
    pip install -r requirements.txt
    ```

2.  **환경 변수 설정**
    `KCTF_notification` 디렉토리 안에 `.env` 파일을 생성하고 다음 내용을 작성하세요.
    ```env
    MONGO_URI=mongodb://localhost:27017/ # 또는 사용 중인 MongoDB URI
    DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
    ```

## 실행 방법

```bash
python main.py
```

## WSL Cron 등록 (하루 1회 실행)

WSL 환경에서 매일 특정 시간(예: 오전 9시)에 스크립트를 자동으로 실행하려면 `cron`을 사용하세요.

1.  **Crontab 편집**
    ```bash
    crontab -e
    ```

2.  **스케줄 추가**
    파일 맨 아래에 다음 줄을 추가합니다. (경로는 실제 프로젝트 경로로 수정해주세요)
    ```cron
    # 매시 5분에 실행 (예: 1:05, 2:05, 3:05 ...)
    5 * * * * cd /home/shwoo03/Project/KCTF_notification && /usr/bin/python3 main.py > /dev/null 2>&1
    ```
    *   `5 * * * *`: 매 시간 5분에 실행합니다.
    *   코드 내부에 "하루 1회 실행 체크" 로직이 있으므로, 매시간 실행되더라도 실제 크롤링과 알림은 **하루에 한 번(가장 먼저 실행된 시점)**만 수행됩니다.
    *   `cd ... && ...`: 해당 디렉토리로 이동 후 실행해야 `.env` 파일을 잘 찾을 수 있습니다.

3.  **Cron 서비스 시작** (WSL을 켤 때마다 필요할 수 있음)
    ```bash
    sudo service cron start
    ```
