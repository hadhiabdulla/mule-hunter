# Real-CATS evaluation (real addresses, data to May 2024)

## BTC: trained on addresses first seen up to 2023-11-27, tested on later ones (37985 addresses, 1132 criminal)

| Method | ROC-AUC | PR-AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|
| random forest | 0.785 | 0.213 | 0.295 | 0.297 | 0.296 |
| logistic regression | 0.644 | 0.107 | 0.345 | 0.116 | 0.173 |

| Crime type (test) | Addresses | Caught | Recall |
|---|---|---|---|
| Impersonation Scam | 320 | 119 | 0.37 |
| Sextortion Scam | 185 | 30 | 0.16 |
| Fake Returns Scam | 117 | 33 | 0.28 |
| Phishing Scam | 106 | 39 | 0.37 |
| Hack | 104 | 27 | 0.26 |
| Blackmail Scam | 82 | 17 | 0.21 |
| Ransomware | 44 | 7 | 0.16 |
| Other | 42 | 16 | 0.38 |
| Romance Scam | 39 | 13 | 0.33 |
| Fake Project Scam | 31 | 12 | 0.39 |
| Pigbutchering Scam | 20 | 6 | 0.30 |

## ETH: trained on addresses first seen up to 2022-11-27, tested on later ones (7952 addresses, 2215 criminal)

| Method | ROC-AUC | PR-AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|
| random forest | 0.804 | 0.655 | 0.505 | 0.744 | 0.602 |
| logistic regression | 0.812 | 0.648 | 0.539 | 0.716 | 0.615 |

| Crime type (test) | Addresses | Caught | Recall |
|---|---|---|---|
| Phishing Scam | 1349 | 919 | 0.68 |
| Impersonation Scam | 309 | 266 | 0.86 |
| Hack Scam | 139 | 118 | 0.85 |
| Fake Returns Scam | 87 | 70 | 0.80 |
| NFT Airdrop Scam | 63 | 53 | 0.84 |
| Fake Project Scam | 55 | 49 | 0.89 |
| Pigbutchering Scam | 54 | 41 | 0.76 |
| Rug Pull Scam | 46 | 42 | 0.91 |
| Contract Exploit Scam | 39 | 33 | 0.85 |
| Other | 26 | 20 | 0.77 |
| Romance Scam | 22 | 16 | 0.73 |
