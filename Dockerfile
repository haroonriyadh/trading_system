FROM python:3.12-slim

WORKDIR /app

# تثبيت أدوات البناء و git و bash على Debian
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    bash \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملفات المشروع
COPY . /app

# تثبيت مكتبات Python
RUN python3 -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

CMD ["python3", "WebSocket_Real_time.py"]
