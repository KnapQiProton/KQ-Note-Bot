import asyncio
import logging
import sys
import os
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from bot.config import settings
from bot.database.session import init_db
from bot.handlers import expense, reports, tools
from bot.web.app import app as web_app

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
        BotCommand(command="web", description="Buka Web Dashboard visual 📊"),
        BotCommand(command="list", description="Daftar 10 transaksi terakhir"),
        BotCommand(command="hari_ini", description="Rekap pengeluaran hari ini"),
        BotCommand(command="bulan_ini", description="Rekap pengeluaran bulan ini"),
        BotCommand(command="undo", description="Batalkan transaksi terakhir"),
        BotCommand(command="hapus", description="Hapus transaksi (/hapus <ID>)"),
        BotCommand(command="split", description="Bagi tagihan (/split <nominal> <orang>)"),
        BotCommand(command="budget", description="Set limit budget bulanan"),
        BotCommand(command="backup", description="Download file backup database (.json)"),
        BotCommand(command="restore", description="Restore data dari file backup"),
        BotCommand(command="export", description="Download data dalam format .csv"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Menu tombol command berhasil didaftarkan ke Telegram! (｡•̀ᴗ-)✧")
    except Exception as e:
        logger.warning(f"Gagal mendaftarkan menu commands: {e}")

async def run_bot(bot: Bot, dp: Dispatcher):
    """Menjalankan bot polling dengan auto-retry jika ada conflict saat rolling deploy."""
    while True:
        try:
            logger.info("🤖 Memulai polling Telegram bot...")
            await bot.delete_webhook(drop_pending_updates=True)
            # handle_signals=False agar tidak bentrok dengan Uvicorn
            await dp.start_polling(bot, handle_signals=False)
            break
        except Exception as e:
            logger.warning(f"Polling terinterupsi ({e}). Mencoba kembali dalam 3 detik...")
            await asyncio.sleep(3)

async def run_web(server: uvicorn.Server):
    """Menjalankan Uvicorn web server."""
    try:
        await server.serve()
    except Exception as e:
        logger.error(f"Error pada web server: {e}")

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

    # Konfigurasi Web Dashboard Server (FastAPI)
    port = int(os.getenv("PORT", str(settings.PORT)))
    web_config = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(web_config)

    logger.info(f"🌐 Web Dashboard berjalan di port {port}!")
    logger.info(f"🤖 Bot Telegram polling aktif! ૮ ˶ᵔ ᵕ ᵔ˶ ა")

    try:
        # Jalankan Web Server dan Bot Telegram secara bersamaan
        await asyncio.gather(
            run_web(server),
            run_bot(bot, dp)
        )
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Aplikasi dimatikan secara aman. Sampai jumpa! (づ ᴗ _ᴗ)づ♡")
