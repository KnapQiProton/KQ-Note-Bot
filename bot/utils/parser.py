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

def detect_category(text: str) -> str | None:
    """Mendeteksi kategori yang sesuai berdasarkan kata kunci di deskripsi teks."""
    text_lower = text.lower()

    # 1. Minuman (Prioritas untuk kata kunci minuman spesifik)
    minuman_patterns = [
        r"\bkopi\s*susu\b", r"\bkopi\b", r"\bteh\b", r"\bjus\b", r"\bsusu\b",
        r"\bes\b", r"\bminuman\b", r"\bboba\b", r"\blatte\b", r"\bcappuccino\b",
        r"\bmatcha\b", r"\bamericano\b", r"\bespresso\b", r"\bsirup\b",
        r"\bair\s*mineral\b", r"\baqua\b"
    ]
    for pat in minuman_patterns:
        if re.search(pat, text_lower):
            return "Minuman"

    # 2. Transportasi / Perjalanan
    transport_patterns = [
        r"\bbensin\b", r"\bpertalite\b", r"\bpertamax\b", r"\bsolar\b",
        r"\bojol\b", r"\bgojek\b", r"\bgrab\b", r"\bmaxim\b", r"\bparkir\b",
        r"\btol\b", r"\btiket\b", r"\bkereta\b", r"\bkrl\b", r"\bmrt\b",
        r"\bbusway\b", r"\bangkot\b", r"\btransport(?:asi)?\b", r"\bperjalanan\b"
    ]
    for pat in transport_patterns:
        if re.search(pat, text_lower):
            return "Transport"

    # 3. Makan
    makan_patterns = [
        r"\bmakan(?:an)?\b", r"\bnasi\b", r"\bmie\b", r"\bbakso\b", r"\bayam\b",
        r"\bsoto\b", r"\broti\b", r"\bsnack\b", r"\bcamilan\b", r"\bgorengan\b",
        r"\bmartabak\b", r"\bpecel\b", r"\bbubur\b", r"\bsate\b"
    ]
    for pat in makan_patterns:
        if re.search(pat, text_lower):
            return "Makan"

    # 4. Tagihan
    tagihan_patterns = [
        r"\blistrik\b", r"\bpln\b", r"\bpdam\b", r"\bpulsa\b", r"\bkuota\b",
        r"\btoken\b", r"\bwifi\b", r"\bindi(?:home)?\b", r"\bsewa\b",
        r"\bkos(?:an)?\b", r"\bcicilan\b", r"\btagihan\b"
    ]
    for pat in tagihan_patterns:
        if re.search(pat, text_lower):
            return "Tagihan"

    # 5. Belanja
    belanja_patterns = [
        r"\bbelanja\b", r"\bbeli\b", r"\bminimarket\b", r"\bindomaret\b",
        r"\balfamart\b", r"\bsupermarket\b", r"\bpakaian\b", r"\bbaju\b", r"\bsepatu\b"
    ]
    for pat in belanja_patterns:
        if re.search(pat, text_lower):
            return "Belanja"

    # 6. Hiburan
    hiburan_patterns = [
        r"\bnonton\b", r"\bbioskop\b", r"\bgame\b", r"\bsteam\b", r"\btopup\b",
        r"\blangganan\b", r"\bspotify\b", r"\bnetflix\b", r"\byoutube\b", r"\bhiburan\b"
    ]
    for pat in hiburan_patterns:
        if re.search(pat, text_lower):
            return "Hiburan"

    # 7. Kesehatan
    kesehatan_patterns = [
        r"\bobat\b", r"\bapotek\b", r"\bdokter\b", r"\bklinik\b",
        r"\brumah\s*sakit\b", r"\bvitamin\b", r"\bmedis\b", r"\bkesehatan\b"
    ]
    for pat in kesehatan_patterns:
        if re.search(pat, text_lower):
            return "Kesehatan"

    # 8. Edukasi
    edukasi_patterns = [
        r"\bbuku\b", r"\bkuliah\b", r"\bspp\b", r"\bkursus\b", r"\bseminar\b",
        r"\bujian\b", r"\bprint\b", r"\bfotokopi\b", r"\bedukasi\b", r"\bsekolah\b"
    ]
    for pat in edukasi_patterns:
        if re.search(pat, text_lower):
            return "Edukasi"

    return None

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

    # Deteksi kategori yang disarankan otomatis berdasarkan deskripsi dan tag
    suggested_category = detect_category(desc)
    if not suggested_category and primary_tag:
        suggested_category = detect_category(primary_tag)

    return {
        "amount": best_val,
        "description": desc,
        "tag": primary_tag,
        "date": target_date,
        "suggested_category": suggested_category
    }
