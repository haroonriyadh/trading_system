# ========================
# Stage 1: Build
# ========================
FROM rust:latest AS builder

# تثبيت الأدوات المطلوبة للبناء باستخدام musl
RUN apt-get update && apt-get install -y \
    musl-tools \
    build-essential \
    pkg-config \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# إعداد Rust للربط مع musl
RUN rustup target add x86_64-unknown-linux-musl

WORKDIR /app

# نسخ ملفات المشروع
COPY . .

# بناء الباينري statically
RUN cargo build --release --target x86_64-unknown-linux-musl

# ========================
# Stage 2: Runtime (حاوية صغيرة جدًا)
# ========================
FROM scratch

WORKDIR /app

# نسخ الباينري المكتمل statically
COPY --from=builder /app/target/x86_64-unknown-linux-musl/release/websocket_candle_rust .

# نسخ المجلد المشترك (shared) للوصول إلى symbols.json
COPY shared/ ./shared/

# نسخ شهادات SSL اللازمة (optional إذا كنت تتصل بـ HTTPS)
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# تشغيل الباينري
CMD ["./websocket_candle_rust"]
