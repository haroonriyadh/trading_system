FROM rust:1.92-slim AS builder
WORKDIR /app

COPY services/data_feed/ ./services/data_feed/
COPY shared/ ./shared/

WORKDIR /app/services/data_feed
RUN cargo build --release

FROM ubuntu:24.04
WORKDIR /app

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/services/data_feed/target/release/websocket_candle_rust .
COPY shared/ ./shared/

CMD ["./websocket_candle_rust"]
