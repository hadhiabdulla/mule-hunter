# Evaluation on real Elliptic labels

Train steps 1-34 (29894 labelled, 3462 illicit). Test steps 35-49 (16562 labelled, 975 illicit). 108 test-period illicit transactions were revealed as analyst seeds and are excluded from scoring.

| Method | ROC-AUC | PR-AUC | Precision | Recall | F1 | Precision@k |
|---|---|---|---|---|---|---|
| ensemble (final) | 0.932 | 0.785 | 0.846 | 0.719 | 0.777 | 0.732 |
| random forest only | 0.930 | 0.783 | 0.850 | 0.723 | 0.782 | 0.729 |
| logistic regression only | 0.869 | 0.288 | 0.315 | 0.589 | 0.410 | 0.368 |
| seeded taint only | 0.517 | 0.746 | 0.059 | 1.000 | 0.111 | 0.874 |
| isolation forest only (unsupervised) | 0.319 | 0.039 | 0.054 | 0.873 | 0.102 | 0.005 |
| baseline: degree | 0.363 | 0.060 | 0.059 | 1.000 | 0.111 | 0.012 |
