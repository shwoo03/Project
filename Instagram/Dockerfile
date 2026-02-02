# Instagram Follower Tracker
FROM python:3.11-slim

# 시스템 의존성 설치 (Playwright용)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치
RUN playwright install chromium
RUN playwright install-deps chromium

# 애플리케이션 코드 복사
COPY *.py ./
COPY routers/ ./routers/
COPY repositories/ ./repositories/
COPY templates/ ./templates/
COPY static/ ./static/

# 포트 노출
EXPOSE 10000

# 환경 변수 (런타임에 오버라이드)
ENV PYTHONUNBUFFERED=1

# 대시보드 서버 실행
CMD ["python", "dashboard.py"]
