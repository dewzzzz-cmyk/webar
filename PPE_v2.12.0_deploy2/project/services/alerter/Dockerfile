FROM python:3.11-slim

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY main.py .

# Создаём директории
RUN mkdir -p /app/configs /app/violations

# Запуск
CMD ["python", "main.py"]
