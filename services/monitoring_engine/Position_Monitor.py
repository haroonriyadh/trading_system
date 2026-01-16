import asyncio
import datetime
import json
import time
from types import NoneType
import numpy as np
from telegram_bot import send_telegram_message
import traceback
from shared.database import (
    db_Orders,
    init_redis,
    json_deserialize,
    json_serialize
)


async def worker_wrapper(fn):
    while True:
        try:
           await fn()
        except Exception as e:
            print(traceback.format_exc())
            asyncio.sleep(5)

async def main():
    await asyncio.create_task(
        worker_wrapper(
        # Do Anything
        )
    )


if __name__ == "__main__":
    asyncio.run(main())