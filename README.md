# LedgerLens

**AI-assisted invoice processing and validation for UAE SMEs.**

LedgerLens extracts structured data from PDF invoices, checks invoice fields and arithmetic, categorizes expenses, detects duplicates, and routes invoices for human review.

## Features

- **Invoice extraction:** Extracts vendor details, invoice numbers, dates, line items, VAT, totals, and currency.
- **Validation:** Checks required fields, TRN format, dates, line-item arithmetic, subtotal, VAT treatment, total, and currency.
- **Duplicate detection:** Flags identical PDF files and invoices with matching vendor and invoice number.
- **Expense categorization:** Uses a scikit-learn text-classification pipeline to predict expense categories.
- **Human review:** Provides an interface to review invoices and record decisions.
- **Automated tests:** Uses pytest and GitHub Actions to run tests on pushes and pull requests.

## Technology Stack

Python, FastAPI, Streamlit, SQLAlchemy, SQLite, pdfplumber, pandas, scikit-learn, Pydantic, pytest, and GitHub Actions.

## Run Locally

Activate your Python environment, then install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the API:

```powershell
python -m uvicorn app.api:app --reload
```

Open the API documentation at http://127.0.0.1:8000/docs.

In a second terminal, activate the same environment and start the dashboard:

```powershell
python -m streamlit run ui/streamlit_app.py
```

Open the dashboard at http://localhost:8501.

## Run Tests

```powershell
python -m pytest -v
```

GitHub Actions automatically runs the test suite when code is pushed to `main` or a pull request targets `main`.

## Evaluation

## Evaluation

LedgerLens was evaluated using a synthetic invoice dataset containing clean invoices and deliberately injected errors.

### Invoice validation and duplicate detection

| Metric | Result |
|---|---:|
| Invoices evaluated | 100 |
| True positives (errors correctly flagged) | 42 |
| False positives (clean invoices incorrectly flagged) | 0 |
| False negatives (review cases missed) | 0 |
| True negatives (clean invoices correctly passed) | 58 |
| Review precision | 100% |
| Review recall | 100% |

These results cover field validation combined with vendor/invoice-number duplicate detection on the current synthetic test and hard splits.

### Expense classification

| Dataset split | Invoices evaluated | Accuracy | Macro F1 |
|---|---:|---:|---:|
| Test | 27 | 100% | 100% |
| Hard | 31 | 100% | 100% |

### Limitations

These results are from a synthetic dataset with deliberately structured examples. They do not establish real-world accuracy or production readiness. The classifier's descriptions are designed around expense categories, which may make classification easier than it would be on unseen real invoices.

LedgerLens remains human-review-only. Automatic approval will not be enabled based on synthetic evaluation results alone.

## Safety and Limitations

- Invoices are routed for human review; automatic approval is not enabled.
- LedgerLens does not make tax decisions or claim regulatory compliance.
- Validation rules are screening checks, not a substitute for professional accounting review.
- Synthetic-data performance does not establish production readiness.

## Project Status

Core application, evaluation scripts, tests, GitHub repository, and automated test workflow are in place. Public deployment and further reliability checks remain future steps.