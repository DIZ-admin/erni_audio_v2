# =============================================================================
# Dockerfile для Erni Audio v2
# Оптимизированный для production
# =============================================================================

FROM python:3.11-slim

# Метаданные образа
LABEL maintainer="Erni Audio Team"
LABEL version="2.0"
LABEL description="Speech Pipeline with Diarization, Transcription and Voiceprint Analysis"

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    libmagic1 \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Создаём пользователя для безопасности
RUN groupadd -r erni && useradd -r -g erni erni

# Создаём рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Создаём необходимые директории с правильными правами
RUN mkdir -p data/raw data/interim data/processed voiceprints logs cache \
    && chown -R erni:erni /app

# Копируем код приложения
COPY --chown=erni:erni . .

# Устанавливаем права на выполнение для скриптов
RUN chmod +x speech_pipeline.py health_check.py

# Переключаемся на непривилегированного пользователя
USER erni

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python health_check.py --json || exit 1

# Expose порт для webhook сервера
EXPOSE 8000

# Устанавливаем точку входа (можно переопределить)
ENTRYPOINT ["python", "speech_pipeline.py"]

# По умолчанию показываем help
CMD ["--help"]
