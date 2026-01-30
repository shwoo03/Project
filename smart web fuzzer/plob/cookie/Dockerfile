FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy structure
COPY app.py .
# COPY flag.txt .
RUN echo "DH{7952074b69ee388ab45432737f9b0c56}" > flag.txt
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8000

CMD ["python", "app.py"]
