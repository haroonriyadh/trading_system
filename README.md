# نظام التداول الآلي للعملات الرقمية

نظام تداول آلي متقدم للعملات الرقمية يعتمد على هندسة **Modular Monolith** مع اكتشاف Order Blocks و Flag Patterns وتنفيذ الأوامر تلقائياً.

## الهندسة المعمارية

النظام مبني على **Event-Driven Modular Monolith** حيث تتواصل الوحدات عبر Redis Pub/Sub:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Feed     │────▶│ Indicator Engine│────▶│ Strategy Engine │
│   (Rust WS)     │     │  (Highs/Lows)   │     │ (Flag/OB)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Telegram Engine │◀────│ Execution Engine│◀────│   Contracts     │
│  (Notifications)│     │   (Orders)      │     │   (Interfaces)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## هيكل المشروع

```
trading_system/
├── contracts/                 # 🆕 Interfaces للتواصل بين الوحدات
│   ├── __init__.py           # Exports
│   ├── types.py              # TypedDict definitions (DTOs)
│   ├── channels.py           # Redis channel functions
│   └── serializers.py        # JSON serialization helpers
│
├── services/
│   ├── data_feed/            # Rust WebSocket (Binance/Bybit)
│   ├── indicator_engine/     # Highs/Lows Indicator
│   ├── strategy_engine/      # Order Blocks + Flag Pattern
│   ├── execution_engine/     # Order Execution
│   ├── telegram_engine/      # Notifications + Charts
│   └── monitoring_engine/    # Position Monitoring
│
├── Database.py               # MongoDB + Redis connections
└── docker-compose.yml        # Docker configuration
```

## Contracts Module (جديد)

الـ Contracts توفر interfaces موحدة للتواصل بين الوحدات بطريقة FP:

### Types (TypedDict)

```python
from contracts import CandleDTO, TradeSignalDTO, OrderDTO, HighLowDTO

# استخدام الأنواع
candle: CandleDTO = {
    "symbol": "BTCUSDT",
    "open_time": datetime.now(),
    "open": 50000.0,
    "high": 50100.0,
    "low": 49900.0,
    "close": 50050.0
}
```

### Channels

```python
from contracts import candle_close_channel, hl_updated_channel, trade_signal_channel

# بدلاً من f-strings مباشرة
channel = candle_close_channel("BTCUSDT")  # -> "BTCUSDT_Close_Candle"
```

### Serializers

```python
from contracts import serialize, deserialize, to_signal

json_str = serialize(data)
signal = to_signal(deserialize(json_str))
```

## التقنيات المستخدمة

| Technology | Usage |
|------------|-------|
| **Rust** | WebSocket data feed |
| **Python 3.12** | Business logic |
| **MongoDB** | Data persistence |
| **Redis** | Pub/Sub + Caching |
| **Docker** | Containerization |
| **Telegram API** | Notifications |

## التثبيت والتشغيل

### 1. تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

### 2. إعداد متغيرات البيئة

```bash
cp .env.example .env
nano .env
```

### 3. تشغيل النظام

```bash
# تشغيل جميع الخدمات
docker-compose up -d

# مراقبة السجلات
docker-compose logs -f
```

## الوحدات (Modules)

### Data Feed (Rust)
- استقبال الشموع من Binance/Bybit WebSocket
- تخزين في MongoDB
- نشر أحداث `{symbol}_Close_Candle`

### Indicator Engine
- **Highs/Lows**: اكتشاف نقاط الـ High و Low
- نشر أحداث `{symbol}_HL_Updated`

### Strategy Engine
- **Order Blocks**: اكتشاف مناطق الدعم والمقاومة
- **Flag Pattern**: اكتشاف نمط العلم
- نشر إشارات التداول

### Execution Engine
- تنفيذ الأوامر على البورصة
- إدارة المخاطر
- حساب TP/SL

### Telegram Engine
- إرسال تنبيهات
- رسوم بيانية تلقائية

## الأمان

⚠️ **تحذير**: تأكد من إعداد المفاتيح في ملف `.env` وعدم مشاركتها.

## الترخيص

هذا المشروع مخصص للاستخدام التعليمي.
