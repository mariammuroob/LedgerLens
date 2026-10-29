
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from app.extraction import extract_invoice
from app.validation import validate_invoice


LABELS_PATH = ROOT / "data" / "labels.csv"
PDF_ROOT = ROOT / "data" / "rebuilt_invoices"


def get_field(invoice, field):
    if isinstance(invoice, dict):
        value = invoice.get(field, "")
    else:
        value = getattr(invoice, field, "")

    return str(value or "").strip()


def main():
    labels = pd.read_csv(LABELS_PATH, dtype=str).fillna("")

    # Evaluate test and hard examples; keep injection tests separate.
    rows = labels[labels["split"].isin(["test", "hard"])].copy()

    # Process non-duplicates first so each duplicate can match its
    # previously processed original invoice.
    rows["_is_duplicate"] = rows["injected_error"].eq("duplicate")
    rows = rows.sort_values("_is_duplicate", kind="stable")

    seen_invoices = set()
    results = []

    for _, row in rows.iterrows():
        pdf_path = PDF_ROOT / row["split"] / Path(row["filename"]).name
        expected_review = row["expected_review"].lower() == "true"
        error_type = row["injected_error"] or "clean"

        if not pdf_path.exists():
            results.append({
                "split": row["split"],
                "error": error_type,
                "expected_review": expected_review,
                "flagged": False,
                "duplicate_detected": False,
                "missing_file": True,
                "validation_errors": "PDF not found",
            })
            continue

        try:
            invoice = extract_invoice(pdf_path)
            validation = validate_invoice(invoice)

            vendor = get_field(invoice, "vendor").casefold()
            invoice_number = get_field(
                invoice, "invoice_number"
            ).casefold()

            identity = (vendor, invoice_number)

            duplicate_detected = (
                bool(vendor)
                and bool(invoice_number)
                and identity in seen_invoices
            )

            if vendor and invoice_number:
                seen_invoices.add(identity)

            validation_errors = list(validation["errors"])

            if duplicate_detected:
                validation_errors.append(
                    "Duplicate vendor and invoice number"
                )

            # Either a field-validation failure or a duplicate
            # should route the invoice to human review.
            flagged = not validation["valid"] or duplicate_detected

            results.append({
                "split": row["split"],
                "error": error_type,
                "expected_review": expected_review,
                "flagged": flagged,
                "duplicate_detected": duplicate_detected,
                "missing_file": False,
                "validation_errors": "; ".join(validation_errors),
            })

        except Exception as exc:
            results.append({
                "split": row["split"],
                "error": error_type,
                "expected_review": expected_review,
                "flagged": True,
                "duplicate_detected": False,
                "missing_file": False,
                "validation_errors": f"Evaluation exception: {exc}",
            })

    results_df = pd.DataFrame(results)

    if results_df.empty:
        print("No invoices were evaluated.")
        return

    evaluated = results_df[~results_df["missing_file"]]
    expected = evaluated["expected_review"]
    flagged = evaluated["flagged"]

    tp = int((expected & flagged).sum())
    fp = int((~expected & flagged).sum())
    fn = int((expected & ~flagged).sum())
    tn = int((~expected & ~flagged).sum())

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0

    print("LEDGERLENS COMBINED REVIEW EVALUATION")
    print("=" * 45)
    print(f"Rows in dataset: {len(results_df)}")
    print(f"PDFs evaluated: {len(evaluated)}")
    print(f"Missing PDFs: {int(results_df['missing_file'].sum())}")
    print(f"Duplicates detected: {int(evaluated['duplicate_detected'].sum())}")
    print()
    print(f"True positives:   {tp}")
    print(f"False positives:  {fp}")
    print(f"False negatives:  {fn}")
    print(f"True negatives:   {tn}")
    print(f"Review precision: {precision:.3f}")
    print(f"Review recall:    {recall:.3f}")

    print("\nRESULTS BY SPLIT AND ERROR TYPE")
    print("-" * 45)

    summary = (
        evaluated.groupby(["split", "error"])
        .agg(
            invoices=("flagged", "size"),
            flagged=("flagged", "sum"),
            duplicates_detected=("duplicate_detected", "sum"),
        )
        .reset_index()
    )

    summary["flag_rate"] = (
        summary["flagged"] / summary["invoices"]
    ).round(3)

    print(summary.to_string(index=False))

    print("\nMISSED REVIEW CASES")
    print("-" * 45)

    misses = evaluated[expected & ~flagged]

    if misses.empty:
        print("No expected-review invoices were missed.")
    else:
        print(
            misses[
                ["split", "error", "validation_errors"]
            ].to_string(index=False)
        )

    print(
        "\nNote: these results evaluate field validation plus "
        "vendor/invoice-number duplicate detection. "
        "They do not establish production readiness."
    )


if __name__ == "__main__":
    main()
