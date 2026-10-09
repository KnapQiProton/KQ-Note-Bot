import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from bot.config import settings
from bot.database.session import init_db
from bot.handlers import expense, reports, tools

# Konfigurasi Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ExpenseBot")

async def main():
    if not settings.BOT_TOKEN:
        logger.error(
            "BOT_TOKEN belum diisi! Silakan buat file .env atau isi environment variable BOT_TOKEN."
        )
        sys.exit(1)

    logger.info("Menghubungkan ke database...")
    await init_db()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Mendaftarkan seluruh router handler
    dp.include_router(tools.router)
    dp.include_router(reports.router)
    dp.include_router(expense.router)

    logger.info("Bot Telegram siap berjalan! ૮ ˶ᵔ ᵕ ᵔ˶ ა")

    # Bersihkan webhook / pending updates sebelumnya
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot dimatikan secara aman. Sampai jumpa! (づ ᴗ _ᴗ)づ♡")
