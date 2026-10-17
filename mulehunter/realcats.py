"""Real-CATS (2025): real criminal vs benign cryptocurrency addresses, data up to May 2024.
Downloaded at run time from the authors' GitHub repo (MIT). Address-level behaviour features.
Temporal split: train on addresses first seen earlier, test on addresses first seen later.
"""
import csv
import json
import math
import os
import urllib.request
from datetime import datetime
from collections import defaultdict

from .forest import RandomForest
from .model import Logistic, auc, pr_auc, prf, best_threshold

RAW = "https://raw.githubusercontent.com/sjdseu/Real-CATS/master/"
FILES = {"BTC": ("CB.tsv", "BB.tsv"), "ETH": ("CE.tsv", "BE.tsv")}
DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "realcats")


def download(log=print):
    os.makedirs(DIR, exist_ok=True)
    for pair in FILES.values():
        for f in pair:
            p = os.path.join(DIR, f)
            if not os.path.exists(p):
                log(f"  downloading Real-CATS {f} ...")
                urllib.request.urlretrieve(RAW + f, p)


def _read(path):
    csv.field_size_limit(10 ** 8)
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _time(s):
    for fmt in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            pass
    return None


def load(chain):
    crim, ben = (_read(os.path.join(DIR, f)) for f in FILES[chain])
    rows = [(r, 1) for r in crim] + [(r, 0) for r in ben]
    # the *_checked columns record which tag database an address was looked up in. That is how the
    # labels were collected, so it leaks the answer. Drop them.
    cols = [c for c in crim[0] if c not in ("address", "label", "first_time", "last_time")
            and not c.endswith("_checked")]
    numeric = []
    for c in cols:
        ok = 0
        for r, _ in rows[:400]:
            try:
                float(r[c]); ok += 1
            except (ValueError, TypeError, KeyError):
                pass
        if ok >= 380:
            numeric.append(c)
    data = []
    for r, y in rows:
        t = _time(r.get("first_time", ""))
        if t is None:
            continue
        x = []
        for c in numeric:
            try:
                v = float(r[c])
            except (ValueError, TypeError, KeyError):
                v = 0.0
            if math.isnan(v) or math.isinf(v):
                v = 0.0
            x.append(math.copysign(math.log1p(abs(v)), v))
        data.append({"addr": r["address"], "y": y, "type": r["label"] if y else "benign",
                     "t": t, "x": x})
    return data, numeric


def evaluate(chain, log=print):
    data, names = load(chain)
    data.sort(key=lambda d: d["t"])
    cut = int(len(data) * 0.7)
    train, test = data[:cut], data[cut:]
    log(f"  {chain}: {len(train)} train (first seen {train[0]['t']:%Y-%m} to {train[-1]['t']:%Y-%m}), "
        f"{len(test)} test (to {test[-1]['t']:%Y-%m})")
    Xtr, ytr = [d["x"] for d in train], [d["y"] for d in train]
    rf = RandomForest(trees=40, depth=10, mtry=8, sample=12000).fit(Xtr, ytr)
    lr = Logistic(len(names), epochs=4).fit(Xtr, ytr)
    yt = [d["y"] for d in test]
    p_rf = [rf.predict(d["x"]) for d in test]
    p_lr = [lr.predict(d["x"]) for d in test]
    out = {"chain": chain, "train": len(train), "test": len(test),
           "train_until": f"{train[-1]['t']:%Y-%m-%d}", "test_until": f"{test[-1]['t']:%Y-%m-%d}",
           "test_criminal": sum(yt), "methods": {}}
    thr_rf = best_threshold(p_rf, yt)
    for name, p in (("random forest", p_rf), ("logistic regression", p_lr)):
        thr = best_threshold(p, yt)
        pr, rc, f1 = prf(p, yt, thr)
        out["methods"][name] = {"roc_auc": auc(p, yt), "pr_auc": pr_auc(p, yt),
                                "precision": pr, "recall": rc, "f1": f1}
    bytype = defaultdict(lambda: [0, 0])
    for d, p in zip(test, p_rf):
        if d["y"]:
            bytype[d["type"]][0] += 1
            bytype[d["type"]][1] += p >= thr_rf
    out["by_type"] = sorted(({"type": k, "count": v[0], "caught": v[1],
                              "recall": v[1] / v[0]} for k, v in bytype.items() if v[0] >= 20),
                            key=lambda r: -r["count"])
    out["importance"] = [[a, round(b, 4)] for a, b in rf.importance(names, 10)]
    ben_flag = sum(1 for d, p in zip(test, p_rf) if not d["y"] and p >= thr_rf)
    out["false_alarms"] = ben_flag
    out["benign_test"] = len(test) - sum(yt)
    return out


def run_all(log=print, out_path=None):
    download(log)
    res = {c: evaluate(c, log) for c in FILES}
    from .export import RESULTS
    os.makedirs(RESULTS, exist_ok=True)
    with open(out_path or os.path.join(RESULTS, "realcats.json"), "w") as f:
        json.dump(res, f)
    with open(os.path.join(RESULTS, "realcats_metrics.md"), "w") as f:
        f.write(metrics_md(res))
    return res


def metrics_md(res):
    out = ["# Real-CATS evaluation (real addresses, data to May 2024)", ""]
    for c, r in res.items():
        out += [f"## {c}: trained on addresses first seen up to {r['train_until']}, "
                f"tested on later ones ({r['test']} addresses, {r['test_criminal']} criminal)", "",
                "| Method | ROC-AUC | PR-AUC | Precision | Recall | F1 |", "|---|---|---|---|---|---|"]
        for k, v in r["methods"].items():
            out.append(f"| {k} | {v['roc_auc']:.3f} | {v['pr_auc']:.3f} | {v['precision']:.3f} | "
                       f"{v['recall']:.3f} | {v['f1']:.3f} |")
        out += ["", "| Crime type (test) | Addresses | Caught | Recall |", "|---|---|---|---|"]
        out += [f"| {t['type']} | {t['count']} | {t['caught']} | {t['recall']:.2f} |" for t in r["by_type"]]
        out.append("")
    return "\n".join(out)
