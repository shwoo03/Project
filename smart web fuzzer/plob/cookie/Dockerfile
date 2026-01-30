FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy structure
COPY app.py .
COPY flag.txt .
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8000

CMD ["python", "app.py"]
