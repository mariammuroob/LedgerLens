
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import pdfplumber
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
)

from app.classifier import train_classifier

LABELS_PATH = ROOT / "data" / "labels.csv"
PDF_ROOT = ROOT / "data" / "rebuilt_invoices"


def extract_description(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    for line in text.splitlines():
        if line.startswith("Description:"):
            return line.split(":", 1)[1].strip()

    return ""


def evaluate_split(model, labels, split_name):
    rows = labels[
        (labels["split"] == split_name)
        & (labels["injected_error"] == "")
        & (labels["category"] != "")
    ]

    actual = []
    predicted = []
    skipped = 0

    for _, row in rows.iterrows():
        pdf_path = PDF_ROOT / split_name / Path(row["filename"]).name

        if not pdf_path.exists():
            skipped += 1
            continue

        description = extract_description(pdf_path)

        if not description:
            skipped += 1
            continue

        actual.append(row["category"])
        predicted.append(model.predict([description])[0])

    print(f"\n{'=' * 50}")
    print(f"Split: {split_name}")
    print(f"{'=' * 50}")
    print(f"Eligible invoices: {len(rows)}")
    print(f"Evaluated: {len(actual)}")
    print(f"Skipped: {skipped}")

    if not actual:
        print("No invoices were evaluated.")
        return

    print(f"Accuracy: {accuracy_score(actual, predicted):.3f}")
    print(
        "Macro F1: "
        f"{f1_score(actual, predicted, average='macro', zero_division=0):.3f}"
    )
    print("\nClassification report:")
    print(classification_report(actual, predicted, zero_division=0))


def main():
    labels = pd.read_csv(LABELS_PATH, dtype=str).fillna("")
    model = train_classifier()

    evaluate_split(model, labels, "test")
    evaluate_split(model, labels, "hard")


if __name__ == "__main__":
    main()
