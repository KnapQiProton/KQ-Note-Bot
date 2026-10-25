import os
import io
import csv
from datetime import datetime, timedelta
from calendar import monthrange
from pydantic import BaseModel
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc
from bot.database.session import async_session
from bot.database.models import Expense, Budget
from bot.utils.parser import get_current_time

app = FastAPI(title="KQ-Note Dashboard & Management")

template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)

# Helper Kaomoji & Emoji Kategori Dinamis
CATEGORY_EMOJIS = {
    "Makan": "🍔",
    "Minuman": "🧋",
    "Transport": "🛵",
    "Belanja": "🛒",
    "Tagihan": "💡",
    "Hiburan": "🎮",
    "Kesehatan": "💊",
    "Edukasi": "📚",
    "Lainnya": "✨"
}

CATEGORY_STYLES = {
    "Makan": "bg-orange-50 dark:bg-orange-500/10 text-orange-600 dark:text-orange-400 border border-orange-100 dark:border-orange-500/20",
    "Minuman": "bg-cyan-50 dark:bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-100 dark:border-cyan-500/20",
    "Transport": "bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-500/20",
    "Belanja": "bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-100 dark:border-purple-500/20",
    "Tagihan": "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-100 dark:border-amber-500/20",
    "Hiburan": "bg-pink-50 dark:bg-pink-500/10 text-pink-600 dark:text-pink-400 border border-pink-100 dark:border-pink-500/20",
    "Kesehatan": "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-500/20",
    "Edukasi": "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-500/20",
    "Lainnya": "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
}

def get_category_display(category: str | None) -> str:
    """Mengembalikan nama kategori dengan ikon emoji yang sesuai."""
    if not category:
        return "✨ Lainnya"
    cat = category.strip().capitalize()
    emoji = CATEGORY_EMOJIS.get(cat, "🏷️")
    return f"{emoji} {cat}"

def get_badge_class(category: str | None) -> str:
    """Mengembalikan kelas CSS Tailwind untuk badge kategori secara dinamis."""
    if not category:
        return CATEGORY_STYLES["Lainnya"]
    cat = category.strip().capitalize()
    if cat in CATEGORY_STYLES:
        return CATEGORY_STYLES[cat]
    dynamic_badges = [
        "bg-teal-50 dark:bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-100 dark:border-teal-500/20",
        "bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-100 dark:border-rose-500/20",
        "bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-100 dark:border-violet-500/20",
        "bg-lime-50 dark:bg-lime-500/10 text-lime-600 dark:text-lime-400 border border-lime-100 dark:border-lime-500/20",
        "bg-fuchsia-50 dark:bg-fuchsia-500/10 text-fuchsia-600 dark:text-fuchsia-400 border border-fuchsia-100 dark:border-fuchsia-500/20",
        "bg-sky-50 dark:bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-100 dark:border-sky-500/20"
    ]
    idx = abs(hash(cat)) % len(dynamic_badges)
    return dynamic_badges[idx]

templates.env.globals["get_category_display"] = get_category_display
templates.env.globals["get_badge_class"] = get_badge_class

# Schemas untuk request body
class ExpenseCreate(BaseModel):
    amount: float
    category: str
    description: str
    tag: str | None = None
    date: str | None = None
    user_id: int | None = None

class ExpenseUpdate(BaseModel):
    amount: float
    category: str
    description: str
    tag: str | None = None
    date: str | None = None

class BudgetUpdate(BaseModel):
    monthly_limit: float
    user_id: int | None = None

async def get_active_user_id(session, user_id: int | None = None) -> int:
    """Mendapatkan user_id aktif (otomatis mendeteksi user Telegram)."""
    if user_id:
        return user_id
    res = await session.execute(select(Expense.user_id).order_by(desc(Expense.created_at)).limit(1))
    latest_uid = res.scalar_one_or_none()
    if latest_uid:
        return latest_uid
    res_b = await session.execute(select(Budget.user_id).limit(1))
    budget_uid = res_b.scalar_one_or_none()
    if budget_uid:
        return budget_uid
    return 1

@app.get("/health")
async def health_check():
    """Railway healthcheck endpoint."""
    return {"status": "ok", "timestamp": get_current_time().isoformat()}

