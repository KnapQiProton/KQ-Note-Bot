def format_rupiah(amount: float | int) -> str:
    """Format angka menjadi representasi Rupiah, contoh: Rp25.000"""
    try:
        val = float(amount)
        return f"Rp{val:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return f"Rp{amount}"
