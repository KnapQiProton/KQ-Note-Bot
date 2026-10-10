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
        if active_uid != 1:
            base_conditions.append(Expense.user_id == active_uid)

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
            select(Expense.category, func.sum(Expense.amount))
            .where(
                *base_conditions,
                Expense.date >= start_of_month,
                Expense.date <= end_of_month
            )
            .group_by(Expense.category)
            .order_by(desc(func.sum(Expense.amount)))
        )
        cat_results = (await session.execute(cat_stmt)).all()
        category_labels = [r[0] or "Lainnya" for r in cat_results]
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

        # 6. Daftar Transaksi Terbaru (100 record)
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

    # Bersihkan tagar jika user mengetik dengan '#'
    clean_tag = data.tag.strip().lstrip("#") if data.tag else None

    async with async_session() as session:
        active_uid = await get_active_user_id(session, data.user_id)
        expense = Expense(
            user_id=active_uid,
            amount=data.amount,
            category=data.category.capitalize(),
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
        expense.category = data.category.capitalize()
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
        active_uid = await get_active_user_id(session, user_id)
        stmt = (
            select(Expense)
            .where(
                Expense.is_confirmed == True,
                Expense.is_deleted == False
            )
            .order_by(Expense.date.asc())
        )
        if active_uid != 1:
            stmt = stmt.where(Expense.user_id == active_uid)
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
