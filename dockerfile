# استخدم صورة بايثون 3.11 خفيفة
FROM python:3.11-alpine

# إعداد مجلد العمل
WORKDIR /app

# نسخ ملفات المشروع
COPY . /app

# تحديث pip وتثبيت المتطلبات
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# الأمر الافتراضي لتشغيل البوت
CMD ["python3", "WebSocket_Real_time.py"]
