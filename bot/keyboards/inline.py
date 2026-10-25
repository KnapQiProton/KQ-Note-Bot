from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils.formatters import format_rupiah

CATEGORIES = [
    ("🍔 Makan", "makan"),
    ("🧋 Minuman", "minuman"),
    ("🛵 Transport", "transport"),
    ("🛒 Belanja", "belanja"),
    ("💡 Tagihan", "tagihan"),
    ("🎮 Hiburan", "hiburan"),
    ("💊 Kesehatan", "kesehatan"),
    ("📚 Edukasi", "edukasi"),
    ("✨ Lainnya", "lainnya")
]

def get_category_keyboard(expense_id: int, suggested: str | None = None) -> InlineKeyboardMarkup:
    """Membuat inline keyboard untuk memilih kategori pengeluaran."""
    buttons = []
    
    # Jika ada kategori yang disarankan otomatis oleh parser, tampilkan tombol cepat di atas
    if suggested:
        matched_label = None
        matched_code = None
        for label, code in CATEGORIES:
            if code.lower() == suggested.lower() or label.lower().endswith(suggested.lower()):
                matched_label = label
                matched_code = code
                break
        if matched_label and matched_code:
            buttons.append([
                InlineKeyboardButton(
                    text=f"✨ Rekomendasi: {matched_label} ✨",
                    callback_data=f"cat:{expense_id}:{matched_code}"
                )
            ])

    row = []
    for label, code in CATEGORIES:
        display_text = f"⭐ {label}" if suggested and (code.lower() == suggested.lower() or label.lower().endswith(suggested.lower())) else label
        row.append(InlineKeyboardButton(text=display_text, callback_data=f"cat:{expense_id}:{code}"))
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
