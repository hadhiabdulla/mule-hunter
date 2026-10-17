"""Account-level mule analysis for YOUR data (CSV upload) and for live blockchain data.

Input: list of transactions {src, dst, amount, ts(datetime), label(optional 0/1)}.
No training data is needed. Signals:
  relay      money received is forwarded onward within hours, almost intact (layering)
  cycle      round trips that return money to its source
  fan        many-to-one collection or one-to-many distribution hubs
  anomaly    Isolation Forest on behaviour features (unsupervised)
  structure  repeated amounts just under a reporting limit
  taint      proximity to accounts you labelled as bad (only if labels given)
Signals are merged with a noisy-OR so one strong signal is enough, several raise confidence.
"""
import math
from collections import defaultdict, deque
from statistics import mean, pstdev

from .iforest import IsolationForest

WEIGHTS = {"neighbour": 0.5, "relay": 0.8, "cycle": 0.6, "fan": 0.35, "anomaly": 0.45, "structure": 0.55,
           "taint": 0.85}
TEXT = {
    "neighbour": "Sits directly in a relay chain with a high-risk account",
    "relay": "Forwards most of what it receives within hours (layering / pass-through)",
    "cycle": "Takes part in round trips that return money to where it started",
    "fan": "Collects from, or distributes to, many accounts (hub behaviour)",
    "anomaly": "Behaviour is a statistical outlier compared with the other accounts",
    "structure": "Repeated amounts just under the reporting limit (structuring)",
    "taint": "Receives money forwarded directly from an account you labelled as bad",
}


