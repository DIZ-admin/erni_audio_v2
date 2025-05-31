FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Создаём рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаём необходимые директории
RUN mkdir -p data/raw data/interim data/processed voiceprints logs

# Устанавливаем точку входа
ENTRYPOINT ["python", "speech_pipeline.py"]

# По умолчанию показываем help
CMD ["--help"]
