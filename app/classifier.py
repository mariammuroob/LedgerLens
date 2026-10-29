
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parent.parent
LABELS_PATH = ROOT / "data" / "labels.csv"
PDF_ROOT = ROOT / "data" / "rebuilt_invoices"


def load_training_data():
    labels = pd.read_csv(LABELS_PATH, dtype=str).fillna("")
    rows = labels[
        (labels["split"] == "train")
        & (labels["injected_error"] == "")
        & (labels["category"] != "")
    ]

    descriptions = []
    categories = []

    for _, row in rows.iterrows():
        pdf_path = PDF_ROOT / row["split"] / Path(row["filename"]).name
        if not pdf_path.exists():
            continue

        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        description = next(
            (
                line.split(":", 1)[1].strip()
                for line in text.splitlines()
                if line.startswith("Description:")
            ),
            "",
        )

        if description:
            descriptions.append(description)
            categories.append(row["category"])

    return descriptions, categories


def train_classifier():
    descriptions, categories = load_training_data()

    if len(descriptions) < 10:
        raise ValueError(
            f"Not enough training examples: {len(descriptions)}"
        )

    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
        ("model", LogisticRegression(max_iter=1000)),
    ])

    model.fit(descriptions, categories)
    return model


def predict_category(description: str) -> dict:
    model = train_classifier()
    probabilities = model.predict_proba([description])[0]
    best_index = probabilities.argmax()

    return {
        "category": str(model.classes_[best_index]),
        "confidence": round(float(probabilities[best_index]), 3),
    }
