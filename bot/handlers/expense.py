from datetime import datetime
from zoneinfo import ZoneInfo
from calendar import monthrange
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, desc, func
from bot.config import settings
from bot.database.session import async_session
from bot.database.models import Expense, Budget
from bot.utils.parser import parse_expense_text, get_current_time
from bot.utils.formatters import format_rupiah
from bot.keyboards.inline import get_category_keyboard

router = Router()

async def check_budget_alert(user_id: int, session) -> str | None:
    """Mengecek apakah pengeluaran bulan ini sudah mendekati atau melebihi limit."""
    now = get_current_time()
    _, last_day = monthrange(now.year, now.month)
    tz = now.tzinfo
    start_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=tz)
    end_of_month = datetime(now.year, now.month, last_day, 23, 59, 59, 999999, tzinfo=tz)

    budget_res = await session.execute(select(Budget).where(Budget.user_id == user_id))
    budget_row = budget_res.scalar_one_or_none()

    if not budget_row or float(budget_row.monthly_limit) <= 0:
        return None

    monthly_limit = float(budget_row.monthly_limit)

    total_res = await session.execute(
        select(func.sum(Expense.amount)).where(
            Expense.user_id == user_id,
            Expense.is_confirmed == True,
            Expense.is_deleted == False,
            Expense.date >= start_of_month,
            Expense.date <= end_of_month
        )
    )
    total_spent = float(total_res.scalar() or 0.0)
    percent = (total_spent / monthly_limit) * 100

    if percent >= 100:
        return (
            f"\n\n🚨 *WARNING (;;・_・)*: Pengeluaran bulan ini sudah *{percent:.1f}%* "
            f"({format_rupiah(total_spent)} dari limit {format_rupiah(monthly_limit)})! "
            f"Yuk ngerem dikit jajanannya kak~ ૮ ˶- ﻌ -˶ ა"
        )
    elif percent >= 80:
        return (
            f"\n\n⚠️ *Peringatan (๑> <๑)*: Pengeluaran bulan ini sudah *{percent:.1f}%* "
            f"({format_rupiah(total_spent)} dari limit {format_rupiah(monthly_limit)}). Hati-hati yaa!"
        )
    return None

@router.message(F.text & ~F.text.startswith("/"))
async def handle_natural_input(message: Message):
    parsed = parse_expense_text(message.text)
    if not parsed:
        return

    now = get_current_time()
    async with async_session() as session:
        expense = Expense(
            user_id=message.from_user.id,
            amount=parsed["amount"],
            description=parsed["description"],
            tag=parsed["tag"],
            date=parsed["date"],
            is_confirmed=False
        )
        session.add(expense)
        await session.commit()
        await session.refresh(expense)

    tag_str = f" `#{parsed['tag']}`" if parsed["tag"] else ""
    date_str = " _(catatan kemarin)_" if parsed["date"].date() < now.date() else ""

    text = (
        f"Nyuu~ ૮ ˶ᵔ ᵕ ᵔ˶ ა Mau catat pengeluaran:\n"
        f"💵 *{format_rupiah(parsed['amount'])}*\n"
        f"📝 *{parsed['description']}*{tag_str}{date_str}\n\n"
        f"Pilih kategorinya di bawah yaa! (๑> <๑)"
    )
    await message.reply(text, reply_markup=get_category_keyboard(expense.id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("cat:"))
async def handle_category_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    expense_id = int(parts[1])
    cat_code = parts[2]

    async with async_session() as session:
        expense = await session.get(Expense, expense_id)
        if not expense or expense.user_id != callback.from_user.id:
            await callback.answer("Entri ini tidak valid atau bukan milikmu ૮(˶ㅠ-ㅠ˶)ა", show_alert=True)
            return

        expense.category = cat_code.capitalize()
        expense.is_confirmed = True
        await session.commit()

        alert_msg = await check_budget_alert(callback.from_user.id, session)

    alert_text = alert_msg or ""
    tag_info = f" #{expense.tag}" if expense.tag else ""
    await callback.message.edit_text(
        f"Yeay! Berhasil dicatat (｡•̀ᴗ-)✧\n"
        f"📌 *Kategori:* {expense.category}\n"
        f"💰 *Nominal:* {format_rupiah(expense.amount)}\n"
        f"📝 *Catatan:* {expense.description}{tag_info}"
        f"{alert_text}",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cancel:"))
async def handle_cancel_callback(callback: CallbackQuery):
    expense_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        expense = await session.get(Expense, expense_id)
        if expense and expense.user_id == callback.from_user.id:
            await session.delete(expense)
            await session.commit()
    await callback.message.edit_text("Pencatatan dibatalkan yaa ૮ ˶- ﻌ -˶ ა")
    await callback.answer()

@router.callback_query(F.data.startswith("split_rec:"))
async def handle_split_record_callback(callback: CallbackQuery):
    amount_val = float(callback.data.split(":")[1])
    now = get_current_time()

    async with async_session() as session:
        expense = Expense(
            user_id=callback.from_user.id,
            amount=amount_val,
            description="Bagian Split Bill",
            tag="split_bill",
            date=now,
            is_confirmed=False
        )
        session.add(expense)
        await session.commit()
        await session.refresh(expense)

    await callback.message.reply(
        f"Yuk pilih kategori untuk bagianmu *{format_rupiah(amount_val)}* (づ ᴗ _ᴗ)づ♡",
        reply_markup=get_category_keyboard(expense.id),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(F.text == "/undo")
async def handle_undo(message: Message):
    async with async_session() as session:
        stmt = (
            select(Expense)
            .where(
                Expense.user_id == message.from_user.id,
                Expense.is_confirmed == True,
                Expense.is_deleted == False
            )
            .order_by(desc(Expense.created_at))
            .limit(1)
        )
        res = await session.execute(stmt)
        last_expense = res.scalar_one_or_none()

        if not last_expense:
            await message.reply("Belum ada transaksi terakhir yang bisa dibatalkan kak ૮₍ ˶•⤙•˶ ₎ა")
            return

        last_expense.is_deleted = True
        await session.commit()

    await message.reply(
        f"Sip! Catatan terakhir berhasil di-undo (づ ᴗ _ᴗ)づ♡\n"
        f"❌ Dihapus: *{format_rupiah(last_expense.amount)}* ({last_expense.description})",
        parse_mode="Markdown"
    )
