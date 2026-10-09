from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, Numeric, DateTime, Boolean, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tag: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., 'tugas_kuliah'
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("ix_user_date", "user_id", "date"),
    )

class Budget(Base):
    __tablename__ = "budgets"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    monthly_limit: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
