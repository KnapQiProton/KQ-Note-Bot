import io
import csv
from datetime import datetime
from calendar import monthrange
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from sqlalchemy import select, func, desc
from bot.database.session import async_session
from bot.database.models import Expense
from bot.utils.formatters import format_rupiah
from bot.utils.parser import get_current_time

router = Router()

@router.message(Command("list", "riwayat"))
async def handle_list_expenses(message: Message):
    async with async_session() as session:
        stmt = (
            select(Expense)
            .where(
                Expense.user_id == message.from_user.id,
                Expense.is_confirmed == True,
                Expense.is_deleted == False
            )
            .order_by(desc(Expense.date), desc(Expense.id))
            .limit(10)
        )
        expenses = (await session.execute(stmt)).scalars().all()

    if not expenses:
        await message.reply("Belum ada catatan pengeluaran kak ૮ ˶ᵔ ᵕ ᵔ˶ ა", parse_mode="Markdown")
        return

    items_text = []
    for exp in expenses:
        date_str = exp.date.strftime("%d/%m")
        cat_str = f"[{exp.category or 'Lainnya'}]"
        tag_str = f" `#{exp.tag}`" if exp.tag else ""
        items_text.append(
            f"🆔 *#{exp.id}* • {date_str} {cat_str}\n"
            f"   💰 *{format_rupiah(exp.amount)}* - {exp.description}{tag_str}"
        )

    list_body = "\n\n".join(items_text)
    text = (
        f"📋 *10 Transaksi Terakhir Kamu* ૮ ˶ᵔ ᵕ ᵔ˶ ა\n\n"
        f"{list_body}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 _Mau hapus salah satu? Ketik_ `/hapus <ID>`, _misal:_ `/hapus {expenses[0].id}` (｡•̀ᴗ-)✧"
    )
    await message.reply(text, parse_mode="Markdown")

@router.message(Command("hari_ini"))
async def handle_report_today(message: Message):
    now = get_current_time()
    tz = now.tzinfo
    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=tz)
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59, 999999, tzinfo=tz)

    async with async_session() as session:
        stmt = (
            select(Expense.category, func.sum(Expense.amount))
            .where(
                Expense.user_id == message.from_user.id,
                Expense.is_confirmed == True,
                Expense.is_deleted == False,
                Expense.date >= start_of_day,
                Expense.date <= end_of_day
            )
            .group_by(Expense.category)
        )
        results = (await session.execute(stmt)).all()

    if not results:
        await message.reply("Belum ada pengeluaran hari ini kak! Hemat banget ૮ ˶ᵔ ᵕ ᵔ˶ ა")
        return

    total = sum(float(r[1]) for r in results)
    breakdown = "\n".join([f"• *{r[0] or 'Lainnya'}*: {format_rupiah(float(r[1]))}" for r in results])

    text = (
        f"📊 *Rekap Pengeluaran Hari Ini* ૮ ˶ᵔ ᵕ ᵔ˶ ა\n\n"
        f"{breakdown}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *Total:* *{format_rupiah(total)}*"
    )
    await message.reply(text, parse_mode="Markdown")

@router.message(Command("bulan_ini"))
async def handle_report_month(message: Message):
    now = get_current_time()
    _, last_day = monthrange(now.year, now.month)
    tz = now.tzinfo
    start_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=tz)
    end_of_month = datetime(now.year, now.month, last_day, 23, 59, 59, 999999, tzinfo=tz)

    async with async_session() as session:
        stmt = (
            select(Expense.category, func.sum(Expense.amount))
            .where(
                Expense.user_id == message.from_user.id,
                Expense.is_confirmed == True,
                Expense.is_deleted == False,
                Expense.date >= start_of_month,
                Expense.date <= end_of_month
            )
            .group_by(Expense.category)
        )
        results = (await session.execute(stmt)).all()

    if not results:
        await message.reply("Bulan ini belum ada pengeluaran yang tercatat nih (๑> <๑)")
        return

    total = sum(float(r[1]) for r in results)
    breakdown = "\n".join([f"• *{r[0] or 'Lainnya'}*: {format_rupiah(float(r[1]))}" for r in results])

    text = (
        f"📅 *Rekap Pengeluaran Bulan Ini* (づ ᴗ _ᴗ)づ♡\n\n"
        f"{breakdown}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *Total:* *{format_rupiah(total)}*"
    )
    await message.reply(text, parse_mode="Markdown")

@router.message(Command("export"))
async def handle_export_csv(message: Message):
    async with async_session() as session:
        stmt = (
            select(Expense)
            .where(
                Expense.user_id == message.from_user.id,
                Expense.is_confirmed == True,
                Expense.is_deleted == False
            )
            .order_by(Expense.date.asc())
        )
        expenses = (await session.execute(stmt)).scalars().all()

    if not expenses:
        await message.reply("Belum ada data pengeluaran buat di-export kak (๑> <๑)")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Tanggal", "Nominal", "Kategori", "Deskripsi", "Tag"])

    for exp in expenses:
        writer.writerow([
            exp.id,
            exp.date.strftime("%Y-%m-%d %H:%M:%S"),
            f"{float(exp.amount):.2f}",
            exp.category or "",
            exp.description,
            exp.tag or ""
        ])

    now = get_current_time()
    csv_bytes = output.getvalue().encode("utf-8")
    file_doc = BufferedInputFile(
        file=csv_bytes,
        filename=f"pengeluaran_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    )

    await message.reply_document(
        document=file_doc,
        caption="Ini file .csv data pengeluaran kamu yaa! ૮ ˶ᵔ ᵕ ᵔ˶ ა"
    )
