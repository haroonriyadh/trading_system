#Trading System Design
```mermaid
graph TD
    Websocket_Candle
    Websocket_Candle --> Mongodb_Candle
    Websocket_Candle --> Redis
    
    Stratery_Engine
    Mongodb_Candle --> Stratery_Engine
    

