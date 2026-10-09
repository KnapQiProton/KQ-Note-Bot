from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.database.session import async_session
from bot.database.models import Budget
from bot.utils.parser import parse_expense_text
from bot.utils.formatters import format_rupiah
from bot.keyboards.inline import get_split_bill_keyboard

router = Router()

@router.message(Command("start"))
@router.message(Command("help"))
async def handle_start(message: Message):
    text = (
        "Hai kak! ૮ ˶ᵔ ᵕ ᵔ˶ ა Aku bot pencatat keuangan pribadimu.\n\n"
        "✨ *Cara pakai gampang banget:*\n"
        "Tulis aja pengeluaranmu secara santai, contoh:\n"
        "• `25000 kopi kampus`\n"
        "• `kemarin 50rb bensin #perjalanan`\n"
        "• `1.5jt sewa kosan`\n"
        "• `print materi 15.000 #kuliah`\n\n"
        "🛠 *Command yang tersedia:*\n"
        "• `/hari_ini` : Rekap pengeluaran hari ini\n"
        "• `/bulan_ini` : Rekap pengeluaran bulan ini\n"
        "• `/undo` : Batalkan catatan terakhir\n"
        "• `/split <nominal> <orang>` : Hitung bagi tagihan\n"
        "• `/budget <nominal>` : Pasang batas pengeluaran bulanan\n"
        "• `/export` : Download laporan dalam bentuk file .csv"
    )
    await message.reply(text, parse_mode="Markdown")

@router.message(Command("split"))
async def handle_split_bill(message: Message):
    args = message.text.split()[1:]
    if len(args) < 2:
        await message.reply(
            "Formatnya gini ya kak: `/split <nominal> <jumlah orang>`\n"
            "Contoh: `/split 100000 4` atau `/split 100k 4` ૮ ˶- ﻌ -˶ ა",
            parse_mode="Markdown"
        )
        return

    parsed = parse_expense_text(args[0])
    try:
        nominal = parsed["amount"] if parsed else float(args[0])
        people = int(args[1])
        if people <= 0:
            raise ValueError
    except ValueError:
        await message.reply("Nominal atau jumlah orangnya gak valid nih kak (๑> <๑)")
        return

    per_person = nominal / people
    text = (
        f"🍕 *Hasil Split Bill* (づ ᴗ _ᴗ)づ♡\n\n"
        f"💵 Total: *{format_rupiah(nominal)}*\n"
        f"👥 Jumlah orang: *{people} orang*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👉 *Masing-masing bayar:* *{format_rupiah(per_person)}*\n\n"
        f"Mau langsung mencatat bagianmu ke pengeluaran?"
    )
    await message.reply(
        text,
        reply_markup=get_split_bill_keyboard(per_person),
        parse_mode="Markdown"
    )

@router.message(Command("budget"))
async def handle_set_budget(message: Message):
    args = message.text.split()[1:]
    if not args:
        await message.reply(
            "Ketik `/budget <nominal>` ya kak, misal: `/budget 2000000` atau `/budget 2jt` ૮ ˶ᵔ ᵕ ᵔ˶ ა",
            parse_mode="Markdown"
        )
        return

    parsed = parse_expense_text(args[0])
    amount = parsed["amount"] if parsed else None
    if not amount or amount <= 0:
        await message.reply("Nominal budget-nya gak kebaca atau kurang dari 0 nih kak (๑> <๑)")
        return

    async with async_session() as session:
        budget = await session.get(Budget, message.from_user.id)
        if not budget:
            budget = Budget(user_id=message.from_user.id, monthly_limit=amount)
            session.add(budget)
        else:
            budget.monthly_limit = amount
        await session.commit()

    await message.reply(
        f"Sip! Budget bulanan kamu berhasil diset ke *{format_rupiah(amount)}* (｡•̀ᴗ-)✧\n"
        f"Nanti aku ingatkan kalau pengeluaranmu udah mendekati batas yaa!",
        parse_mode="Markdown"
    )
