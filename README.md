# LedgerLens

**AI-assisted invoice processing and validation for UAE SMEs.**

LedgerLens is a Python-based invoice processing project that extracts structured information from PDF invoices, validates invoice fields and arithmetic, categorizes expenses, detects duplicates, and routes invoices for human review.

## Features

- **Invoice extraction:** Extracts vendor details, invoice numbers, dates, line items, VAT, totals, and currency.
- **Validation:** Checks required fields, TRN format, dates, line-item arithmetic, subtotals, VAT treatment, totals, and currency.
- **Duplicate detection:** Flags identical PDF files and invoices with matching vendor and invoice number.
- **Expense categorization:** Uses a scikit-learn text-classification pipeline to predict expense categories.
- **Human review:** Provides an interface to review invoices and record decisions.
- **Automated tests:** Uses pytest and GitHub Actions to run tests on pushes and pull requests.

## Technology Stack

Python, FastAPI, Streamlit, SQLAlchemy, SQLite, pdfplumber, pandas, scikit-learn, Pydantic, pytest, and GitHub Actions.

## Run Locally

### 1. Install dependencies

Activate your Python environment, navigate to the project directory, and run:

```powershell
python -m pip install -r requirements.txt
```

### 2. Start the API

```powershell
python -m uvicorn app.api:app --reload
```

Open the API documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 3. Start the dashboard

Open a second terminal, activate the same Python environment, and run:

```powershell
python -m streamlit run ui/streamlit_app.py
```

Open the dashboard at [http://localhost:8501](http://localhost:8501).

## Run Tests

Run the automated test suite with:

```powershell
python -m pytest -v
```

GitHub Actions is configured to run the test suite on pushes to `main` and pull requests targeting `main`.

## Evaluation

LedgerLens has been evaluated using a synthetic invoice dataset containing clean invoices and deliberately injected errors.

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

These figures reflect the existing synthetic evaluation of invoice validation and duplicate detection across the evaluated splits. They should not be interpreted as real-world performance guarantees.

### Expense classification

| Dataset split | Invoices evaluated | Accuracy | Macro F1 |
|---|---:|---:|---:|
| Test | 27 | 92.6% | 93.8% |
| Hard | 31 | 77.4% | 76.0% |

The classifier performed better on the test set than on the harder set. The accuracy decrease suggests that more challenging expense descriptions remain a weakness.

A description-overlap check found zero distinct descriptions shared between the training set and either the test or hard set. This reduces the risk of duplicate-description leakage, but does not eliminate every possible source of evaluation bias.

## Safety and Limitations

- Invoices are routed for human review; automatic approval is not enabled.
- LedgerLens does not make tax decisions or claim regulatory compliance.
- Validation rules are screening checks, not a substitute for professional accounting review.
- The evaluation dataset is synthetic and relatively small.
- Synthetic-data performance does not establish production readiness or generalization to real invoices.
- Further evaluation on representative real-world invoices is needed.

## Project Status

The project includes the core application, evaluation scripts, automated tests, an evaluation report, and a GitHub Actions workflow.

The classifier has been evaluated on separate synthetic test and hard sets. Further work should focus on reviewing misclassifications, expanding the evaluation dataset, and verifying reliability on representative real-world invoices before making production-performance claims.
