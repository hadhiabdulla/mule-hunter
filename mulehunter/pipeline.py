"""Feature building, training, scoring and evaluation on the Elliptic graph."""
import math
from collections import defaultdict

from . import graph as G
from .iforest import IsolationForest
from .model import Logistic, auc, pr_auc, prf, best_threshold
from .forest import RandomForest

TRAIN_MAX_STEP = 34      # standard Elliptic split: steps 1-34 train, 35-49 test

FEATURES = ["indeg", "outdeg", "fan_in_2hop", "fan_out_2hop", "chain_len", "chain_pos",
            "pagerank_fwd", "pagerank_rev", "taint_down", "taint_up",
            "known_illicit_nbrs", "known_licit_nbrs"]

FRIENDLY = {
    "indeg": "number of inputs (consolidation)",
    "outdeg": "number of outputs (splitting)",
    "fan_in_2hop": "how many transactions feed it within 2 hops (fan-in hub)",
    "fan_out_2hop": "how many transactions it fans out to within 2 hops (distribution hub)",
    "chain_len": "sits in a long one-in-one-out relay chain (layering)",
    "chain_pos": "position inside a relay chain",
    "pagerank_fwd": "importance as a destination of flows",
    "pagerank_rev": "importance as a source of flows",
    "taint_down": "receives money from transactions linked to known illicit ones",
    "taint_up": "sends money towards transactions linked to known illicit ones",
    "known_illicit_nbrs": "direct neighbours known to be illicit",
    "known_licit_nbrs": "direct neighbours known to be licit",
}


def build_features(nodes, edges, label, step, log=print):
    g = G.Graph(nodes, edges)
    log("  relay chains ...")
    chains = G.relay_chains(g)
    log("  pagerank ...")
    prf_ = G.pagerank(g)
    prr_ = G.pagerank(g, reverse=True)
    log("  2-hop reach ...")
    fin, fout = G.two_hop(g)
    known = {n: l for n, l in label.items() if l is not None and step[n] <= TRAIN_MAX_STEP}
    seeds = [n for n, l in known.items() if l == 1]
    log(f"  taint propagation from {len(seeds)} known illicit training transactions ...")
    down, up = G.taint(g, seeds)
    ill, lic = G.neighbour_counts(g, known)
    scale = len(nodes)
    X = {}
    for n in nodes:
        cl, cp = chains.get(n, (0, 0))
        X[n] = [g.indeg(n), g.outdeg(n), fin[n], fout[n], cl, cp,
                prf_[n] * scale, prr_[n] * scale, down[n], up[n], ill[n], lic[n]]
    return g, X, known


def _tf(v):
    return [math.log1p(max(x, 0)) for x in v]


STRUCT_IDX = list(range(len(FEATURES)))
SEED_FRACTION = 0.10


