import asyncio
import logging

from aiogram import Bot, Dispatcher

from .bot import r
from .config import BOT_TOKEN
from .db import init_db
from .poller import poll_orders

logging.basicConfig(level=logging.INFO)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    await init_db()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(r)

    try:
        await asyncio.gather(
            dp.start_polling(bot),
            poll_orders(bot),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
