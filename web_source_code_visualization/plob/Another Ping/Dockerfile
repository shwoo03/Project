FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY deploy/ .

EXPOSE 8000

CMD ["python", "app.py"]