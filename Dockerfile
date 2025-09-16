FROM python:3.12-alpine

WORKDIR /app

# نسخ ملفات المشروع
COPY . /app

# تثبيت مكتبات Python
RUN python3 -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# يمكنك تحديد السكربت المراد تشغيله بواسطة متغير بيئة SCRIPT_NAME
# إذا لم يتم تحديده، سيتم تشغيل WebSocket_Real_time.py افتراضيًا
ENV SCRIPT_NAME=WebSocket_Real_time.py

CMD ["sh", "-c", "python3 /app/$SCRIPT_NAME"]
