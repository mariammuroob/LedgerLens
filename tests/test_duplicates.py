
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, Invoice
from app.duplicates import calculate_file_hash


def test_file_hash_is_consistent():
    file_path = "data/invoices/train/train_0001.pdf"

    first_hash = calculate_file_hash(file_path)
    second_hash = calculate_file_hash(file_path)

    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_duplicate_invoice_matches_vendor_and_number(monkeypatch):
    # Use an isolated in-memory database; never touch ledgerlens.db.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine)

    Base.metadata.create_all(engine)

    with TestSession() as session:
        session.add(
            Invoice(
                file_hash="existing-test-hash",
                filename="existing.pdf",
                vendor="Barnett, Rogers and Snyder",
                invoice_number="INV-TEST-0001",
                status="pending_review",
                is_valid=True,
                validation_errors="[]",
            )
        )
        session.commit()

    monkeypatch.setattr("app.duplicates.SessionLocal", TestSession)

    from app.duplicates import is_duplicate_invoice

    assert is_duplicate_invoice(
        "Barnett, Rogers and Snyder",
        "INV-TEST-0001",
    )

    engine.dispose()


def test_duplicate_invoice_ignores_case_and_outer_spaces(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine)

    Base.metadata.create_all(engine)

    with TestSession() as session:
        session.add(
            Invoice(
                file_hash="another-test-hash",
                filename="another.pdf",
                vendor="Barnett, Rogers and Snyder",
                invoice_number="INV-TEST-0001",
                status="pending_review",
                is_valid=True,
                validation_errors="[]",
            )
        )
        session.commit()

    monkeypatch.setattr("app.duplicates.SessionLocal", TestSession)

    from app.duplicates import is_duplicate_invoice

    assert is_duplicate_invoice(
        "  BARNETT, ROGERS AND SNYDER  ",
        " inv-test-0001 ",
    )

    engine.dispose()


def test_missing_identity_fields_are_not_duplicates():
    from app.duplicates import is_duplicate_invoice

    assert not is_duplicate_invoice("", "INV-TEST-0001")
    assert not is_duplicate_invoice("Barnett, Rogers and Snyder", "")
