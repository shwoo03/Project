FROM python:3.12-slim

WORKDIR /app

# System deps (including Playwright browser dependencies)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        # Playwright Chromium deps
        libnss3 \
        libnspr4 \
        libatk-bridge2.0-0 \
        libdrm2 \
        libxkbcommon0 \
        libgbm1 \
        libasound2 \
        libatspi2.0-0 \
        libxshmfence1 \
        libxdamage1 \
        libxrandr2 \
        libxcomposite1 \
        libxfixes3 \
        libcups2 \
        libpango-1.0-0 \
        libcairo2 \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Install Codex CLI (optional, Node.js required)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @openai/codex && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium
RUN playwright install chromium

# App code
COPY . .

# Create data directories
RUN mkdir -p data/sessions

# Non-root user
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "import config; print('ok')" || exit 1

# Default: run scheduler
CMD ["python", "-m", "scheduler.main"]
