# ==============================================================================
# Enterprise AI Knowledge Platform — Multi-Service Dockerfile
# ==============================================================================

FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose backend (8000) and frontend (8501) ports
EXPOSE 8000 8501

# Default command launches backend API (respecting dynamic PORT environment variable)
CMD ["sh", "-c", "python scripts/seed_data.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
