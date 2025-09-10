#Trading System Design
```mermaid
flowchart TD
    A[Websocket_Candle] --> B[Chaching]
    A[Websocket_Candle] --> C[Mongodb]
    C --> D[Strategy_Engine]
    D --> C
    C --> F[Open_trade]
    B --> F
