# استخدم نسخة Python مناسبة وخفيفة
FROM python:3.12-alpine

# إعداد مجلد العمل
WORKDIR /app

# نسخ ملفات المشروع
COPY . /app

# تثبيت مكتبات Python
RUN python3 -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# الأمر الافتراضي لتشغيل السكربت
CMD ["python3", "WebSocket_Real_time.py"]
