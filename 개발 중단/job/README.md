# Enki Job Notification Bot

엔키(Enki) 채용 사이트의 인턴 공고를 크롤링하여 새로운 공고가 올라오면 디스코드 웹훅으로 알림을 보내는 파이썬 스크립트입니다.

## 기능

*   **크롤링**: Playwright를 사용하여 동적으로 로드되는 채용 공고 정보를 수집합니다.
*   **수집 항목**: 직군, 직무, 경력사항, 고용형태 등 상세 정보를 파싱합니다.
*   **DB 동기화**: MongoDB를 사용하여 중복 알림을 방지합니다.
*   **실행 제어**: 하루에 한 번만 실행되도록 체크하는 로직이 포함되어 있습니다.

## 설치 방법

1.  **필수 라이브러리 설치**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Playwright 브라우저 설치**
    ```bash
    playwright install
    ```

3.  **환경 변수 설정**
    `job` 디렉토리 안에 `.env` 파일을 생성하고 다음 내용을 작성하세요.
    ```env
    MONGO_URI=mongodb://localhost:27017/
    DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
    ```

## 실행 방법

```bash
python enki.py
```

## WSL Cron 등록 (매시 10분 실행)

WSL 환경에서 매시 10분마다 스크립트를 실행하려면 `cron`을 사용하세요.
(코드 내부에 하루 1회 실행 제한 로직이 있어, 매시간 실행해도 실제 알림은 하루 한 번만 갑니다.)

1.  **Crontab 편집**
    ```bash
    crontab -e
    ```

2.  **스케줄 추가**
    파일 맨 아래에 다음 줄을 추가합니다.
    ```cron
    # 매시 10분에 실행
    10 * * * * cd /home/shwoo03/Project/job && /usr/bin/python3 enki.py > /dev/null 2>&1
    ```
    *   `10 * * * *`: 매 시간 10분에 실행합니다.
    *   `cd ... && ...`: 해당 디렉토리로 이동 후 실행해야 `.env` 파일을 잘 찾을 수 있습니다.

3.  **Cron 서비스 시작** (WSL을 켤 때마다 필요할 수 있음)
    ```bash
    sudo service cron start
    ```
