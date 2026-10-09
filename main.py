import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from bot.config import settings
from bot.database.session import init_db
from bot.handlers import expense, reports, tools

# Konfigurasi Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ExpenseBot")

async def setup_bot_commands(bot: Bot):
    """Mendaftarkan menu tombol slash command ke Telegram."""
    commands = [
        BotCommand(command="start", description="Panduan & cara pakai bot"),
        BotCommand(command="list", description="Daftar 10 transaksi terakhir"),
        BotCommand(command="hari_ini", description="Rekap pengeluaran hari ini"),
        BotCommand(command="bulan_ini", description="Rekap pengeluaran bulan ini"),
        BotCommand(command="undo", description="Batalkan transaksi terakhir"),
        BotCommand(command="hapus", description="Hapus transaksi (/hapus <ID>)"),
        BotCommand(command="split", description="Bagi tagihan (/split <nominal> <orang>)"),
        BotCommand(command="budget", description="Set limit budget bulanan"),
        BotCommand(command="export", description="Download data dalam format .csv"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Menu tombol command berhasil didaftarkan ke Telegram! (｡•̀ᴗ-)✧")

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

    # Daftarkan menu command ke tombol Menu Telegram
    await setup_bot_commands(bot)

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