@app.get("/api/categories")
async def get_categories():
    """Mengambil semua kategori unik (DISTINCT) langsung dari database pengeluaran."""
    async with async_session() as session:
        stmt = (
            select(func.trim(Expense.category))
            .where(
                Expense.is_deleted == False,
                Expense.category.is_not(None),
                func.trim(Expense.category) != ""
            )
            .distinct()
            .order_by(func.trim(Expense.category).asc())
        )
        res = (await session.execute(stmt)).scalars().all()
        categories = sorted(list(set(c for c in res if c)))
        if not categories:
            categories = ["Makan", "Minuman", "Transport", "Belanja", "Tagihan", "Hiburan", "Kesehatan", "Edukasi", "Lainnya"]
        return {"categories": categories}

@app.get("/api/stats")
async def get_dashboard_stats(user_id: int | None = None):
    """
    Menyediakan data statistik dinamis pengeluaran per kategori dan tren mingguan untuk Chart.js.
    Format JSON: { 'labels': [...], 'data': [...], 'categories': {...}, 'weekly': {...} }
    """
    now = get_current_time()
    tz = now.tzinfo
    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=tz)
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59, 999999, tzinfo=tz)
    _, last_day = monthrange(now.year, now.month)
    start_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=tz)
    end_of_month = datetime(now.year, now.month, last_day, 23, 59, 59, 999999, tzinfo=tz)

    async with async_session() as session:
        base_conditions = [
            Expense.is_confirmed == True,
            Expense.is_deleted == False
        ]
        if user_id:
            base_conditions.append(Expense.user_id == user_id)

        # 1. Proporsi Kategori Bulan Ini (Donut Chart)
        cat_stmt = (
            select(
                func.coalesce(func.nullif(func.trim(Expense.category), ''), 'Lainnya').label("category"),
                func.sum(Expense.amount).label("total")
            )
            .where(
                *base_conditions,
                Expense.date >= start_of_month,
                Expense.date <= end_of_month
            )
            .group_by(func.coalesce(func.nullif(func.trim(Expense.category), ''), 'Lainnya'))
            .order_by(desc(func.sum(Expense.amount)))
        )
        cat_results = (await session.execute(cat_stmt)).all()

        # Fallback jika data bulan berjalan belum ada transaksi
        if not cat_results:
            all_cat_stmt = (
                select(
                    func.coalesce(func.nullif(func.trim(Expense.category), ''), 'Lainnya').label("category"),
                    func.sum(Expense.amount).label("total")
                )
                .where(*base_conditions)
                .group_by(func.coalesce(func.nullif(func.trim(Expense.category), ''), 'Lainnya'))
                .order_by(desc(func.sum(Expense.amount)))
            )
            cat_results = (await session.execute(all_cat_stmt)).all()

        labels = [r[0] for r in cat_results]
        data = [float(r[1]) for r in cat_results]

        # 2. Tren 7 Hari Terakhir (Bar Chart)
        start_7_days = start_of_day - timedelta(days=6)
        weekly_stmt = (
            select(Expense.date, Expense.amount)
            .where(
                *base_conditions,
                Expense.date >= start_7_days,
                Expense.date <= end_of_day
            )
            .order_by(Expense.date.asc())
        )
        weekly_expenses = (await session.execute(weekly_stmt)).all()

        daily_sums = {}
        weekly_labels = []
        for i in range(7):
            day_dt = start_7_days + timedelta(days=i)
            key = day_dt.strftime("%d/%m")
            weekly_labels.append(key)
            daily_sums[key] = 0.0

        for exp_date, amount in weekly_expenses:
            date_key = exp_date.astimezone(tz).strftime("%d/%m")
            if date_key in daily_sums:
                daily_sums[date_key] += float(amount)

        weekly_data = [daily_sums[k] for k in weekly_labels]

        return {
            "status": "success",
            "labels": labels,
            "data": data,
            "categories": {
                "labels": labels,
                "data": data
            },
            "weekly": {
                "labels": weekly_labels,
                "data": weekly_data
            }
        }

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user_id: int | None = None):
    now = get_current_time()
    tz = now.tzinfo

    # Rentang Hari Ini
    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=tz)
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59, 999999, tzinfo=tz)

    # Rentang Bulan Ini
    _, last_day = monthrange(now.year, now.month)
    start_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=tz)
    end_of_month = datetime(now.year, now.month, last_day, 23, 59, 59, 999999, tzinfo=tz)

    async with async_session() as session:
        active_uid = await get_active_user_id(session, user_id)
        base_conditions = [
            Expense.is_confirmed == True,
            Expense.is_deleted == False
        ]
        if user_id:
            base_conditions.append(Expense.user_id == user_id)

        # 1. Total Bulan Ini
        month_stmt = select(func.sum(Expense.amount), func.count(Expense.id)).where(
            *base_conditions,
            Expense.date >= start_of_month,
            Expense.date <= end_of_month
        )
        month_res = (await session.execute(month_stmt)).first()
        total_month = float(month_res[0] or 0.0)
        count_month = int(month_res[1] or 0)

        # 2. Total Hari Ini
        today_stmt = select(func.sum(Expense.amount)).where(
            *base_conditions,
            Expense.date >= start_of_day,
            Expense.date <= end_of_day
        )
        total_today = float((await session.execute(today_stmt)).scalar() or 0.0)

        # 3. Budget Limit
        budget_stmt = select(Budget).where(Budget.user_id == active_uid)
        budget_row = (await session.execute(budget_stmt)).scalars().first()
        budget_limit = float(budget_row.monthly_limit) if budget_row else 0.0
        budget_percent = (total_month / budget_limit * 100) if budget_limit > 0 else 0.0

        # 4. Proporsi Kategori Bulan Ini (Donut Chart)
        cat_stmt = (
            select(
                func.coalesce(func.nullif(func.trim(Expense.category), ''), 'Lainnya').label("category"),
                func.sum(Expense.amount).label("total")
            )
            .where(
                *base_conditions,
                Expense.date >= start_of_month,
                Expense.date <= end_of_month
            )
            .group_by(func.coalesce(func.nullif(func.trim(Expense.category), ''), 'Lainnya'))
            .order_by(desc(func.sum(Expense.amount)))
        )
        cat_results = (await session.execute(cat_stmt)).all()

        if not cat_results:
            # Fallback jika data bulan berjalan belum ada catatan
            all_cat_stmt = (
                select(
                    func.coalesce(func.nullif(func.trim(Expense.category), ''), 'Lainnya').label("category"),
                    func.sum(Expense.amount).label("total")
                )
                .where(*base_conditions)
                .group_by(func.coalesce(func.nullif(func.trim(Expense.category), ''), 'Lainnya'))
                .order_by(desc(func.sum(Expense.amount)))
            )
            cat_results = (await session.execute(all_cat_stmt)).all()

        category_labels = [r[0] for r in cat_results]
        category_values = [float(r[1]) for r in cat_results]

        # 5. Tren 7 Hari Terakhir (Bar Chart)
        start_7_days = start_of_day - timedelta(days=6)
        weekly_stmt = (
            select(Expense.date, Expense.amount)
            .where(
                *base_conditions,
                Expense.date >= start_7_days,
                Expense.date <= end_of_day
            )
            .order_by(Expense.date.asc())
        )
        weekly_expenses = (await session.execute(weekly_stmt)).all()

        daily_sums = {}
        day_labels = []
        for i in range(7):
            day_dt = start_7_days + timedelta(days=i)
            key = day_dt.strftime("%d/%m")
            day_labels.append(key)
            daily_sums[key] = 0.0

        for exp_date, amount in weekly_expenses:
            date_key = exp_date.astimezone(tz).strftime("%d/%m")
            if date_key in daily_sums:
                daily_sums[date_key] += float(amount)

        weekly_labels = day_labels
        weekly_values = [daily_sums[k] for k in day_labels]

        # 6. Seluruh Kategori Unik dari Database (DISTINCT)
        distinct_stmt = (
            select(func.trim(Expense.category))
            .where(
                Expense.is_deleted == False,
                Expense.category.is_not(None),
                func.trim(Expense.category) != ""
            )
            .distinct()
            .order_by(func.trim(Expense.category).asc())
        )
        db_cats = [c for c in (await session.execute(distinct_stmt)).scalars().all() if c]
        all_cats = sorted(list(set(db_cats + [l for l in category_labels if l != "Lainnya"])))
        if not all_cats:
            all_cats = ["Makan", "Minuman", "Transport", "Belanja", "Tagihan", "Hiburan", "Kesehatan", "Edukasi", "Lainnya"]
        elif "Lainnya" not in all_cats:
            all_cats.append("Lainnya")

        # 7. Daftar Transaksi Terbaru (100 record)
        recent_stmt = (
            select(Expense)
            .where(*base_conditions)
            .order_by(desc(Expense.date), desc(Expense.id))
            .limit(100)
        )
        expenses = (await session.execute(recent_stmt)).scalars().all()

    context = {
        "active_user_id": active_uid,
        "total_month": total_month,
        "count_month": count_month,
        "total_today": total_today,
        "budget_limit": budget_limit,
        "budget_percent": budget_percent,
        "category_labels": category_labels,
        "category_values": category_values,
        "weekly_labels": weekly_labels,
        "weekly_values": weekly_values,
        "categories": all_cats,
        "expenses": expenses
    }
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context
    )

