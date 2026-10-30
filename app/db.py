
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
    inspect,
    text,
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

    # Audit fields for category edits
    previous_category: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    new_category: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


def init_db() -> None:
    """Create missing tables and add new columns without deleting data."""
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    with engine.begin() as connection:
        invoice_columns = {
            column["name"] for column in inspector.get_columns("invoices")
        }

        if "category" not in invoice_columns:
            connection.execute(
                text("ALTER TABLE invoices ADD COLUMN category VARCHAR(100)")
            )

        if "category_confidence" not in invoice_columns:
            connection.execute(
                text(
                    "ALTER TABLE invoices "
                    "ADD COLUMN category_confidence FLOAT"
                )
            )

        review_columns = {
            column["name"] for column in inspect(connection).get_columns("reviews")
        }

        if "previous_category" not in review_columns:
            connection.execute(
                text(
                    "ALTER TABLE reviews "
                    "ADD COLUMN previous_category VARCHAR(100)"
                )
            )

        if "new_category" not in review_columns:
            connection.execute(
                text(
                    "ALTER TABLE reviews "
                    "ADD COLUMN new_category VARCHAR(100)"
                )
            )


if __name__ == "__main__":
    init_db()
    print(f"Database ready: {DATABASE_PATH}")
