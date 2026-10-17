# Mule Hunter

Graph-based detection of money-laundering and mule-account behaviour, built on **real labelled transaction data**.

Money mules pass stolen money along chains of accounts so the trail goes cold. Mule Hunter looks at the *shape* of the money flow (relay chains, hubs, round trips, who feeds whom), combines it with machine learning written from scratch, and explains every score in plain language.

It has three modes, all in one local web app:

| Mode | Data | Needs labels? |
|---|---|---|
| **Elliptic (Bitcoin)** | The public Elliptic Bitcoin graph, 203,769 real transactions with illicit/licit labels | Yes (provided) |
| **Upload your CSV** | Your own transactions (sender, receiver, amount, timestamp, optional label) | No |
| **Real-CATS (BTC+ETH)** | Real-CATS: real criminal and benign Bitcoin and Ethereum addresses, data to 2024 | Yes (provided) |
| **Live Bitcoin** | Recent confirmed Bitcoin transactions pulled from the free public mempool.space API (no key) | No |

No third-party Python packages. Standard library only.

## What the data really is (please read)

* The built-in dataset is the **Elliptic Data Set**: real Bitcoin transactions from 2019, labelled by Elliptic as illicit (scams, ransomware, darknet markets, laundering and similar) or licit. **It is crypto data, not bank accounts.** "Mule-like" here means relay and layering behaviour inside illicit money flows, which is the same pattern a bank mule account shows.
* Only 23% of transactions are labelled (4,545 illicit, 42,019 licit). The rest are unknown.
* No public dataset of real bank mule accounts with an open licence exists. This is the closest real, labelled, downloadable data.
* **Licence:** CC BY-NC-ND 4.0 (non-commercial, no derivatives). This repository does **not** contain the data. `run.py --download` fetches it from a public mirror on Hugging Face. Source and licence: <https://www.kaggle.com/datasets/ellipticco/elliptic-data-set>. Use it for study and research only.
* Live mode has no ground truth. Its scores are leads to look at, not accusations. Exchanges and busy services can look suspicious.
* The sample CSV and the test fixtures are tiny made-up examples, used only to show the file format and test the code. All reported results come from real labelled data (Elliptic and Real-CATS).

## Quick start

```bash
git clone https://github.com/hadhiabdulla/mule-hunter.git
cd mule-hunter

python3 run.py --download     # one time, about 700 MB, takes a few minutes
python3 run.py --elliptic     # trains and evaluates, about 1 minute
python3 run.py --realcats     # optional: downloads Real-CATS (about 90 MB) and evaluates, about 30 seconds
python3 run.py --serve        # open http://127.0.0.1:8000
```

On Windows use `python` instead of `python3`. The Upload and Live tabs work even before the Elliptic steps.

Score a file from the terminal: `python3 run.py --csv sample_transactions.csv`
Score live Bitcoin from the terminal: `python3 run.py --live`
Run the tests: `python3 -m unittest discover tests` (includes an end-to-end upload test with made-up bad rows)

## Upload your own data

Open the **Upload your CSV** tab, drop a file, check the detected column mapping, press Analyse. The file stays on your computer.

```csv
sender,receiver,amount,timestamp,label
ACC001,ACC114,4900.00,2026-03-02 09:14:00,1
ACC114,ACC207,4650.00,2026-03-02 10:02:00,
ACC207,ACC310,4400.00,2026-03-02 11:30:00,
```

* `label` is optional. `1` marks a transaction known to be fraud: its receiver becomes a suspect and money forwarded onward from it is traced. Leave empty if unknown.
* Column names are auto-detected (sender/from/source, receiver/to/dest, amount, timestamp/date, label/is_fraud). You can correct any of them.
* Timestamps: `2026-03-02 09:14:00`, `2026-03-02`, `02/03/2026 09:14`, or Unix seconds.
* Rows with a missing party, equal sender and receiver, non-positive amount or bad date are skipped and reported. Limit: 200,000 rows.

## Results on the real Elliptic data

Trained on time steps 1-34 (the past), tested on steps 35-49 (the future, never seen). 108 illicit test-period transactions are revealed as "analyst seeds" and excluded from scoring.

| Method | ROC-AUC | PR-AUC | Precision | Recall | F1 | Precision@k |
|---|---|---|---|---|---|---|
| ensemble (final) | 0.932 | 0.785 | 0.846 | 0.719 | 0.777 | 0.732 |
| random forest only | 0.930 | 0.783 | 0.850 | 0.723 | 0.782 | 0.729 |
| logistic regression only | 0.869 | 0.288 | 0.315 | 0.589 | 0.410 | 0.368 |
| seeded taint only | 0.517 | 0.746 | 0.059 | 1.000 | 0.111 | 0.874 |
| isolation forest only (unsupervised) | 0.319 | 0.039 | 0.054 | 0.873 | 0.102 | 0.005 |
| baseline: degree | 0.363 | 0.060 | 0.059 | 1.000 | 0.111 | 0.012 |

