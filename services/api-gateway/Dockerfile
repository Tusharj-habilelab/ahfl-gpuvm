FROM python:3.10-slim

LABEL service="api-gateway" version="1.1.0"

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY services/api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy gateway service + shared core
COPY services/api-gateway/ .
COPY core/ ./core/

EXPOSE 8000

RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
