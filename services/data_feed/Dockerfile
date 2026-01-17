# ========================
# Stage 1: Build
# ========================
FROM rust:latest AS builder

# تثبيت الأدوات المطلوبة للبناء
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# نسخ ملفات المشروع (Context is project root)
COPY services/data_feed/ ./services/data_feed/
COPY shared/ ./shared/

# بناء الباينري (Dynamic linking with glibc)
WORKDIR /app/services/data_feed
RUN cargo build --release

# ========================
# Stage 2: Runtime (Ubuntu)
# ========================
# استخدام Ubuntu 24.04 كما هو في السيرفر
FROM ubuntu:24.04

# تثبيت المكتبات المطلوبة للتشغيل
RUN apt-get update && apt-get install -y \
    ca-certificates \
    openssl \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# نسخ الباينري المكتمل
COPY --from=builder /app/services/data_feed/target/release/websocket_candle_rust .

# نسخ المجلد المشترك (shared) للوصول إلى symbols.json
COPY shared/ ./shared/

# تشغيل الباينري
CMD ["./websocket_candle_rust"]
