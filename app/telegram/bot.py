import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import get_settings
from app.telegram.handlers import router


async def main():
    settings = get_settings()

    proxy_url = settings.telegram_proxy_url

    bot_kwargs = {"token": settings.telegram_bot_token}
    if proxy_url:
        session = AiohttpSession(proxy=proxy_url)
        bot_kwargs["session"] = session

    bot = Bot(**bot_kwargs)
    dp = Dispatcher()

    dp.include_router(router)

    if proxy_url:
        print(f"[Proxy] {proxy_url}")
    else:
        print("[!] Proxy not set — direct connection")

    print("[Bot] Job Sniffer started. Waiting for messages...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
