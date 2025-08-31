FROM python:3.12-slim

# تثبيت أدوات البناء الأساسية
RUN apk add --no-cache \
    build-base \
    git \
    bash \
    python3-dev \
    libffi-dev \
    openssl-dev

WORKDIR /app

COPY . /app

# تحديث pip وتثبيت المكتبات
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1

CMD ["python3", "WebSocket_Real_time.py"]
