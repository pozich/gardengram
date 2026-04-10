# bot/main.py
import asyncio
import logging
import sys
import os
import httpx

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, MenuButtonWebApp, WebAppInfo

TOKEN = os.getenv('BOT_TOKEN')
WEB_APP_URL = os.getenv('BASE_DOMAIN')

dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: Message):
        user = response.json()
        role = user.get("role", "CLIENT")
        text = (
            f"🥗 {html.bold('Добро пожаловать в Foodgram!')}\n\n"
            f"Привет, {html.bold(html.quote(message.from_user.full_name))}!\n\n"
            f"{ROLE_LINES.get(role, '')}\n\n"
            f"Нажми {html.bold('Open')} чтобы открыть приложение."
        )
    except Exception as e:
        logging.error(f"Sync error: {e}")
        text = "❌ Foodgram временно недоступен."

    await message.answer(text)

@dp.message()
async def help_handler(message: Message):
    await message.answer(
        f"{html.bold('Как пользоваться:')}\n\n"
        f"1. Нажмите {html.bold('Open')} внизу слева.\n"
        f"2. Выберите заведение на карте.\n"
        f"3. Забронируйте товар и заберите его вовремя!"
    )

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    await set_main_menu(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")