How to read it: a supervised model on the dataset's features does the heavy lifting. Graph taint adds little to overall ROC but is very precise at the top of its list (87% of its top-ranked are truly illicit) when an analyst supplies a few confirmed seeds. The unsupervised Isolation Forest does **worse than random** on this data, because Elliptic's illicit transactions look structurally ordinary. It stays in the project because it is the only option on unlabelled data (upload and live modes) and the table shows its limits. The time split is hard: a darknet market shut down at step 43 and models trained earlier lose accuracy after it, a known effect in the literature.


## Second dataset: Real-CATS (2025, data up to 2024)

Real-CATS has real criminal addresses taken from public reports (ransomware, phishing, impersonation, romance and other scams, hacks and so on) and benign exchange-customer addresses, for Bitcoin and Ethereum. Repository licence is MIT: <https://github.com/sjdseu/Real-CATS> (paper: <https://arxiv.org/abs/2501.15553>). It is downloaded when you run `python3 run.py --realcats` and is not stored in this repo. It describes addresses, not a transaction graph, so only the supervised models are used here.

Split by time: train on addresses first seen earlier, test on addresses first seen later (BTC test: 37,985 addresses, 1,132 criminal; ETH test: 7,952 addresses, 2,215 criminal).

| Data and method | ROC-AUC | PR-AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|
| BTC random forest | 0.785 | 0.213 | 0.295 | 0.297 | 0.296 |
| BTC logistic regression | 0.644 | 0.107 | 0.345 | 0.116 | 0.173 |
| ETH random forest | 0.804 | 0.655 | 0.505 | 0.744 | 0.602 |
| ETH logistic regression | 0.812 | 0.648 | 0.539 | 0.716 | 0.615 |

Bitcoin is much harder than Ethereum here: the newer criminal addresses look different from older ones. Recall per crime type is in the web app and in `results/realcats_metrics.md`. I dropped the `*_checked` columns because they record which tag database an address was found in, which gives the label away. Criminal labels come from reports, so some noise is expected.

## Known-bad address lists (live and upload)

Uploaded and live results are also checked against two public lists, downloaded when needed: the US OFAC sanctions list (913 crypto addresses across BTC, ETH and TRX when tested) and the ScamSniffer scam-address list (2,530 Ethereum addresses when tested, GPL-3.0, so fetched and never bundled). A match sets the risk to 100 (OFAC) or at least 90 (ScamSniffer) and says why. Only the lists are downloaded. Your data is never sent anywhere.

## How it works

```
   CSV upload ──┐
   Live Bitcoin ┼─► accounts.py ─► relay links, round trips, hubs, structuring,
   (mempool API)┘                  Isolation Forest, label taint ─► noisy-OR risk + reasons ─┐
                                                                                             ├─► web app
   Elliptic ────► graph.py + features ─► Random Forest + Logistic + seeded taint ─► risk ────┘
                                                      └─► case files (results/cases/)
```

| Piece | File | What it does |
|---|---|---|
| Graph analytics | `mulehunter/graph.py` | Relay chains, PageRank (forward and reverse), 2-hop fan-in/fan-out, taint propagation |
| Random Forest | `mulehunter/forest.py` | From scratch: histogram splits, Gini, balanced bootstrap |
| Isolation Forest | `mulehunter/iforest.py` | From scratch (Liu et al. 2008) |
| Logistic regression | `mulehunter/model.py` | SGD, plus ROC-AUC, PR-AUC, F1 |
| Elliptic pipeline | `mulehunter/pipeline.py` | Features, time-split training, seeded taint, clusters |
| Account pipeline | `mulehunter/accounts.py` | Rules and anomaly scoring for upload and live data |
| Live data | `mulehunter/live.py` | Keyless public API, fallback server, retries |
| Upload | `mulehunter/upload.py` | Column detection, validation |
| Web app | `mulehunter/web.py`, `static/index.html` | Local server and interactive network viewer |

The full guide (architecture, every method explained, using each mode, and evaluation) is in [`docs/GUIDE.md`](docs/GUIDE.md) and [`docs/Mule_Hunter_Guide.pdf`](docs/Mule_Hunter_Guide.pdf).

## Limits

* Scores are for human review, not proof of wrongdoing.
* Elliptic is from 2019 and is Bitcoin only; patterns change. Real-CATS is newer (to 2024) but address-level only.
* The upload and live methods are hand-tuned heuristics and have not been validated against labelled bank mule data.
* Pure Python keeps it dependency-free but not fast; very large files are capped.

## Licence

Code: MIT. The Elliptic data is **not** included and keeps its own CC BY-NC-ND 4.0 licence.
