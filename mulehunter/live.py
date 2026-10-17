"""Live mode: pull recent confirmed Bitcoin transactions from the free, keyless public
mempool.space API (falls back to blockstream.info) and turn them into account-level edges.
"""
import json
import time
import urllib.request
from datetime import datetime

APIS = ["https://mempool.space/api", "https://blockstream.info/api"]
UA = {"User-Agent": "mule-hunter/1.0 (research demo)"}


def _get(path, retries=3):
    last = None
    for base in APIS:
        for k in range(retries):
            try:
                req = urllib.request.Request(base + path, headers=UA)
                with urllib.request.urlopen(req, timeout=20) as r:
                    return json.loads(r.read().decode())
            except Exception as e:      # network, 429, 5xx
                last = e
                time.sleep(0.6 * (k + 1))
    raise RuntimeError(f"Public blockchain API not reachable right now ({last}).")


def fetch(n_blocks=6, per_block=100, log=print):
    """Collect per_block transactions from each of the last n_blocks blocks.
    Each tx becomes address->address edges (input share x output value).
    Timestamps are the block time plus a tiny per-position offset so order inside a block is kept.
    """
    from datetime import timedelta
    blocks = _get("/blocks")[:n_blocks]
    edges, collected = [], 0
    for b in blocks:
        base = datetime.utcfromtimestamp(b["timestamp"])
        pos = 0
        for start in range(0, min(per_block, b["tx_count"]), 25):
            txs = _get(f"/block/{b['id']}/txs/{start}")
            for t in txs:
                pos += 1
                ts = base + timedelta(milliseconds=pos)
                ins = [(v["prevout"]["scriptpubkey_address"], v["prevout"]["value"])
                       for v in t["vin"] if v.get("prevout") and v["prevout"].get("scriptpubkey_address")]
                outs = [(o["scriptpubkey_address"], o["value"]) for o in t["vout"]
                        if o.get("scriptpubkey_address")]
                if not ins or not outs:
                    continue
                total_in = sum(v for _, v in ins) or 1
                for a, av in ins:
                    for c, cv in outs:
                        share = (av / total_in) * cv / 1e8
                        if a != c and share > 0:
                            edges.append({"src": a, "dst": c, "amount": share, "ts": ts,
                                          "label": None, "txid": t["txid"]})
                collected += 1
            time.sleep(0.15)
        log(f"  block {b['height']}: running total {collected} transactions")
    return edges, {"blocks": [b["height"] for b in blocks], "txs": collected,
                   "newest_block_time_utc": datetime.utcfromtimestamp(blocks[0]["timestamp"]).isoformat()}
