import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from bot.config import settings

REGEX_TAG = r"#(\w+)"
REGEX_AMOUNT = r"(?i)\b(rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(k|rb|ribu|jt|juta)?\b"

def get_current_time() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(settings.TIMEZONE)
        return datetime.now(tz)
    except Exception:
        # Fallback WIB (UTC+7) jika tzdata belum terpasang di Windows
        tz = timezone(timedelta(hours=7))
        return datetime.now(tz)

def parse_expense_text(text: str) -> dict | None:
    """
    Mem-parse input teks natural menjadi dict:
    {
        'amount': float,
        'description': str,
        'tag': str | None,
        'date': datetime
    }
    """
    if not text:
        return None

    now = get_current_time()
    target_date = now

    # 1. Parse Waktu ("kemarin")
    cleaned_text = text
    if re.search(r"\bkemarin\b", cleaned_text, re.IGNORECASE):
        target_date = now - timedelta(days=1)
        cleaned_text = re.sub(r"\bkemarin\b", "", cleaned_text, flags=re.IGNORECASE).strip()

    # 2. Parse Tagar (#tag)
    tags = re.findall(REGEX_TAG, cleaned_text)
    primary_tag = tags[0] if tags else None
    cleaned_text = re.sub(REGEX_TAG, "", cleaned_text).strip()

    # 3. Temukan seluruh kandidat angka
    candidates = []
    for match in re.finditer(REGEX_AMOUNT, cleaned_text):
        has_rp = bool(match.group(1))
        num_str = match.group(2)
        multiplier_str = (match.group(3) or "").lower()

        multiplier = 1
        if multiplier_str in ["k", "rb", "ribu"]:
            multiplier = 1_000
        elif multiplier_str in ["jt", "juta"]:
            multiplier = 1_000_000

        try:
            if multiplier > 1:
                clean_num = num_str.replace(",", ".")
                val = float(clean_num) * multiplier
            else:
                if "." in num_str or "," in num_str:
                    clean_num = num_str.replace(".", "").replace(",", "")
                else:
                    clean_num = num_str
                val = float(clean_num)
        except ValueError:
            continue

        if val <= 0:
            continue

        # Scoring prioritas kandidat angka
        score = 0.0
        if has_rp:
            score += 100.0
        if multiplier > 1:
            score += 50.0
        if val >= 500:
            score += 20.0
        score += min(val / 10000.0, 10.0)

        candidates.append((score, val, match))

    if not candidates:
        return None

    # Pilih kandidat dengan bobot tertinggi
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, best_val, best_match = candidates[0]

    # Deskripsi adalah teks sisa setelah angka dibuang
    desc = cleaned_text[:best_match.start()] + " " + cleaned_text[best_match.end():]
    desc = " ".join(desc.split()).strip()
    if not desc:
        desc = "Pengeluaran tanpa catatan"

    return {
        "amount": best_val,
        "description": desc,
        "tag": primary_tag,
        "date": target_date
    }