# ==========================================
# API CRUD & MANAJEMEN TRANSAKSI
# ==========================================

@app.post("/api/expenses")
async def create_expense(data: ExpenseCreate):
    """Menambahkan transaksi pengeluaran baru dari web."""
    now = get_current_time()
    target_date = now

    if data.date:
        try:
            target_date = datetime.fromisoformat(data.date)
            if target_date.tzinfo is None:
                target_date = target_date.replace(tzinfo=now.tzinfo)
        except Exception:
            pass

    clean_tag = data.tag.strip().lstrip("#") if data.tag else None

    async with async_session() as session:
        active_uid = await get_active_user_id(session, data.user_id)
        expense = Expense(
            user_id=active_uid,
            amount=data.amount,
            category=data.category.strip().capitalize(),
            description=data.description.strip(),
            tag=clean_tag,
            date=target_date,
            is_confirmed=True,
            is_deleted=False
        )
        session.add(expense)
        await session.commit()
        await session.refresh(expense)

    return {"status": "success", "message": "Transaksi berhasil ditambahkan ૮ ˶ᵔ ᵕ ᵔ˶ ა", "id": expense.id}

@app.put("/api/expenses/{expense_id}")
@app.post("/api/expenses/{expense_id}/update")
async def update_expense(expense_id: int, data: ExpenseUpdate):
    """Mengubah / mengedit transaksi yang ada."""
    now = get_current_time()
    async with async_session() as session:
        expense = await session.get(Expense, expense_id)
        if not expense or expense.is_deleted:
            raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")

        expense.amount = data.amount
        expense.category = data.category.strip().capitalize()
        expense.description = data.description.strip()
        expense.tag = data.tag.strip().lstrip("#") if data.tag else None

        if data.date:
            try:
                parsed_dt = datetime.fromisoformat(data.date)
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=now.tzinfo)
                expense.date = parsed_dt
            except Exception:
                pass

        await session.commit()

    return {"status": "success", "message": "Transaksi berhasil diperbarui (｡•̀ᴗ-)✧"}

