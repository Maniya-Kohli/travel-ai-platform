FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ✅ shared code from repo root
COPY platform_common ./platform_common

# ✅ worker service dependencies (note the path)
COPY worker-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ✅ worker service application code
COPY worker-service/app ./app

# Make repo root importable so 'platform_common' works
ENV PYTHONPATH=/app

CMD ["python", "-m", "app.main"]