def run(nodes, edges, label, step, getfeat, log=print):
    import random
    g, X, known = build_features(nodes, edges, label, step, log)
    struct_cols = [i for i, f in enumerate(FEATURES)
                   if f not in ("taint_down", "taint_up", "known_illicit_nbrs", "known_licit_nbrs")]
    sn = [FEATURES[i] for i in struct_cols]
    names = sn + [f"elliptic_f{i + 1}" for i in range(165)]

    def vec(n):
        return [math.log1p(max(X[n][i], 0)) for i in struct_cols] + getfeat(n)

    train = list(known)
    test = [n for n in nodes if step[n] > TRAIN_MAX_STEP]
    log("  training logistic regression on train period ...")
    lr = Logistic(len(names), epochs=6).fit([vec(n) for n in train], [known[n] for n in train])

    # analyst feedback: a few confirmed illicit transactions in the test period act as seeds
    rnd = random.Random(5)
    test_ill = sorted(n for n in test if label[n] == 1)
    seeds = set(rnd.sample(test_ill, max(1, int(len(test_ill) * SEED_FRACTION))))
    log(f"  taint propagation from {len(seeds)} analyst-confirmed test-period seeds ...")
    down, up = G.taint(g, seeds, hops=4, decay=0.6)

    log(f"  scoring {len(test)} test-period transactions ...")
    log("  training random forest on train period ...")
    rf = RandomForest().fit([vec(n) for n in train], [known[n] for n in train])
    p_lr = {n: lr.predict(vec(n)) for n in test}
    p_rf = {n: rf.predict(vec(n)) for n in test}
    p_ta = {n: min(1.0, 3 * (down[n] + up[n])) for n in test}
    iso_cols = list(range(len(sn)))
    iso = IsolationForest().fit([vec(n)[:len(sn)] for n in train])
    p_if = {n: iso.score(vec(n)[:len(sn)]) for n in test}
    final = {n: min(1.0, 0.85 * p_rf[n] + 0.15 * p_lr[n] + 0.5 * p_ta[n]) for n in test}

    eval_nodes = [n for n in test if label[n] is not None and n not in seeds]
    y = [label[n] for n in eval_nodes]

    def evaluate(d):
        s = [d[n] for n in eval_nodes]
        thr = best_threshold(s, y)
        p, r, f1 = prf(s, y, thr)
        k = sum(y)
        top = sorted(zip(s, y), reverse=True)[:k]
        return {"roc_auc": auc(s, y), "pr_auc": pr_auc(s, y), "precision": p,
                "recall": r, "f1": f1, "precision_at_k": sum(t for _, t in top) / k}

    deg = {n: X[n][0] + X[n][1] for n in test}
    metrics = {
        "split": {"train_steps": f"1-{TRAIN_MAX_STEP}", "test_steps": f"{TRAIN_MAX_STEP + 1}-49",
                  "train_labelled": len(train), "train_illicit": sum(known.values()),
                  "test_labelled_evaluated": len(eval_nodes), "test_illicit_evaluated": sum(y),
                  "analyst_seeds": len(seeds)},
        "ensemble (final)": evaluate(final),
        "random forest only": evaluate(p_rf),
        "logistic regression only": evaluate(p_lr),
        "seeded taint only": evaluate(p_ta),
        "isolation forest only (unsupervised)": evaluate(p_if),
        "baseline: degree": evaluate(deg),
    }
    contrib = {}
    w, mu, sd = lr.w, lr.mu, lr.sd
    top_nodes = sorted(test, key=lambda n: -final[n])[:3000]
    for n in top_nodes:
        z = [(v - m) / s for v, m, s in zip(vec(n), mu, sd)]
        c = sorted(((wi * zi, nm) for wi, zi, nm in zip(w, z, names)), reverse=True)
        contrib[n] = [nm for val, nm in c[:3] if val > 0.15]
    return {"g": g, "X": X, "final": final, "p_lr": p_lr, "p_if": p_if, "p_ta": p_ta,
            "metrics": metrics, "weights": rf.importance(names), "test": test,
            "explain": contrib, "known": known, "seeds": seeds}


def explain(res, n):
    reasons, anon = [], []
    for f in res["explain"].get(n, []):
        if f in FRIENDLY:
            reasons.append(FRIENDLY[f])
        else:
            anon.append(f.replace("elliptic_", ""))
    if anon:
        reasons.append("unusual mix of the dataset's anonymised transaction features (" + ", ".join(anon) + ")")
    if res["p_ta"][n] > 0.15:
        reasons.append("close in the money flow to analyst-confirmed illicit transactions")
    return reasons[:4] or ["statistically unusual overall profile"]


def clusters(res, label, top_frac=0.01, min_size=3):
    """Connected groups of high-risk transactions: candidate laundering networks."""
    test = res["test"]
    k = int(len(test) * top_frac)
    hot = set(sorted(test, key=lambda n: -res["final"][n])[:k])
    parent = {n: n for n in hot}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    g = res["g"]
    for n in hot:
        for m in g.out[n]:
            if m in hot:
                parent[root(n)] = root(m)
    groups = defaultdict(list)
    for n in hot:
        groups[root(n)].append(n)
    out = []
    for ms in groups.values():
        if len(ms) < min_size:
            continue
        out.append({"nodes": ms, "size": len(ms),
                    "confirmed_illicit": sum(1 for n in ms if label[n] == 1),
                    "unlabelled_leads": sum(1 for n in ms if label[n] is None),
                    "known_licit": sum(1 for n in ms if label[n] == 0),
                    "avg_risk": sum(res["final"][n] for n in ms) / len(ms)})
    out.sort(key=lambda c: (-c["confirmed_illicit"] - c["unlabelled_leads"], -c["size"]))
    for i, c in enumerate(out, 1):
        c["id"] = f"N{i}"
    return out
