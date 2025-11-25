FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if you need others, add here)
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Shared code from repo root
COPY platform_common ./platform_common

# Gateway service dependencies (note the path)
COPY gateway-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Gateway service application code
COPY gateway-service/app ./app

# Make repo root importable so 'platform_common' works
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