def analyse(tx, reporting_limit=10000, relay_window_h=6, keep=0.7):
    tx = sorted(tx, key=lambda t: t["ts"])
    inc, out = defaultdict(list), defaultdict(list)
    for i, t in enumerate(tx):
        t["i"] = i
        out[t["src"]].append(t)
        inc[t["dst"]].append(t)
    accts = set(inc) | set(out)

    # --- relay linking: an inflow followed soon by an outflow of nearly the same size
    links = defaultdict(list)
    for a in accts:
        for t in inc[a]:
            for u in out[a]:
                dt = (u["ts"] - t["ts"]).total_seconds() / 3600
                if 0 < dt <= relay_window_h and keep * t["amount"] <= u["amount"] <= 1.02 * t["amount"]:
                    links[t["i"]].append(u["i"])
    relayed_in = defaultdict(set)
    for i, js in links.items():
        relayed_in[tx[i]["dst"]].add(i)
    depth_after = {}

    def after(i):
        if i not in depth_after:
            depth_after[i] = 0
            depth_after[i] = max([1 + after(j) for j in links.get(i, [])] or [0])
        return depth_after[i]

    before = defaultdict(int)
    for i in sorted(links):
        for j in links[i]:
            before[j] = max(before[j], before[i] + 1)
    chain_len = defaultdict(int)
    for i, t in enumerate(tx):
        if i in links or before[i]:
            for k in ("src", "dst"):
                chain_len[t[k]] = max(chain_len[t[k]], before[i] + after(i) + 1)

    # --- round trip cycles (3-4 accounts, within 72h)
    in_cycle = defaultdict(int)
    seen = set()
    for t0 in tx:
        stack = [(t0["dst"], t0, 1, [t0["src"], t0["dst"]])]
        while stack:
            node, last, ln, path = stack.pop()
            for u in out.get(node, []):
                dt = (u["ts"] - last["ts"]).total_seconds() / 3600
                if not (0 < dt <= 72 and 0.75 * last["amount"] <= u["amount"] <= 1.02 * last["amount"]):
                    continue
                if u["dst"] == t0["src"] and ln + 1 >= 3:
                    key = frozenset(path)
                    if key not in seen:
                        seen.add(key)
                        for p in path:
                            in_cycle[p] += 1
                elif u["dst"] not in path and ln + 1 < 4 and \
                        (u["ts"] - t0["ts"]).total_seconds() <= 72 * 3600:
                    stack.append((u["dst"], u, ln + 1, path + [u["dst"]]))

    # --- behaviour features (FIFO dwell time = how long money sits in the account)
    feats = {}
    for a in accts:
        ev = sorted([(t["ts"], "in", t) for t in inc[a]] + [(t["ts"], "out", t) for t in out[a]],
                    key=lambda e: e[0])
        q, dw, da = deque(), 0.0, 0.0
        for ts, k, t in ev:
            if k == "in":
                q.append([ts, t["amount"]])
            else:
                need = t["amount"]
                while need > 1e-9 and q:
                    take = min(need, q[0][1])
                    dw += take * (ts - q[0][0]).total_seconds() / 3600
                    da += take
                    q[0][1] -= take
                    need -= take
                    if q[0][1] <= 1e-9:
                        q.popleft()
        ia = sum(t["amount"] for t in inc[a])
        oa = sum(t["amount"] for t in out[a])
        times = [e[0] for e in ev]
        gaps = [(y - x).total_seconds() / 3600 for x, y in zip(times, times[1:])]
        feats[a] = {
            "tx_in": len(inc[a]), "tx_out": len(out[a]),
            "senders": len({t["src"] for t in inc[a]}), "receivers": len({t["dst"] for t in out[a]}),
            "received": ia, "sent": oa,
            "pass_ratio": min(oa / ia, 1.5) if ia else 0,
            "dwell_h": dw / da if da else 24 * 30,
            "burst": (pstdev(gaps) / mean(gaps)) if len(gaps) > 2 and mean(gaps) > 0 else 0,
            "near_limit": sum(1 for t in inc[a] if 0.85 * reporting_limit <= t["amount"] < reporting_limit),
            "round_frac": (sum(1 for t in inc[a] if t["amount"] % 100 == 0) / len(inc[a])) if inc[a] else 0,
        }

    def vec(f):
        return [math.log1p(f["tx_in"]), math.log1p(f["tx_out"]), math.log1p(f["senders"]),
                math.log1p(f["receivers"]), f["pass_ratio"], math.log1p(f["dwell_h"]), f["burst"],
                f["round_frac"], f["near_limit"], math.log1p(f["received"]),
                (f["senders"] - f["receivers"]) / max(f["senders"] + f["receivers"], 1)]

    names = list(accts)
    X = [vec(feats[a]) for a in names]
    pct = {}
    if len(X) >= 8:
        forest = IsolationForest(trees=80, sample=min(128, len(X))).fit(X)
        raw = [forest.score(x) for x in X]
        for r, i in enumerate(sorted(range(len(raw)), key=lambda i: raw[i])):
            pct[names[i]] = r / max(len(raw) - 1, 1)

    # --- labels -> taint (direct neighbours of labelled-bad accounts)
    bad = set()
    for t in tx:
        if t.get("label") == 1:
            bad.add(t["dst"])      # receiver of a known-fraudulent transaction is the suspect
    neigh_bad = defaultdict(float)
    if bad:
        for t in tx:
            if t["src"] in bad:          # money flowing on FROM a bad account (not its victims)
                neigh_bad[t["dst"]] += t["amount"]

    def combine(s, a):
        p = 1.0
        for k, v in s.items():
            p *= 1 - WEIGHTS[k] * v
        risk = 100 * (1 - p)
        return max(risk, 90) if a in bad else risk

    sig = {}
    for a in accts:
        f = feats[a]
        s = {}
        recv = f["tx_in"]
        rel = len(relayed_in.get(a, ()))
        s["relay"] = min(1.0, 1.1 * rel / recv) if (recv and rel >= 2) else (0.25 if rel == 1 else 0.0)
        s["cycle"] = min(1.0, in_cycle.get(a, 0) / 2)
        s["fan"] = min(1.0, max(f["senders"], f["receivers"]) / 15) if \
            (f["pass_ratio"] > 0.6 and f["tx_in"] >= 3) else 0.0
        s["anomaly"] = pct.get(a, 0.0) ** 4
        s["structure"] = min(1.0, f["near_limit"] / 4)
        s["taint"] = 0.0 if a in bad or not neigh_bad[a] else min(1.0, neigh_bad[a] / max(f["received"], 1) * 1.5)
        sig[a] = s
    first = {a: combine(sig[a], a) for a in accts}
    neigh = defaultdict(float)
    for i, js in links.items():
        a, b = tx[i]["src"], tx[i]["dst"]
        for j in js:
            c = tx[j]["dst"]
            neigh[c] = max(neigh[c], first[b] / 100)
    result = {}
    for a in accts:
        f, s = feats[a], sig[a]
        s["neighbour"] = neigh[a] if neigh[a] >= 0.6 else 0.0
        risk = combine(s, a)
        reasons = [{"signal": k, "strength": round(v, 2), "text": TEXT[k]}
                   for v, k in sorted(((WEIGHTS[k] * v, k) for k, v in s.items() if v > 0.1), reverse=True)][:4]
        if a in bad:
            reasons.insert(0, {"signal": "label", "strength": 1.0, "text": "You labelled this account as bad"})
        result[a] = {"account": a, "risk": round(risk, 1), "signals": s, "reasons": reasons,
                     "received": round(f["received"], 2), "sent": round(f["sent"], 2),
                     "tx_in": f["tx_in"], "tx_out": f["tx_out"], "chain": chain_len.get(a, 0)}
    return {"accounts": result, "tx": tx, "links": links, "cycles": len(seen)}


def network(res, min_risk=40, max_nodes=250):
    """Subgraph for the viewer: risky accounts plus their direct counterparties."""
    A = res["accounts"]
    risky = [a for a, r in sorted(A.items(), key=lambda kv: -kv[1]["risk"]) if r["risk"] >= min_risk]
    risky = risky[:max_nodes]
    keep = set(risky)
    agg = defaultdict(lambda: [0.0, 0])
    for t in res["tx"]:
        if t["src"] in keep or t["dst"] in keep:
            agg[(t["src"], t["dst"])][0] += t["amount"]
            agg[(t["src"], t["dst"])][1] += 1
    # cap neighbours
    neigh = set()
    for (s, d) in agg:
        for x in (s, d):
            if x not in keep:
                neigh.add(x)
    neigh = set(sorted(neigh, key=lambda a: -A[a]["risk"])[:max(0, max_nodes - len(keep))])
    nodes_set = keep | neigh
    edges = [{"s": s, "d": d, "amt": round(v[0], 2), "n": v[1]} for (s, d), v in agg.items()
             if s in nodes_set and d in nodes_set]
    nodes = [{"id": a, "risk": A[a]["risk"], "reasons": [r["text"] for r in A[a]["reasons"]],
              "recv": A[a]["received"], "sent": A[a]["sent"]} for a in nodes_set]
    return {"nodes": nodes, "edges": edges}
