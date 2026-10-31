# LedgerLens — Classifier Evaluation

## Overview

LedgerLens is a project for classifying invoice descriptions into expense categories. This evaluation measures performance on held-out synthetic invoice descriptions.

## Evaluation Results

| Metric | Test Set | Hard Set |
|---|---:|---:|
| Eligible invoices | 27 | 31 |
| Evaluated invoices | 27 | 31 |
| Skipped invoices | 0 | 0 |
| Accuracy | 92.6% | 77.4% |
| Macro F1 | 93.8% | 76.0% |

## Data Leakage Check

Compared the extracted descriptions in the training set against those in the test and hard sets.

- Test set: 0 overlapping descriptions
- Hard set: 0 overlapping descriptions

The evaluation sets use descriptions distinct from those in the training set, reducing the risk of duplicate-description leakage.

## Findings

The classifier performed better on the test set than on the hard set. Accuracy decreased by 15.2 percentage points on the hard set, indicating that more challenging wording may reduce classification performance.

## Limitations

- The evaluation uses synthetic invoice data.
- The test and hard sets are small.
- Results may not reflect performance on real invoices from different businesses, vendors, or document formats.
- Further validation on representative real-world data is needed before making claims about production accuracy.

## Next Steps

- Review misclassified invoices, especially in categories with weaker hard-set results.
- Expand the evaluation dataset with more varied descriptions.
- Test on representative real-world invoices where appropriate.
