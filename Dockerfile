# استخدم صورة بايثون خفيفة
FROM python:3.12-alpine

# ضبط متغير البيئة لمنع .pyc و buffering
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# إنشاء مجلد التطبيق
WORKDIR /app

# نسخ ملفات المشروع
COPY . /app

# تحديث pip وتثبيت المتطلبات
RUN doas pip install --upgrade pip \
    && doas pip install --no-cache-dir -r requirements.txt

# فتح البورتات اللازمة إذا لزم الأمر (مثلاً للتواصل مع WebSocket أو Redis)
EXPOSE 8000

# الأمر الافتراضي لتشغيل البرنامج
CMD ["python", "WebSocket_Candle.py"]
