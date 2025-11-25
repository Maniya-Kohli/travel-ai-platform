FROM python:3.11-slim

# Set working directory at project root inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy shared code first (for better caching)
COPY platform_common ./platform_common

# Copy requirements for this service
COPY db-service/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy this service's application code
COPY db-service/app ./app

# Make repo root importable so 'platform_common' works
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8001

# Run the application (db service's FastAPI app)
CMD ["uvicorn", "app.main:app","--host", "0.0.0.0","--port", "8001","--log-level", "info","--no-access-log"]

