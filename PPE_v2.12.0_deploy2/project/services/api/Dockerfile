FROM python:3.11-slim

WORKDIR /app

# Установка curl для health check и libgl для OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем ВСЕ Python файлы
COPY *.py .

# Создаём директории
RUN mkdir -p /app/configs /app/violations /app/models /app/training_data

# Запуск
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
