import os
from datetime import datetime, timedelta
from calendar import monthrange
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc
from bot.database.session import async_session
from bot.database.models import Expense, Budget
from bot.utils.parser import get_current_time

app = FastAPI(title="KQ-Note Dashboard")

template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)

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
        # Base filter
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
        budget_stmt = select(Budget)
        if user_id:
            budget_stmt = budget_stmt.where(Budget.user_id == user_id)
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

        # Agregasikan per hari (7 hari)
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

        # 6. Daftar Transaksi Terbaru (50 record)
        recent_stmt = (
            select(Expense)
            .where(*base_conditions)
            .order_by(desc(Expense.date), desc(Expense.id))
            .limit(50)
        )
        expenses = (await session.execute(recent_stmt)).scalars().all()

    context = {
        "request": request,
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

@app.get("/api/stats", response_class=JSONResponse)
async def api_stats(user_id: int | None = None):
    now = get_current_time()
    tz = now.tzinfo
    start_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=tz)

    async with async_session() as session:
        base_conditions = [
            Expense.is_confirmed == True,
            Expense.is_deleted == False
        ]
        if user_id:
            base_conditions.append(Expense.user_id == user_id)

        month_stmt = select(func.sum(Expense.amount), func.count(Expense.id)).where(
            *base_conditions,
            Expense.date >= start_of_month
        )
        month_res = (await session.execute(month_stmt)).first()

    return {
        "total_month": float(month_res[0] or 0.0),
        "count_month": int(month_res[1] or 0),
        "timestamp": now.isoformat()
    }
