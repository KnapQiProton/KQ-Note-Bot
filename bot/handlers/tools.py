import json
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from sqlalchemy import select
from bot.database.session import async_session
from bot.database.models import Expense, Budget
from bot.utils.parser import parse_expense_text, get_current_time
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
        "• `/list` : Lihat 10 riwayat transaksi terakhir beserta ID\n"
        "• `/hapus <ID>` : Hapus transaksi tertentu (misal: `/hapus 5`)\n"
        "• `/undo` : Batalkan transaksi paling terakhir\n"
        "• `/hari_ini` : Rekap pengeluaran hari ini\n"
        "• `/bulan_ini` : Rekap pengeluaran bulan ini\n"
        "• `/split <nominal> <orang>` : Hitung bagi tagihan\n"
        "• `/budget <nominal>` : Pasang batas pengeluaran bulanan\n"
        "• `/backup` : Download file backup database (.json)\n"
        "• `/restore` : Pulihkan database dari file backup\n"
        "• `/export` : Download laporan dalam format .csv"
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

@router.message(Command("backup"))
async def handle_backup(message: Message):
    async with async_session() as session:
        # Ambil semua data transaksi pengguna
        exp_stmt = (
            select(Expense)
            .where(Expense.user_id == message.from_user.id)
            .order_by(Expense.date.asc())
        )
        expenses = (await session.execute(exp_stmt)).scalars().all()

        # Ambil data budget
        budget_stmt = select(Budget).where(Budget.user_id == message.from_user.id)
        budget = (await session.execute(budget_stmt)).scalar_one_or_none()

    now = get_current_time()
    backup_payload = {
        "version": "1.0",
        "user_id": message.from_user.id,
        "backup_at": now.isoformat(),
        "budget": {
            "monthly_limit": float(budget.monthly_limit) if budget else 0.0
        },
        "expenses": [
            {
                "id": exp.id,
                "amount": float(exp.amount),
                "description": exp.description,
                "category": exp.category,
                "tag": exp.tag,
                "date": exp.date.isoformat(),
                "is_confirmed": exp.is_confirmed,
                "is_deleted": exp.is_deleted,
                "created_at": exp.created_at.isoformat()
            }
            for exp in expenses
        ]
    }

    json_str = json.dumps(backup_payload, indent=2, ensure_ascii=False)
    file_bytes = json_str.encode("utf-8")
    time_str = now.strftime("%Y%m%d_%H%M%S")
    file_doc = BufferedInputFile(
        file=file_bytes,
        filename=f"backup_kq_note_{time_str}.json"
    )

    caption = (
        f"📦 *File Backup Database Kamu* ૮ ˶ᵔ ᵕ ᵔ˶ ა\n\n"
        f"• Total transaksi: *{len(expenses)} data*\n"
        f"• Budget bulanan: *{format_rupiah(backup_payload['budget']['monthly_limit'])}*\n"
        f"• Waktu backup: `{time_str}`\n\n"
        f"💡 *Cara Restore:*\n"
        f"Jika sewaktu-waktu data hilang / database reset, cukup kirim/reply file ini dengan caption `/restore`!"
    )
    await message.reply_document(document=file_doc, caption=caption, parse_mode="Markdown")

@router.message(Command("restore"))
@router.message(F.document)
async def handle_restore(message: Message, bot: Bot):
    # Cek apakah command /restore disertai file, atau me-reply file backup
    doc = message.document
    if not doc and message.reply_to_message and message.reply_to_message.document:
        doc = message.reply_to_message.document

    if not doc or not (doc.file_name or "").endswith(".json"):
        if message.text and message.text.startswith("/restore"):
            await message.reply(
                "Kirim atau reply file backup (`.json`) dengan teks `/restore` ya kak! ૮ ˶- ﻌ -˶ ა",
                parse_mode="Markdown"
            )
        return

    # Download file backup dari Telegram
    import io
    file_buffer = io.BytesIO()
    await bot.download(doc, destination=file_buffer)
    file_buffer.seek(0)

    try:
        raw_text = file_buffer.read().decode("utf-8")
        backup_data = json.loads(raw_text)
        expenses_list = backup_data.get("expenses", [])
        budget_data = backup_data.get("budget", {})
    except Exception:
        await message.reply("Format file backup tidak valid atau rusak kak (๑> <๑)")
        return

    async with async_session() as session:
        # Restore budget
        monthly_limit = budget_data.get("monthly_limit", 0.0)
        if monthly_limit > 0:
            user_budget = await session.get(Budget, message.from_user.id)
            if not user_budget:
                user_budget = Budget(user_id=message.from_user.id, monthly_limit=monthly_limit)
                session.add(user_budget)
            else:
                user_budget.monthly_limit = monthly_limit

        # Restore transaksi
        restored_count = 0
        for item in expenses_list:
            try:
                date_val = datetime.fromisoformat(item["date"])
            except Exception:
                date_val = get_current_time()

            new_expense = Expense(
                user_id=message.from_user.id,
                amount=item.get("amount", 0.0),
                description=item.get("description", "Restored"),
                category=item.get("category"),
                tag=item.get("tag"),
                date=date_val,
                is_confirmed=item.get("is_confirmed", True),
                is_deleted=item.get("is_deleted", False)
            )
            session.add(new_expense)
            restored_count += 1

        await session.commit()

    await message.reply(
        f"Yeay! Database berhasil dipulihkan! ૮ ˶ᵔ ᵕ ᵔ˶ ა\n\n"
        f"✅ *{restored_count} data transaksi* berhasil di-restore ke PostgreSQL!\n"
        f"Ketik `/list` atau `/bulan_ini` untuk mengeceknya yaa (｡•̀ᴗ-)✧",
        parse_mode="Markdown"
    )