@app.delete("/api/expenses/{expense_id}")
@app.post("/api/expenses/{expense_id}/delete")
async def delete_expense(expense_id: int):
    """Menghapus transaksi (soft-delete)."""
    async with async_session() as session:
        expense = await session.get(Expense, expense_id)
        if not expense or expense.is_deleted:
            raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")

        expense.is_deleted = True
        await session.commit()

    return {"status": "success", "message": "Transaksi berhasil dihapus (づ ᴗ _ᴗ)づ♡"}

@app.post("/api/budget")
async def set_budget(data: BudgetUpdate):
    """Mengatur target budget bulanan dari web."""
    async with async_session() as session:
        active_uid = await get_active_user_id(session, data.user_id)
        budget = await session.get(Budget, active_uid)
        if not budget:
            budget = Budget(user_id=active_uid, monthly_limit=data.monthly_limit)
            session.add(budget)
        else:
            budget.monthly_limit = data.monthly_limit
        await session.commit()

    return {"status": "success", "message": "Budget bulanan berhasil diperbarui! 🎯"}

@app.get("/export-csv")
async def export_csv(user_id: int | None = None):
    """Mendownload file CSV langsung dari website."""
    async with async_session() as session:
        stmt = (
            select(Expense)
            .where(
                Expense.is_confirmed == True,
                Expense.is_deleted == False
            )
            .order_by(Expense.date.asc())
        )
        if user_id:
            stmt = stmt.where(Expense.user_id == user_id)
        expenses = (await session.execute(stmt)).scalars().all()

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

    output.seek(0)
    now_str = get_current_time().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pengeluaran_{now_str}.csv"}
    )
