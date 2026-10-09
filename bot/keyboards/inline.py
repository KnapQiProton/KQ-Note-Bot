from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils.formatters import format_rupiah

CATEGORIES = [
    ("🍔 Makan", "makan"),
    ("🛵 Transport", "transport"),
    ("🛒 Belanja", "belanja"),
    ("💡 Tagihan", "tagihan"),
    ("🎮 Hiburan", "hiburan"),
    ("💊 Kesehatan", "kesehatan"),
    ("📚 Edukasi", "edukasi"),
    ("✨ Lainnya", "lainnya")
]

def get_category_keyboard(expense_id: int) -> InlineKeyboardMarkup:
    """Membuat inline keyboard untuk memilih kategori pengeluaran."""
    buttons = []
    row = []
    for label, code in CATEGORIES:
        row.append(InlineKeyboardButton(text=label, callback_data=f"cat:{expense_id}:{code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Tombol pembatalan
    buttons.append([InlineKeyboardButton(text="❌ Batalkan", callback_data=f"cancel:{expense_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_split_bill_keyboard(amount_per_person: float) -> InlineKeyboardMarkup:
    """Keyboard cepat untuk langsung mencatat bagian split bill."""
    rounded_val = int(round(amount_per_person))
    button = InlineKeyboardButton(
        text=f"📝 Catat Bagianku ({format_rupiah(rounded_val)})",
        callback_data=f"split_rec:{rounded_val}"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])
