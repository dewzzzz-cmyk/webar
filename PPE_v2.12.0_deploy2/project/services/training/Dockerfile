# PPE Training Service Dockerfile
# Celery worker with YOLOv8 for model training

FROM pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime

LABEL maintainer="PPE Detection System"
LABEL description="Training worker for PPE detection models"

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download YOLOv8 models
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Copy application
COPY worker.py .

# Create directories
RUN mkdir -p /app/training_data/datasets \
             /app/training_data/runs \
             /app/training_data/images \
             /app/models

# Environment
ENV PYTHONUNBUFFERED=1
ENV C_FORCE_ROOT=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD celery -A worker inspect ping || exit 1

# Default command
CMD ["celery", "-A", "worker", "worker", "-l", "info", "-c", "1", "-Q", "training"]
