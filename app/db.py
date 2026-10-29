
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


DATABASE_PATH = Path(__file__).resolve().parent.parent / "ledgerlens.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subtotal: Mapped[float | None] = mapped_column(Float, nullable=True)
    vat: Mapped[float | None] = mapped_column(Float, nullable=True)
    total: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # Persisted ML prediction
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="pending")
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(30))
    reviewer: Mapped[str] = mapped_column(String(100), default="human")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


def init_db() -> None:
    """Create missing tables; existing tables are not rebuilt."""
    Base.metadata.create_all(bind=engine)

    # SQLite create_all does not add columns to an existing table.
    # Add the new nullable columns without deleting existing invoices.
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("invoices")}

    with engine.begin() as connection:
        if "category" not in columns:
            connection.execute(
                text("ALTER TABLE invoices ADD COLUMN category VARCHAR(100)")
            )
        if "category_confidence" not in columns:
            connection.execute(
                text("ALTER TABLE invoices ADD COLUMN category_confidence FLOAT")
            )


if __name__ == "__main__":
    init_db()
    print(f"Database ready: {DATABASE_PATH}")
